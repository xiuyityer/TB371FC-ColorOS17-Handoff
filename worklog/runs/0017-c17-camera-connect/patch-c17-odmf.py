from pathlib import Path
import hashlib
import struct
import zipfile
import zlib

run = Path(__file__).resolve().parent
source = run / "c17-odmf.jar"
output = run / "c17-odmf-surface.jar"
assert hashlib.sha256(source.read_bytes()).hexdigest() == "e2764db867e1038122d129015921bcb332de28a8dd5f8971f2cf26102dabf0c5"
with zipfile.ZipFile(source) as jar:
    dex = bytearray(jar.read("classes.dex"))
    assert dex[0x644c4:0x644cc] == bytes.fromhex("54ac0208390c0900")
    assert dex[0x644da:0x644de] == bytes.fromhex("54ac0708")
    dex[0x644c6:0x644c8] = dex[0x644dc:0x644de]
    dex[12:32] = hashlib.sha1(dex[32:]).digest()
    struct.pack_into("<I", dex, 8, zlib.adler32(dex[12:]))
    with zipfile.ZipFile(output, "w") as out:
        for item in jar.infolist():
            out.writestr(item, bytes(dex) if item.filename=="classes.dex" else jar.read(item))
with zipfile.ZipFile(output) as out:
    assert out.testzip() is None
print(hashlib.sha256(output.read_bytes()).hexdigest())
