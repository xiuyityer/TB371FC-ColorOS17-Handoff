from pathlib import Path
import sys
import types
import zipfile
apk = types.ModuleType('androguard.core.apk')
apk.APK = type('APK', (), {})
sys.modules['androguard.core.apk'] = apk
from loguru import logger
logger.remove()
from androguard.core.dex import DEX

p=Path("c17-port/casefs/my_product/app/OplusCamera/OplusCamera.apk")
with zipfile.ZipFile(p) as apk:
    for n in apk.namelist():
        if not (n.startswith('classes') and n.endswith('.dex')): continue
        raw=apk.read(n)
        if b'FeatureManager.java' not in raw: continue
        dex=DEX(raw)
        for c in dex.get_classes():
            if c.get_name() != 'Ljb/c1;': continue
            for m in c.get_methods():
                if m.get_name() not in ('f','<init>','<clinit>') or not m.get_code(): continue
                print(n,c.get_name(),m.get_name(),m.get_descriptor())
                for insn in m.get_instructions():
                    print(insn.get_name(),insn.get_output())
