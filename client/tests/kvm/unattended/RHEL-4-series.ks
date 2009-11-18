install
cdrom
text
reboot
lang en_US.UTF-8
langsupport --default=en_US.UTF-8 en_US.UTF-9
keyboard us
network --bootproto dhcp
rootpw 123456
firewall --enabled --ssh
selinux --enforcing
timezone --utc America/New_York
firstboot --disable
bootloader --location=mbr
zerombr
clearpart --all --initlabel
autopart
reboot

%packages
@ admin-tools
@ core
@ base
@ base-x
@ gnome-desktop
@ development-libs
@ development-tools

%post --interpreter /usr/bin/python
import socket, os
os.system('chkconfig sshd on')
os.system('iptables -F')
os.system('echo 0 > /selinux/enforce')
port = 12323
buf = 1024
addr = ('10.0.2.2', port)
client = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
client.connect(addr)
client.sendto('done', addr)
client.close()
