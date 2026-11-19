#!/usr/bin/env python3
"""Archive framework-quiesced data with labels before the C17 upgrade.

File archive, not an atomic block snapshot. Init/native daemons remain running.
The duplicate /data/user/0 bind mount and regenerated caches are excluded.
"""
import datetime
import gzip
import hashlib
import json
from pathlib import Path
import shlex
import subprocess
import tarfile
import pilot_prepare as p

out=p.ROOT/'c17-port/pre-c17-backup'
out.mkdir(exist_ok=True)
p.LOG=out/'commands.jsonl'
before=p.root('id; getprop ro.product.board; getprop ro.board.platform; getprop ro.boot.slot_suffix; cat /proc/sys/kernel/random/boot_id; getprop sys.boot_completed')
assert 'uid=0(root)' in before and 'spinel' in before and 'kona' in before and '_a' in before
(out/'device-before.txt').write_text(before)
excludes=['./user/0','./dalvik-cache','./resource-cache','./local/tmp','./lost+found']
p.root('stop; sync')
command='tar --selinux -cf - '+ ' '.join('--exclude='+shlex.quote(x) for x in excludes)+' -C /data . 2>/data/local/tmp/c17-backup-tar-errors.txt'
archive=out/'data-r2.tar.gz'
with (out/'tar-stderr.txt').open('wb') as err, archive.open('xb') as dest:
    proc=subprocess.Popen(p.ADB+['exec-out','su -c '+shlex.quote(command)],stdout=subprocess.PIPE,stderr=err)
    with gzip.GzipFile(filename='',fileobj=dest,mode='wb',compresslevel=1,mtime=0) as compressed:
        while chunk:=proc.stdout.read(8<<20):
            compressed.write(chunk)
    rc=proc.wait(timeout=60)
assert rc==0, (out/'tar-stderr.txt').read_text()
p.run(p.ADB+['pull','/data/local/tmp/c17-backup-tar-errors.txt',str(out/'tar-device-stderr.txt')])
for name in ('metadata','recovery_a'):
    target=out/(name+'.img')
    if not target.exists():
        with target.open('xb') as f:
            proc=subprocess.run(p.ADB+['exec-out','su -c '+shlex.quote('cat /dev/block/by-name/'+name)],stdout=f,stderr=subprocess.PIPE,timeout=120)
        assert proc.returncode==0,proc.stderr
    expected=p.root('sha256sum /dev/block/by-name/'+name).split()[0]
    actual=hashlib.sha256(target.read_bytes()).hexdigest()
    assert actual==expected,(name,expected,actual)
assert (out/'metadata.img').stat().st_size==16777216
files=0
members=0
labels=0
roots=set()
with tarfile.open(archive,'r|gz') as tar:
    for entry in tar:
        members+=1
        roots.add(entry.name.lstrip('./').split('/')[0])
        if any('selinux' in k for k in entry.pax_headers):labels+=1
        if entry.isfile():
            source=tar.extractfile(entry)
            left=entry.size
            while chunk:=source.read(8<<20):left-=len(chunk)
            assert left==0
            files+=1
assert members>1000 and files>1000 and labels>1000
assert {'data','app','system','media','adb'}.issubset(roots),roots
h=hashlib.sha256()
with archive.open('rb') as f:
    while chunk:=f.read(8<<20):h.update(chunk)
report=dict(state='FRAMEWORK_STOPPED_FILE_BACKUP_READBACK_PASS',time=datetime.datetime.now(datetime.timezone.utc).isoformat(),
            serial=p.SERIAL,archive=str(archive),bytes=archive.stat().st_size,sha256=h.hexdigest(),
            members=members,regular_files=files,selinux_label_records=labels,excludes=excludes,
            block_consistent_snapshot=False,native_daemons_remained_running=True,data_erased=False,
            framework_still_stopped=True)
(out/'manifest.json').write_text(json.dumps(report,indent=2)+'\n')
print(json.dumps(report,indent=2))
