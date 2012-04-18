from autotest.server import autotest_remote, hosts, subcommand, test
from autotest.server import utils

class iperf(test.test):
    version = 1

    def run_once(self, pair, udp, bidirectional, time, stream_list):
        print "running on %s and %s\n" % (pair[0], pair[1])

        # Designate a lable for the server side tests.
        server_label = 'net_server'

        tagname = "%s_%s" % (pair[0], pair[1])
        server = hosts.create_host(pair[0])
        client = hosts.create_host(pair[1])

        # Ensure the client doesn't have the server label.
        platform_label = client.get_platform_label()
        if platform_label == server_label:
            (server, client) = (client, server)

        # Disable IPFilters if they are present.
        for m in [client, server]:
            status = m.run('iptables -L')
            if not status.exit_status:
                m.disable_ipfilters()

        server_at = autotest_remote.Autotest(server)
        client_at = autotest_remote.Autotest(client)

        template = ''.join(["job.run_test('iperf', server_ip='%s', client_ip=",
                            "'%s', role='%s', udp=%s, bidirectional=%s,",
                            "test_time=%d, stream_list=%s, tag='%s')"])

        server_control_file = template % (server.ip, client.ip, 'server', udp,
                                          bidirectional, time, stream_list,
                                          tagname)
        client_control_file = template % (server.ip, client.ip, 'client', udp,
                                          bidirectional, time, stream_list,
                                          tagname)

        server_command = subcommand.subcommand(server_at.run,
                         [server_control_file, server.hostname])
        client_command = subcommand.subcommand(client_at.run,
                         [client_control_file, client.hostname])

        subcommand.parallel([server_command, client_command])

        for m in [client, server]:
            status = m.run('iptables -L')
            if not status.exit_status:
                m.enable_ipfilters()
