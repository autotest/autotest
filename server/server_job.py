from autotest_lib.server import base_server_job

# site_server_job.py may be non-existant or empty, make sure that an
# appropriate site_server_job class is created nevertheless
try:
    from autotest_lib.server.site_server_job import site_server_job
except ImportError:
    class site_server_job(base_server_job.base_server_job):
        pass

class server_job(site_server_job):
    pass
