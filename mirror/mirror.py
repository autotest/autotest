#!/usr/bin/python2.4
import os, rsync, trigger

excludes = ('2.6.0-test*/', 'broken-out/', '*.sign', '*.gz')

if 'MIRROR_DIR' in os.environ:
	target = os.environ['MIRROR_DIR']
else: 
	target = "/home/mirror"

source = 'rsync://rsync.kernel.org/pub/linux/kernel'
mirror = rsync.rsync(source, target, excludes)

mirror.sync('v2.6/patch-2.6.*.bz2', 'kernel/v2.6')
# for some reason 'linux-2.6.[0-9]*.tar.bz2' doesn't work
mirror.sync('v2.6/linux-2.6.[0-9].tar.bz2', 'kernel/v2.6')
mirror.sync('v2.6/linux-2.6.[0-9][0-9].tar.bz2', 'kernel/v2.6')
mirror.sync('v2.6/snapshots/*.bz2', 'kernel/v2.6/snapshots')
mirror.sync('people/akpm/patches/2.6/*', 'akpm')

for t in trigger.scan(mirror.tmpfile):
	print t
