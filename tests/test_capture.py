import contextlib
import io
import json
import struct
import sys
import tempfile
import unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'src'))
from analyze_capture import records,analyze


def record(payload,kind=2,endian='<'):
    return struct.pack(endian+'IIIB',9+len(payload),100,0,kind)+payload


class Capture(unittest.TestCase):
    def test_header_orders(self):
        for endian in ['<','>']:
            self.assertEqual(list(records(record(b'abc',endian=endian)))[0][3],b'abc')

    def test_truncated_record(self):
        with self.assertRaises(ValueError):list(records(record(b'abc')[:-1]))

    def test_empty_file(self):
        self.assertEqual(list(records(b'')),[])
        self.run_analysis(b'',expected_writes=0)

    def run_analysis(self,data,expected_writes):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/'synthetic.pklg';p.write_bytes(data)
            out=Path(d)/'nested'/'analysis'
            with contextlib.redirect_stdout(io.StringIO()):analyze(p,out)
            self.assertEqual(json.loads((out/'summary.json').read_text())['write_count'],expected_writes)

    def test_synthetic_frame_on_nonhistorical_handle(self):
        att=bytes.fromhex('529900280000002814000f29')
        packet=struct.pack('<HHHH',0x42,len(att)+4,len(att),4)+att
        self.run_analysis(record(packet),1)

    def test_reject_fragmented_acl(self):
        packet=struct.pack('<HHHH',0x1042,5,1,4)+b'\x13'
        with self.assertRaises(ValueError):self.run_analysis(record(packet),0)

    def test_reject_invalid_l2cap_length(self):
        packet=struct.pack('<HHHH',0x42,5,99,4)+b'\x13'
        with self.assertRaises(ValueError):self.run_analysis(record(packet),0)
