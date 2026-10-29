import argparse
import asyncio
import contextlib
import io
import json
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))
import rollei_lumen as light


class Encoding(unittest.TestCase):
    def test_capture_vectors(self):
        for k, b, h in [(4000,20,'280000002814000f29'),(5500,100,'280000003764000f29'),(4500,100,'280000002d64000f29'),(3200,100,'280000002064000f29'),(3200,0,'280000002000000f29')]:
            self.assertEqual(light.command(k,b).hex(),h)

    def test_bounds(self):
        for k,b in [(3199,20),(5600,20),(4050,20),(4000,-1),(4000,101)]:
            with self.assertRaises(ValueError): light.command(k,b)

    def test_dry_run_without_bleak(self):
        with patch.dict(sys.modules, {'bleak': None}), contextlib.redirect_stdout(io.StringIO()) as out:
            self.assertEqual(light.main(['set','--name','Magic-EXAMPLE','--kelvin','4000','--brightness','20','--dry-run']),0)
        self.assertFalse(json.loads(out.getvalue())['bluetooth_used'])

    def test_no_implicit_target(self):
        with contextlib.redirect_stderr(io.StringIO()), self.assertRaises(SystemExit):
            light.parser().parse_args(['set','--kelvin','4000','--brightness','20'])

    def test_utf8_alias_under_simulated_windows_default(self):
        original_read=Path.read_text
        def windows_read(path,*args,**kwargs):
            if not args and 'encoding' not in kwargs:kwargs['encoding']='cp1252'
            return original_read(path,*args,**kwargs)
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)/'lamps.json'
            path.write_bytes(json.dumps({'lamps':[{'name':'Magic-EXAMPLE','label':'Wärme ☀'}]},ensure_ascii=False).encode('utf-8'))
            args=argparse.Namespace(name=None,label='Wärme ☀',all=False,config=path)
            with patch.object(Path,'read_text',windows_read):
                self.assertEqual(light.targets(args),['Magic-EXAMPLE'])

    def test_config_and_duplicates(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/'lamps.json'
            p.write_text(json.dumps({'lamps':[{'name':'Magic-EXAMPLE','label':'left'}]}))
            a=argparse.Namespace(name=None,label='left',all=False,config=p)
            self.assertEqual(light.targets(a),['Magic-EXAMPLE'])
            a.label='missing'
            with self.assertRaises(ValueError):light.targets(a)
            p.write_text(json.dumps({'lamps':[{'name':'same','label':'left'},{'name':'same','label':'right'}]}))
            a.all=True
            with self.assertRaises(ValueError):light.targets(a)


class BluetoothFlow(unittest.IsolatedAsyncioTestCase):
    async def test_duplicate_names_rejected(self):
        entries={str(n):(SimpleNamespace(name='Magic-X'),SimpleNamespace(local_name='Magic-X')) for n in range(2)}
        fake=SimpleNamespace(BleakScanner=SimpleNamespace(discover=AsyncMock(return_value=entries)))
        with patch.dict(sys.modules,{'bleak':fake}),self.assertRaises(ValueError):
            await light.discover('Magic-X',1)

    async def exercise(self, inspect=False, fail=False, incompatible=False):
        events=[]
        write=SimpleNamespace(uuid=light.WRITE_UUID,properties=['write-without-response'])
        notify=SimpleNamespace(uuid=light.NOTIFY_UUID,properties=['notify'])
        class Services(list):
            def get_characteristic(self,uuid):
                if incompatible:return None
                return write if uuid==light.WRITE_UUID else notify
        class Client:
            def __init__(self,*a,**kw):self.services=Services()
            async def __aenter__(self):events.append('connect');return self
            async def __aexit__(self,*a):events.append('disconnect')
            async def start_notify(self,c,cb):events.append('subscribe')
            async def stop_notify(self,c):events.append('unsubscribe')
            async def write_gatt_char(self,c,payload,response):
                events.append(('write',c.uuid,payload.hex(),response))
                if fail:raise RuntimeError('synthetic failure')
        args=argparse.Namespace(action='inspect' if inspect else 'set',kelvin=4000,brightness=20,timeout=1)
        fake=SimpleNamespace(BleakClient=Client)
        with patch.dict(sys.modules,{'bleak':fake}),patch.object(light,'discover',AsyncMock(return_value=object())),patch.object(light.asyncio,'sleep',AsyncMock()),contextlib.redirect_stdout(io.StringIO()):
            if fail or incompatible:
                with self.assertRaises((RuntimeError,ValueError)):await light.operate(args,['first','second'])
            else:await light.operate(args,['first'])
        return events

    async def test_sequence_uses_uuid_and_no_response(self):
        self.assertEqual(await self.exercise(),['connect','subscribe',('write',light.WRITE_UUID,'280000002814000f29',False),'unsubscribe','disconnect'])

    async def test_inspect_never_writes(self):
        self.assertEqual(await self.exercise(inspect=True),['connect','disconnect'])

    async def test_failure_disconnects_and_stops_group(self):
        e=await self.exercise(fail=True)
        self.assertEqual(e.count('connect'),1)
        self.assertEqual(e[-2:],['unsubscribe','disconnect'])

    async def test_missing_characteristics_never_writes(self):
        self.assertEqual(await self.exercise(incompatible=True),['connect','disconnect'])
