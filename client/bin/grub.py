# we regard the grub file as a preamble, plus a sequence of entry stanzas
# starting in 'title'. Whilst probably not entirely accurate, it works
# well enough, and is designed not to be lossy

import shutil
import re
import os
import os.path
import string

class grub:
    config_locations = ['/boot/grub/grub.conf', '/boot/grub/menu.lst',
                            '/etc/grub.conf']

    def __init__(self, config_file=None):
        if config_file:
            self.config = config_file
        else:
            self.config = self.detect()
        self.read()


    def read(self):
        conf_file = file(self.config, 'r')
        self.lines = conf_file.readlines()
        conf_file.close()

        self.entries = []                       # list of stanzas
        self.titles = {}                        # dictionary of titles
        entry = grub_entry(-1)
        count = 0
        for line in self.lines:
            if re.match(r'\s*title', line):
                self.entries.append(entry)
                entry = grub_entry(count)
                count = count + 1
                title = line.replace('title ', '')
                title = title.rstrip('\n')
                entry.set('title', title)
                self.titles[title] = entry
            # if line.startswith('initrd'):
            if re.match(r'\s*initrd', line):
                entry.set('initrd',
                        re.sub(r'\s*initrd\s+', '', line))
            if re.match(r'\s*kernel', line):
                entry.set('kernel',
                        re.sub(r'\s*kernel\s+', '', line))
            entry.lines.append(line)
        self.entries.append(entry)
        self.preamble = self.entries.pop(0)     # separate preamble


    def write(self):
        conf_file = file(self.config, 'w')
        conf_file.write(self.preamble)
        for entry in self.entries:
            conf_file.write(entry.lines)
        conf_file.close()


    def dump(self):
        for line in self.preamble.lines:
            print line,
        for entry in self.entries:
            for line in entry.lines:
                print line,

    def backup(self):
        shutil.copyfile(self.config, self.config+'.bak')
        restore = file(autodir + '/var/autotest.boot.restore', 'w')
        restore.write('cp ' + self.config+'.bak ' + self.config + '\n')
        restore.close()


    def bootloader(self):
        return 'grub'


    def detect(self):
        for config in grub.config_locations:
            if os.path.isfile(config) and not os.path.islink(config):
                return config


    def list_titles(self):
        list = []
        for entry in self.entries:
            list.append(entry.get('title'))
        return list


    def print_entry(self, index):
        entry = self.entries[index]
        entry.print_entry()


    def renamed_entry(self, index, newname, args=False):
        "print a specified entry, renaming it as specified"
        entry = self.entries[index]
        entry.set('title', newname)
        if args:
            entry.set_autotest_kernel()
        entry.print_entry()


    def omit_markers(self, marker):
        # print, ommitting entries between specified markers
        print_state = True
        for line in lines:
            if line.count(marker):
                print_state = not print_state
            else:
                if print_state:
                    print line


    def select(self, title, boot_options=None):
        entry = self.titles[title]
        print "grub: will boot entry %d (0-based)" % entry.index
        self.set_default(entry.index)
        self.set_timeout()


    def set_default(self, index):
        lines = (self.preamble).lines
        for i in range(len(lines)):
            default = 'default %d' % index
            lines[i] = re.sub(r'^\s*default.*',
                                    default, lines[i])


    def set_timeout(self):
        lines = (self.preamble).lines
        for i in range(len(lines)):
            lines[i] = re.sub(r'^timeout.*/',
                                    'timeout 60', lines[i])
            lines[i] = re.sub(r'^(\s*terminal .*--timeout)=\d+',
                                    r'\1=30', lines[i])


# ----------------------------------------------------------------------

# Note that the lines[] section, whilst fairly foul, is needed to make
# sure we preserve the original entry intact with comments, formatting,
# and bits we don't understand.

class grub_entry:
    def __init__(self, count):
        self.lines = []
        self.fields = {}    # title, initrd, kernel, etc
        self.index = count


    def set(self, field, value):
        print "setting '%s' to '%s'" % (field, value)
        self.fields[field] = value
        for i in range(len(self.lines)):
            m = re.match(r'\s*' + field + r'\s+', self.lines[i])
            if m:
                self.lines[i] = m.group() + value + '\n'


    def get(self, field):
        return self.fields[field]


    def print_entry(self):
        print self.lines


    def set_kernel_options(self, options):
        kernel = self.get('kernel')
        re.sub(r'(autotest_args:).*', r'\1'+options, kernel)
        self.set('kernel', kernel)

    def set_autotest_kernel(self):
        kernel_words = []
        found_path = False
        # Want to copy most of the entry, replacing the 'path'
        # part of the entry with vmlinux-autotest in the same
        # dir, and make sure autotest_args: is (uniquely) added
        for word in (self.get('kernel')).split():
            if word.startswith('--'):
                kernel_words.append(word)
                continue
            if not found_path:
                word = os.path.dirname(word)+'vmlinuz-autotest'
                found_path = True
            if re.match(r'auto(bench|test)_args:', word):
                break
            kernel_words.append(word)
        kernel_words.append('autotest_args: ')
        self.set('kernel', string.join(kernel_words))
