#!/usr/bin/python

"""A script that provides conversion between models.job and a protocol
buffer object.

This script contains only one class that takes an job instance and
convert it into a protocol buffer object. The class will also be
responsible for serializing the job instance via protocol buffers.

"""

# import python libraries
import os
import datetime
import time
import random
import re

# import autotest libraries
from autotest.tko import models
from autotest.tko import tko_pb2
from autotest.tko import utils

__author__ = 'darrenkuo@google.com (Darren Kuo)'

mktime = time.mktime
datetime = datetime.datetime


class JobSerializer(object):

    """A class that takes a job object of the tko module and package
    it with a protocol buffer.

    This class will take a model.job object as input and create a
    protocol buffer to include all the content of the job object. This
    protocol buffer object will be serialized into a binary file.
    """

    def __init__(self):

        self.job_type_dict = {'dir': str, 'tests': list, 'user': str,
                              'label': str, 'machine': str,
                              'queued_time': datetime,
                              'started_time': datetime,
                              'finished_time': datetime,
                              'machine_owner': str,
                              'machine_group': str, 'aborted_by': str,
                              'aborted_on': datetime,
                              'keyval_dict': dict}

        self.test_type_dict = {'subdir': str, 'testname': str,
                               'status': str, 'reason': str,
                               'kernel': models.kernel, 'machine': str,
                               'started_time': datetime,
                               'finished_time': datetime,
                               'iterations': list, 'attributes': dict,
                               'labels': list}

        self.kernel_type_dict = {'base': str, 'kernel_hash': str}

        self.iteration_type_dict = {'index': int, 'attr_keyval': dict,
                                    'perf_keyval': dict}

    def deserialize_from_binary(self, infile):
        """Takes in a binary file name and returns a tko job object.

        The method first deserialize the binary into a protocol buffer
        job object and then converts the job object into a tko job
        object.

        :param
        infile: the name of the binary file that will be deserialized.

        :return: a tko job that is represented by the binary file will
        be returned.
        """

        job_pb = tko_pb2.Job()

        binary = open(infile, 'r')
        try:
            job_pb.ParseFromString(binary.read())
        finally:
            binary.close()

        return self.get_tko_job(job_pb)

    def serialize_to_binary(self, the_job, tag, binaryfilename):
        """Serializes the tko job object into a binary by using a
        protocol buffer.

        The method takes a tko job object and constructs a protocol
        buffer job object. Then invokes the native serializing
        function on the object to get a binary string. The string is
        then written to outfile.

        Precondition: Assumes that all the information about the job
        is already in the job object. Any fields that is None will be
        provided a default value.

        :param
        the_job: the tko job object that will be serialized.
        tag: contains the job name and the afe_job_id
        binaryfilename: the name of the file that will be written to

        :return: the filename of the file that contains the
        binary of the serialized object.
        """

        pb_job = tko_pb2.Job()
        self.set_pb_job(the_job, pb_job, tag)

        out = open(binaryfilename, 'wb')
        try:
            out.write(pb_job.SerializeToString())
        finally:
            out.close()

    def set_afe_job_id_and_tag(self, pb_job, tag):
        """Sets the pb job's afe_job_id and tag field.

        :param
        pb_job: the pb job that will have it's fields set.
        tag: used to set pb_job.tag and pb_job.afe_job_id.
        """
        pb_job.tag = tag
        pb_job.afe_job_id = utils.get_afe_job_id(tag)

    # getter setter methods
    def get_tko_job(self, job):
        """Creates a a new tko job object from the pb job object.

        Uses getter methods on the pb objects to extract all the
        attributes and finally constructs a tko job object using the
        models.job constructor.

        :param
        job: a pb job where data is being extracted from.

        :return: a tko job object.
        """

        fields_dict = self.get_trivial_attr(job, self.job_type_dict)

        fields_dict['tests'] = [self.get_tko_test(test) for test in job.tests]

        fields_dict['keyval_dict'] = dict((keyval.name, keyval.value)
                                          for keyval in job.keyval_dict)

        newjob = models.job(fields_dict['dir'], fields_dict['user'],
                            fields_dict['label'],
                            fields_dict['machine'],
                            fields_dict['queued_time'],
                            fields_dict['started_time'],
                            fields_dict['finished_time'],
                            fields_dict['machine_owner'],
                            fields_dict['machine_group'],
                            fields_dict['aborted_by'],
                            fields_dict['aborted_on'],
                            fields_dict['keyval_dict'])

        newjob.tests.extend(fields_dict['tests'])

        return newjob

    def set_pb_job(self, tko_job, pb_job, tag):
        """Set the fields for the new job object.

        Method takes in a tko job and an empty protocol buffer job
        object.  Then safely sets all the appropriate field by first
        testing if the value in the original object is None.

        :param
        tko_job: a tko job instance that will have it's values
        transferred to the new job
        pb_job: a new instance of the job class provided in the
        protocol buffer.
        tag: used to set pb_job.tag and pb_job.afe_job_id.
        """

        self.set_trivial_attr(tko_job, pb_job, self.job_type_dict)
        self.set_afe_job_id_and_tag(pb_job, tag)

        for test in tko_job.tests:
            newtest = pb_job.tests.add()
            self.set_pb_test(test, newtest)

        for key, val in tko_job.keyval_dict.iteritems():
            newkeyval = pb_job.keyval_dict.add()
            newkeyval.name = key
            newkeyval.value = str(val)

    def get_tko_test(self, test):
        """Creates a tko test from pb_test.

        Extracts data from pb_test by calling helper methods and
        creates a tko test using the models.test constructor.

        :param:
        test: a pb_test where fields will be extracted from.

        :return: a new instance of models.test
        """
        fields_dict = self.get_trivial_attr(test, self.test_type_dict)

        fields_dict['kernel'] = self.get_tko_kernel(test.kernel)

        fields_dict['iterations'] = [self.get_tko_iteration(iteration)
                                     for iteration in test.iterations]

        fields_dict['attributes'] = dict((keyval.name, keyval.value)
                                         for keyval in test.attributes)

        fields_dict['labels'] = list(test.labels)

        return models.test(fields_dict['subdir'],
                           fields_dict['testname'],
                           fields_dict['status'],
                           fields_dict['reason'],
                           fields_dict['kernel'],
                           fields_dict['machine'],
                           fields_dict['started_time'],
                           fields_dict['finished_time'],
                           fields_dict['iterations'],
                           fields_dict['attributes'],
                           fields_dict['labels'])

    def set_pb_test(self, tko_test, pb_test):
        """Sets the various fields of test object of the tko protocol.

        Method takes a tko test and a new test of the protocol buffer and
        transfers the values in the tko test to the new test.

        :param
        tko_test: a tko test instance.
        pb_test: an empty protocol buffer test instance.

        """

        self.set_trivial_attr(tko_test, pb_test, self.test_type_dict)

        self.set_pb_kernel(tko_test.kernel, pb_test.kernel)

        for current_iteration in tko_test.iterations:
            pb_iteration = pb_test.iterations.add()
            self.set_pb_iteration(current_iteration, pb_iteration)

        for key, val in tko_test.attributes.iteritems():
            newkeyval = pb_test.attributes.add()
            newkeyval.name = key
            newkeyval.value = str(val)

        for current_label in tko_test.labels:
            pb_test.labels.append(current_label)

    def get_tko_kernel(self, kernel):
        """Constructs a new tko kernel object from a pb kernel object.

        Uses all the getter methods on the pb kernel object to extract
        the attributes and constructs a new tko kernel object using
        the model.kernel constructor.

        :param
        kernel: a pb kernel object where data will be extracted.

        :return: a new tko kernel object.
        """

        fields_dict = self.get_trivial_attr(kernel, self.kernel_type_dict)

        return models.kernel(fields_dict['base'], [], fields_dict['kernel_hash'])

    def set_pb_kernel(self, tko_kernel, pb_kernel):
        """Set a specific kernel of a test.

        Takes the same form of all the other setting methods.  It
        separates the string variables from the int variables and set
        them safely.

        :param
        tko_kernel: a tko kernel.
        pb_kernel: an empty protocol buffer kernel.

        """

        self.set_trivial_attr(tko_kernel, pb_kernel, self.kernel_type_dict)

    def get_tko_iteration(self, iteration):
        """Creates a new tko iteration with the data in the provided
        pb iteration.

        Uses the data in the pb iteration and the models.iteration
        constructor to create a new tko iterations

        :param
        iteration: a pb iteration instance

        :return: a tko iteration instance with the same data.
        """

        fields_dict = self.get_trivial_attr(iteration,
                                            self.iteration_type_dict)

        fields_dict['attr_keyval'] = dict((keyval.name, keyval.value)
                                          for keyval in iteration.attr_keyval)

        fields_dict['perf_keyval'] = dict((keyval.name, keyval.value)
                                          for keyval in iteration.perf_keyval)

        return models.iteration(fields_dict['index'],
                                fields_dict['attr_keyval'],
                                fields_dict['perf_keyval'])

    def set_pb_iteration(self, tko_iteration, pb_iteration):
        """Sets all fields for a particular iteration.

        Takes same form as all the other setting methods. Sets int,
        str and datetime variables safely.

        :param
        tko_iteration: a tko test iteration.
        pb_iteration: an empty pb test iteration.

        """

        self.set_trivial_attr(tko_iteration, pb_iteration,
                              self.iteration_type_dict)

        for key, val in tko_iteration.attr_keyval.iteritems():
            newkeyval = pb_iteration.attr_keyval.add()
            newkeyval.name = key
            newkeyval.value = str(val)

        for key, val in tko_iteration.perf_keyval.iteritems():
            newkeyval = pb_iteration.perf_keyval.add()
            newkeyval.name = key
            newkeyval.value = str(val)

    def get_trivial_attr(self, obj, objdict):
        """Get all trivial attributes from the object.

        This function is used to extract attributes from a pb job. The
        dictionary specifies the types of each attribute in each tko
        class.

        :param
        obj: the pb object that is being extracted.
        objdict: the dict that specifies the type.

        :return: a dict of each attr name and it's corresponding value.
        """

        resultdict = {}
        for field, field_type in objdict.items():
            value = getattr(obj, field)
            if field_type in (str, int, long):
                resultdict[field] = field_type(value)
            elif field_type == datetime:
                resultdict[field] = (
                    datetime.fromtimestamp(value / 1000.0))

        return resultdict

    def set_trivial_attr(self, tko_obj, pb_obj, objdict):
        """Sets all the easy attributes appropriately according to the
        type.

        This function is used to set all the trivial attributes
        provided by objdict, the dictionary that specifies the types
        of each attribute in each tko class.

        :param
        tko_obj: the original object that has the data being copied.
        pb_obj: the new pb object that is being copied into.
        objdict: specifies the type of each attribute in the class we
        are working with.

        """
        for attr, attr_type in objdict.iteritems():
            if attr_type == datetime:
                t = getattr(tko_obj, attr)
                if not t:
                    self.set_attr_safely(pb_obj, attr, t, int)
                else:
                    t = mktime(t.timetuple()) + 1e-6 * t.microsecond
                    setattr(pb_obj, attr, long(t * 1000))
            else:
                value = getattr(tko_obj, attr)
                self.set_attr_safely(pb_obj, attr, value, attr_type)

    def set_attr_safely(self, var, attr, value, vartype):
        """Sets a particular attribute of var if the provided value is
        not None.

        Checks if value is None. If not, set the attribute of the var
        to be the default value. This is necessary for the special
        required fields of the protocol buffer.

        :param
        var: the variable of which one of the attribute is being set.
        attr: the attribute that is being set.
        value: the value that is being checked
        vartype: the expected type of the attr

        """

        supported_types = [int, long, str]
        if vartype in supported_types:
            if value is None:
                value = vartype()
            else:
                assert isinstance(value, vartype), (
                    'Unexpected type %s for attr %s, should be %s' %
                    (type(value), attr, vartype))

            setattr(var, attr, value)
