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

run=Path(__file__).resolve().parent
old,new=[DEX(zipfile.ZipFile(run / f"c{ver}-odmf.jar").read("classes.dex")) for ver in (16,17)]
offset=379156

def methods(dex):
    for c in dex.get_classes():
        for m in c.get_methods():
            if m.get_code():
                yield m

def show(m):
    print(m.get_class_name(),m.get_name(),m.get_descriptor(),hex(m.get_code_off()))
    pos=m.get_code_off()+16
    for i in m.get_instructions():
        if abs(pos-offset) < 80 or m.get_code_off() != match.get_code_off():
            print(hex(pos),i.get_name(),i.get_output(),i.get_raw().hex())
        pos+=i.get_length()

match=next(m for m in methods(old) if m.get_code_off()+16<=offset<m.get_code_off()+16+m.get_code().get_insns_size()*2)
show(match)
print("candidate by exact method signature")
for m in methods(new):
    if m.get_class_name()==match.get_class_name() and m.get_name()==match.get_name() and m.get_descriptor()==match.get_descriptor():
        show(m)
