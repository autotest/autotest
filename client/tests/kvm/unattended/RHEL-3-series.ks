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
timezone America/New_York
firstboot --disable
bootloader --location=mbr
clearpart --all --initlabel
autopart
reboot
mouse generic3ps/2
skipx

%packages --resolvedeps
@ base
@ development-libs
@ development-tools

%post --interpreter /usr/bin/python
import socket, os
os.system('dhclient')
os.system('chkconfig sshd on')
os.system('iptables -F')
os.system('echo 0 > /selinux/enforce')
server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
server.bind(('', 12323))
server.listen(1)
(client, addr) = server.accept()
client.send("done")
client.close()
