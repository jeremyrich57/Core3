"""Read and write SWG TRE archives (version 0005).

Layout (all integers little-endian uint32), matching MMOCoreORB/src/tre3:

    header (36 bytes)
        magic            b"EERT"   ('TREE' as a multi-char literal)
        version          b"5000"   ('0005')
        record_count
        toc_offset       offset of the record table (end of file data)
        toc_compression  0 = raw, 2 = zlib
        toc_size         size of the record table as stored
        names_compression
        names_size       size of the name block as stored
        names_uncompressed_size
    file data            each file's bytes, raw or zlib-compressed
    record table         record_count x 24 bytes:
                         crc, size, offset, compression, stored_size, name_offset
    name block           NUL-terminated lowercase paths
    md5 table            record_count x 16 bytes (md5 of each file's bytes as stored)

The client looks records up by the CRC of their path, so the table is sorted by CRC.
"""

from __future__ import annotations

import hashlib
import struct
import zlib
from dataclasses import dataclass

MAGIC = b"EERT"
VERSION = b"5000"
HEADER = struct.Struct("<4s4s7I")
RECORD = struct.Struct("<6I")

COMPRESSION_NONE = 0
COMPRESSION_ZLIB = 2


def _make_crc_table() -> list[int]:
    table = []
    for i in range(256):
        c = i << 24
        for _ in range(8):
            c = ((c << 1) ^ 0x04C11DB7) if c & 0x80000000 else (c << 1)
        table.append(c & 0xFFFFFFFF)
    return table


_CRC_TABLE = _make_crc_table()


def crc(name: str) -> int:
    """SOE's string CRC (CRC-32/MPEG-2 polynomial, init and final xor 0xFFFFFFFF)."""
    c = 0xFFFFFFFF
    for b in name.encode("ascii"):
        c = _CRC_TABLE[((c >> 24) ^ b) & 0xFF] ^ ((c << 8) & 0xFFFFFFFF)
    return c ^ 0xFFFFFFFF


@dataclass
class Record:
    name: str
    crc: int
    size: int
    offset: int
    compression: int
    stored_size: int
    md5: bytes


def _unpack_block(data: bytes, compression: int, size: int) -> bytes:
    if compression == COMPRESSION_ZLIB:
        out = zlib.decompress(data)
        if len(out) != size:
            raise ValueError(f"block decompressed to {len(out)} bytes, expected {size}")
        return out
    return data[:size]


def read(path: str) -> tuple[list[Record], bytes]:
    """Return the records of a TRE file and the raw file bytes (for read_file)."""
    with open(path, "rb") as f:
        raw = f.read()

    magic, version, count, toc_offset, toc_comp, toc_size, names_comp, names_size, names_usize = \
        HEADER.unpack_from(raw, 0)
    if magic != MAGIC:
        raise ValueError(f"{path}: not a TRE file")
    if version != VERSION:
        raise ValueError(f"{path}: unsupported TRE version {version!r}")

    pos = toc_offset
    toc = _unpack_block(raw[pos:pos + toc_size], toc_comp, count * RECORD.size)
    pos += toc_size
    names = _unpack_block(raw[pos:pos + names_size], names_comp, names_usize)
    pos += names_size
    md5s = raw[pos:pos + 16 * count]

    records = []
    for i in range(count):
        rcrc, size, offset, comp, stored, name_off = RECORD.unpack_from(toc, i * RECORD.size)
        name = names[name_off:names.index(b"\0", name_off)].decode("ascii")
        records.append(Record(name, rcrc, size, offset, comp, stored, md5s[i * 16:(i + 1) * 16]))
    return records, raw


def read_file(raw: bytes, record: Record) -> bytes:
    data = raw[record.offset:record.offset + record.stored_size]
    return _unpack_block(data, record.compression, record.size)


def write(path: str, files: dict[str, bytes]) -> None:
    """Write a TRE file. `files` maps archive paths (e.g. "datatables/x.iff") to contents.

    Output is deterministic for the same input, so unchanged patches keep the same hash.
    """
    entries = []
    for name in files:
        norm = name.replace("\\", "/").strip("/").lower()
        if "/" not in norm:
            raise ValueError(f"{name}: files must be inside a directory (SWG rejects root-level files)")
        entries.append((norm, files[name]))
    entries.sort(key=lambda e: crc(e[0]))

    names = set()
    for norm, _ in entries:
        if norm in names:
            raise ValueError(f"duplicate path {norm}")
        names.add(norm)

    body = bytearray()
    toc = bytearray()
    name_block = bytearray()
    md5s = bytearray()
    offset = HEADER.size

    for norm, data in entries:
        packed = zlib.compress(data, 9)
        if len(packed) < len(data):
            comp, stored = COMPRESSION_ZLIB, packed
        else:
            comp, stored = COMPRESSION_NONE, data
        toc += RECORD.pack(crc(norm), len(data), offset, comp, len(stored), len(name_block))
        name_block += norm.encode("ascii") + b"\0"
        md5s += hashlib.md5(stored).digest()
        body += stored
        offset += len(stored)

    toc_packed = zlib.compress(bytes(toc), 9)
    names_packed = zlib.compress(bytes(name_block), 9)
    header = HEADER.pack(MAGIC, VERSION, len(entries), offset,
                         COMPRESSION_ZLIB, len(toc_packed),
                         COMPRESSION_ZLIB, len(names_packed), len(name_block))

    with open(path, "wb") as f:
        f.write(header)
        f.write(body)
        f.write(toc_packed)
        f.write(names_packed)
        f.write(md5s)
