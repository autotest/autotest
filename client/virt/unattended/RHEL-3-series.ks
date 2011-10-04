install
KVM_TEST_MEDIUM
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
bootloader --location=mbr --append="console=tty0 console=ttyS0,115200"
clearpart --all --initlabel
autopart
reboot
mouse generic3ps/2
skipx

%packages --resolvedeps
@ base
@ development-libs
@ development-tools
ntp

%post --interpreter /usr/bin/python
import socket, os
os.system('/sbin/ifconfig eth0 10.0.2.15 netmask 255.255.255.0 up')
os.system('/sbin/route add default gw 10.0.2.2')
os.system('chkconfig sshd on')
server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
server.bind(('', 12323))
server.listen(1)
(client, addr) = server.accept()
client.send("done")
client.close()
