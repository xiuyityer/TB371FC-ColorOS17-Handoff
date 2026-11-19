#!/usr/bin/env python3
"""Build an ADB-only TWRP diagnostics recovery retaining its header/DTBO.

No recovery UI means no automatic data mounts or decryption attempts.
"""
import gzip
import hashlib
import json
from pathlib import Path
import struct
from build_boot import unpack, BASE, KSU
from build_erofs_boot import cpio_read, cpio_write

W=Path(__file__).resolve().parents[1]
out=W/'twrp-789-r3-headless'
out.mkdir(exist_ok=False)
original=(W/'twrp/twrp_3.7.1.img').read_bytes()
assert hashlib.sha256(original).hexdigest()=='6ce174af2b2bf6ebcec026d94fa95a12037e78ae1c27d3abfe40fbe0008fe7e7'
page=struct.unpack_from('<I',original,36)[0]
align=lambda n:(n+page-1)//page*page
header=bytearray(original[:page])
dtbo_size=struct.unpack_from('<I',header,1632)[0]
dtbo_off=struct.unpack_from('<Q',header,1636)[0]
dtbo=original[dtbo_off:dtbo_off+dtbo_size]
assert dtbo_size>0 and len(dtbo)==dtbo_size and struct.unpack_from('<I',header,24)[0]==0
kernel=unpack(KSU.read_bytes())['kernel']
dtb=unpack(BASE.read_bytes())['dtb']
shim=(W/'overlays/early-erofs-twrp').read_bytes()
module=(W/'overlays/erofs-r2.ko').read_bytes()
rows=cpio_read(gzip.decompress((W/'twrp/ramdisk.bin').read_bytes()))
new=[]
for name,fields,data in rows:
    if name=='init':
        new.extend([('init.twrp',fields,data),('init',[0,0o100750,0,0,1,1793807029,0,0,0,0,0,0,0],shim)])
    elif name=='init.recovery.service.rc':
        assert data.count(b'service recovery /system/bin/recovery\n')==1
        new.append((name,fields,data.replace(b'service recovery /system/bin/recovery\n',b'service recovery /system/bin/recovery\n    disabled\n')))
    else:new.append((name,fields,data))
new.append(('erofs.ko',[0,0o100644,0,0,1,1793807029,0,0,0,0,0,0,0],module))
rd=gzip.compress(cpio_write(new),compresslevel=9,mtime=0)
struct.pack_into('<I',header,8,len(kernel))
struct.pack_into('<I',header,16,len(rd))
struct.pack_into('<I',header,1648,len(dtb))
new_offset=align(align(page+len(kernel))+len(rd))
struct.pack_into('<Q',header,1636,new_offset)
h=hashlib.sha1()
for part in (kernel,rd,b'',dtbo,dtb):h.update(part);h.update(struct.pack('<I',len(part)))
header[576:608]=h.digest()+bytes(12)
image=bytearray(header)
for part in (kernel,rd,dtbo,dtb):image+=part;image+=bytes(-len(image)%page)
assert len(image)<104857600
image+=bytes(104857600-len(image))
assert image[new_offset:new_offset+len(dtbo)]==dtbo
offset=align(page+len(kernel))
check={n:c for n,_,c in cpio_read(gzip.decompress(image[offset:offset+len(rd)]))}
assert b'service recovery /system/bin/recovery\n    disabled\n' in check['init.recovery.service.rc']
assert check['init']==shim and check['erofs.ko']==module
(out/'recovery_a.img').write_bytes(image)
manifest=dict(state='BUILT_HARDWARE_PENDING',serial='DEVICE_SERIAL',target='recovery_a',bytes=len(image),
              sha256=hashlib.sha256(image).hexdigest(),kernel_sha256=hashlib.sha256(kernel).hexdigest(),
              dtb_sha256=hashlib.sha256(dtb).hexdigest(),dtbo_sha256=hashlib.sha256(dtbo).hexdigest(),
              recovery_ui_disabled=True,ksu_module_loaded=False,automatic_data_mount=False,userdata_format=False)
(out/'manifest.json').write_text(json.dumps(manifest,indent=2)+'\n')
print(json.dumps(manifest,indent=2))
