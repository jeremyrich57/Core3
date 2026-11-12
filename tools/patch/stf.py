"""Read and write SWG string table files (.stf), e.g. string/en/cmd_n.stf.

Layout (little-endian):

    uint32 magic 0x0000ABCD, uint8 version (1), uint32 next_id, uint32 count
    count x { uint32 id, uint32 crc (usually 0xFFFFFFFF), uint32 length, UTF-16LE text (length chars) }
    count x { uint32 id, uint32 length, ASCII key (length bytes) }

Keys are lowercase in the stock files and the client looks them up lowercase. The text and key sections are not
in the same order, and a few CRCs are not 0xFFFFFFFF, so both orders and every CRC are kept to round-trip exactly.
"""

from __future__ import annotations

import struct
from dataclasses import dataclass, field

MAGIC = 0xABCD


@dataclass
class StringTable:
    next_id: int
    entries: dict[str, tuple[int, str]] = field(default_factory=dict)  # key -> (id, text), in key-section order
    text_order: list[int] = field(default_factory=list)  # ids in text-section order
    crcs: dict[int, int] = field(default_factory=dict)  # id -> stored CRC (0xFFFFFFFF when absent)

    def set(self, key: str, text: str) -> None:
        key = key.lower()
        if key in self.entries:
            self.entries[key] = (self.entries[key][0], text)
        else:
            self.entries[key] = (self.next_id, text)
            self.text_order.append(self.next_id)
            self.next_id += 1

    def get(self, key: str) -> str | None:
        entry = self.entries.get(key.lower())
        return entry[1] if entry else None


def parse(data: bytes) -> StringTable:
    magic, version, next_id, count = struct.unpack_from("<IBII", data, 0)
    if magic != MAGIC or version != 1:
        raise ValueError(f"not a version 1 string table (magic {magic:#x}, version {version})")
    pos = 13
    table = StringTable(next_id)
    texts = {}
    for _ in range(count):
        id_, crc, length = struct.unpack_from("<III", data, pos)
        pos += 12
        texts[id_] = data[pos:pos + 2 * length].decode("utf-16-le")
        table.text_order.append(id_)
        table.crcs[id_] = crc
        pos += 2 * length
    for _ in range(count):
        id_, length = struct.unpack_from("<II", data, pos)
        pos += 8
        table.entries[data[pos:pos + length].decode("ascii")] = (id_, texts[id_])
        pos += length
    if pos != len(data):
        raise ValueError(f"{len(data) - pos} trailing bytes in string table")
    return table


def dump(table: StringTable) -> bytes:
    out = bytearray(struct.pack("<IBII", MAGIC, 1, table.next_id, len(table.entries)))
    texts = dict(table.entries.values())
    for id_ in table.text_order:
        encoded = texts[id_].encode("utf-16-le")
        out += struct.pack("<III", id_, table.crcs.get(id_, 0xFFFFFFFF), len(encoded) // 2) + encoded
    for key, (id_, _text) in table.entries.items():
        out += struct.pack("<II", id_, len(key)) + key.encode("ascii")
    return bytes(out)
