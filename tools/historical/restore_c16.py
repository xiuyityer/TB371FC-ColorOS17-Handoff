#!/usr/bin/env python3
"""Restore original C16 super and the hardware-booted KSU pilot boot only."""
import datetime
import hashlib
import json
from pathlib import Path
import re
import pilot_prepare as p
from flash_c17 import sha

W=p.ROOT/'c17-port'
base=p.ROOT/'ColorOS16_TB371FC_v27_r108_KB50_20261112_R5_CANDIDATE'
partsdir=base/'super-parts-32m'
manifest=json.loads((partsdir/'manifest.json').read_text())
assert manifest['source_sha256']=='03722511a623cc88babe057e984ae0671d7f3adf00d46d6ddc7749a3534fe09e'
assert manifest['expanded_size']==12884901888
boot=W/'kernel-pilot-r1/boot_a.img'
assert sha(boot)=='b54374c33fbff96c3fd94ca9cde0416c0d9d0389a02b61ee1576f51a8797914d'
out=W/'restore-c16-r1'
out.mkdir(exist_ok=True)
p.LOG=out/'commands.jsonl'
cursor=0
for row in manifest['parts']:
    f=partsdir/row['file']
    assert row['start']==cursor and f.stat().st_size==row['size'] and sha(f)==row['sha256']
    cursor+=row['raw_bytes']
assert cursor==12884901888
fb=['/Users/REDACTED/Developer/unixnu-macos/tools/platform-tools/fastboot','-s',p.SERIAL]
def call(*args):return p.run(fb+list(args),timeout=180)
for key,value in [('product','spinel'),('current-slot','a'),('unlocked','yes')]:
    response=call('getvar',key)
    assert re.search(re.escape(key)+r':\s*'+value+r'\b',response),response
assert '0x300000000' in call('getvar','partition-size:super')
state=dict(serial=p.SERIAL,super_sha256=manifest['source_sha256'],boot_sha256=sha(boot),next_index=0,
           userdata_erased=False,other_partition_writes=False,state='C16_RESTORE_IN_PROGRESS')
progress=out/'checkpoint.json'
if progress.exists():
    old=json.loads(progress.read_text())
    assert old['serial']==state['serial'] and old['super_sha256']==state['super_sha256']
    state['next_index']=old['next_index']
for index in range(state['next_index'],len(manifest['parts'])):
    row=manifest['parts'][index]
    call('flash','super',str(partsdir/row['file']))
    state.update(next_index=index+1,time=datetime.datetime.now(datetime.timezone.utc).isoformat())
    progress.write_text(json.dumps(state,indent=2)+'\n')
    if index%40==0 or index==len(manifest['parts'])-1:print(f'C16 SUPER {index+1}/{len(manifest["parts"])}',flush=True)
call('flash','boot_a',str(boot))
state['state']='C16_SUPER_AND_KSU_BOOT_RESTORED_RUNTIME_PENDING'
progress.write_text(json.dumps(state,indent=2)+'\n')
call('reboot')
print(json.dumps(state,indent=2),flush=True)
