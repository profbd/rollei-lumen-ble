"""Extract unfragmented ATT packets from PacketLogger; never sends Bluetooth data."""
import argparse
import csv
import hashlib
import json
import struct
from collections import Counter
from pathlib import Path


def records(data):
    # Validate the complete file, including record boundaries and timestamp fractions.
    endian = '<' if 9 <= int.from_bytes(data[:4], 'little') < 65536 else '>'
    offset = 0
    while offset < len(data):
        if len(data) - offset < 13:
            raise ValueError(f'Truncated header at {offset}')
        size, seconds, micros, kind = struct.unpack_from(endian + 'IIIB', data, offset)
        if size < 9 or micros >= 1000000 or offset + 4 + size > len(data):
            raise ValueError(f'Invalid record at {offset}')
        yield offset, seconds + micros / 1e6, kind, data[offset + 13:offset + 4 + size]
        offset += 4 + size


def analyze(source, output):
    data = source.read_bytes()
    rows, kinds = [], Counter()
    start = None
    for offset, timestamp, kind, payload in records(data):
        kinds[kind] += 1
        if start is None:
            start = timestamp
        if kind not in (2, 3):
            continue
        if len(payload) < 4:
            raise ValueError('Short ACL packet')
        connection, acl_size = struct.unpack_from('<HH', payload)
        if acl_size != len(payload) - 4:
            raise ValueError('ACL length mismatch')
        if (connection >> 12) & 3 == 1:
            raise ValueError('ACL fragmentation requires reassembly; unsupported')
        if len(payload) < 8:
            raise ValueError('Short L2CAP packet')
        l2_size, cid = struct.unpack_from('<HH', payload, 4)
        if l2_size != len(payload) - 8:
            raise ValueError('L2CAP fragmentation requires reassembly; unsupported')
        if cid != 4:
            continue
        att = payload[8:]
        if not att:
            raise ValueError('Empty ATT packet')
        row = dict(offset=offset, seconds_from_start=round(timestamp-start, 6),
                   direction='TX' if kind == 2 else 'RX', connection=connection & 0xfff,
                   opcode=f'{att[0]:02x}', att_hex=att.hex(), handle='', value_hex='',
                   kelvin_candidate='', brightness_candidate='')
        if att[0] in (0x12, 0x52, 0x1b, 0x1d):
            if len(att) < 3:
                raise ValueError('Short ATT write/notification')
            row['handle'] = f'{int.from_bytes(att[1:3], "little"):04x}'
            value = att[3:]
            row['value_hex'] = value.hex()
            if kind == 2 and len(value) == 9 and value[:4] == bytes.fromhex('28000000') and value[6:] == bytes.fromhex('000f29'):
                row['kelvin_candidate'] = value[4] * 100
                row['brightness_candidate'] = value[5]
        rows.append(row)
    output.mkdir(parents=True, exist_ok=True)
    fields = ['offset', 'seconds_from_start', 'direction', 'connection', 'opcode', 'att_hex', 'handle', 'value_hex', 'kelvin_candidate', 'brightness_candidate']
    with (output/'att_packets.csv').open('w', encoding='utf-8', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)
    writes = [r for r in rows if r['direction'] == 'TX' and r['opcode'] in ('12', '52')]
    summary = dict(source_name=source.name, source_bytes=len(data), sha256=hashlib.sha256(data).hexdigest(),
                   record_count=sum(kinds.values()), record_types=dict(kinds), att_count=len(rows),
                   write_count=len(writes), writes_first=writes[:8], writes_last=writes[-5:])
    (output/'summary.json').write_text(json.dumps(summary, indent=2)+'\n', encoding='utf-8')
    print(json.dumps({k:v for k,v in summary.items() if k not in ('writes_first','writes_last')}, indent=2))

if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('capture', type=Path)
    p.add_argument('output', type=Path)
    a = p.parse_args()
    analyze(a.capture, a.output)
