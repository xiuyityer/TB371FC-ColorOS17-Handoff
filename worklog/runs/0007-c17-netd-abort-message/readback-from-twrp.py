import hashlib
import subprocess
from pathlib import Path

run = Path(__file__).resolve().parent
adb = [str(run.parents[2] / 'host-tools/platform-tools/adb'), '-s', 'DEVICE_SERIAL']

def device(*args, timeout=15):
    return subprocess.check_output(adb + list(args), timeout=timeout)

assert device('get-state').strip() == b'recovery'
assert device('shell', 'id -u').strip() == b'0'
assert device('shell', 'getprop ro.twrp.version').strip().startswith(b'3.7.1')
assert device('shell', 'getprop ro.product.device').strip() == b'TB371FC'
before = dict((path, sha) for sha, path in
              (tuple(line.split()) for line in (run / 'tombstones-before.sha256').read_text().splitlines()))
after = device('shell', 'sha256sum /data/tombstones/tombstone_[0-9][0-9]').decode()
(run / 'tombstones-after.sha256').write_text(after)
for row in after.splitlines():
    digest, path = row.split()
    if before.get(path) == digest:
        continue
    data = device('exec-out', f'cat {path} 2>/dev/null')
    assert hashlib.sha256(data).hexdigest() == digest
    (run / Path(path).name).write_bytes(data)
    for line in data.decode(errors='replace').splitlines():
        if line.startswith(('Timestamp:', 'Cmdline:', 'Abort message:')) or '/data/local/tmp/n.so (' in line:
            print(f'{Path(path).name} {line}')
window = device('exec-out', 'dd if=/dev/block/by-name/boot_a bs=4096 skip=20480 count=1024 2>/dev/null')
assert len(window) == 4 << 20
(run / 'bootlog-window.bin').write_bytes(window)
