#!/usr/bin/python
#
# Copyright 2007 Google Inc. Released under the GPL v2

"""This module defines the KVM class

	KVM: a KVM virtual machine monitor
"""

__author__ = """mbligh@google.com (Martin J. Bligh),
poirier@google.com (Benjamin Poirier),
stutsman@google.com (Ryan Stutsman)"""

import os

import hypervisor
import errors
import utils
import hosts


class KVM(hypervisor.Hypervisor):
	"""This class represents a KVM virtual machine monitor.
	
	Implementation details:
	This is a leaf class in an abstract class hierarchy, it must 
	implement the unimplemented methods in parent classes.
	"""
	
	build_dir= None
	pid_dir= None
	support_dir= None
	addresses= []
	qemu_ifup_script= (
		"#!/bin/sh\n"
		"# $1 is the name of the new qemu tap interface\n"
		"\n"
		"ifconfig $1 0.0.0.0 promisc up\n"
		"brctl addif br0 $1\n")
	check_process_script= (
		'if [ -f "%(pid_file_name)s" ]\n'
		'then\n'
		'	pid=$(cat "%(pid_file_name)s")\n'
		'	if [ -L /proc/$pid/exe ] && stat /proc/$pid/exe | \n'
		'		grep -q --  "-> \`%(qemu_binary)s\'\$"\n'
		'	then\n'
		'		echo "process present"\n'
		'	else\n'
		'		rm "%(pid_file_name)s"\n'
		'	fi\n'
		'fi')
	
	def __del__(self):
		"""Destroy a KVM object.
		
		Guests managed by this hypervisor that are still running will 
		be killed.
		"""
		self.deinitialize()

	def install(self, addresses):
		"""Compile the kvm software on the host that the object was 
		initialized with.
		
		The kvm kernel modules are compiled, for this, the kernel
		sources must be available. A custom qemu is also compiled.
		Note that 'make install' is not run, the kernel modules and 
		qemu are run from where they were built, therefore not 
		conflicting with what might already be installed.
		
		Args:
			addresses: a list of dict entries of the form 
				{"mac" : "xx:xx:xx:xx:xx:xx", 
				"ip" : "yyy.yyy.yyy.yyy"} where x and y 
				are replaced with sensible values. The ip 
				address may be a hostname or an IPv6 instead.
				
				When a new virtual machine is created, the 
				first available entry in that list will be 
				used. The network card in the virtual machine 
				will be assigned the specified mac address and
				autoserv will use the specified ip address to 
				connect to the virtual host via ssh. The virtual
				machine os must therefore be configured to 
				configure its network with the ip corresponding 
				to the mac.
		
		TODO(poirier): check dependencies before building
		kvm needs:
		libasound2-dev
		libsdl1.2-dev (or configure qemu with --disable-gfx-check, how?)
		"""
		self.addresses= [
			{"mac" : address["mac"], 
			"ip" : address["ip"],
			"is_used" : False} for address in addresses]
		
		self.build_dir = self.host.get_tmp_dir()
		self.support_dir= self.host.get_tmp_dir()
		
		self.host.run('echo "%s" > "%s"' % (
			utils.sh_escape(self.qemu_ifup_script),
			utils.sh_escape(os.path.join(self.support_dir, 
				"qemu-ifup.sh")),))
		self.host.run('chmod a+x "%s"' % (
			utils.sh_escape(os.path.join(self.support_dir, 
				"qemu-ifup.sh")),))
		
		self.host.send_file(self.source_material, self.build_dir)
		source_material= os.path.join(self.build_dir, 
				os.path.basename(self.source_material))
		
		# uncompress
		if (source_material.endswith(".gz") or 
			source_material.endswith(".gzip")):
			self.host.run('gunzip "%s"' % (utils.sh_escape(
				source_material)))
			source_material= ".".join(
				source_material.split(".")[:-1])
		elif source_material.endswith("bz2"):
			self.host.run('bunzip2 "%s"' % (utils.sh_escape(
				source_material)))
			source_material= ".".join(
				source_material.split(".")[:-1])
		
		# untar
		if source_material.endswith(".tar"):
			result= self.host.run('tar -xvf "%s" | head -1' % (
				utils.sh_escape(source_material)))
			source_material += result.stdout.strip("\n")
			self.build_dir= source_material
		
		# build
		try:
			self.host.run('make -C "%s" clean' % (
				utils.sh_escape(self.build_dir),))
		except errors.AutoservRunError:
			pass
		self.host.run('cd "%s" && ./configure' % (
			utils.sh_escape(self.build_dir),))
		self.host.run('make -j%d -C "%s"' % (
			self.host.get_num_cpu() * 2, 
			utils.sh_escape(self.build_dir),))
		
		self.initialize()
	
	def initialize(self):
		"""Initialize the hypervisor.
		
		Loads needed kernel modules and creates temporary directories.
		The logic is that you could compile once and 
		initialize - deinitialize many times. But why you would do that
		has yet to be figured.
		
		TODO(poirier): check processor type and support for vm 
			extensions before loading kvm-intel
		"""
		self.pid_dir= self.host.get_tmp_dir()
		
		self.host.run('if ! $(grep -q "^kvm " /proc/modules); '
			'then insmod "%s"; fi' % (utils.sh_escape(
			os.path.join(self.build_dir, "kernel/kvm.ko")),))
		self.host.run('if ! $(grep -q "^kvm_intel " /proc/modules); '
			'then insmod "%s"; fi' % (utils.sh_escape(
			os.path.join(self.build_dir, "kernel/kvm-intel.ko")),))
	
	def deinitialize(self):
		"""Terminate the hypervisor.
		
		Kill all the virtual machines that are still running and
		unload the kernel modules.
		"""
		self.refresh_guests()
		for address in self.addresses:
			if address["is_used"]:
				self.delete_guest(address["is_used"])
		self.pid_dir= None
		
		self.host.run(
			'if $(grep -q "^kvm_intel [[:digit:]]+ 0" '
				'/proc/modules)\n'
			'then\n'
			'	rmmod kvm-intel\n'
			'fi')
		self.host.run(
			'if $(grep -q "^kvm [[:digit:]]+ 0" /proc/modules)\n'
			'then\n'
			'	rmmod kvm\n'
			'fi')
	
	def new_guest(self):
		"""Start a new guest ("virtual machine").
		
		Returns:
			The ip that was picked from the list supplied to 
			install() and assigned to this guest.
		
		Raises:
			AutoservVirtError: no more addresses are available.
		"""
		for address in self.addresses:
			if not address["is_used"]:
				break
		else:
			raise errors.AutoservVirtError(
				"No more addresses available")
		
		# TODO(poirier): uses start-stop-daemon until qemu -pidfile 
		# and -daemonize can work together
		retval= self.host.run(
			'start-stop-daemon -S --exec "%s" --pidfile "%s" -b -- '
			# this is the line of options that can be modified
			'-m 256 -hda /var/local/vdisk.img -snapshot '
			'-pidfile "%s" -nographic '
			#~ '-serial telnet::4444,server '
			#~ '-monitor telnet::4445,server '
			'-net nic,macaddr="%s" -net tap,script="%s" ' % (
			utils.sh_escape(os.path.join(
				self.build_dir, 
				"qemu/x86_64-softmmu/qemu-system-x86_64")),
			utils.sh_escape(os.path.join(
				self.pid_dir, 
				"vhost%s_pid" % (address["ip"],))), 
			utils.sh_escape(os.path.join(
				self.pid_dir, 
				"vhost%s_pid" % (address["ip"],))), 
			utils.sh_escape(address["mac"]),
			utils.sh_escape(os.path.join(
				self.support_dir, 
				"qemu-ifup.sh")),))
		
		address["is_used"]= True
		return address["ip"]
	
	def refresh_guests(self):
		"""Refresh the list of guests addresses.
		
		The is_used status will be updated according to the presence
		of the process specified in the pid file that was written when
		the virtual machine was started.
		
		TODO(poirier): there are a lot of race conditions in this code
		because the process might terminate on its own anywhere in 
		between
		"""
		for address in self.addresses:
			if address["is_used"]:
				pid_file_name= utils.sh_escape(os.path.join(
					self.pid_dir, 
					"vhost%s_pid" % (address["ip"],)))
				retval= self.host.run(
					self.check_process_script % {
					"pid_file_name" : pid_file_name, 
					"qemu_binary" : utils.sh_escape(
					os.path.join(self.build_dir, 
					"qemu/x86_64-softmmu/qemu-system-x86_64"
					)),})
				if (retval.stdout.strip(" \n") != 
					"process present"):
					address["is_used"]= False
	
	def delete_guest(self, guest_hostname):
		"""Terminate a virtual machine.
		
		Args:
			guest_hostname: the ip (as it was specified in the 
				address list given to install()) of the guest 
				to terminate.
		
		TODO(poirier): is there a difference in qemu between 
		sending SIGTEM or quitting from the monitor?
		TODO(poirier): there are a lot of race conditions in this code
		because the process might terminate on its own anywhere in 
		between
		"""
		for address in self.addresses:
			if address["ip"] is guest_hostname:
				break
		else:
			return None
		
		pid_file_name= utils.sh_escape(os.path.join(self.pid_dir, 
			"vhost%s_pid" % (address["ip"],)))
		
		retval= self.host.run(
			self.check_process_script % {
			"pid_file_name" : pid_file_name, 
			"qemu_binary" : utils.sh_escape(os.path.join(
			self.build_dir, 
			"qemu/x86_64-softmmu/qemu-system-x86_64")),})
		if retval.stdout.strip(" \n") == "process present":
			self.host.run('kill $(cat "%s")' %(
				pid_file_name,))
			self.host.run('rm "%s"' %(
				pid_file_name,))
		address["is_used"]= False
