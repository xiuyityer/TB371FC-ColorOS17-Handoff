#!/usr/bin/env python3
"""Read C17 failure evidence using the original TB371FC TWRP, without su.

Never flashes, formats or mounts userdata. A metadata mount, if needed, is ro.
The optional 2 MiB /dev/mem read targets the exact #789 DTB ramoops reservation.
"""
import argparse
import hashlib
import json
from pathlib import Path
import shlex
import pilot_prepare as p


def main(run):
    run=run.resolve()
    run.mkdir(parents=True,exist_ok=True)
    p.LOG=run/'twrp-commands.jsonl'
    identity=p.run(p.ADB+['shell','id; uname -a; cat /proc/sys/kernel/random/boot_id; getprop ro.product.device; getprop ro.twrp.version; getprop ro.boot.slot_suffix; getenforce'])
    (run/'twrp-identity.txt').write_text(identity)
    assert 'uid=0(root)' in identity and 'TB371FC' in identity,identity
    assert '4.19.157-perf+ #1' in identity,'Use the original tested TWRP, not a rebuilt recovery'
    recovery_hash=p.run(p.ADB+['shell','dd if=/dev/block/by-name/recovery_a bs=1048576 count=69 2>/dev/null | sha256sum']).split()[0]
    assert recovery_hash=='6ce174af2b2bf6ebcec026d94fa95a12037e78ae1c27d3abfe40fbe0008fe7e7'
    local=run/'twrp-readback'
    assert not local.exists(),'Preserve previous readbacks; use a new run directory'
    remote='/tmp/c17-readback-'+run.name
    assert all(c.isalnum() or c in '-_.' for c in run.name)
    script=r'''set -e
base=REMOTE
mkdir -p "$base"
dmesg > "$base/twrp-dmesg.txt"
getprop > "$base/twrp-properties.txt"
cat /proc/mounts > "$base/mounts-before.txt"
cat /proc/iomem > "$base/iomem.txt"
for source in /proc/last_kmsg /sys/kernel/debug/last_kmsg /tmp/recovery.log /cache/recovery/last_log /data/debugging/last_kmsg.txt; do
    if test -f "$source"; then
        target=$(echo "$source" | tr / _)
        cat "$source" > "$base/$target" 2>"$base/$target.stderr" || true
    fi
done
if test -d /sys/fs/pstore; then cp -a /sys/fs/pstore "$base/"; else echo NO_PSTORE_VFS > "$base/pstore-interface.txt"; fi
if ! test -c /dev/mem; then mknod /dev/mem c 1 1 2>"$base/devmem-node.stderr" || true; fi
if test -c /dev/mem; then
    # Physical 0x27e000000, length 0x200000; READ ONLY, no write operand.
    if dd if=/dev/mem of="$base/ramoops-reserved.bin" bs=4096 skip=2613248 count=512 2>"$base/devmem-read.stderr"; then
        echo READ_COMMAND_SUCCESS > "$base/devmem-state.txt"
    else echo READ_COMMAND_FAILED > "$base/devmem-state.txt"; fi
else echo NO_DEVMEM_INTERFACE > "$base/devmem-state.txt"; fi
mounted_here=0
if ! awk '$2=="/metadata" {found=1} END {exit !found}' /proc/mounts; then
    mkdir -p /metadata
    if mount -t ext4 -o ro,noload /dev/block/by-name/metadata /metadata 2>"$base/metadata-mount.stderr"; then mounted_here=1; fi
fi
if test -d /metadata/c17-port-early; then cp -a /metadata/c17-port-early "$base/"; fi
if test "$mounted_here" = 1; then umount /metadata; fi
for source in /data/local/tmp/c17-port /data/tombstones /data/system/dropbox; do
    if test -d "$source"; then
        target=$(echo "$source" | tr / _)
        cp -a "$source" "$base/$target" 2>"$base/$target.stderr" || true
    fi
done
cat /proc/mounts > "$base/mounts-after.txt"
echo COLLECTION_FINISHED
'''.replace('REMOTE',shlex.quote(remote))
    p.run(p.ADB+['shell',script],timeout=180)
    p.run(p.ADB+['pull',remote,str(local)],timeout=180)
    files=[]
    for path in sorted(local.rglob('*')):
        if path.is_file():
            files.append(dict(path=str(path.relative_to(local)),bytes=path.stat().st_size,
                              sha256=hashlib.sha256(path.read_bytes()).hexdigest()))
    raw=local/'ramoops-reserved.bin'
    report=dict(state='TWRP_READBACK_COMPLETE_NOT_BOOT_SUCCESS',serial=p.SERIAL,identity=identity,original_twrp_image_sha256=recovery_hash,
                files=files,ramoops_exact_2m_read=raw.exists() and raw.stat().st_size==2097152,
                data_formatted=False,partitions_flashed=False,recovery_modified=False)
    (run/'readback-manifest.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps({k:v for k,v in report.items() if k not in ('files','identity')},indent=2))


if __name__=='__main__':
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--run-dir',type=Path,required=True)
    main(ap.parse_args().run_dir)
