import asyncio
import copy
import json
import queue
import sys
import tempfile
import unittest
import os
from unittest.mock import patch
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'src'))
from studio_model import Level, Transition, effective, default_data, load_data, save_data
from studio_ble import StudioBLE


class StudioModel(unittest.TestCase):
    def test_eight_independent_channels_and_exact_endpoints(self):
        start={str(i):Level(3200,i*10) for i in range(8)}
        end={str(i):Level(5500,100-i*10) for i in range(8)}
        t=Transition(start,end,10,100)
        self.assertEqual(t.sample(100),(start,False))
        middle,done=t.sample(105)
        self.assertFalse(done);self.assertEqual(len(middle),8)
        self.assertTrue(all(v.brightness==50 for v in middle.values()))
        self.assertEqual(t.sample(110),(end,True))

    def test_repeated_bounce_holds_and_finish(self):
        a={'x':Level(4000,0)};b={'x':Level(4000,100)}
        t=Transition(a,b,2,0,repeats=2,bounce=True,hold=1)
        self.assertEqual(t.sample(2.5)[0],b)
        self.assertEqual(t.sample(4)[0]['x'].brightness,50)
        self.assertEqual(t.sample(5.5)[0],a)
        self.assertEqual(t.sample(12),(a,True))

    def test_continuous_repeat(self):
        t=Transition({'x':Level()},{'x':Level(4000,80)},2,0,repeats=0)
        self.assertFalse(t.sample(10000)[1])

    def test_invalid_timing_rejected(self):
        for duration,hold,repeats in [(0,0,1),(float('nan'),0,1),(1,-1,1),(1,0,-1)]:
            with self.assertRaises(ValueError):Transition({'x':Level()},{'x':Level()},duration,0,hold=hold,repeats=repeats)

    def test_master_blackout_does_not_destroy_base(self):
        base=Level(4500,80)
        self.assertEqual(effective(base,50,False),Level(4500,40))
        self.assertEqual(effective(base,50,True),Level(4500,0))
        self.assertEqual(base,Level(4500,80))

    def test_custom_presets_and_scenes_round_trip(self):
        d=default_data();d['presets'][0]={'name':'Key soft','kelvin':4500,'brightness':35}
        d['scenes']=[{'name':'Interview','levels':{f'Magic-DEMO-{i}':Level(4000,i*10).json() for i in range(8)}}]
        with tempfile.TemporaryDirectory() as p:
            path=Path(p)/'studio.json';save_data(path,d)
            self.assertEqual(load_data(path),d)
            invalid=copy.deepcopy(d);invalid['presets'][0]['brightness']=999
            with self.assertRaises(ValueError):save_data(path,invalid)
            self.assertEqual(load_data(path),d)

    def test_utf8_roundtrip_under_simulated_windows_default(self):
        original_read, original_fdopen = Path.read_text, os.fdopen
        def windows_read(path, *args, **kwargs):
            if not args and 'encoding' not in kwargs:
                kwargs['encoding'] = 'cp1252'
            return original_read(path, *args, **kwargs)
        def windows_fdopen(fd, mode='r', *args, **kwargs):
            if 'b' not in mode and 'encoding' not in kwargs:
                kwargs['encoding'] = 'cp1252'
            return original_fdopen(fd, mode, *args, **kwargs)
        data=default_data()
        data['presets'][0]['name']='Wärme ☀'
        data['scenes']=[{'name':'Interview 日本語','levels':{'Magic-DEMO':Level().json()}}]
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)/'studio.json'
            with patch.object(Path,'read_text',windows_read), patch('studio_model.os.fdopen',windows_fdopen):
                save_data(path,data)
                self.assertEqual(load_data(path),data)
            self.assertIn('Wärme ☀',path.read_bytes().decode('utf-8'))

    def test_unknown_version_and_corrupt_file_preserved(self):
        with tempfile.TemporaryDirectory() as p:
            path=Path(p)/'studio.json';path.write_text('{broken')
            with self.assertRaises(ValueError):load_data(path)
            self.assertEqual(path.read_text(),'{broken')
            path.write_text(json.dumps({'version':2}))
            with self.assertRaises(ValueError):load_data(path)


class PreviewTransport(unittest.IsolatedAsyncioTestCase):
    async def test_connect_eight_without_writes_and_disconnect(self):
        ble=StudioBLE.__new__(StudioBLE);ble.preview=True;ble.events=queue.Queue();ble.clients={};ble.pending={}
        names=[f'Magic-DEMO-{i}' for i in range(8)]
        await ble.connect(names)
        self.assertEqual(len(ble.clients),8);self.assertEqual(ble.pending,{})
        await ble._write(names[0],Level())
        self.assertTrue(any(e[0]=='sent' for e in list(ble.events.queue)))
        await ble.disconnect()
        self.assertEqual(ble.clients,{})
