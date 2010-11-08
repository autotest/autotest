from autotest_lib.server import autotest, hosts, subcommand, test
from autotest_lib.server import utils

class netperf2(test.test):
    version = 2

    def run_once(self, pair, test, time, stream_list, cycles):
        print "running on %s and %s\n" % (pair[0], pair[1])

        # Designate a label for the server side tests.
        server_label = 'net_server'

        server = hosts.create_host(pair[0])
        client = hosts.create_host(pair[1])

        # If client has the server_label, then swap server and client.
        platform_label = client.get_platform_label()
        if platform_label == server_label:
            (server, client) = (client, server)


        # Disable IPFilters if they are enabled.
        for m in [client, server]:
            status = m.run('/sbin/iptables -L')
            if not status.exit_status:
                m.disable_ipfilters()

        server_at = autotest.Autotest(server)
        client_at = autotest.Autotest(client)

        template = ''.join(["job.run_test('netperf2', server_ip='%s', ",
                            "client_ip='%s', role='%s', test='%s', ",
                            "test_time=%d, stream_list=%s, tag='%s', ",
                            "iterations=%d)"])

        server_control_file = template % (server.ip, client.ip, 'server', test,
                                          time, stream_list, test, cycles)
        client_control_file = template % (server.ip, client.ip, 'client', test,
                                          time, stream_list, test, cycles)

        server_command = subcommand.subcommand(server_at.run,
                                    [server_control_file, server.hostname])
        client_command = subcommand.subcommand(client_at.run,
                                    [client_control_file, client.hostname])

        subcommand.parallel([server_command, client_command])

        for m in [client, server]:
            status = m.run('/sbin/iptables -L')
            if not status.exit_status:
                m.enable_ipfilters()
