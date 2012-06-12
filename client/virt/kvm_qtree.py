"""
Utility classes and functions to handle KVM Qtree parsing and verification.

@author: Lukas Doktor <ldoktor@redhat.com>
@copyright: 2012 Red Hat Inc.
"""
import logging
import os
import re
from autotest.client.virt import virt_storage

OFFSET_PER_LEVEL = 2

_RE_BLANKS = re.compile(r'^([ ]*)')
_RE_CLASS = re.compile(r'^class ([^,]*), addr (\d\d:\d\d.\d+), pci id '
                        '(\w{4}:\w{4}) \(sub (\w{4}:\w{4})\)')


class IncompatibleTypeError(TypeError):
    def __init__(self, prop, desired_type, value):
        super(IncompatibleTypeError, self).__init__()
        self.prop = prop
        self.desired = desired_type
        self.value = value

    def __str__(self):
        return "%s have to be %s, not %s" % (self.prop, type(self.desired),
                                             type(self.value))


class QtreeNode(object):
    """
    Generic Qtree node
    """
    def __init__(self):
        self.parent = None      # Parent node
        self.qtree = {}         # List of qtree attributes
        self.children = []     # List of child nodes
        self.params = {}        # generated params from qtree

    def __str__(self):
        out = self.str_short()
        if self.parent:
            out += "\n[parent]\n %s" % self.parent.str_short()
        if self.qtree:
            out += "\n[info qtree]"
        for tmp in self.qtree.iteritems():
            out += "\n %s = %s" % (tmp[0], tmp[1])
        if self.children:
            out += "\n[children]"
        for tmp in self.children:
            out += "\n %s" % tmp.str_short()
        if self.params:
            out += "\n[params]"
        for tmp in self.params.iteritems():
            out += "\n %s = %s" % (tmp[0], [tmp[1]])
        return out

    def set_parent(self, parent):
        if not isinstance(parent, QtreeNode) and parent is not None:
            raise IncompatibleTypeError('parent', QtreeNode(), parent)
        self.parent = parent

    def get_parent(self):
        return self.parent

    def add_child(self, child):
        if not isinstance(child, QtreeNode):
            raise IncompatibleTypeError('child', QtreeNode(), child)
        self.children.append(child)

    def replace_child(self, oldchild, newchild):
        if not oldchild in self.children:
            raise ValueError('child %s not in children %s' % (oldchild,
                                                               self.children))
        self.add_child(newchild)
        self.children.remove(oldchild)

    def get_children(self):
        return self.children

    def set_qtree(self, qtree):
        if not isinstance(qtree, dict):
            raise IncompatibleTypeError('qtree', {}, qtree)
        self.qtree = qtree

    def set_qtree_prop(self, prop, value):
        if prop in self.qtree:
            raise ValueError("Property %s = %s, not rewriting with %s" % (prop,
                             self.qtree.get(prop), value))
        self.update_qtree_prop(prop, value)

    def update_qtree_prop(self, prop, value):
        self.qtree[prop] = value

    def get_qtree(self):
        return self.qtree

    def guess_type(self):
        """ Detect type of this object from qtree props """
        return QtreeNode

    def str_short(self):
        return "id: '%s', type: %s" % (self.qtree.get('id'), type(self))

    def str_qtree(self):
        out = "%s" % self.str_short()
        for child in self.children:
            for line in child.str_qtree().splitlines():
                out += "\n  %s" % line
        return out

    def generate_params(self):
        pass

    def get_params(self):
        return self.params

    def update_params(self, param, value):
        self.params[param] = value

    def verify(self):
        pass


class QtreeBus(QtreeNode):
    """ bus: qtree object """
    def __init__(self):
        super(QtreeBus, self).__init__()

    def add_child(self, child):
        if not isinstance(child, QtreeDev):
            raise IncompatibleTypeError('child', QtreeDev(), child)
        super(QtreeBus, self).add_child(child)

    def guess_type(self):
        return QtreeBus


class QtreeDev(QtreeNode):
    """ dev: qtree object """
    def __init__(self):
        super(QtreeDev, self).__init__()

    def add_child(self, child):
        if not isinstance(child, QtreeBus):
            raise IncompatibleTypeError('child', QtreeBus(), child)
        super(QtreeDev, self).add_child(child)

    def guess_type(self):
        if ('dev-prop: drive' in self.qtree and
                self.qtree['type'] != 'usb-storage'):
            # ^^ HOOK when usb-storage-containter is detected as disk
            return QtreeDisk
        else:
            return QtreeDev


class QtreeDisk(QtreeDev):
    """ qtree disk object """
    def __init__(self):
        super(QtreeDisk, self).__init__()
        self.block = {}     # Info from 'info block'

    def __str__(self):
        out = super(QtreeDisk, self).__str__()
        if self.block:
            out += "\n[info block]"
        for tmp in self.block.iteritems():
            out += "\n%s = %s" % (tmp[0], tmp[1])
        return out

    def set_block_prop(self, prop, value):
        if prop in self.block:
            raise ValueError("Property %s = %s, not rewriting with %s" % (prop,
                             self.block.get(prop), value))
        self.update_block_prop(prop, value)

    def update_block_prop(self, prop, value):
        self.block[prop] = value

    def get_block(self):
        return self.block

    def generate_params(self):
        if not self.qtree or not self.block:
            raise ValueError("Node doesn't have qtree or block info yet.")
        if self.block.get('backing_file'):
            self.params['image_snapshot'] = 'yes'
            self.params['image_name'] = os.path.realpath(
                                                self.block.get('backing_file'))
        elif self.block.get('file'):
            self.params['image_name'] = os.path.realpath(
                                                        self.block.get('file'))
        else:
            raise ValueError("Missing 'file' or 'backing_file' information "
                             "in self.block.")
        if self.block.get('ro') and self.block.get('ro') != '0':
            self.params['image_readonly'] = 'yes'
        self.params['drive_format'] = self.qtree.get('type')

    def get_qname(self):
        return self.qtree.get('dev-prop: drive')


class QtreeContainer(object):
    """ Container for Qtree """
    def __init__(self):
        self.nodes = None

    def get_qtree(self):
        """ @return: root of qtree """
        if self.nodes:
            return self.nodes[-1]

    def get_nodes(self):
        """
        @return: flat list of all qtree nodes (last one is main-system-bus)
        """
        return self.nodes

    def parse_info_qtree(self, info):
        """
        Parses 'info qtree' output. Creates list of self.nodes. Last node is
        the main-system-bus (whole qtree)
        """
        def _replace_node(old, newtype):
            if isinstance(old, newtype):
                return old
            new = newtype()
            new.set_parent(old.get_parent())
            new.get_parent().replace_child(old, new)
            new.set_qtree(old.get_qtree())
            for child in old.get_children():
                child.set_parent(new)
                new.add_child(child)
            return new

        def _hook_usb2_disk(node):
            """
            usb2 disk - from point of qtree - is scsi disk inside the
            usb-storage device.
            """
            # We're looking for scsi disk with grand-grand parent of
            # usb sorage type
            if not isinstance(node, QtreeDisk):
                return  # Not a disk
            if not node.get_qtree().get('type').startswith('scsi'):
                return  # Not scsi disk
            if not (node.get_parent() and node.get_parent().get_parent()):
                return  # Doesn't have grand-grand parent
            if not (node.get_parent().get_parent().get_qtree().get('type') ==
                                                                'usb-storage'):
                return  # grand-grand parent is not usb-storage
            # This disk is not scsi disk, it's virtual usb-storage drive
            node.update_qtree_prop('type', 'usb2')
        info = info.split('\n')
        current = None
        offset = 0
        self.nodes = []
        line = info.pop(0)
        while True:
            _offset = len(_RE_BLANKS.match(line).group(0))
            if not line.strip():
                if len(info) == 0:
                    break
                line = info.pop(0)
                continue
            if _offset >= offset:
                offset = _offset
                line = line[offset:]
                # Strip out all dev-prop/bus-prop/...
                # bus/dev/prop
                if line.startswith('bus: '):
                    # bus: scsi.0
                    new = QtreeBus()
                    if current:
                        current.add_child(new)
                        new.set_parent(current)
                    current = new
                    offset += OFFSET_PER_LEVEL
                    line = ['id', line[5:].strip()]
                elif line.startswith('dev: '):
                    # dev: scsi-disk, id ""
                    new = QtreeDev()
                    if current:
                        current.add_child(new)
                        new.set_parent(current)
                    current = new
                    line = line[5:].split(',')
                    current.set_qtree_prop('id', line[1][5:-1])
                    offset += OFFSET_PER_LEVEL
                    line = ['type', line[0]]
                elif _RE_CLASS.match(line):
                    # class IDE controller, addr 00:01.1, pci id 8086:7010 (..
                    line = _RE_CLASS.match(line).groups()
                    current.set_qtree_prop('class_addr', line[1])
                    current.set_qtree_prop('class_pciid', line[2])
                    current.set_qtree_prop('class_sub', line[3])
                    line = ['class', line[0]]
                elif '=' in line:
                    # bus-prop: addr = 02.0
                    line = line.split('=', 1)
                elif ':' in line:
                    # bar 0: i/o at 0xc280 [0xc2bf]
                    line = line.split(':', 1)
                elif ' ' in line:
                    # mmio ffffffffffffffff/0000000000100000
                    line = line.split(' ', 1)
                    # HOOK: mmio can have multiple values
                    if line[0] == 'mmio':
                        if not 'mmio' in current.qtree:
                            current.set_qtree_prop('mmio', [])
                        current.qtree['mmio'].append(line[1])
                        line = None
                else:
                    # Corrupted qtree
                    raise ValueError('qtree line not recognized:\n%s' % line)
                if line:
                    current.set_qtree_prop(line[0].strip(), line[1].strip())
                if len(info) == 0:
                    break
                line = info.pop(0)
            else:
                # Node can be of different type
                current = _replace_node(current, current.guess_type())
                self.nodes.append(current)
                current = current.get_parent()
                offset -= OFFSET_PER_LEVEL
        # Read out remaining self.nodes
        while offset > 0:
            current = _replace_node(current, current.guess_type())
            self.nodes.append(current)
            current = current.get_parent()
            offset -= OFFSET_PER_LEVEL
        # This is the place to put HOOKs for nasty qtree devices
        for i in xrange(len(self.nodes)):
            _hook_usb2_disk(self.nodes[i])


class QtreeDisksContainer(object):
    """
    Container for QtreeDisks verification.
    It's necessary because some information can be verified only from
    informations about all disks, not only from single disk.
    """
    def __init__(self, nodes):
        """ work only with QtreeDisks instances """
        self.disks = []
        for node in nodes:
            if isinstance(node, QtreeDisk):
                self.disks.append(node)

    def parse_info_block(self, info):
        """
        Extracts all information about self.disks and fills them in.
        @param info: output of 'info block' command
        @return: (self.disks defined in qtree but not in info block,
                  self.disks defined in block info but not in qtree)
        """
        additional = 0
        missing = 0
        names = []
        for disk in self.disks:
            names.append(disk.get_qname())
        info = info.split('\n')
        for line in info:
            if not line.strip():
                continue
            line = line.split(':', 1)
            name = line[0].strip()
            if name not in names:
                logging.error("disk %s is in block but not in qtree", name)
                missing += 1
                continue
            else:
                disk = self.disks[names.index(name)]
            for _ in line[1].strip().split(' '):
                (prop, value) = _.split('=', 1)
                disk.set_block_prop(prop, value)
        for disk in self.disks:
            if isinstance(disk, QtreeDisk) and disk.get_block() == {}:
                logging.error("disk in qtree but not in info block\n%s", disk)
                additional += 1
        return (additional, missing)

    def generate_params(self):
        """
        Generate params from current self.qtree and self.block info.
        @note: disk name is not yet the one from autotest params
        @return: number of fails
        """
        err = 0
        for disk in self.disks:
            try:
                disk.generate_params()
            except ValueError:
                logging.error("generate_params error: %s", disk)
                err += 1
        return err

    def check_guests_proc_scsi(self, info):
        """
        Check info from guest's /proc/scsi/scsi file with qtree/block info
        @note: Not tested disks are of different type (virtio_blk, ...)
        @param info: contents of guest's /proc/scsi/scsi file
        @return: (#disks missing in guest os, #disks missing in qtree,
                  #not tested disks from qtree, #not tested disks from guest)
        """
        # Check only channel, id and lun for now
        additional = 0
        missing = 0
        qtree_not_scsi = 0
        proc_not_scsi = 0
        # host, channel, id, lun, vendor
        _scsis = re.findall(r'Host:\s+(\w+)\s+Channel:\s+(\d+)\s+Id:\s+(\d+)'
                             '\s+Lun:\s+(\d+)\n\s+Vendor:\s+([a-zA-Z0-9_-]+)'
                             '\s+Model: ', info)
        disks = set()
        # Check only scsi disks
        for disk in self.disks:
            if (disk.get_qtree()['type'].startswith('scsi') or
                    disk.get_qtree()['type'].startswith('usb2')):
                props = disk.get_qtree()
                disks.add('%d-%d-%d' % (int(props.get('bus-prop: channel')),
                                        int(props.get('bus-prop: scsi-id')),
                                        int(props.get('bus-prop: lun'))))
            else:
                qtree_not_scsi += 1
        scsis = set()
        for scsi in _scsis:
            # Ignore IDE disks
            # TODO: Consider passthrough devices
            if scsi[4].startswith('QEMU'):
                scsis.add("%d-%d-%d" % (int(scsi[1]), int(scsi[2]),
                                        int(scsi[3])))
            else:
                proc_not_scsi += 1
        for disk in disks.difference(scsis):
            logging.error('Disk %s is in qtree but not in /proc/scsi/scsi.',
                          disk)
            additional += 1
        for disk in scsis.difference(disks):
            logging.error('Disk %s is in /proc/scsi/scsi but not in qtree.',
                          disk)
            missing += 1
        return (additional, missing, qtree_not_scsi, proc_not_scsi)

    def check_disk_params(self, params, root_dir=''):
        """
        Check gathered info from qtree/block with params
        @param params: autotest params
        @param root_dir: root_dir of images. If all images use absolute path
                         it's safe to omit this param.
        @return: number of errors
        """
        err = 0
        disks = {}
        for disk in self.disks:
            if isinstance(disk, QtreeDisk):
                disks[disk.get_qname()] = disk.get_params().copy()
        # We don't have the params name so we need to map file_names instead
        qname = None
        for name in params.objects('images'):
            current = None
            image_params = params.object_params(name)
            image_name = os.path.realpath(
                        virt_storage.get_image_filename(image_params, root_dir))
            for (qname, disk) in disks.iteritems():
                if disk.get('image_name') == image_name:
                    current = disk
                    # autotest params might use relative path
                    current['image_name'] = image_params.get('image_name')
                    break
            if not current:
                logging.error("Disk %s is not in qtree but is in params.", name)
                err += 1
                continue
            for prop in current.iterkeys():
                handled = False
                if prop == "drive_format":
                    # HOOK: params to qemu translation
                    if current.get(prop).startswith(image_params.get(prop)):
                        handled = True
                elif (image_params.get(prop) and
                        image_params.get(prop) == current.get(prop)):
                    handled = True
                if not handled:
                    logging.error("Disk %s property %s=%s doesn't match params"
                                  " %s", qname, prop, current.get(prop),
                                  image_params.get(prop))
                    err += 1
            disks.pop(qname)
        if disks:
            logging.error('Some disks were in qtree but not in autotest params'
                          ': %s', disks)
            err += 1
        return err
