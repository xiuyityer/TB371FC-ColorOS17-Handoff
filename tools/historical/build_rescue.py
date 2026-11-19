#!/usr/bin/env python3
"""Standalone diagnostics ramdisk; no recovery UI or userdata mounts."""
import gzip
import hashlib
import json
import re
from pathlib import Path
from build_erofs_boot import cpio_read, cpio_write, repack
from build_boot import unpack, BASE

W=Path(__file__).resolve().parents[1]
out=W/'rescue-r1'
out.mkdir(exist_ok=False)
rows=cpio_read(gzip.decompress((W/'evidence/recovery-ramdisk.gz').read_bytes()))
result=[]
for name,fields,content in rows:
    if name in ('prop.default','default.prop') and fields[1]&0o170000==0o100000:
        text=content.decode()
        for key,value in [('ro.secure','0'),('ro.debuggable','1'),('ro.adb.secure','0')]:
            text=re.sub(r'^'+re.escape(key)+r'=.*$',key+'='+value,text,flags=re.M)
        content=text.encode()
    if name=='system/etc/init/hw/init.rc':
        text=content.decode()
        text=text.replace('service recovery /system/bin/recovery\n','service recovery /system/bin/recovery\n    disabled\n')
        text+='''
# Fixed diagnostics only. The recovery UI is disabled; no mount_all /data.
service c17_rescue_capture /system/bin/sh /system/etc/c17-rescue.sh
    disabled
    oneshot
    user root
    group root
    seclabel u:r:recovery:s0

on boot
    setprop service.adb.root 1
    setprop sys.usb.config adb
    start c17_rescue_capture
'''
        content=text.encode()
    result.append((name,fields,content))
script=b'''#!/system/bin/sh
mkdir -p /tmp/c17-rescue /sys/fs/pstore
mount -t pstore pstore /sys/fs/pstore 2>/tmp/c17-rescue/pstore-mount.txt
cp -a /sys/fs/pstore/. /tmp/c17-rescue/
dmesg > /tmp/c17-rescue/rescue-dmesg.txt
cat /proc/cmdline > /tmp/c17-rescue/rescue-cmdline.txt
getprop > /tmp/c17-rescue/rescue-props.txt
chmod -R a+rX /tmp/c17-rescue
'''
result.append(('system/etc/c17-rescue.sh',[0,0o100755,0,0,1,1793807029,0,0,0,0,0,0,0],script))
ramdisk=gzip.compress(cpio_write(result),compresslevel=9,mtime=0)
base=BASE.read_bytes();parts=unpack(base)
image=repack(base,parts['kernel'],ramdisk,parts['dtb'])
check={n:c for n,_,c in cpio_read(gzip.decompress(unpack(image)['ramdisk']))}
assert b'service recovery /system/bin/recovery\n    disabled\n' in check['system/etc/init/hw/init.rc']
assert check['system/etc/c17-rescue.sh']==script
assert b'ro.debuggable=1' in check['prop.default']
(out/'boot_a.img').write_bytes(image)
report=dict(state='RESCUE_BUILT_HARDWARE_PENDING',bytes=len(image),sha256=hashlib.sha256(image).hexdigest(),
            kernel_source=str(BASE),ramdisk_source='Device recovery_a',userdata_mount=False,recovery_ui_disabled=True,
            intended_write='boot_a only',no_super_or_userdata_write=True)
(out/'manifest.json').write_text(json.dumps(report,indent=2)+'\n')
print(json.dumps(report,indent=2))
