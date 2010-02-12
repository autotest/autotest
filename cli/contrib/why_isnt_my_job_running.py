#!/usr/bin/python

import sys, optparse, pwd
import common
from autotest_lib.cli import rpc, host
from autotest_lib.client.common_lib import host_queue_entry_states

parser = optparse.OptionParser(
    usage='Usage: %prog [options] <job id> [<hostname>]\n\n'
          'Describes why the given job on the given host has not started.')
parser.add_option('-w', '--web',
                  help='Autotest server to use (i.e. "autotest")')
options, args = parser.parse_args()

if len(args) < 1:
    parser.print_help()
    sys.exit(1)

job_id = int(args[0])

autotest_host = rpc.get_autotest_server(options.web)
proxy = rpc.afe_comm(autotest_host)

# job exists?
jobs = proxy.run('get_jobs', id=job_id)
if not jobs:
    print 'No such job', job_id
    sys.exit(1)
job = jobs[0]
owner = job['owner']

RUNNING_HQE_STATUSES = host_queue_entry_states.ACTIVE_STATUSES

# any entry eligible for this host?
queue_entries = proxy.run('get_host_queue_entries', job__id=job_id)

### Divine why an atomic group job is or is not running.
if queue_entries and queue_entries[0]['atomic_group']:
    if queue_entries[0]['status'] in RUNNING_HQE_STATUSES:
        print 'Job %d appears to have started (status: %s).' % (
                job_id, queue_entries[0]['status'])
        sys.exit(0)
    # Hosts in Repairing or Repair Failed will have Queued queue entries.
    # We shouldn't consider those queue entries as a multi-group job.
    repair_hostnames = []
    for queue_entry in queue_entries:
        if queue_entry['host'] and queue_entry['host']['status']:
            if queue_entry['host']['status'].startswith('Repair'):
                repair_hostnames.append(queue_entry['host']['hostname'])
        if queue_entry['status'] in ('Completed', 'Stopped'):
            print 'This job has already finished.'
            sys.exit(0)
    queue_entries_with_hosts = [queue_entry for queue_entry in queue_entries
                                if queue_entry['host']]
    all_queue_entries_have_hosts = (len(queue_entries) ==
                                    len(queue_entries_with_hosts))
    if (not all_queue_entries_have_hosts and len(queue_entries) > 1 and
        not repair_hostnames):
        # We test repair_hostnames so that this message is not printed when
        # the script is run on an atomic group job which has hosts assigned
        # but is not running because too many of them are in Repairing or will
        # never run because hosts have exited Repairing into the Repair Failed
        # dead end.
        print 'This script does not support multi-group atomic group jobs.'
        print
        print 'Jobs scheduled in that state are typically unintentional.'
        print
        print 'Did you perhaps schedule the job via the web frontend and ask'
        print 'that it run on more than 1 (atomic group) of hosts via the '
        print '"Run on any" box?  If so, always enter 1 there when scheduling'
        print 'jobs on anything marked "(atomic group)".'
        print
        print len(queue_entries), 'non-started atomic group HostQueueEntries',
        print 'found for job', job_id
        sys.exit(1)
    atomic_group_name = queue_entries[0]['atomic_group']['name']
    # Get the list of labels associated with this atomic group.
    atomic_labels = proxy.run('get_labels',
                              atomic_group__name=atomic_group_name)
    if len(atomic_labels) < 1:
        print 'Job requests atomic group %s but no labels' % atomic_group_name
        print '(and thus no hosts) are associated with that atomic group.'

    job_sync_count = job['synch_count']
    # Ugh! This is returned as a comma separated str of label names.
    if job.get('dependencies'):
        job_dependency_label_names = job['dependencies'].split(',')
    else:
        job_dependency_label_names = []

    meta_host_name = queue_entries[0]['meta_host']
    if meta_host_name:
        meta_host = proxy.run('get_labels', atomic_group__name=meta_host_name)[0]
    else:
        meta_host = None

    # A mapping from label name -> a list of hostnames usable for this job.
    runnable_atomic_label_names = {}

    # A mapping from label name -> a host_exclude_reasons map as described
    # within the loop below.  Any atomic group labels in this map are not
    # ready to run the job for the reasons contained within.
    atomic_label_exclude_reasons = {}

    for label in atomic_labels:
        label_name = label['name']
        if meta_host and meta_host_name != label_name:
            print 'Cannot run on atomic label %s due to meta_host %s.' % (
                    label_name, meta_host_name)
            continue
        for dep_name in job_dependency_label_names:
            if dep_name != label_name:
                print 'Not checking hosts in atomic label %s against' % (
                        label_name,)
                print 'job dependency label %s.  There may be less hosts' % (
                        dep_name,)
                print 'than examined below available to run this job.'

        # Get the list of hosts associated with this atomic group label.
        atomic_hosts = proxy.run('get_hosts', multiple_labels=[label_name])

        # A map of hostname -> A list of reasons it can't be used.
        host_exclude_reasons = {}

        atomic_hostnames = [h['hostname'] for h in atomic_hosts]

        # Map hostnames to a list of ACL names on that host.
        acl_groups = proxy.run('get_acl_groups',
                               hosts__hostname__in=atomic_hostnames)
        hostname_to_acl_name_list = {}
        for acl in acl_groups:
            for hostname in acl['hosts']:
                hostname_to_acl_name_list.setdefault(hostname, []).append(
                        acl['name'])

        # Exclude any hosts that ACLs deny us access to.
        accessible_hosts = proxy.run('get_hosts', hostname__in=atomic_hostnames,
                                     aclgroup__users__login=owner)
        assert len(accessible_hosts) <= len(atomic_hosts)
        if len(accessible_hosts) != len(atomic_hosts):
            accessible_hostnames = set(h['hostname'] for h in accessible_hosts)
            acl_excluded_hostnames = (set(atomic_hostnames) -
                                      accessible_hostnames)
            for hostname in acl_excluded_hostnames:
                acls = ','.join(hostname_to_acl_name_list[hostname])
                host_exclude_reasons.setdefault(hostname, []).append(
                        'User %s does not have ACL access. ACLs: %s' % (
                                owner, acls))

        # Check for locked hosts.
        locked_hosts = [h for h in atomic_hosts if h['locked']]
        for host in locked_hosts:
            locker = host.get('locked_by') or 'UNKNOWN'
            msg = 'Locked by user %s on %s.  No jobs will schedule on it.' % (
                    locker, host.get('lock_time'))
            host_exclude_reasons.setdefault(host['hostname'], []).append(msg)

        # Exclude hosts that are not Ready.
        for host in atomic_hosts:
            hostname = host['hostname']
            if host['status'] != 'Ready':
                message = 'Status is %s' % host['status']
                if host['status'] in ('Verifying', 'Pending', 'Running'):
                    running_hqes = proxy.run(
                            'get_host_queue_entries', host__hostname=hostname,
                            status__in=RUNNING_HQE_STATUSES)
                    if not running_hqes:
                        message += ' (unknown job)'
                    else:
                        message += ' (job %d)' % running_hqes[0]['job']['id']
                host_exclude_reasons.setdefault(hostname, []).append(message)

        # If we don't have enough usable hosts, this group cannot run the job.
        usable_hostnames = [host['hostname'] for host in atomic_hosts
                            if host['hostname'] not in host_exclude_reasons]
        if len(usable_hostnames) < job_sync_count:
            message = ('%d hosts are required but only %d available.' %
                       (job_sync_count, len(usable_hostnames)))
            atomic_label_exclude_reasons[label_name] = (message,
                                                        host_exclude_reasons)
        else:
            runnable_atomic_label_names[label_name] = usable_hostnames

    for label_name, reason_tuple in atomic_label_exclude_reasons.iteritems():
        job_reason, hosts_reasons = reason_tuple
        print 'Atomic group "%s" via label "%s" CANNOT run job %d because:' % (
                atomic_group_name, label_name, job_id)
        print job_reason
        for hostname in sorted(hosts_reasons.keys()):
            for reason in hosts_reasons[hostname]:
                print '%s\t%s' % (hostname, reason)
        print

    for label_name, host_list in runnable_atomic_label_names.iteritems():
        print 'Atomic group "%s" via label "%s" is READY to run job %d on:' % (
                atomic_group_name, label_name, job_id)
        print ', '.join(host_list)
        print 'Is the job scheduler healthy?'
        print

    sys.exit(0)


### Not an atomic group synchronous job:

if len(args) != 2:
    if len(queue_entries) == 1 and queue_entries[0]['host']:
        hostname = queue_entries[0]['host']['hostname']
    else:
        parser.print_help()
        print '\nERROR: A hostname associated with the job is required.'
        sys.exit(1)
else:
    hostname = args[1]

# host exists?
hosts = proxy.run('get_hosts', hostname=hostname)
if not hosts:
    print 'No such host', hostname
    sys.exit(1)
host = hosts[0]

# Boolean to track our findings.  We want to list all reasons it won't run,
# not just the first.
job_will_run = True

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

# meets atomic group requirements?
host_labels = proxy.run('get_labels', name__in=list(host_label_names))
host_atomic_group_labels = [label for label in host_labels
                            if label['atomic_group']]
host_atomic_group_name = None
if host_atomic_group_labels:
    atomic_groups = set()
    for label in host_atomic_group_labels:
        atomic_groups.add(label['atomic_group']['name'])
    if len(atomic_groups) != 1:
        print 'Host has more than one atomic group!'
        print list(atomic_groups)
        sys.exit(1)
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
    job_will_run = False

# host locked?
if host['locked']:
    print 'Host is locked by', host['locked_by'], 'no jobs will schedule on it.'
    job_will_run = False

# acl accessible?
accessible = proxy.run('get_hosts', hostname=hostname,
                       aclgroup__users__login=owner)
if not accessible:
    host_acls = ', '.join(group['name'] for group in
                          proxy.run('get_acl_groups', hosts__hostname=hostname))
    owner_acls = ', '.join(group['name'] for group in
                           proxy.run('get_acl_groups', users__login=owner))
    print 'Host not ACL-accessible to job owner', owner
    print ' Host ACLs:', host_acls
    print ' Owner Acls:', owner_acls
    job_will_run = False

# meets dependencies?
job_deps_list = job['dependencies'].split(',')
job_deps = set()
if job_deps_list != ['']:
    job_deps = set(job_deps_list)
unmet = job_deps - host_label_names
if unmet:
    print ("Host labels (%s) don't satisfy job dependencies: %s" %
           (', '.join(host_label_names), ', '.join(unmet)))
    job_will_run = False

# at this point, if the job is for an unassigned atomic group, things are too
# complicated to proceed
unassigned_atomic_group_entries = [entry for entry in queue_entries
                                   if entry['atomic_group']
                                   and not entry['host']]
if unassigned_atomic_group_entries:
    print ("Job is for an unassigned atomic group.  That's too complicated, I "
           "can't give you any definite answers.  Sorry.")
    sys.exit(1)

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
            job_will_run = False

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
    job_will_run = False

if job_will_run:
    print ("Job %s should run on host %s; if you've already waited about ten "
           "minutes or longer, it's probably a server issue or a bug." %
           (job_id, hostname))
    sys.exit(1)
else:
    print "All of the reasons this job is not running are listed above."
    sys.exit(0)
