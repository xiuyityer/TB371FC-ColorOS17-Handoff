#!/usr/bin/env python3
"""Guarded, resumable TB371FC C17 candidate flash: super and boot_a only."""
import argparse
import datetime
import hashlib
import json
from pathlib import Path
import re
import subprocess
import time
import pilot_prepare as p

W=p.ROOT/'c17-port'
FB=['/Users/REDACTED/Developer/unixnu-macos/tools/platform-tools/fastboot','-s',p.SERIAL]


def sha(path):
    h=hashlib.sha256()
    with path.open('rb') as f:
        while chunk:=f.read(8<<20):h.update(chunk)
    return h.hexdigest()


def main(resume, run_dir=None, recovery=None):
    run=run_dir.resolve() if run_dir else W/'rom-r1/hardware-run'
    run.mkdir(parents=True,exist_ok=True)
    p.LOG=run/'commands.jsonl'
    report=json.loads((W/'rom-r1/super.json').read_text())
    partsdir=W/'rom-r1/super-parts-32m'
    manifestfile=partsdir/'manifest.json'
    manifest=json.loads(manifestfile.read_text())
    backup=json.loads((W/'pre-c17-backup/manifest.json').read_text())
    assert backup['state']=='FRAMEWORK_STOPPED_FILE_BACKUP_READBACK_PASS' and backup['serial']==p.SERIAL
    assert manifest['source_sha256']==report['sha256'] and manifest['all_decoded_spans_verified']
    boot=W/'rom-r1/boot/boot_a.img'
    bootmanifest=json.loads((boot.parent/'manifest.json').read_text())
    assert sha(boot)==bootmanifest['sha256'] and boot.stat().st_size==100663296
    assert 'my_bigball_a' in (W/'evidence/c17-android-lpdump.txt').read_text()
    cursor=0
    for row in manifest['parts']:
        path=partsdir/row['file']
        assert row['start']==cursor and path.stat().st_size==row['size'] and row['size']<=33554432
        assert sha(path)==row['sha256'],path
        cursor+=row['raw_bytes']
    assert cursor==12884901888
    checkpoint=run/'checkpoint.json'
    identity=dict(serial=p.SERIAL,super_sha256=report['sha256'],parts_manifest_sha256=sha(manifestfile),boot_sha256=sha(boot))
    if recovery:
        recovery=recovery.resolve()
        assert recovery.stat().st_size==72351744
        assert sha(recovery)=='6ce174af2b2bf6ebcec026d94fa95a12037e78ae1c27d3abfe40fbe0008fe7e7'
        identity['recovery_sha256']=sha(recovery)
    if resume:
        state=json.loads(checkpoint.read_text())
        assert all(state[k]==v for k,v in identity.items())
        next_index=state['next_index']
    else:
        assert not checkpoint.exists(), 'Use --resume only for this exact interrupted flash'
        before=p.root('id; getprop ro.product.board; getprop ro.board.platform; getprop ro.boot.slot_suffix; cat /proc/sys/kernel/random/boot_id')
        assert 'uid=0(root)' in before and 'spinel' in before and 'kona' in before and '_a' in before
        (run/'device-before.txt').write_text(before)
        p.run(p.ADB+['reboot','bootloader'])
        next_index=0
        state={**identity,'next_index':0,'state':'AWAITING_BOOTLOADER'}
        checkpoint.write_text(json.dumps(state,indent=2)+'\n')
    for attempt in range(30):
        result=subprocess.run(FB+['devices'],capture_output=True,text=True,timeout=10)
        if p.SERIAL in result.stdout:break
        time.sleep(1)
    else:raise RuntimeError('Device did not enter fastboot')
    def fb(*args):return p.run(FB+list(args),timeout=180)
    def getvar(name):
        text=fb('getvar',name)
        match=re.search(re.escape(name)+r':\s*(\S+)',text)
        assert match,text
        return match.group(1)
    assert getvar('product')=='spinel'
    assert getvar('current-slot')=='a'
    assert getvar('unlocked')=='yes'
    assert int(getvar('partition-size:super'),16)==12884901888
    assert int(getvar('partition-size:boot_a'),16)==100663296
    maxdownload=int(getvar('max-download-size'),16)
    assert all(row['size']<=maxdownload for row in manifest['parts'])
    if recovery and not state.get('original_twrp_installed'):
        assert int(getvar('partition-size:recovery_a'),16)==104857600
        fb('flash','recovery_a',str(recovery))
        state['original_twrp_installed']=True
        checkpoint.write_text(json.dumps(state,indent=2)+'\n')
    for index in range(next_index,len(manifest['parts'])):
        row=manifest['parts'][index]
        fb('flash','super',str(partsdir/row['file']))
        state.update(state='SUPER_FLASH_IN_PROGRESS',next_index=index+1,time=datetime.datetime.now(datetime.timezone.utc).isoformat())
        checkpoint.write_text(json.dumps(state,indent=2)+'\n')
        if index%20==0 or index+1==len(manifest['parts']):print(f'SUPER {index+1}/{len(manifest["parts"])}',flush=True)
    fb('flash','boot_a',str(boot))
    state.update(state='SUPER_AND_BOOT_FASTBOOT_WRITES_ACKNOWLEDGED_RUNTIME_PENDING')
    checkpoint.write_text(json.dumps(state,indent=2)+'\n')
    fb('reboot')
    print(json.dumps(state,indent=2),flush=True)


if __name__=='__main__':
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--resume',action='store_true')
    ap.add_argument('--run-dir',type=Path)
    ap.add_argument('--recovery',type=Path)
    args=ap.parse_args()
    main(args.resume,args.run_dir,args.recovery)
