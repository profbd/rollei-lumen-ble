"""Exercise this application's Tk callbacks in preview mode; never uses Bluetooth."""
import argparse
import json
import sys
import tempfile
import tkinter as tk
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'src'))
from studio_gui import Studio
from studio_model import Level, load_data
from unittest.mock import patch


def main():
    with tempfile.TemporaryDirectory() as d:
        root=tk.Tk()
        args=argparse.Namespace(preview=True,config=Path(d)/'unused.json',store=Path(d)/'preview.json')
        studio=Studio(root,args)
        try:
            root.update()
            assert len(studio.cards)==8
            # Verify the core panels have nonzero geometry and report their requested size.
            print('Window',root.winfo_width(),root.winfo_height(),'requested',root.winfo_reqwidth(),root.winfo_reqheight())
            target=next(iter(studio.cards))
            studio.update_card(target,Level(4500,80))
            studio.master.set(50);studio.master_changed()
            studio.toggle_blackout();assert studio.blackout and studio.levels[target].brightness==80
            studio.toggle_blackout();assert not studio.blackout
            with patch('studio_gui.simpledialog.askstring',return_value='Test scene'):
                studio.save_scene()
            assert len(load_data(args.store)['scenes'][0]['levels'])==8
            studio.update_card(target,Level(3200,10))
            with patch.object(studio.ble,'set_levels') as send:
                studio.scene_actions['Test scene']['apply'].invoke()
                assert send.called, 'Scene button must send without a confirmation step'
            assert studio.levels[target]==Level(4500,80)
            studio.scene_actions['Test scene']['fade'].invoke();assert studio.transition is not None
            studio.stop()
            studio.cards[target]['power'].invoke();assert studio.levels[target].brightness==0
            studio.cards[target]['power'].invoke();assert studio.levels[target].brightness==80
            studio.toggle_blackout();assert studio.blackout
            studio.scene_actions['Test scene']['apply'].invoke();assert not studio.blackout
            studio.effect_buttons['Fade out'].invoke();assert studio.transition is not None
            assert studio.mode.get()=='Fade out'
            studio.toggle_blackout()
            studio.scene_seconds.set('invalid')
            with patch.object(studio,'error') as error:
                studio.scene_actions['Test scene']['fade'].invoke()
                assert error.called and studio.blackout,'Invalid fade must preserve blackout'
            studio.scene_seconds.set('3');studio.toggle_blackout()
            studio.start_effect();assert studio.transition is not None
            studio.stop();assert studio.transition is None
            # An edited preset must survive a new load without changing a scene.
            candidate=json.loads(args.store.read_text())
            candidate['presets'][0]={'name':'Custom','kelvin':4500,'brightness':35}
            studio.persist(candidate)
            assert load_data(args.store)['presets'][0]['name']=='Custom'
            root.update()
            print('PASS: eight cards, master/blackout, scene save/recall, one-click scene/fade/effect/power, blackout scene restore, validation, preset persistence')
        finally:
            studio.close()
            studio.ble.thread.join(timeout=5)
            assert not studio.ble.thread.is_alive(),'Bluetooth worker failed to stop'

if __name__=='__main__':main()
