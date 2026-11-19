#!/usr/bin/env python3
"""Replace one compressed EROFS file with appended uncompressed data.

The inode number, metadata and directory entries are preserved. The source
image is never modified. Only the target inode, superblock block count/CRC,
and newly appended data differ in the output image.
"""
import argparse
import hashlib
import json
from pathlib import Path
import struct

CRC32C_POLY_LE = 0x82F63B78
EROFS_SUPER_OFFSET = 1024
EROFS_SUPER_MAGIC_V1 = 0xE0F5E1E2
EROFS_FEATURE_COMPAT_SB_CHKSUM = 1


def sha256(path):
    digest = hashlib.sha256()
    with path.open('rb') as stream:
        for block in iter(lambda: stream.read(8 << 20), b''):
            digest.update(block)
    return digest.hexdigest()


def crc32c(data):
    crc = 0xFFFFFFFF
    for byte in data:
        crc ^= byte
        for _ in range(8):
            crc = (crc >> 1) ^ (CRC32C_POLY_LE if crc & 1 else 0)
    return crc


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--source', type=Path, required=True)
    ap.add_argument('--output', type=Path, required=True)
    ap.add_argument('--payload', type=Path, required=True)
    ap.add_argument('--nid', type=int, required=True)
    ap.add_argument('--source-sha256', required=True)
    ap.add_argument('--payload-sha256', required=True)
    ap.add_argument('--record', type=Path, required=True)
    args = ap.parse_args()

    if args.output.exists() or args.record.exists():
        raise FileExistsError('Refusing to overwrite an attributed candidate')
    actual_source_sha = sha256(args.source)
    if actual_source_sha != args.source_sha256:
        raise ValueError(f'Source SHA-256 mismatch: {actual_source_sha}')
    actual_payload_sha = sha256(args.payload)
    if actual_payload_sha != args.payload_sha256:
        raise ValueError(f'Payload SHA-256 mismatch: {actual_payload_sha}')

    source_size = args.source.stat().st_size
    payload_size = args.payload.stat().st_size
    if source_size % 4096:
        raise ValueError('Source image is not block aligned')

    with args.source.open('rb') as stream:
        image = bytearray(stream.read())
    if len(image) != source_size:
        raise RuntimeError('Short source read')

    sb = bytearray(image[EROFS_SUPER_OFFSET:4096])
    magic, old_checksum, feature_compat = struct.unpack_from('<III', sb, 0)
    blkszbits = sb[12]
    old_blocks = struct.unpack_from('<I', sb, 36)[0]
    if magic != EROFS_SUPER_MAGIC_V1 or blkszbits != 12:
        raise ValueError('Unexpected EROFS superblock')
    if not feature_compat & EROFS_FEATURE_COMPAT_SB_CHKSUM:
        raise ValueError('Expected superblock checksum feature')
    if old_blocks * 4096 != source_size:
        raise ValueError('Source size does not match superblock blocks')
    checksum_input = bytearray(sb)
    struct.pack_into('<I', checksum_input, 4, 0)
    actual_checksum = crc32c(checksum_input)
    if actual_checksum != old_checksum:
        raise ValueError(f'Source superblock CRC32C verification failed: computed {actual_checksum:08x}, stored {old_checksum:08x}')

    inode_offset = args.nid * 32
    inode = bytearray(image[inode_offset:inode_offset + 32])
    old_format, xattr_count, mode, nlink, inode_size = struct.unpack_from('<HHHHI', inode, 0)
    if old_format != 6:
        raise ValueError(f'Expected compact compressed inode (format 6), got {old_format}')
    if mode & 0o170000 != 0o100000 or nlink != 1 or inode_size != payload_size:
        raise ValueError('Target inode does not match the payload')
    if xattr_count != 11:
        raise ValueError('Unexpected xattr layout; refusing to change inode metadata')
    old_compressed_blocks = struct.unpack_from('<I', inode, 16)[0]

    data_blocks = (payload_size + 4095) // 4096
    new_blocks = old_blocks + data_blocks
    struct.pack_into('<H', inode, 0, old_format & 1)  # flat plain, compact inode
    struct.pack_into('<I', inode, 16, old_blocks)
    struct.pack_into('<I', inode, 8, payload_size)

    struct.pack_into('<I', sb, 36, new_blocks)
    struct.pack_into('<I', sb, 4, 0)
    new_checksum = crc32c(sb)
    struct.pack_into('<I', sb, 4, new_checksum)

    image[EROFS_SUPER_OFFSET:4096] = sb
    image[inode_offset:inode_offset + 32] = inode
    with args.output.open('xb') as stream:
        stream.write(image)
        stream.write(args.payload.read_bytes())
        stream.write(b'\0' * (data_blocks * 4096 - payload_size))

    record = {
        'state': 'BUILT_REQUIRES_FILESYSTEM_AND_METADATA_READBACK_AND_HARDWARE_TEST',
        'method': 'preserve inode and xattrs; append uncompressed payload; flat-plain data layout',
        'source': str(args.source),
        'source_sha256': actual_source_sha,
        'output': str(args.output),
        'output_sha256': sha256(args.output),
        'output_bytes': args.output.stat().st_size,
        'payload': str(args.payload),
        'payload_sha256': actual_payload_sha,
        'nid': args.nid,
        'inode_offset': inode_offset,
        'old_inode_format': old_format,
        'new_inode_format': old_format & 1,
        'old_compressed_blocks': old_compressed_blocks,
        'appended_data_block': old_blocks,
        'appended_data_blocks': data_blocks,
        'old_superblock_blocks': old_blocks,
        'new_superblock_blocks': new_blocks,
        'old_superblock_crc32c': f'{old_checksum:08x}',
        'new_superblock_crc32c': f'{new_checksum:08x}',
        'unchanged_inode_bytes_except_format_and_data_pointer': True,
        'hardware_tested': False,
    }
    args.record.write_text(json.dumps(record, indent=2) + '\n')
    print(json.dumps(record, indent=2))


if __name__ == '__main__':
    main()
