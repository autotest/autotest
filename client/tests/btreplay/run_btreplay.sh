#!/bin/sh

device=$1
devices=$2
tmpdir=$3

alldevs="-d /dev/${device}"
alldnames=$device
for dev in $devices
do
  alldevs="${alldevs} -d /dev/${dev}"
  alldnames="${alldnames} ${dev}"
done

./btreplay/btrecord -d .. -D ${tmpdir} ${device}

/usr/bin/time ./btreplay/btreplay -d ${tmpdir} -N -W ${device} 2>&1

./blktrace -D ${tmpdir} ${alldevs} >/dev/null &
./btreplay/btreplay -d ${tmpdir} -W ${device}
killall -INT blktrace
./blkparse -q -D ${tmpdir} -d ${tmpdir}/trace.bin -O ${alldnames} >/dev/null
./btt/btt -i ${tmpdir}/trace.bin
