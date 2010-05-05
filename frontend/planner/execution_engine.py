import time, logging
from autotest_lib.frontend.afe import model_attributes as afe_model_attributes
from autotest_lib.frontend.shared import rest_client
from autotest_lib.frontend.planner import model_attributes, support
from autotest_lib.server import frontend


TICK_INTERVAL_SECS = 10
PAUSE_BEFORE_RESTARTING_SECS = 60

class ExecutionEngine(object):
    """
    Provides the Test Planner execution engine
    """

    _planner_rpc = frontend.Planner()
    _tko_rpc = frontend.TKO()

    def __init__(self, plan_id, server, label_name, owner):
        self._plan_id = plan_id
        self._server = server
        self._label_name = label_name
        self._owner = owner
        self._afe_rest = rest_client.Resource.load(
                'http://%s/afe/server/resources' % server)


    def start(self):
        """
        Starts the execution engine.

        Thread remains in this method until the execution engine is complete.
        """
        while True:
            try:
                self._initialize_plan()

                while not self._tick():
                    time.sleep(TICK_INTERVAL_SECS)

                self._cleanup()
                break
            except Exception, e:
                logging.error('Execution engine caught exception, restarting:'
                              '\n%s', e)
                time.sleep(PAUSE_BEFORE_RESTARTING_SECS)


    def _initialize_plan(self):
        """
        Performs actions necessary to start a test plan.

        Adds the hosts into the proper atomic group, and waits for the plan to
        be ready to start before returning
        """
        plan = self._planner_rpc.run('get_plan', id=self._plan_id)
        name = plan['name'] + '_set_atomic_group'
        if not self._afe_rest.jobs.get(name=name).total_results:
            self._launch_set_atomic_group_job(name)

        self._wait_for_initialization()


    def _launch_set_atomic_group_job(self, name):
        """
        Launch the job to set the hosts' atomic group, and initate the plan

        If the hosts are already part of an atomic group, wait for a tick and
        try again. Return when successful
        """
        while True:
            hosts = self._planner_rpc.run('get_hosts', plan_id=self._plan_id)
            control = (self._planner_rpc.run('get_atomic_group_control_file') %
                       dict(server=self._server, label_name=self._label_name,
                            plan_id=self._plan_id))

            info = self._afe_rest.execution_info.get().execution_info
            info['control_file'] = control
            info['cleanup_before_job'] = afe_model_attributes.RebootBefore.NEVER
            info['cleanup_after_job'] = afe_model_attributes.RebootAfter.NEVER
            info['run_verify'] = False
            info['machines_per_execution'] = len(hosts)

            entries = self._afe_rest.queue_entries_request.get(
                    hosts=hosts).queue_entries

            job_req = {'name' : name,
                       'owner': self._owner,
                       'execution_info' : info,
                       'queue_entries' : entries}

            try:
                self._afe_rest.jobs.post(job_req)
                logging.info('created job to set atomic group')
                break
            except rest_client.ClientError, e:
                logging.info('hosts already in atomic group')
                logging.info('(error was %s)' % e.message)
                logging.info('waiting...')
            time.sleep(TICK_INTERVAL_SECS)


    def _wait_for_initialization(self):
        while True:
            plan = self._planner_rpc.run('get_plan', id=self._plan_id)
            if plan['initialized']:
                break
            logging.info('waiting for initialization...')
            time.sleep(TICK_INTERVAL_SECS)


    def _cleanup(self):
        self._afe_rest.labels.get(name=self._label_name).members[0].delete()


    def _tick(self):
        """
        Processes one tick of the execution engine.

        Returns True if the engine has completed the plan.
        """
        logging.info('tick')
        self._process_finished_runs()
        self._check_tko_jobs()
        return self._schedule_new_runs()


    def _process_finished_runs(self):
        """
        Finalize the test runs that have finished.

        Look for runs that are in PASSED or FAILED, perform any additional
        processing required, and set the entry to 'finalized'.
        """
        Status = model_attributes.TestRunStatus
        runs = self._planner_rpc.run('get_test_runs', plan__id=self._plan_id,
                                     status__in=(Status.PASSED, Status.FAILED),
                                     finalized=False)
        for run in runs:
            logging.info('finalizing test run %s', run)

            controller = support.TestPlanController(
                    machine=run['host']['host'],
                    test_alias=run['test_job']['test_config']['alias'])
            self._run_execute_after(controller, tko_test_id=run['tko_test'],
                                    success=(run['status'] == Status.PASSED))

            if controller._fail:
                raise NotImplemented('TODO: implement forced failure')

            failed = (run['status'] == Status.FAILED or controller._fail)
            if failed and not controller._unblock:
                self._planner_rpc.run('modify_host', id=run['host']['id'],
                                      blocked=True)
            self._planner_rpc.run('modify_test_run', id=run['id'],
                                  finalized=True)


    def _check_tko_jobs(self):
        """
        Instructs the server to update the Planner test runs table

        Sends an RPC to have the server pull the proper TKO tests and add them
        to the Planner tables. Logs information about what was added.
        """
        test_runs_updated = self._planner_rpc.run('update_test_runs',
                                                  plan_id=self._plan_id)
        for update in test_runs_updated:
            logging.info('added %s test run for tko test id %s (%s)',
                         update['status'], update['tko_test_idx'],
                         update['hostname'])


    def _schedule_new_runs(self):
        next_configs = self._planner_rpc.run('get_next_test_configs',
                                             plan_id=self._plan_id)
        if next_configs['complete']:
            return True

        for config in next_configs['next_configs']:
            config_id = config['next_test_config_id']
            controller = support.TestPlanController(
                    machine=config['host'],
                    test_alias=config['next_test_config_alias'])
            self._run_execute_before(controller)
            if controller._skip:
                self._planner_rpc.run('skip_test', test_config_id=config_id,
                                      hostname=config['host'])
                continue

            self._run_job(hostname=config['host'],
                          test_config_id=config_id,
                          cleanup_before_job=controller._reboot_before,
                          cleanup_after_job=controller._reboot_after,
                          run_verify=controller._run_verify)

        return False


    def _run_job(self, hostname, test_config_id, cleanup_before_job,
                 cleanup_after_job, run_verify):
        if run_verify is None:
            run_verify = True

        test_config = self._planner_rpc.run('get_wrapped_test_config',
                                            id=test_config_id,
                                            hostname=hostname,
                                            run_verify=run_verify)

        info = self._afe_rest.execution_info.get().execution_info
        info['control_file'] = test_config['wrapped_control_file']
        info['is_server'] = True
        info['cleanup_before_job'] = cleanup_before_job
        info['cleanup_after_job'] = cleanup_after_job
        info['run_verify'] = False

        atomic_group_class = self._afe_rest.labels.get(
                name=self._label_name).members[0].get().atomic_group_class.href

        request = self._afe_rest.queue_entries_request.get(
                hosts=(hostname,), atomic_group_class=atomic_group_class)
        entries = request.queue_entries

        plan = self._planner_rpc.run('get_plan', id=self._plan_id)
        prefix = plan['label_override']
        if prefix is None:
            prefix = plan['name']
        job_req = {'name' : '%s_%s_%s' % (prefix, test_config['alias'],
                                          hostname),
                   'owner': self._owner,
                   'execution_info' : info,
                   'queue_entries' : entries}

        logging.info('starting test alias %s for host %s',
                     test_config['alias'], hostname)
        job = self._afe_rest.jobs.post(job_req)
        self._planner_rpc.run('add_job',
                              plan_id=self._plan_id,
                              test_config_id=test_config_id,
                              afe_job_id=job.get().id)


    def _run_execute_before(self, controller):
        """
        Execute the global support's execute_before() for the plan
        """
        self._run_global_support(controller, 'execute_before')


    def _run_execute_after(self, controller, tko_test_id, success):
        """
        Execute the global support's execute_after() for the plan
        """
        self._run_global_support(controller, 'execute_after',
                                 tko_test_id=tko_test_id, success=success)


    def _run_global_support(self, controller, function_name, **kwargs):
        plan = self._planner_rpc.run('get_plan', id=self._plan_id)
        if plan['support']:
            context = {'model_attributes': afe_model_attributes}
            exec plan['support'] in context
            function = context.get(function_name)
            if function:
                if not callable(function):
                    raise Exception('Global support defines %s, but it is not '
                                    'callable' % function_name)
                function(controller, **kwargs)
