===========================
 Job and Test Organization
===========================

In Autotest, a :class:`Job <autotest.frontend.afe.models.Job>` is enqueued via
the Autotest's Frontend (aka AFE). Its results are then automatically parsed
into the TKO database consists of one or more tests.

Each test has a :attr:`autotest.frontent.tko.models.Job.status`.
