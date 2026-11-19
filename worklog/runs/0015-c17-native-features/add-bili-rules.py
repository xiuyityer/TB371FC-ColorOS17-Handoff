#!/usr/bin/env python3
"""Merge Bilibili rules into the C17 XML, preserving donor-specific entries."""
import ctypes
from hashlib import sha256
import html
import json
from pathlib import Path
import re
import subprocess
import xml.etree.ElementTree as ET

run = Path(__file__).resolve().parent
workspace = run.parents[2]
source = run / "my-product-a-pen.img"
output = run / "my-product-a-native.img"
dump = workspace / "tool-src/erofs-utils-1.8.10/dump/dump.erofs"
codec = ctypes.CDLL(str(run.parent / "0010-c17-ringbuf-kernel/liblz4-build.dylib"))
codec.LZ4_compress_HC.argtypes = [ctypes.c_void_p, ctypes.c_void_p] + [ctypes.c_int] * 3
codec.LZ4_decompress_safe_partial.argtypes = codec.LZ4_compress_HC.argtypes
rules = json.loads((workspace.parent / "sources/rom/patches/native-window-rules.json").read_text())
package = "tv.danmaku.bili"
entries = [
    ("sys_fantasy_window_managed", 0, 914756, 2_275_090_432, 65536),
    ("sys_full_orientation_managed", 0, 112498, 2_275_188_736, 16384),
]


def parse_config(node):
    return json.loads(node.attrib["custom_config_body"].replace("^", '"'))


def decode(padded, size):
    stream = padded.lstrip(b"\0")
    buffer = ctypes.create_string_buffer(size)
    assert codec.LZ4_decompress_safe_partial(stream, buffer, len(stream), size, size) == size
    return buffer.raw


def update_xml(original, rule_name, start, end):
    root = ET.fromstring(original)
    nodes = [node for node in root if node.get("package_name") == package]
    assert len(nodes) == 1
    settings = parse_config(nodes[0])
    c16 = rules[rule_name]["apps"][package]
    if rule_name == "sys_fantasy_window_managed":
        settings["UX"]["isDraggable"] = c16["UX"]["isDraggable"]
        settings["UX"]["windowsRatio"] = c16["UX"]["windowsRatio"]
        for item in c16["Activities"]:
            if item["name"] == "*":
                continue
            activities = settings["Activities"]
            current = next((row for row in activities if row["name"] == item["name"]), None)
            if current is None:
                activities.append(item.copy())
            else:
                current.update(item)
    else:
        current = settings.setdefault("force_relaunch_activity", [])
        current.extend(name for name in c16["force_relaunch_activity"] if name not in current)
    encoded = html.escape(json.dumps(settings, separators=(",", ":"), ensure_ascii=False)
                          .replace('"', "^"), quote=True).encode()
    data = original[start:end]
    tag_pattern = rb'(<[A-Za-z]+\b[^>]*\bpackage_name="tv\.danmaku\.bili"[^>]*\bcustom_config_body=")([^"]*)(")'
    matches = list(re.finditer(tag_pattern, data))
    assert len(matches) == 1
    match = matches[0]
    version = int(root.findtext("version"))
    data = data[:match.start(2)] + encoded + data[match.end(2):]
    data, count = re.subn(rb"(<version>)\d+(</version>)",
                          lambda m: m[1] + str(version + 1).encode() + m[2], data)
    assert count == 1
    remaining = len(data) - (end - start)

    def reclaim(match):
        nonlocal remaining
        ws = match[0]
        trim = min(remaining, len(ws))
        remaining -= trim
        return ws[:len(ws) - trim]

    assert remaining >= 0
    # Drop indentation only between adjacent XML tags inside the touched extent.
    data = re.sub(rb"(?<=>\r\n) +(?=<)", reclaim, data)
    assert remaining == 0 and len(data) == end - start
    updated = original[:start] + data + original[end:]
    verify = ET.fromstring(updated)
    node = next(node for node in verify if node.get("package_name") == package)
    assert parse_config(node) == settings
    assert verify.findtext("version") == str(version + 1)
    node.attrib["custom_config_body"] = nodes[0].attrib["custom_config_body"]
    verify.find("version").text = str(version)
    ET.indent(root)
    ET.indent(verify)
    assert ET.tostring(root) == ET.tostring(verify)
    return updated


expected = {}
assert not output.exists()
subprocess.run(["cp", "-c", source, output], check=True)
with output.open("r+b") as image:
    for name, start, end, offset, capacity in entries:
        option = f"--path=/etc/fantasy/{name}.xml"
        original = subprocess.check_output([dump, "--cat", option, source])
        updated = update_xml(original, name, start, end)
        image.seek(offset)
        current = image.read(capacity)
        assert decode(current, end - start) == original[start:end]
        buffer = ctypes.create_string_buffer(capacity)
        patched = updated[start:end]
        length = codec.LZ4_compress_HC(patched, buffer, len(patched), capacity, 12)
        assert length > 0, (name, capacity)
        packed = buffer.raw[:length].rjust(capacity, b"\0")
        assert decode(packed, end - start) == patched
        image.seek(offset)
        image.write(packed)
        expected[option] = updated
for option, content in expected.items():
    assert subprocess.check_output([dump, "--cat", option, output]) == content
    (run / option.split("/")[-1]).write_bytes(content)
assert source.stat().st_size == output.stat().st_size == 2570592256
print({name: sha256(data).hexdigest() for name, data in expected.items()})
