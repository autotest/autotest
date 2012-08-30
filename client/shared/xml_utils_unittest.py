#!/usr/bin/python

import unittest, tempfile, os, glob, logging

try:
    import autotest.common as common
except ImportError:
    import common

from autotest.client.shared import xml_utils, ElementTree


class xml_test_data(unittest.TestCase):

    def get_tmp_files(self, prefix, sufix):
        path_string = os.path.join('/tmp', "%s*%s" % (prefix, sufix))
        return glob.glob(path_string)

    def setUp(self):
        # Previous testing may have failed / left behind extra files
        for filename in self.get_tmp_files(xml_utils.TMPPFX, xml_utils.TMPSFX):
            os.unlink(filename)
        for filename in self.get_tmp_files(xml_utils.TMPPFX,
                                           xml_utils.TMPSFX + xml_utils.EXSFX):
            os.unlink(filename)
        # Compacted to save excess scrolling
        self.TEXT_REPLACE_KEY="TEST_XML_TEXT_REPLACE"
        self.XMLSTR="""<?xml version='1.0' encoding='UTF-8'?><capabilities><host>
        <uuid>4d515db1-9adc-477d-8195-f817681e72e6</uuid><cpu><arch>x86_64</arch>
        <model>Westmere</model><vendor>Intel</vendor><topology sockets='1'
        cores='2' threads='2'/><feature name='rdtscp'/><feature name='x2apic'/>
        <feature name='xtpr'/><feature name='tm2'/><feature name='est'/>
        <feature name='vmx'/><feature name='ds_cpl'/><feature name='monitor'/>
        <feature name='pbe'/><feature name='tm'/><feature name='ht'/><feature
        name='ss'/><feature name='acpi'/><feature name='ds'/><feature
        name='vme'/></cpu><migration_features><live/><uri_transports>
        <uri_transport>tcp</uri_transport></uri_transports>
        </migration_features><topology><cells num='1'><cell id='0'><cpus
        num='4'><cpu id='0'/><cpu id='1'/><cpu id='2'/><cpu id='3'/></cpus>
        </cell></cells></topology><secmodel><model>selinux</model><doi>0</doi>
        </secmodel></host><guest><os_type>hvm</os_type><arch name='i686'>
        <wordsize>32</wordsize><emulator>$TEST_XML_TEXT_REPLACE</emulator>
        <machine>rhel6.2.0</machine><machine canonical='rhel6.2.0'>pc</machine>
        <machine>rhel6.1.0</machine><machine>rhel6.0.0</machine><machine>
        rhel5.5.0</machine><machine>rhel5.4.4</machine><machine>rhel5.4.0
        </machine><domain type='qemu'></domain><domain type='kvm'><emulator>
        /usr/libexec/qemu-kvm</emulator></domain></arch><features><cpuselection
        /><deviceboot/><pae/><nonpae/><acpi default='on' toggle='yes'/><apic
        default='on' toggle='no'/></features></guest></capabilities>"""
        (fd, self.XMLFILE) = tempfile.mkstemp(suffix=xml_utils.TMPSFX,
                                              prefix=xml_utils.TMPPFX)
        os.write(fd, self.XMLSTR)
        os.close(fd)
        self.canonicalize_test_xml()


    def tearDown(self):
        os.unlink(self.XMLFILE)
        leftovers = self.get_tmp_files(xml_utils.TMPPFX, xml_utils.TMPSFX)
        if len(leftovers) > 0:
            self.fail('Leftover files: %s' % str(leftovers))

    def canonicalize_test_xml(self):
        et = ElementTree.parse(self.XMLFILE)
        et.write(self.XMLFILE, encoding="UTF-8")
        f = file(self.XMLFILE)
        self.XMLSTR = f.read()
        f.close()


class test_ElementTree(xml_test_data):

    def test_bundled_elementtree(self):
        self.assertEqual(xml_utils.ElementTree.VERSION, ElementTree.VERSION)


class test_TempXMLFile(xml_test_data):

    def test_prefix_sufix(self):
        filename = os.path.basename(self.XMLFILE)
        self.assert_(filename.startswith(xml_utils.TMPPFX))
        self.assert_(filename.endswith(xml_utils.TMPSFX))


    def test_test_TempXMLFile_canread(self):
        tmpf = xml_utils.TempXMLFile()
        tmpf.write(self.XMLSTR)
        tmpf.seek(0)
        stuff = tmpf.read()
        self.assertEqual(stuff, self.XMLSTR)
        del tmpf


    def test_TempXMLFile_implicit(self):
        def out_of_scope_tempxmlfile():
            tmpf = xml_utils.TempXMLFile()
            return tmpf.name
        self.assertRaises(OSError, os.stat, out_of_scope_tempxmlfile())


    def test_TempXMLFile_explicit(self):
        tmpf = xml_utils.TempXMLFile()
        tmpf_name = tmpf.name
        # Assert this does NOT raise an exception
        os.stat(tmpf_name)
        del tmpf
        self.assertRaises(OSError, os.stat, tmpf_name)


class test_XMLBackup(xml_test_data):

    class_to_test = xml_utils.XMLBackup


    def is_same_contents(self, filename, other=None):
        try:
            f = file(filename, "rb")
            s = f.read()
        except (IOError, OSError):
            logging.warning("File %s does not exist" % filename)
            return False
        if other is None:
            return s == self.XMLSTR
        else:
            other_f = file(other, "rb")
            other_s = other_f.read()
            return s == other_s


    def test_backup_filename(self):
        xmlbackup = self.class_to_test(self.XMLFILE)
        self.assertEqual(xmlbackup.sourcefilename, self.XMLFILE)


    def test_backup_file(self):
        xmlbackup = self.class_to_test(self.XMLFILE)
        self.assertTrue(self.is_same_contents(xmlbackup.name))


    def test_rebackup_file(self):
        xmlbackup = self.class_to_test(self.XMLFILE)
        oops = file(xmlbackup.name, "wb")
        oops.write("foobar")
        oops.close()
        self.assertFalse(self.is_same_contents(xmlbackup.name))
        xmlbackup.backup()
        self.assertTrue(self.is_same_contents(xmlbackup.name))


    def test_restore_file(self):
        xmlbackup = self.class_to_test(self.XMLFILE)
        # nuke source
        os.unlink(xmlbackup.sourcefilename)
        xmlbackup.restore()
        self.assertTrue(self.is_same_contents(xmlbackup.name))


    def test_remove_backup_file(self):
        xmlbackup = self.class_to_test(self.XMLFILE)
        filename = xmlbackup.name
        os.unlink(filename)
        del xmlbackup
        self.assertRaises(OSError, os.unlink, filename)


    def test_TempXMLBackup_implicit(self):
        def out_of_scope_xmlbackup():
            tmpf = self.class_to_test(self.XMLFILE)
            return tmpf.name
        filename = out_of_scope_xmlbackup()
        self.assertRaises(OSError, os.unlink, filename)


    def test_TempXMLBackup_exception_exit(self):
        tmpf = self.class_to_test(self.XMLFILE)
        filename = tmpf.name
        # simulate exception exit DOES NOT DELETE
        tmpf.__exit__(Exception, "foo", "bar")
        self.assertTrue(self.is_same_contents(filename + xml_utils.EXSFX))
        os.unlink(filename + xml_utils.EXSFX)


    def test_TempXMLBackup_unexception_exit(self):
        tmpf = self.class_to_test(self.XMLFILE)
        filename = tmpf.name
        # simulate normal exit DOES DELETE
        tmpf.__exit__(None, None, None)
        self.assertRaises(OSError, os.unlink, filename)


class test_XMLTreeFile(test_XMLBackup):

    class_to_test = xml_utils.XMLTreeFile

    def test_sourcebackupfile_closed_file(self):
        xml = self.class_to_test(self.XMLFILE)
        self.assertRaises(ValueError, xml.sourcebackupfile.write, 'foobar')


    def test_sourcebackupfile_closed_string(self):
        xml = self.class_to_test(self.XMLSTR)
        self.assertRaises(ValueError, xml.sourcebackupfile.write, 'foobar')


    def test_init_str(self):
        xml = self.class_to_test(self.XMLSTR)
        self.assert_(xml.sourcefilename is not None)
        self.assertEqual(xml.sourcebackupfile.name,
                         xml.sourcefilename)


    def test_init_xml(self):
        xml = self.class_to_test(self.XMLFILE)
        self.assert_(xml.sourcefilename is not None)
        self.assertEqual(xml.sourcebackupfile.name,
                         xml.sourcefilename)


    def test_restore_from_string(self):
        xmlbackup = self.class_to_test(self.XMLSTR)
        os.unlink(xmlbackup.sourcefilename)
        xmlbackup.restore()
        self.assertTrue(self.is_same_contents(xmlbackup.sourcefilename))


    def test_restore_from_file(self):
        xmlbackup = self.class_to_test(self.XMLFILE)
        os.unlink(xmlbackup.sourcefilename)
        xmlbackup.restore()
        self.assertTrue(self.is_same_contents(xmlbackup.name))


    def test_backup_backup_and_remove(self):
        tmpf = self.class_to_test(self.XMLFILE)
        tmps = self.class_to_test(self.XMLSTR)
        bu_tmpf = tmpf.backup_copy()
        bu_tmps = tmps.backup_copy()
        self.assertTrue(self.is_same_contents(bu_tmpf.name, tmpf.name))
        self.assertTrue(self.is_same_contents(bu_tmps.name, tmps.name))
        tmpf.remove_by_xpath('guest/arch/wordsize')
        tmps.find('guest/arch/wordsize').text = 'FOOBAR'
        tmpf.write()
        tmps.write()
        self.assertFalse(self.is_same_contents(bu_tmpf.name, tmpf.name))
        self.assertFalse(self.is_same_contents(bu_tmps.name, tmps.name))
        self.assertTrue(self.is_same_contents(bu_tmpf.name, bu_tmps.name))
        self.assertFalse(self.is_same_contents(tmpf.name, tmps.name))
        del bu_tmpf
        del bu_tmps


    def test_write_default(self):
        xmlbackup = self.class_to_test(self.XMLFILE)
        wordsize = xmlbackup.find('guest/arch/wordsize')
        self.assertTrue(wordsize is not None)
        self.assertEqual(int(wordsize.text), 32)
        wordsize.text = str(64)
        xmlbackup.write()
        self.assertFalse(self.is_same_contents(xmlbackup.name))


    def test_write_other(self):
        xmlbackup = self.class_to_test(self.XMLFILE)
        otherfile = xml_utils.TempXMLFile()
        xmlbackup.write(otherfile)
        otherfile.close()
        self.assertTrue(self.is_same_contents(otherfile.name))


    def test_write_other_changed(self):
        xmlbackup = self.class_to_test(self.XMLSTR)
        otherfile = xml_utils.TempXMLFile()
        wordsize = xmlbackup.find('guest/arch/wordsize')
        wordsize.text = str(64)
        xmlbackup.write(otherfile)
        otherfile.close()
        xmlbackup.write(self.XMLFILE)
        xmlbackup.close()
        self.canonicalize_test_xml()
        self.assertTrue(self.is_same_contents(otherfile.name))


    def test_read_other_changed(self):
        xmlbackup = self.class_to_test(self.XMLSTR)
        wordsize = xmlbackup.find('guest/arch/wordsize')
        wordsize.text = str(64)
        otherfile = xml_utils.TempXMLFile()
        xmlbackup.write(otherfile)
        otherfile.close()
        xmlbackup.backup()
        self.assertTrue(self.is_same_contents(xmlbackup.name))
        xmlbackup.read(otherfile.name)
        self.assertFalse(self.is_same_contents(otherfile.name))
        xmlbackup.write(self.XMLFILE)
        self.assertFalse(self.is_same_contents(otherfile.name))
        self.canonicalize_test_xml()
        self.assertTrue(self.is_same_contents(otherfile.name))


class test_templatized_xml(xml_test_data):

    def setUp(self):
        self.MAPPING = {"foo":"bar", "bar":"baz", "baz":"foo"}
        self.FULLREPLACE = """<$foo $bar="$baz">${baz}${foo}${bar}</$foo>"""
        self.RESULTCHECK = """<bar baz="foo">foobarbaz</bar>"""
        super(test_templatized_xml, self).setUp()


    def test_sub(self):
        sub = xml_utils.Sub(**self.MAPPING)
        self.assertEqual(sub.substitute(self.FULLREPLACE), self.RESULTCHECK)


    def test_MappingTreeBuilder_standalone(self):
        txtb = xml_utils.TemplateXMLTreeBuilder(**self.MAPPING)
        txtb.feed(self.FULLREPLACE)
        et = txtb.close()
        result = ElementTree.tostring(et)
        self.assertEqual(result, self.RESULTCHECK)


    def test_TemplateXMLTreeBuilder_nosub(self):
        txtb = xml_utils.TemplateXMLTreeBuilder()
        # elementree pukes on identifiers starting with $
        txtb.feed(self.RESULTCHECK)
        et = txtb.close()
        result = ElementTree.tostring(et)
        self.assertEqual(result, self.RESULTCHECK)


    def test_TemplateXML(self):
        tx = xml_utils.TemplateXML(self.FULLREPLACE, **self.MAPPING)
        et = ElementTree.ElementTree(None, tx.name)
        check = ElementTree.tostring(et.getroot())
        self.assertEqual(check, self.RESULTCHECK)


    def test_restore_fails(self):
        testmapping = {self.TEXT_REPLACE_KEY:"foobar"}
        xmlbackup = xml_utils.TemplateXML(self.XMLFILE, **testmapping)
        # Unless the backup was initialized from a string (into a temp file)
        # assume the source is read-only and should be protected.
        self.assertRaises(IOError, xmlbackup.restore)


if __name__ == "__main__":
    unittest.main()
