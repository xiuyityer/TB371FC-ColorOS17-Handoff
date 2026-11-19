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
p=Path("c17-port/trees/system/system/framework/telephony-common.jar")
with zipfile.ZipFile(p) as z:
    for n in z.namelist():
        if not (n.startswith('classes') and n.endswith('.dex')): continue
        d=DEX(z.read(n))
        for c in d.get_classes():
            if c.get_name()!='Lcom/android/internal/telephony/uicc/UiccController;': continue
            for m in c.get_methods():
                if m.get_name()!='updateCarrierServices': continue
                print(n,c.get_name(),m.get_name(),m.get_descriptor(),hex(m.get_code_off()))
                offset=m.get_code_off()+16
                for i in m.get_instructions():
                    print(hex(offset),i.get_name(),i.get_output(),i.get_raw().hex())
                    offset += i.get_length()
