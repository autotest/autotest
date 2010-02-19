class ExecutionEngine(object):
    """
    Provides the Test Planner execution engine
    """

    def __init__(self, plan_id):
        self.plan_id = plan_id


    def start(self):
        """
        Starts the execution engine.

        Thread remains in this method until the execution engine is complete.
        """
        pass
