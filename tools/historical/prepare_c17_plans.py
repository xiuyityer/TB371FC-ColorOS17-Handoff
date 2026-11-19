#!/usr/bin/env python3
"""Describe C17 first-boot changes without copying C16 framework bytecode."""
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
WORK = ROOT / 'c17-port'


def main():
    plans = WORK / 'rom-r1/plans'
    plans.mkdir(parents=True, exist_ok=True)
    def file(source, mode=None, label=None):
        p = WORK / source
        assert p.is_file(), p
        change = dict(source=str(p), sha256=hashlib.sha256(p.read_bytes()).hexdigest())
        if mode:
            change['mode'] = mode
        if label:
            change['label'] = label
        return change
    contexts = (WORK / 'trees/system/system/etc/selinux/plat_file_contexts').read_text()
    contexts += '\n/system/bin/c17-netbpfload u:object_r:bpfloader_exec:s0\n'
    (WORK / 'overlays/plat_file_contexts').write_text(contexts)
    system = dict(files={
        '/system/etc/selinux/plat_sepolicy.cil': file('policy-inputs/plat_sepolicy.cil'),
        '/system/etc/selinux/plat_file_contexts': file('overlays/plat_file_contexts'),
        '/system/etc/selinux/mapping/30.0.cil': file('policy-inputs/30.0.cil', '0644', 'u:object_r:sepolicy_file:s0'),
        '/system/etc/init/netbpfload.rc': file('overlays/netbpfload.rc'),
        '/system/bin/c17-netbpfload': file('overlays/c17-netbpfload', '0755', 'u:object_r:bpfloader_exec:s0'),
        '/system/etc/vintf/compatibility_matrix.5.xml': file('base-c16/compatibility_matrix.5.xml', '0644', 'u:object_r:system_file:s0'),
    })
    manager = 'donor/KernelSU_v3.3.1-40_32720-release.apk'
    assert hashlib.sha256((WORK / manager).read_bytes()).hexdigest() == 'aa445d3da3d05f0e0dcc9ebc107706b9a694e7bfac8ce4c40877898797d3b095'
    ext = dict(files={
        '/etc/selinux/mapping/30.0.cil': file('policy-inputs/system_ext-30.0.cil', '0644', 'u:object_r:system_file:s0'),
        '/apex/com.android.vndk.v30.apex': file('base-c16/com.android.vndk.v30.apex', '0644', 'u:object_r:system_file:s0'),
        '/app/OTA/OTA.apk': file('base-c16/OTA-port-notice.apk'),
        '/etc/init/c17-port.rc': file('overlays/c17-port.rc', '0644', 'u:object_r:system_file:s0'),
        '/etc/c17-port/capture.sh': file('overlays/capture.sh', '0644', 'u:object_r:system_file:s0'),
        '/etc/c17-port/KernelSU-manager.apk': file(manager, '0644', 'u:object_r:system_file:s0'),
    }, dirs={'/etc/c17-port': dict(mode='0755', label='u:object_r:system_file:s0')},
       remove=['/app/OTA/oat'])
    records = {
        'system': system,
        'system_ext': ext,
        'my_manifest': dict(files={'/build.prop': file('overlays/my_manifest-build.prop')}),
        'my_product': dict(files={'/build.prop': file('overlays/my_product-build.prop')}),
    }
    for name, plan in records.items():
        (plans / (name + '.json')).write_text(json.dumps(plan, indent=2) + '\n')
    summary = dict(state='PLANS_ONLY_NO_C17_FLASH',
                   donor='OPD2413_17.0.0.103(CN01)', android_sdk=37,
                   manager_version='v3.3.1-40 / 32720 / UAPI6',
                   kernel='#789 plus EROFS module; hardware pilot in progress',
                   old_vendor_sdk=30, product_first_api_level=33,
                   framework_patches_from_C16_automatically_applied=False,
                   pending=['EROFS runtime mount/read validation', 'C17 boot fstab',
                            'vendor policy/init migration', 'dynamic partition layout',
                            'all image metadata readback', 'C17 first boot and hardware regression'],
                   data_erase=False)
    (WORK / 'rom-r1/plan-summary.json').write_text(json.dumps(summary, indent=2) + '\n')
    print(json.dumps(summary, indent=2))


if __name__ == '__main__':
    main()
