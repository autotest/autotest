"""\
        client/bin/nway.py:
        Host-resident shared code for twoway and N-way container tests.
        Exports  run_twoway_pair()  and run_twoway_matrix()
           which are invoked from client-side control scripts
           e.g.  client/tests/container_twoway/control

        run_twoway_pair():
        Runs a single pair of benchmarks, in equal-size containers.
        Measure speeds when running two programs concurrently
        on same host in separate half-machine containers.

        run_twoway_matrix():
        Runs many pairs of benchmarks, one pair at a time.
        Repeat for all M*N combinations of chosen benchmark programs
        and chosen antagonist second programs.
        Then run each program by itself, in same half-machine container,
        to establish baseline speed when it has no interference.

        Chosen programs should have roughly-equal runtimes of
        about 2-3 minutes.
        """

__author__ = """duanes@google.com (Duane Sand), Copyright Google 2008"""

from autotest_lib.client.common_lib import error
from autotest_lib.client.bin        import cpuset


def _set_kernel_options(stale_page_age, kswapd_merge, 
                        sched_idle_antag, sched_idle, vma_max):
    # apply kernel options chosen for these runs, and build keyval summary
    cpuset.set_stale_page_age(stale_page_age)
    vma_max = cpuset.set_vma_max(vma_max)
    numa_fake = cpuset.get_boot_numa()
    return { 'stale_page_age'  : stale_page_age, 
             'numa_fake'       : numa_fake,
             'kswapd_merge'    : kswapd_merge,  
             'sched_idle'      : sched_idle,
             'sched_idle_antag': sched_idle_antag, 
             'vma_max'         : vma_max, }


def _half_machine(job):
    # return half of all avail cpu cores and half of avail mem nodes
    # cpuset.release_dead_containers() -- not working well yet
    total_cpus = job.cpu_count()
    total_nodes = len(cpuset.my_available_exclusive_mem_nodes())
    print "avail cpus", total_cpus, ", avail nodes", total_nodes,
    print ", mb/node", cpuset.mbytes_per_mem_node()
    node_cnt = total_nodes // 2
    cpus     = total_cpus  // 2
    if cpus <= 0 or node_cnt <= 0:
        raise error.JobError('Not enough cpus or mem for containers')
    return (cpus, node_cnt)


def _constrained_test(job, testname, all_args, node_cnt, cpu_list, 
                      antagonist, koptions, pairtag):
    # run an Autotest basic test in own custom temporary container
    # antagonist is '' if testname is running solo
    mbytes = int( node_cnt * cpuset.mbytes_per_mem_node() )
    myargs = all_args.get(testname, {}).copy()
    keyvals = koptions.copy()
    keyvals['twoway'             ] = antagonist
    keyvals['container_mem_nodes'] = node_cnt
    keyvals['container_cores'    ] = len(cpu_list)
    if not antagonist:
        del keyvals['sched_idle_antag']
    myargs['test_attributes'] = keyvals
    # In TKO database, qualify each test name with '.twoway' to keep
    #   these runs separate from all unconstrained serial runs
    testtag = myargs.pop('tag', '')    # e.g. 'eth0'
    if testtag:
        testtag += '.'
    testtag += 'twoway'
    # In results-log directory names, further qualify test name with
    #   '.[<pairedtestname>].[ant.]NN'
    #   to separate the multiple runs' results within total job
    subdir_tag = antagonist + '.' + pairtag
    if koptions['sched_idle']:
        cpuset.set_sched_idle()
    job.new_container(mbytes=mbytes, cpus=cpu_list, 
                      kswapd_merge=koptions['kswapd_merge'])
    job.run_test(testname, tag=testtag, subdir_tag=subdir_tag, **myargs)
    job.release_container()


def _oneway_test(job, test, args, node_cnt, cpus, koptions, nth):
    # run single test in single container, sized to subset of machine
    tag = str(nth)
    _constrained_test(job, test, args, 
                      node_cnt, range(cpus), '', koptions, tag)


def _twoway_test(job, test1, test2, args, node_cnt, cpus, koptions, nth):
    # run 1 pair of tests concurrently, in separate equal-sized containers
    # antagonist test2 may run at lesser priority.
    koptions2 = koptions.copy()
    koptions2['sched_idle'      ] = koptions['sched_idle_antag']
    koptions2['sched_idle_antag'] = koptions['sched_idle'      ]
    tag1 = str(nth)
    tag2 = 'ant.' + tag1
    tasks = []
    tasks.append( [ _constrained_test, job, test1, args,
                    node_cnt, range(cpus*0, cpus*1), test2, koptions,  tag1 ] )
    tasks.append( [ _constrained_test, job, test2, args,
                    node_cnt, range(cpus*1, cpus*2), test1, koptions2, tag2 ] )
    job.parallel(*tasks)


def run_twoway_pair(job, benchmark, antagonist, args, 
                    stale_page_age=0, sched_idle_antag=False,
                    sched_idle=False, kswapd_merge=False, 
                    vma_max=25, repeats=1):
    # Run a single two-way container test of some pair of benchmarks
    # Called from client-side control scripts
    koptions = _set_kernel_options(stale_page_age, kswapd_merge, 
                                   sched_idle_antag, sched_idle, vma_max)
    (cpus, node_cnt) = _half_machine(job)
    for i in xrange(repeats):
        _twoway_test(job, benchmark, antagonist, args, node_cnt, cpus, 
                     koptions, i)


def run_twoway_matrix(job, benchmarks, antagonists, args,
                        stale_page_age=0, sched_idle_antag=False,
                        sched_idle=False, kswapd_merge=False,
                        vma_max=25,
                        twoway_repeats=1, oneway_repeats=1):
    # Run a series of two-way container tests of pairs of basic tests,
    #   for each MxN pairing of tests from benchmarks & antagonists.
    # Also collect baseline one-way container tests of same benchmarks.
    # Called from client-side control scripts
    koptions = _set_kernel_options(stale_page_age, kswapd_merge, 
                                   sched_idle_antag, sched_idle, vma_max)
    (cpus, node_cnt) = _half_machine(job)

    # collect samples of all distinct twoway test combos
    for test1 in benchmarks:
        for test2 in antagonists:
            # When running antagonists in a symmetric way,
            # running pair (A, B) also gives speeds for (B, A)
            # Skip one of (A, B) or (B, A) if both in MxN matrix
            if (sched_idle_antag  or  test1 <= test2  or
                    test1 not in antagonists  or  test2 not in benchmarks):
                for i in xrange(twoway_repeats):
                    _twoway_test(job, test1, test2, args, 
                                 node_cnt, cpus, koptions, i)

    # collect samples of corresponding single-test runs
    for test1 in benchmarks:
        for i in xrange(oneway_repeats):
            _oneway_test(job, test1, args, node_cnt, cpus, koptions, i)


def run_solo(job, benchmarks, args, stale_page_age=0, 
             sched_idle=False, kswapd_merge=False, vma_max=25, repeats=1):
   # run each benchmark alone without antagonist, in same
   #   half-machine containers used by twoway_matrix.
   run_twoway_matrix(job, benchmarks, antagonists=set(), args=args,
                     stale_page_age=stale_page_age, sched_idle_antag=False,
                     sched_idle=sched_idle, kswapd_merge=kswapd_merge,
                     vma_max=vma_max,
                     twoway_repeats=0, oneway_repeats=repeats)
