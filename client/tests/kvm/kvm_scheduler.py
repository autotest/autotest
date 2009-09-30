import os, select
import kvm_utils, kvm_vm, kvm_subprocess


class scheduler:
    """
    A scheduler that manages several parallel test execution pipelines on a
    single host.
    """

    def __init__(self, tests, num_workers, total_cpus, total_mem, bindir):
        """
        Initialize the class.

        @param tests: A list of test dictionaries.
        @param num_workers: The number of workers (pipelines).
        @param total_cpus: The total number of CPUs to dedicate to tests.
        @param total_mem: The total amount of memory to dedicate to tests.
        @param bindir: The directory where environment files reside.
        """
        self.tests = tests
        self.num_workers = num_workers
        self.total_cpus = total_cpus
        self.total_mem = total_mem
        self.bindir = bindir
        # Pipes -- s stands for scheduler, w stands for worker
        self.s2w = [os.pipe() for i in range(num_workers)]
        self.w2s = [os.pipe() for i in range(num_workers)]
        self.s2w_r = [os.fdopen(r, "r", 0) for r, w in self.s2w]
        self.s2w_w = [os.fdopen(w, "w", 0) for r, w in self.s2w]
        self.w2s_r = [os.fdopen(r, "r", 0) for r, w in self.w2s]
        self.w2s_w = [os.fdopen(w, "w", 0) for r, w in self.w2s]
        # "Personal" worker dicts contain modifications that are applied
        # specifically to each worker.  For example, each worker must use a
        # different environment file and a different MAC address pool.
        self.worker_dicts = [{"env": "env%d" % i} for i in range(num_workers)]


    def worker(self, index, run_test_func):
        """
        The worker function.

        Waits for commands from the scheduler and processes them.

        @param index: The index of this worker (in the range 0..num_workers-1).
        @param run_test_func: A function to be called to run a test
                (e.g. job.run_test).
        """
        r = self.s2w_r[index]
        w = self.w2s_w[index]
        self_dict = self.worker_dicts[index]

        # Inform the scheduler this worker is ready
        w.write("ready\n")

        while True:
            cmd = r.readline().split()
            if not cmd:
                continue

            # The scheduler wants this worker to run a test
            if cmd[0] == "run":
                test_index = int(cmd[1])
                test = self.tests[test_index].copy()
                test.update(self_dict)
                test_iterations = int(test.get("iterations", 1))
                status = run_test_func("kvm", params=test,
                                       tag=test.get("shortname"),
                                       iterations=test_iterations)
                w.write("done %s %s\n" % (test_index, status))
                w.write("ready\n")

            # The scheduler wants this worker to free its used resources
            elif cmd[0] == "cleanup":
                env_filename = os.path.join(self.bindir, self_dict["env"])
                env = kvm_utils.load_env(env_filename, {})
                for obj in env.values():
                    if isinstance(obj, kvm_vm.VM):
                        obj.destroy()
                    elif isinstance(obj, kvm_subprocess.kvm_spawn):
                        obj.close()
                kvm_utils.dump_env(env, env_filename)
                w.write("cleanup_done\n")
                w.write("ready\n")

            # There's no more work for this worker
            elif cmd[0] == "terminate":
                break


    def scheduler(self):
        """
        The scheduler function.

        Sends commands to workers, telling them to run tests, clean up or
        terminate execution.
        """
        idle_workers = []
        closing_workers = []
        test_status = ["waiting"] * len(self.tests)
        test_worker = [None] * len(self.tests)
        used_cpus = [0] * self.num_workers
        used_mem = [0] * self.num_workers

        while True:
            # Wait for a message from a worker
            r, w, x = select.select(self.w2s_r, [], [])

            someone_is_ready = False

            for pipe in r:
                worker_index = self.w2s_r.index(pipe)
                msg = pipe.readline().split()
                if not msg:
                    continue

                # A worker is ready -- add it to the idle_workers list
                if msg[0] == "ready":
                    idle_workers.append(worker_index)
                    someone_is_ready = True

                # A worker completed a test
                elif msg[0] == "done":
                    test_index = int(msg[1])
                    test = self.tests[test_index]
                    status = int(eval(msg[2]))
                    test_status[test_index] = ("fail", "pass")[status]
                    # If the test failed, mark all dependent tests as "failed" too
                    if not status:
                        for i, other_test in enumerate(self.tests):
                            for dep in other_test.get("depend", []):
                                if dep in test["name"]:
                                    test_status[i] = "fail"

                # A worker is done shutting down its VMs and other processes
                elif msg[0] == "cleanup_done":
                    used_cpus[worker_index] = 0
                    used_mem[worker_index] = 0
                    closing_workers.remove(worker_index)

            if not someone_is_ready:
                continue

            for worker in idle_workers[:]:
                # Find a test for this worker
                test_found = False
                for i, test in enumerate(self.tests):
                    # We only want "waiting" tests
                    if test_status[i] != "waiting":
                        continue
                    # Make sure the test isn't assigned to another worker
                    if test_worker[i] is not None and test_worker[i] != worker:
                        continue
                    # Make sure the test's dependencies are satisfied
                    dependencies_satisfied = True
                    for dep in test["depend"]:
                        dependencies = [j for j, t in enumerate(self.tests)
                                        if dep in t["name"]]
                        bad_status_deps = [j for j in dependencies
                                           if test_status[j] != "pass"]
                        if bad_status_deps:
                            dependencies_satisfied = False
                            break
                    if not dependencies_satisfied:
                        continue
                    # Make sure we have enough resources to run the test
                    test_used_cpus = int(test.get("used_cpus", 1))
                    test_used_mem = int(test.get("used_mem", 128))
                    # First make sure the other workers aren't using too many
                    # CPUs (not including the workers currently shutting down)
                    uc = (sum(used_cpus) - used_cpus[worker] -
                          sum(used_cpus[i] for i in closing_workers))
                    if uc and uc + test_used_cpus > self.total_cpus:
                        continue
                    # ... or too much memory
                    um = (sum(used_mem) - used_mem[worker] -
                          sum(used_mem[i] for i in closing_workers))
                    if um and um + test_used_mem > self.total_mem:
                        continue
                    # If we reached this point it means there are, or will
                    # soon be, enough resources to run the test
                    test_found = True
                    # Now check if the test can be run right now, i.e. if the
                    # other workers, including the ones currently shutting
                    # down, aren't using too many CPUs
                    uc = (sum(used_cpus) - used_cpus[worker])
                    if uc and uc + test_used_cpus > self.total_cpus:
                        continue
                    # ... or too much memory
                    um = (sum(used_mem) - used_mem[worker])
                    if um and um + test_used_mem > self.total_mem:
                        continue
                    # Everything is OK -- run the test
                    test_status[i] = "running"
                    test_worker[i] = worker
                    idle_workers.remove(worker)
                    # Update used_cpus and used_mem
                    used_cpus[worker] = test_used_cpus
                    used_mem[worker] = test_used_mem
                    # Assign all related tests to this worker
                    for j, other_test in enumerate(self.tests):
                        for other_dep in other_test["depend"]:
                            # All tests that depend on this test
                            if other_dep in test["name"]:
                                test_worker[j] = worker
                                break
                            # ... and all tests that share a dependency
                            # with this test
                            for dep in test["depend"]:
                                if dep in other_dep or other_dep in dep:
                                    test_worker[j] = worker
                                    break
                    # Tell the worker to run the test
                    self.s2w_w[worker].write("run %s\n" % i)
                    break

                # If there won't be any tests for this worker to run soon, tell
                # the worker to free its used resources
                if not test_found and (used_cpus[worker] or used_mem[worker]):
                    self.s2w_w[worker].write("cleanup\n")
                    idle_workers.remove(worker)
                    closing_workers.append(worker)

            # If there are no more new tests to run, terminate the workers and
            # the scheduler
            if len(idle_workers) == self.num_workers:
                for worker in idle_workers:
                    self.s2w_w[worker].write("terminate\n")
                break
