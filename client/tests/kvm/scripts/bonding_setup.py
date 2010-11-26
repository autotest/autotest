import os, re, commands, sys
"""This script is used to setup bonding, macaddr of bond0 should be assigned by
argv1"""

if len(sys.argv) != 2:
    sys.exit(1)
mac = sys.argv[1]
eth_nums = 0
ifconfig_output = commands.getoutput("ifconfig")
re_eth = "eth[0-9]*"
for ename in re.findall(re_eth, ifconfig_output):
    eth_config_file = "/etc/sysconfig/network-scripts/ifcfg-%s" % ename
    eth_config = """DEVICE=%s
USERCTL=no
ONBOOT=yes
MASTER=bond0
SLAVE=yes
BOOTPROTO=none
""" % ename
    f = file(eth_config_file,'w')
    f.write(eth_config)
    f.close()

bonding_config_file = "/etc/sysconfig/network-scripts/ifcfg-bond0"
bond_config = """DEVICE=bond0
BOOTPROTO=dhcp
NETWORKING_IPV6=no
ONBOOT=yes
USERCTL=no
MACADDR=%s
""" % mac
f = file(bonding_config_file, "w")
f.write(bond_config)
f.close()
os.system("modprobe bonding")
os.system("service NetworkManager stop")
os.system("service network restart")
