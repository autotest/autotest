#!/usr/bin/python

import sys, optparse, pwd
import common
from autotest_lib.cli import rpc, host

parser = optparse.OptionParser(
    usage= 'usage: %prog [options] <job id> <hostname>')
parser.add_option('-w', '--web',
                  help='Autotest server to use (i.e. "autotest")')
options, args = parser.parse_args()

if len(args) != 2:
    parser.print_usage()
    sys.exit(1)

job_id = int(args[0])
hostname = args[1]

autotest_host = rpc.get_autotest_server(options.web)
proxy = rpc.afe_comm(autotest_host)

# host exists?
hosts = proxy.run('get_hosts', hostname=hostname)
if not hosts:
    print 'No such host', hostname
    sys.exit(1)
host = hosts[0]

# job exists?
jobs = proxy.run('get_jobs', id=job_id)
if not jobs:
    print 'No such job', job_id
    sys.exit(1)

# any entry eligible for this host?
queue_entries = proxy.run('get_host_queue_entries', job__id=job_id)
entries_for_this_host = [entry for entry in queue_entries
                         if entry['host']
                         and entry['host']['hostname'] == hostname]
host_label_names = set(host['labels'])
eligible_metahost_entries = [entry for entry in queue_entries
                             if entry['meta_host'] and not entry['host']
                             and entry['meta_host'] in host_label_names
                             and not entry['complete']]

if entries_for_this_host:
    assert len(entries_for_this_host) == 1, (
        'Multiple entries for this job assigned to this host!')
    entry = entries_for_this_host[0]
    if entry['active'] or entry['complete']:
        print ('Job already ran or is running on this host! (status: %s)' %
               entry['full_status'])
        sys.exit(0)
    is_metahost = False
else:
    # no entry for this host -- maybe an eligible metahost entry?
    if not eligible_metahost_entries:
        print ("Host isn't scheduled for this job, and no eligible metahost "
               "entry exists")
        sys.exit(0)
    is_metahost = True

# host ready?
if host['status'] != 'Ready':
    if host['status'] == 'Pending':
        active = proxy.run('get_host_queue_entries',
                           host=host['id'], active=True)
        if not active:
            print ('Host %s seems to be in "Pending" state incorrectly; please '
                   'report this to the Autotest team' % hostname)
            sys.exit(1)
    print 'Host not in "Ready" status (status="%s")' % host['status']
    sys.exit(0)

# host locked?
if host['locked']:
    print 'Host is locked'
    sys.exit(0)

# acl accessible?
job = jobs[0]
owner = job['owner']
accessible = proxy.run('get_hosts', hostname=hostname,
                       aclgroup__users__login=owner)
if not accessible:
    host_acls = ', '.join(group['name'] for group in
                          proxy.run('get_acl_groups', hosts__hostname=hostname))
    owner_acls = ', '.join(group['name'] for group in
                           proxy.run('get_acl_groups', users__login=owner))
    print 'Host not ACL-accessible to job owner', owner
    print 'Host ACLs:', host_acls
    print 'Owner Acls:', owner_acls
    sys.exit(0)

# meets dependencies?
job_deps_list = job['dependencies'].split(',')
job_deps = set()
if job_deps_list != ['']:
    job_deps = set(job_deps_list)
unmet = job_deps - host_label_names
if unmet:
    print ("Host labels (%s) don't satisfy job dependencies: %s" %
           (', '.join(host_label_names), ', '.join(unmet)))
    sys.exit(0)

# at this point, if the job is for an unassigned atomic group, things are too
# complicated to proceed
unassigned_atomic_group_entries = [entry for entry in queue_entries
                                   if entry['atomic_group']
                                   and not entry['host']]
if unassigned_atomic_group_entries:
    print ("Job is for an unassigned atomic group.  That's too complicated, I "
           "can't give you any definite answers.  Sorry.")
    sys.exit(1)

# meets atomic group requirements?
host_labels = proxy.run('get_labels', name__in=list(host_label_names))
host_atomic_group_labels = [label for label in host_labels
                            if label['atomic_group']]
host_atomic_group_name = None
if host_atomic_group_labels:
    assert len(host_atomic_group_labels) == 1, (
        'Host has more than one atomic group label!')
    host_atomic_group_label = host_atomic_group_labels[0]
    host_atomic_group_name = host_atomic_group_label['atomic_group']['name']

job_atomic_groups = set(entry['atomic_group'] for entry in queue_entries)
assert len(job_atomic_groups) == 1, 'Job has more than one atomic group value!'
job_atomic_group = job_atomic_groups.pop() # might be None
job_atomic_group_name = None
if job_atomic_group:
    job_atomic_group_name = job_atomic_group['name']

if host_atomic_group_name != job_atomic_group_name:
    print ('Job is for atomic group %s, but host is in atomic group %s '
           '(label %s)' %
           (job_atomic_group_name, host_atomic_group_name,
            host_atomic_group_label['name']))
    sys.exit(0)

# meets only_if_needed labels?
if is_metahost:
    metahost_names = set(entry['meta_host']
                         for entry in eligible_metahost_entries)
    job_deps_and_metahosts = job_deps.union(metahost_names)
    for label in host_labels:
        unmet_exclusive_label = (label['only_if_needed'] and
                                 label['name'] not in job_deps_and_metahosts)
        if unmet_exclusive_label:
            print ('Host contains "only if needed" label %s, unused by job '
                   'dependencies and metahosts' % label['name'])
            sys.exit(0)

print ("Job %s should run on host %s; if you've already waited about ten "
       "minutes or longer, it's probably a server issue or a bug." %
       (job_id, hostname))
sys.exit(1)
