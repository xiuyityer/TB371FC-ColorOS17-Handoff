#!/usr/bin/env python3
"""Capture failed-boot records immediately after returning to C16."""
import json
import subprocess
import time
from pathlib import Path
import pilot_prepare as p

out=p.ROOT/'c17-port/restore-c16-r1'
p.LOG=out/'collect-commands.jsonl'
for i in range(90):
    proc=subprocess.run(p.ADB+['get-state'],capture_output=True,text=True,timeout=8)
    if proc.returncode==0 and proc.stdout.strip()=='device':break
    time.sleep(2)
else:raise RuntimeError('ADB unavailable after C16 restore')
before=p.root('id; uname -a; getprop sys.boot_completed; getprop ro.build.version.sdk; getprop ro.boot.slot_suffix; cat /proc/sys/kernel/random/boot_id; getenforce')
(out/'device-return.txt').write_text(before)
assert 'uid=0(root)' in before and '#789 ' in before and '_a' in before
command='''set -e
base=/data/local/tmp/c17-return-records
mkdir -p "$base" /sys/fs/pstore
mount -t pstore pstore /sys/fs/pstore 2>"$base/pstore-mount.txt" || true
cp -a /sys/fs/pstore "$base/"
dmesg > "$base/return-dmesg.txt"
getprop > "$base/return-props.txt"
cat /proc/cmdline > "$base/return-cmdline.txt"
cat /proc/mounts > "$base/return-mounts.txt"
logcat -b all -d -t 2000 > "$base/return-logcat.txt"
sha256sum /dev/block/by-name/boot_a > "$base/boot-a-sha256.txt"
chmod -R a+rX "$base"
'''
p.root(command)
p.run(p.ADB+['pull','/data/local/tmp/c17-return-records',str(out/'device-records')],timeout=120)
print(before)
print('Records captured',out/'device-records')
