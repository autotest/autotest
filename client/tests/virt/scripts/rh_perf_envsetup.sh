#!/bin/bash
# @author Amos Kong <akong@redhat.com>
# @copyright: 2012 Red Hat, Inc.
#
# This script is prepared for RHEL/Fedora system, it's just an
# example, users can reference it to custom their own script.

if [[ $# != 2 ]];then
    echo "usage: $0 <guest/host> <rebooted/none>"
    exit
fi
guest=$1
reboot=$2

########################
echo "Setup env for performance testing, reboot isn't needed"
####
echo "Run test on a private LAN, as there are multpile nics, so set arp_filter to 1"
sysctl net.ipv4.conf.default.arp_filter=1
sysctl net.ipv4.conf.all.arp_filter=1
echo "Disable netfilter on bridges"
sysctl net.bridge.bridge-nf-call-ip6tables=0
sysctl net.bridge.bridge-nf-call-iptables=0
sysctl net.bridge.bridge-nf-call-arptables=0
echo "Set bridge forward delay to 0"
sysctl brctl setfd switch 0

####
echo "Stop the running serivices"

if [[ $guest = "host" ]];then
    echo "Run tunning profile on host"
    # RHEL6, requst 'tuned' package
    tuned-adm profile enterprise-storage
    # RHEL5
    service tuned start
fi
service auditd stop
service avahi-daemon stop
service anacron stop
service qpidd stop
service smartd stop
service crond stop
service haldaemon stop
service opensmd stop
service openibd stop
service yum-updatesd stop
service collectd stop
service bluetooth stop
service cups stop
service cpuspeed stop
service hidd stop
service isdn stop
service kudzu stop
service lvm2-monitor stop
service mcstrans stop
service mdmonitor stop
service messagebus stop
service restorecond stop
service rhnsd stop
service rpcgssd stop
service setroubleshoot stop
service smartd stop
########################

if [[ $reboot = "rebooted" ]];then
    echo "OS already rebooted"
    echo "Environment setup finished"
    exit
fi

########################
echo "Setup env for performance testing, reboot is needed"
####
echo "Setup runlevel to 3"
if [[ $guest = "guest" ]];then
   echo sed -ie "s/id:.*:initdefault:/id:3:initdefault:/g"  /etc/inittab
fi

####
echo "Off services when host starts up"

chkconfig  auditd off
chkconfig  autofs off
chkconfig  avahi-daemon off
chkconfig  crond off
chkconfig  cups off
chkconfig  ip6tables off
chkconfig  sendmail off
chkconfig  smartd off
chkconfig  xfs off
chkconfig  acpid off
chkconfig  atd off
chkconfig  haldaemon off
chkconfig  mdmonitor off
chkconfig  netfs off
chkconfig  rhnsd off
chkconfig  rpcgssd off
chkconfig  rpcidmapd off
chkconfig  abrtd off
chkconfig  kdump off
chkconfig  koan off
chkconfig  libvirt-guests off
chkconfig  ntpdate off
chkconfig  portreserve off
chkconfig  postfix off
chkconfig  rhsmcertd off
chkconfig  tuned off

########################
echo "Environment setup finished"
echo "OS should reboot"
