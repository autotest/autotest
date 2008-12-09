# Copyright Martin J. Bligh, Google Inc 2008
# Released under the GPL v2

"""
This class allows you to communicate with the frontend to submit jobs etc
It is designed for writing more sophisiticated server-side control files that
can recursively add and manage other jobs.

We turn the JSON dictionaries into real objects that are more idiomatic

For docs, see http://autotest//afe/server/noauth/rpc/
http://docs.djangoproject.com/en/dev/ref/models/querysets/#queryset-api
"""

import os, time, traceback
import common
from autotest_lib.frontend.afe import rpc_client_lib
from autotest_lib.client.common_lib import utils


def dump_object(header, obj):
    """
    Standard way to print out the frontend objects (eg job, host, acl, label)
    in a human-readable fashion for debugging
    """
    result = header + '\n'
    for key in obj.hash:
        if key == 'afe' or key == 'hash':
            continue
        result += '%20s: %s\n' % (key, obj.hash[key])
    return result


class afe(object):
    """
    AFE class for communicating with the autotest frontend

    All the constructors go in the afe class. 
    Manipulating methods go in the classes themselves
    """
    def __init__(self, user=os.environ.get('LOGNAME'),
                 web_server='http://autotest', print_log=True, debug=False):
        """
        Create a cached instance of a connection to the AFE

            user: username to connect as
            web_server: AFE instance to connect to
            print_log: pring a logging message to stdout on every operation
            debug: print out all RPC traffic
        """
        self.user = user
        self.print_log = print_log
        self.debug = debug
        headers = {'AUTHORIZATION' : self.user}
        rpc_server = web_server + '/afe/server/noauth/rpc/'
        self.proxy = rpc_client_lib.get_proxy(rpc_server, headers=headers)


    def run(self, call, **dargs):
        """
        Make a RPC call to the AFE server
        """
        rpc_call = getattr(self.proxy, call)
        if self.debug:
            print 'DEBUG: %s %s' % (call, dargs)
        return utils.strip_unicode(rpc_call(**dargs))


    def log(self, message):
        if self.print_log:
            print message


    def host_statuses(self, live=None):
        dead_statuses = ['Dead', 'Repair Failed']
        statuses = self.run('get_static_data')['host_statuses']
        if live == True:
            return list(set(statuses) - set(['Dead', 'Repair Failed']))
        if live == False:
            return dead_statuses
        else:
            return statuses


    def get_hosts(self, **dargs):
        hosts = self.run('get_hosts', **dargs)
        return [host(self, h) for h in hosts]


    def create_host(self, hostname, **dargs):
        id = self.run('add_host', **dargs)
        return self.get_hosts(id=id)[0]


    def get_labels(self, **dargs):
        labels = self.run('get_labels', **dargs)
        return [label(self, l) for l in labels]


    def create_label(self, name, **dargs):
        id = self.run('add_label', **dargs)
        return self.get_labels(id=id)[0]


    def get_acls(self, **dargs):
        acls = self.run('get_acl_groups', **dargs)
        return [acl(self, a) for a in acls]


    def create_acl(self, name, **dargs):
        id = self.run('add_acl_group', **dargs)
        return self.get_acls(id=id)[0]


    def get_jobs(self, summary=False, **dargs):
        if summary:
            jobs_data = self.run('get_jobs_summary', **dargs)
        else:
            jobs_data = self.run('get_jobs', **dargs)
        return [job(self, j) for j in jobs_data]


    def get_host_queue_entries(self, **data):
        entries = self.run('get_host_queue_entries', **data)
        return [job_status(self, e) for e in entries]


    def create_job_by_test(self, tests, kernel=None, **dargs):
        """
        Given a test name, fetch the appropriate control file from the server
        and submit it
        """
        results = self.run('generate_control_file', tests=tests, kernel=kernel,
                           use_container=False, do_push_packages=True)
        if results['is_server']:
            dargs['control_type'] = 'Server'
        else:
            dargs['control_type'] = 'Client'
        dargs['dependencies'] = dargs.get('dependencies', []) + \
                                results['dependencies']
        dargs['control_file'] = results['control_file']
        dargs['synch_count'] = results['synch_count']
        return self.create_job(**dargs)


    def create_job(self, control_file, name=' ', priority='Medium',
                control_type='Client', **dargs):
        id = self.run('create_job', name=name, priority=priority,
                 control_file=control_file, control_type=control_type, **dargs)
        return self.get_jobs(id=id)[0]


    def run_test_suites(self, pairings, kernel, kernel_label, wait=True,
                        poll_interval=5, email_from=None, email_to=None):
        """
        Run a list of test suites on a particular kernel.
    
        Poll for them to complete, and return whether they worked or not.
    
            pairings: list of MachineTestPairing objects to invoke
            kernel: name of the kernel to run
            kernel_label: label of the kernel to run
                                        (<kernel-version> : <config> : <date>)
            wait: boolean - wait for the results to come back?
            poll_interval: interval between polling for job results (in minutes)
            email_from: send notification email upon completion from here
            email_from: send notification email upon completion to here
        """
        jobs = []
        for pairing in pairings:
            job = self.invoke_test(pairing, kernel, kernel_label)
            job.notified = False
            jobs.append(job)
            if email_from and email_to:
                subject = 'Testing started: %s : %s' % (job.name, job.id)
                utils.send_email(email_from, email_to, subject, subject)
        if not wait:
            return
        while True:
            time.sleep(60 * poll_interval)
            result = self.poll_all_jobs(jobs, email_from, email_to)
            if result is not None:
                return result


    def result_notify(self, job, email_from, email_to):
        """
        Notify about the result of a job. Will always print, if email data
        is provided, will send email for it as well.

            job: job object to notify about
            email_from: send notification email upon completion from here
            email_from: send notification email upon completion to here
        """
        if job.result == True:
            subject = 'Testing PASSED: '
        else:
            subject = 'Testing FAILED: '
        subject += '%s : %s\n' % (job.name, job.id)
        text = []
        for platform in job.results_platform_map:
            for status in job.results_platform_map[platform]:
                if status == 'Total':
                    continue
                hosts = ','.join(job.results_platform_map[platform][status])
                text.append('%20s %10s %s' % (platform, status, hosts))
        text.append("\nhttp://autotest/tko/compose_query.cgi?columns=test&rows=machine_group&condition=tag~'%s-%%25'&title=Report" % job.id)
        body = "\n".join(text)
        print "---------------------------------------------------"
        print "Subject: ", subject
        print body
        print "---------------------------------------------------"
        if email_from and email_to:
            print "Sending email ..."
            utils.send_email(email_from, email_to, subject, body)
        print
        

    def poll_all_jobs(self, jobs, email_from, email_to):
        """
        Poll all jobs in a list.
            jobs: list of job objects to poll
            email_from: send notification email upon completion from here
            email_from: send notification email upon completion to here

        Returns:
            a) All complete successfully (return True)
            b) One or more has failed (return False)
            c) Cannot tell yet (return None)
        """
        results = []
        for job in jobs:
            job.result = self.poll_job_results(job, debug=False)
            results.append(job.result)
            if job.result is not None and not job.notified:
                self.result_notify(job, email_from, email_to)
                job.notified = True

            if job.result is None:
                print 'PENDING',
            elif job.result == True:
                print 'PASSED',
            elif job.result == False:
                print 'FAILED',
            print ' %s : %s' % (job.id, job.name)

        if None in results:
            return None
        elif False in results:
            return False
        else:
            return True


    def invoke_test(self, pairing, kernel, kernel_label, priority='Medium'):
        """
        Given a pairing of a control file to a machine label, find all machines
        with that label, and submit that control file to them.
    
        Returns a job object
        """
        job_name = '%s : %s' % (pairing.machine_label, kernel_label)
        hosts = self.get_hosts(multiple_labels=[pairing.machine_label])
        host_list = [h.hostname for h in hosts if h.status != 'Repair Failed']
        new_job = self.create_job_by_test(name=job_name,
                                     dependencies=[pairing.machine_label],
                                     tests=[pairing.control_file],
                                     priority=priority,
                                     hosts=host_list,
                                     kernel=kernel)
        print 'Invoked test %s : %s' % (new_job.id, job_name)
        return new_job


    def poll_job_results(self, job, debug=False):
        """
        Analyse all job results by platform, return:
    
            False: if any platform has more than one failure
            None:  if any platform has more than one machine not yet Good.
            True:  if all platforms have at least all-but-one machines Good.
        """
        try:
            job_statuses = self.get_host_queue_entries(job=job.id)
        except Exception:
            print "Ignoring exception on poll job; RPC interface is flaky"
            traceback.print_exc()
            return None
    
        platform_map = {}
        for job_status in job_statuses:
            hostname = job_status.host.hostname
            status = job_status.status
            platform = job_status.host.platform
            if platform not in platform_map:
                platform_map[platform] = {'Total' : [hostname]}
            else:
                platform_map[platform]['Total'].append(hostname)
            new_host_list = platform_map[platform].get(status, []) + [hostname]
            platform_map[platform][status] = new_host_list
        job.results_platform_map = platform_map
    
        good_platforms = []
        bad_platforms = []
        unknown_platforms = []
        for platform in platform_map:
            total = len(platform_map[platform]['Total'])
            completed = len(platform_map[platform].get('Completed', []))
            failed = len(platform_map[platform].get('Failed', []))
            if failed > 1:
                bad_platforms.append(platform)
            elif completed + 1 >= total:
                # if all or all but one are good, call the job good.
                good_platforms.append(platform)
            else:
                unknown_platforms.append(platform)
            detail = []
            for status in platform_map[platform]:
                if status == 'Total':
                    continue
                detail.append('%s=%s' % (status,platform_map[platform][status]))
            if debug:
                print '%20s %d/%d %s' % (platform, completed, total, 
                                         ' '.join(detail))
                print
    
        if len(bad_platforms) > 0:
            if debug:
                print 'Result bad - platforms: ' + ' '.join(bad_platforms)
            return False
        if len(unknown_platforms) > 0:
            if debug:
                platform_list = ' '.join(unknown_platforms)
                print 'Result unknown - platforms: ', platform_list
            return None
        if debug:
            platform_list = ' '.join(good_platforms)
            print 'Result good - all platforms passed: ', platform_list
        return True


class rpc_object(object):
    """
    Generic object used to construct python objects from rpc calls
    """
    def __init__(self, afe, hash):
        self.afe = afe
        self.hash = hash
        self.__dict__.update(hash)


    def __str__(self):
        return dump_object(self.__repr__(), self)


class label(rpc_object):
    """
    AFE label object

    Fields:
        name, invalid, platform, kernel_config, id, only_if_needed
    """
    def __repr__(self):
        return 'LABEL: %s' % self.name


    def add_hosts(self, hosts):
        return self.afe.run('label_add_hosts', self.id, hosts)


    def remove_hosts(self, hosts):
        return self.afe.run('label_remove_hosts', self.id, hosts)


class acl(rpc_object):
    """
    AFE acl object

    Fields:
        users, hosts, description, name, id
    """
    def __repr__(self):
        return 'ACL: %s' % self.name


    def add_hosts(self, hosts):
        self.afe.log('Adding hosts %s to ACL %s' % (hosts, self.name))
        return self.afe.run('acl_group_add_hosts', self.id, hosts)


    def remove_hosts(self, hosts):
        self.afe.log('Removing hosts %s from ACL %s' % (hosts, self.name))
        return self.afe.run('acl_group_remove_hosts', self.id, hosts)


class job(rpc_object):
    """
    AFE job object

    Fields:
        name, control_file, control_type, synch_count, reboot_before,
        run_verify, priority, email_list, created_on, dependencies,
        timeout, owner, reboot_after, id
    """
    def __repr__(self):
        return 'JOB: %s' % self.id


class job_status(rpc_object):
    """
    AFE job_status object

    Fields:
        status, complete, deleted, meta_host, host, active, execution_subdir, id
    """
    def __init__(self, afe, hash):
        # This should call super
        self.afe = afe
        self.hash = hash
        self.__dict__.update(hash)
        self.job = job(afe, self.job)
        if self.host:
            self.host = afe.get_hosts(hostname=self.host['hostname'])[0]


    def __repr__(self):
        return 'JOB STATUS: %s-%s' % (self.job.id, self.host.hostname)


class host(rpc_object):
    """
    AFE host object

    Fields:
        status, lock_time, locked_by, locked, hostname, invalid,
        synch_id, labels, platform, protection, dirty, id
    """
    def __repr__(self):
        return 'HOST OBJECT: %s' % self.hostname


    def show(self):
        labels = list(set(self.labels) - set([self.platform]))
        print '%-6s %-7s %-7s %-16s %s' % (self.hostname, self.status,
                                           self.locked, self.platform,
                                           ', '.join(labels))


    def get_acls(self):
        return self.afe.get_acls(hosts__hostname=self.hostname)


    def add_acl(self, acl_name):
        self.afe.log('Adding ACL %s to host %s' % (acl_name, self.hostname))
        return self.afe.run('acl_group_add_hosts', id=acl_name,
                            hosts=[self.hostname])


    def remove_acl(self, acl_name):
        self.afe.log('Removing ACL %s from host %s' % (acl_name, self.hostname))
        return self.afe.run('acl_group_remove_hosts', id=acl_name,
                            hosts=[self.hostname])


    def get_labels(self):
        return self.afe.get_labels(host__hostname__in=[self.hostname])


    def add_labels(self, labels):
        self.afe.log('Adding labels %s to host %s' % (labels, self.hostname))
        return self.afe.run('host_add_labels', id=self.id, labels=labels)


    def remove_labels(self, labels):
        self.afe.log('Removing labels %s from host %s' % (labels,self.hostname))
        return self.afe.run('host_remove_labels', id=self.id, labels=labels)


class MachineTestPairing(object):
    """
    Object representing the pairing of a machine label with a control file
    """
    def __init__(self, machine_label, control_file):
        self.machine_label = machine_label
        self.control_file = control_file
