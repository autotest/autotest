import logging
from autotest_lib.client.common_lib import error
from autotest_lib.client.virt import virt_test_utils


def run_ping(test, params, env):
    """
    Ping the guest with different size of packets.

    Packet Loss Test:
    1) Ping the guest with different size/interval of packets.

    Stress Test:
    1) Flood ping the guest.
    2) Check if the network is still usable.

    @param test: KVM test object.
    @param params: Dictionary with the test parameters.
    @param env: Dictionary with test environment.
    """
    vm = env.get_vm(params["main_vm"])
    vm.verify_alive()
    session = vm.wait_for_login(timeout=int(params.get("login_timeout", 360)))

    counts = params.get("ping_counts", 100)
    flood_minutes = float(params.get("flood_minutes", 10))
    nics = params.get("nics").split()
    strict_check = params.get("strict_check", "no") == "yes"

    packet_size = [0, 1, 4, 48, 512, 1440, 1500, 1505, 4054, 4055, 4096, 4192,
                   8878, 9000, 32767, 65507]

    try:
        for i, nic in enumerate(nics):
            ip = vm.get_address(i)
            if not ip:
                logging.error("Could not get the ip of nic index %d: %s",
                              i, nic)
                continue

            for size in packet_size:
                logging.info("Ping with packet size %s", size)
                status, output = virt_test_utils.ping(ip, 10,
                                                     packetsize=size,
                                                     timeout=20)
                if strict_check:
                    ratio = virt_test_utils.get_loss_ratio(output)
                    if ratio != 0:
                        raise error.TestFail("Loss ratio is %s for packet size"
                                             " %s" % (ratio, size))
                else:
                    if status != 0:
                        raise error.TestFail("Ping failed, status: %s,"
                                             " output: %s" % (status, output))

            logging.info("Flood ping test")
            virt_test_utils.ping(ip, None, flood=True, output_func=None,
                                timeout=flood_minutes * 60)

            logging.info("Final ping test")
            status, output = virt_test_utils.ping(ip, counts,
                                                 timeout=float(counts) * 1.5)
            if strict_check:
                ratio = virt_test_utils.get_loss_ratio(output)
                if ratio != 0:
                    raise error.TestFail("Ping failed, status: %s,"
                                         " output: %s" % (status, output))
            else:
                if status != 0:
                    raise error.TestFail("Ping returns non-zero value %s" %
                                         output)
    finally:
        session.close()
