"""
    Utility module standardized on ElementTree 2.6 to minimize dependencies
    in python 2.4 systems.
"""

import os.path, shutil, tempfile, string

try:
    import autotest.common as common
except ImportError:
    import common

import logging

from autotest.client.shared import ElementTree

# Used by unittests
TMPPFX='xml_utils_temp_'
TMPSFX='.xml'

class TempXMLFile(file):
    """
    Temporary XML file auto-removed on instance del / module exit.
    """

    def __init__(self, suffix=TMPSFX, prefix=TMPPFX, mode="wb+", buffer=1):
        """
        Initialize temporary XML file removed on instance destruction.

        param: suffix: temporary file's suffix
        param: prefix: temporary file's prefix
        param: mode: file access mode
        param: buffer: size of buffer in bytes, 1: line buffered
        """
        fd,path = tempfile.mkstemp(suffix=suffix, prefix=prefix)
        os.close(fd)
        super(TempXMLFile, self).__init__(path, mode, buffer)


    def __exit__(self, exc_type, exc_value, traceback):
        """
        Always remove temporary file on module exit.
        """

        self.__del__()
        super(TempXMLFile, self).__exit__(exc_type, exc_value, traceback)


    def __del__(self):
        """
        Remove temporary file on instance delete.
        """

        try:
            os.unlink(self.name)
        except OSError:
            pass # don't care


class XMLBackup(TempXMLFile):
    """
    Backup file copy of XML data, automatically removed on instance destruction.
    """

    # Allow users to reference original source of XML data
    sourcefilename = None

    def __init__(self, sourcefilename):
        """
        Initialize a temporary backup from sourcefilename.
        """

        super(XMLBackup, self).__init__()
        self.sourcefilename = sourcefilename
        self.backup()


    def backup(self):
        """
        Overwrite temporary backup with contents of original source.
        """

        self.flush()
        self.seek(0)
        shutil.copyfileobj(file(self.sourcefilename, "rb"), super(XMLBackup,self))
        self.seek(0)


    def restore(self):
        """
        Overwrite original source with contents of temporary backup
        """

        self.flush()
        self.seek(0)
        shutil.copyfileobj(super(XMLBackup,self), file(self.sourcefilename, "wb+"))
        self.seek(0)


    def _info(self):
        logging.info("Retaining backup of %s in %s", self.sourcefilename,
                                                     self.name)


    def __exit__(self, exc_type, exc_value, traceback):
        """
        Remove temporary backup on unexceptional module exit.
        """

        if exc_type is None and exc_value is None and traceback is None:
            super(XMLBackup, self).__del__()
        else:
            self._info()


    def __del__(self):
        """
        Remove temporary file on instance delete.
        """

        self._info()


class XMLTreeFile(ElementTree.ElementTree, XMLBackup):
    """
    Combination of ElementTree root and auto-cleaned XML backup file.
    """

    # Closed file object of original source or TempXMLFile
    # self.sourcefilename inherited from parent
    sourcebackupfile = None

    def __init__(self, xml):
        """
        Initialize from a string or filename containing XML source.

        param: xml: A filename or string containing XML
        """

        # xml param could be xml string or readable filename
        # If it's a string, use auto-delete TempXMLFile
        # to hold the original content.
        try:
            self.sourcebackupfile = open(xml, "rb")
            # Prevent source modification
            self.sourcebackupfile.close()
        except (IOError, OSError):
            # this will auto-delete when XMLBase instance goes out of scope
            self.sourcebackupfile = TempXMLFile()
            self.sourcebackupfile.write(xml)
            # Prevent source modification
            self.sourcebackupfile.close()
            xml = self.sourcebackupfile.name
        XMLBackup.__init__(self, sourcefilename=xml)
        ElementTree.ElementTree.__init__(self, element=None,
                                         file=self.name)
        # Ensure parsed content matches file content
        self.write()
        self.flush()


    def write(self, filename=None, encoding="UTF-8"):
        """
        Write current XML tree to filename, or self.name if None.
        """

        if filename is None:
            filename = self.name
        ElementTree.ElementTree.write(self, filename, encoding)


    def read(self, xml):
        self.__del__()
        self.__init__(xml)


class Sub(object):
    """String substituter using string.Template"""

    def __init__(self, **mapping):
        """Initialize substitution mapping."""

        self._mapping = mapping


    def substitute(self, text):
        """
        Use string.safe_substitute on text and return the result

        @param: text: string to substitute
        """

        return string.Template(text).safe_substitute(**self._mapping)


class TemplateXMLTreeBuilder(ElementTree.XMLTreeBuilder, Sub):
    """Resolve XML templates into temporary file-backed ElementTrees"""

    BuilderClass = ElementTree.TreeBuilder

    def __init__(self, **mapping):
        """
        Initialize parser that substitutes keys with values in data

        @param: **mapping: values to be substituted for ${key} in XML input
        """

        Sub.__init__(self, **mapping)
        ElementTree.XMLTreeBuilder.__init__(self, target=self.BuilderClass())


    def feed(self, data):
        ElementTree.XMLTreeBuilder.feed(self, self.substitute(data))


class TemplateXML(XMLTreeFile):
    """Template-sourced XML ElementTree backed by temporary file."""

    ParserClass = TemplateXMLTreeBuilder

    def __init__(self, xml, **mapping):
        """
        Initialize from a XML string or filename, and string.template mapping.

        @param: xml: A filename or string containing XML
        @param: **mapping: keys/values to feed with XML to string.template
        """

        self.parser = self.ParserClass(**mapping)
        # ElementTree.init calls self.parse()
        super(TemplateXML, self).__init__(xml)
        # XMLBase.__init__ calls self.write() after super init


    def parse(self, source):
        """
        Parse source XML file or filename using TemplateXMLTreeBuilder

        @param: source: XML file or filename
        @param: parser: ignored
        """

        return super(TemplateXML, self).parse(source, self.parser)


    def restore(self):
        """
        Raise an IOError to protect the original template source.
        """

        raise IOError("Protecting template source, disallowing restore to %s" %
                        self.sourcefilename)
