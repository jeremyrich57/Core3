"""Read and write SWG DataTable IFF files (FORM DTII, version 0001).

Layout (IFF: 4-byte tag + big-endian uint32 size; chunk contents little-endian):

    FORM DTII
        FORM 0001
            COLS  uint32 column_count, then NUL-terminated column names
            TYPE  NUL-terminated type per column, e.g. "s", "i", "f", "b", "h", "e(...)[default]"
            ROWS  uint32 row_count, then each row's cells in column order:
                  string types: NUL-terminated; everything else: 4 bytes (int32 or float32)

Matches MMOCoreORB/src/templates/datatables/DataTableIff.cpp.
"""

from __future__ import annotations

import os
import struct
from dataclasses import dataclass, field

import tre


@dataclass
class DataTable:
    columns: list[str]
    types: list[str]
    rows: list[list] = field(default_factory=list)

    def column(self, name: str) -> int:
        return self.columns.index(name)


def _is_string(type_: str) -> bool:
    return type_[:1].lower() in ("s", "p")


def _is_float(type_: str) -> bool:
    return type_[:1].lower() == "f"


def _chunks(data: bytes):
    pos = 0
    while pos < len(data):
        tag = data[pos:pos + 4].decode("ascii")
        (size,) = struct.unpack_from(">I", data, pos + 4)
        yield tag, data[pos + 8:pos + 8 + size]
        pos += 8 + size  # SWG IFFs do not pad odd-sized chunks


def _cstrings(data: bytes) -> list[str]:
    return [s.decode("ascii") for s in data.split(b"\0")[:-1]]


def parse(data: bytes) -> DataTable:
    tag, body = next(_chunks(data))
    if tag != "FORM" or body[:4] != b"DTII":
        raise ValueError("not a DataTable IFF (FORM DTII)")
    tag, version = next(_chunks(body[4:]))
    if tag != "FORM" or version[:4] != b"0001":
        raise ValueError(f"unsupported DataTable version {version[:4]!r}")

    chunks = dict(_chunks(version[4:]))
    (ncols,) = struct.unpack_from("<I", chunks["COLS"], 0)
    columns = _cstrings(chunks["COLS"][4:])[:ncols]
    types = _cstrings(chunks["TYPE"])[:ncols]

    rows_data = chunks["ROWS"]
    (nrows,) = struct.unpack_from("<I", rows_data, 0)
    pos = 4
    rows = []
    for _ in range(nrows):
        row = []
        for t in types:
            if _is_string(t):
                end = rows_data.index(b"\0", pos)
                row.append(rows_data[pos:end].decode("ascii"))
                pos = end + 1
            elif _is_float(t):
                row.append(struct.unpack_from("<f", rows_data, pos)[0])
                pos += 4
            else:
                row.append(struct.unpack_from("<i", rows_data, pos)[0])
                pos += 4
        rows.append(row)
    return DataTable(columns, types, rows)


def _chunk(tag: str, body: bytes) -> bytes:
    return tag.encode("ascii") + struct.pack(">I", len(body)) + body


def dump(table: DataTable) -> bytes:
    cols = struct.pack("<I", len(table.columns)) + b"".join(c.encode("ascii") + b"\0" for c in table.columns)
    types = b"".join(t.encode("ascii") + b"\0" for t in table.types)
    rows = bytearray(struct.pack("<I", len(table.rows)))
    for row in table.rows:
        for t, v in zip(table.types, row):
            if _is_string(t):
                rows += v.encode("ascii") + b"\0"
            elif _is_float(t):
                rows += struct.pack("<f", v)
            else:
                rows += struct.pack("<i", v)
    version = _chunk("FORM", b"0001" + _chunk("COLS", cols) + _chunk("TYPE", types) + _chunk("ROWS", bytes(rows)))
    return _chunk("FORM", b"DTII" + version)


class TreSet:
    """Look up files across stock TREs in the server's search order (first match wins)."""

    def __init__(self, tre_dir: str, names: list[str]):
        self.archives = []
        for name in names:
            path = os.path.join(os.path.expanduser(tre_dir), name)
            if os.path.exists(path):
                records, raw = tre.read(path)
                self.archives.append((name, {r.name: r for r in records}, raw))

    def get(self, name: str) -> tuple[str, bytes]:
        for archive, records, raw in self.archives:
            if name in records:
                return archive, tre.read_file(raw, records[name])
        raise FileNotFoundError(name)
