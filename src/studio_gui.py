"""A local, neutral studio desk for Rollei BLE lights."""
import argparse
import copy
import json
import queue
import time
import tkinter as tk
from pathlib import Path
from tkinter import ttk, messagebox, simpledialog
from studio_model import Level, Transition, effective, load_data, save_data
from studio_ble import StudioBLE


class Studio:
    def __init__(self, root, args):
        self.root, self.args = root, args
        self.data = load_data(args.store)
        if args.preview:
            self.config = {'lamps': [{'name': f'Magic-DEMO-{i+1}', 'label': f'Light {i+1}'} for i in range(8)]}
        else:
            self.config = json.loads(args.config.read_text(encoding='utf-8')) if args.config.exists() else {'lamps': []}
        names, labels = set(), set()
        for lamp in self.config['lamps']:
            if not lamp['name'] or not lamp['label'] or lamp['name'] in names or lamp['label'] in labels:
                raise ValueError('Each configured light needs a unique nonempty name and label')
            names.add(lamp['name']); labels.add(lamp['label'])
        self.levels = {l['name']: Level() for l in self.config['lamps']}
        self.cards = {}
        self.restore_brightness = {n:20 for n in self.levels}
        self.transition = None
        self.blackout = False
        self.busy = False
        self.ble = StudioBLE(args.preview)
        self.master = tk.DoubleVar(value=100)
        self.status = tk.StringVar(value='Draft values · connect, then Apply selected. Physical switches must be ON.')
        root.title('Lumen Studio' + (' — PREVIEW / no Bluetooth' if args.preview else ''))
        root.geometry('1360x960'); root.minsize(1080, 760)
        root.configure(bg='#eef1f3')
        style = ttk.Style(root)
        style.theme_use('clam')
        style.configure('.', font=('Helvetica', 11), background='#eef1f3', foreground='#202c36')
        style.configure('TButton', padding=(8, 6))
        style.configure('TLabelframe', padding=10)
        style.configure('TLabelframe.Label', font=('Helvetica', 11, 'bold'))
        style.configure('Title.TLabel', font=('Helvetica', 22, 'bold'))
        style.configure('Accent.TButton', background='#d2e5ed')
        header = ttk.Frame(root, padding=(18,12)); header.pack(fill='x')
        ttk.Label(header, text='LUMEN / STUDIO', style='Title.TLabel').pack(side='left')
        ttk.Label(header, text='PREVIEW · 8 virtual lights' if args.preview else 'Local Bluetooth lighting desk').pack(side='left', padx=20)
        ttk.Button(header, text='Add light…', command=self.scan).pack(side='right')
        self.disconnect_button = ttk.Button(header, text='Disconnect', command=self.disconnect)
        self.disconnect_button.pack(side='right', padx=5)
        self.connect_button = ttk.Button(header, text='Connect all', command=self.connect)
        self.connect_button.pack(side='right')
        toolbar = ttk.Frame(root, padding=(18,0,18,10)); toolbar.pack(fill='x')
        ttk.Label(toolbar, text='MASTER').pack(side='left')
        ttk.Scale(toolbar, from_=0, to=100, variable=self.master, length=230, command=self.master_changed).pack(side='left', padx=10)
        self.master_label = ttk.Label(toolbar, text='100%', width=6); self.master_label.pack(side='left')
        ttk.Button(toolbar, text='Apply selected', command=self.apply_selected, style='Accent.TButton').pack(side='left', padx=8)
        ttk.Button(toolbar, text='Select all', command=lambda: self.select(True)).pack(side='left')
        ttk.Button(toolbar, text='Select none', command=lambda: self.select(False)).pack(side='left', padx=5)
        self.blackout_button = ttk.Button(toolbar, text='BLACKOUT', command=self.toggle_blackout)
        self.blackout_button.pack(side='right')
        ttk.Button(toolbar, text='STOP  /  Esc', command=self.stop).pack(side='right', padx=8)
        viewport = ttk.Frame(root); viewport.pack(fill='both', expand=True, padx=18)
        self.canvas = tk.Canvas(viewport, bg='#eef1f3', highlightthickness=0)
        scroll = ttk.Scrollbar(viewport, orient='vertical', command=self.canvas.yview)
        self.canvas.configure(yscrollcommand=scroll.set)
        self.canvas.pack(side='left', fill='both', expand=True); scroll.pack(side='right', fill='y')
        self.grid = ttk.Frame(self.canvas)
        self.window = self.canvas.create_window((0,0), window=self.grid, anchor='nw')
        self.grid.bind('<Configure>', lambda e: self.canvas.configure(scrollregion=self.canvas.bbox('all')))
        self.canvas.bind('<Configure>', lambda e: self.canvas.itemconfigure(self.window, width=e.width))
        self.draw_cards()
        lower = ttk.Frame(root, padding=(18,10)); lower.pack(fill='x')
        scenes = ttk.LabelFrame(lower, text='SCENES · all configured lights'); scenes.pack(side='left', fill='both', expand=True, padx=(0,8))
        self.scene_name = tk.StringVar()
        for column in range(4):scenes.columnconfigure(column,weight=1)
        ttk.Button(scenes,text='Save new…',command=self.save_scene).grid(row=0,column=0,sticky='ew',padx=2)
        ttk.Button(scenes,text='Manage scenes…',command=self.manage_scenes).grid(row=0,column=1,sticky='ew',padx=2)
        ttk.Button(scenes,text='Edit 5 presets…',command=self.edit_presets).grid(row=0,column=2,columnspan=2,sticky='ew',padx=2)
        scene_view=ttk.Frame(scenes);scene_view.grid(row=1,column=0,columnspan=4,sticky='nsew',pady=6)
        self.scene_canvas=tk.Canvas(scene_view,height=118,bg='#eef1f3',highlightthickness=0)
        scene_scroll=ttk.Scrollbar(scene_view,orient='vertical',command=self.scene_canvas.yview)
        self.scene_canvas.configure(yscrollcommand=scene_scroll.set)
        self.scene_canvas.pack(side='left',fill='both',expand=True);scene_scroll.pack(side='right',fill='y')
        self.scene_buttons=ttk.Frame(self.scene_canvas)
        scene_window=self.scene_canvas.create_window((0,0),window=self.scene_buttons,anchor='nw')
        self.scene_buttons.bind('<Configure>',lambda e:self.scene_canvas.configure(scrollregion=self.scene_canvas.bbox('all')))
        self.scene_canvas.bind('<Configure>',lambda e:self.scene_canvas.itemconfigure(scene_window,width=e.width))
        self.scene_seconds = tk.StringVar(value='3')
        ttk.Label(scenes,text='Fade duration').grid(row=2,column=0,sticky='w')
        ttk.Entry(scenes,textvariable=self.scene_seconds,width=5).grid(row=2,column=1,sticky='w')
        ttk.Label(scenes,text='seconds').grid(row=2,column=2,sticky='w')
        self.scene_last=ttk.Label(scenes,text='Click a scene to apply it immediately.')
        self.scene_last.grid(row=3,column=0,columnspan=4,sticky='w',pady=(4,0))
        fx = ttk.LabelFrame(lower,text='TRANSITIONS · selected lights'); fx.pack(side='left',fill='both',expand=True)
        self.mode = tk.StringVar(value='Linear fade')
        launch=ttk.Frame(fx);launch.grid(row=0,column=0,columnspan=4,sticky='ew',pady=(0,4))
        self.effect_buttons={}
        for i,mode in enumerate(['Linear fade','Fade in','Fade out','Breathing']):
            button=ttk.Button(launch,text=mode,command=lambda m=mode:self.run_effect(m),style='Accent.TButton')
            button.grid(row=0,column=i,padx=2,sticky='ew');launch.columnconfigure(i,weight=1)
            self.effect_buttons[mode]=button
        ttk.Label(fx,text='Brightness %').grid(row=1,column=2)
        ttk.Label(fx,text='Temperature K').grid(row=1,column=3)
        self.start_b=tk.StringVar(value='20'); self.end_b=tk.StringVar(value='60')
        self.start_k=tk.StringVar(value='4000'); self.end_k=tk.StringVar(value='4000')
        for row,title,b,k in [(2,'Start',self.start_b,self.start_k),(3,'End',self.end_b,self.end_k)]:
            ttk.Label(fx,text=title).grid(row=row,column=0,sticky='w')
            ttk.Entry(fx,textvariable=b,width=8).grid(row=row,column=2,padx=4,pady=3)
            ttk.Entry(fx,textvariable=k,width=8).grid(row=row,column=3,padx=4)
        self.duration=tk.StringVar(value='5'); self.hold=tk.StringVar(value='0'); self.repeats=tk.StringVar(value='1')
        for col,(text,var) in enumerate([('Seconds / leg',self.duration),('Hold / endpoint',self.hold),('Cycles (0=∞)',self.repeats)]):
            ttk.Label(fx,text=text).grid(row=4,column=col,padx=3)
            ttk.Entry(fx,textvariable=var,width=9).grid(row=5,column=col,padx=3)
        self.bounce=tk.BooleanVar(value=False)
        ttk.Checkbutton(fx,text='Return to start',variable=self.bounce).grid(row=4,column=3)
        self.effect_status=ttk.Label(fx,text='Click an effect to start · Esc stops')
        self.effect_status.grid(row=6,column=0,columnspan=4,sticky='w')
        ttk.Label(root,textvariable=self.status,padding=(18,5),wraplength=1250).pack(fill='x')
        ttk.Label(root,text='SETPOINTS, not measured output  •  100 K / 1% steps  •  Best-effort BLE timing; eight connections not hardware-verified',padding=(18,0,18,10)).pack(fill='x')
        self.refresh_scenes()
        root.bind('<Escape>',lambda e:self.stop())
        root.protocol('WM_DELETE_WINDOW',self.close)
        root.after(100,self.tick)

    def error(self, error):
        messagebox.showerror('Lumen Studio',str(error),parent=self.root)

    def persist(self, candidate):
        save_data(self.args.store,candidate)
        self.data=candidate

    def draw_cards(self):
        for child in self.grid.winfo_children():child.destroy()
        previous=self.cards
        self.cards={}
        for col in range(4):self.grid.columnconfigure(col,weight=1,uniform='light')
        for index,lamp in enumerate(self.config['lamps']):
            name=lamp['name']; level=self.levels[name]
            card=ttk.LabelFrame(self.grid,text=lamp['label']);card.grid(row=index//4,column=index%4,sticky='nsew',padx=4,pady=5)
            selected=tk.BooleanVar(value=previous[name]['selected'].get() if name in previous else True); b=tk.DoubleVar(value=level.brightness);k=tk.DoubleVar(value=level.kelvin)
            state=tk.StringVar(value=previous[name]['state'].get() if name in previous else 'Offline · draft only')
            values=tk.StringVar(value=f'{level.brightness}%  /  {level.kelvin} K')
            heading=ttk.Frame(card);heading.pack(fill='x')
            ttk.Checkbutton(heading,text='Include in selection',variable=selected).pack(side='left')
            power=ttk.Button(heading,text='Light off' if level.brightness else 'Light on',command=lambda n=name:self.toggle_light(n))
            power.pack(side='right')
            ttk.Label(card,textvariable=values,font=('Helvetica',16,'bold')).pack(anchor='w',pady=(7,2))
            numeric=ttk.Frame(card);numeric.pack(fill='x',pady=2)
            for label,var,lo,hi,step in [('B %',b,0,100,1),('K',k,3200,5500,100)]:
                ttk.Label(numeric,text=label).pack(side='left',padx=(0,3))
                entry=ttk.Spinbox(numeric,from_=lo,to=hi,increment=step,textvariable=var,width=6,format='%.0f',command=lambda n=name:self.numeric(n))
                entry.pack(side='left',padx=(0,7))
                entry.bind('<Return>',lambda e,n=name:self.numeric(n))
            ttk.Label(card,text='Brightness').pack(anchor='w')
            ttk.Scale(card,from_=0,to=100,variable=b,command=lambda v,n=name:self.slider(n)).pack(fill='x')
            ttk.Label(card,text='Color temperature').pack(anchor='w')
            ttk.Scale(card,from_=3200,to=5500,variable=k,command=lambda v,n=name:self.slider(n)).pack(fill='x')
            buttons=ttk.Frame(card);buttons.pack(fill='x',pady=5)
            for i,preset in enumerate(self.data['presets']):
                ttk.Button(buttons,text=preset['name'],width=6,command=lambda n=name,p=i:self.preset(n,p)).grid(row=i//3,column=i%3,padx=1,pady=1,sticky='ew')
            ttk.Label(card,textvariable=state,wraplength=260).pack(anchor='w',pady=4)
            self.cards[name]={'selected':selected,'b':b,'k':k,'state':state,'values':values,'power':power}
        if not self.cards:ttk.Label(self.grid,text='No lights configured. Add a light to begin.',padding=30).pack()

    def selected(self):
        return [n for n,c in self.cards.items() if c['selected'].get()]

    def select(self,value):
        for c in self.cards.values():c['selected'].set(value)

    def update_card(self,name,level):
        self.levels[name]=level;c=self.cards[name]
        if level.brightness:self.restore_brightness[name]=level.brightness
        c['power'].configure(text='Light off' if level.brightness else 'Light on')
        c['b'].set(level.brightness);c['k'].set(level.kelvin)
        c['values'].set(f'{level.brightness}%  /  {level.kelvin} K')

    def send(self,names):
        self.ble.set_levels({n:effective(self.levels[n],self.master.get(),self.blackout) for n in names})

    def slider(self,name):
        self.stop(quiet=True);c=self.cards[name]
        level=Level(round(c['k'].get()/100)*100,round(c['b'].get()))
        self.update_card(name,level);self.send([name])

    def numeric(self,name):
        try:
            c=self.cards[name]
            Level(int(c['k'].get()),int(c['b'].get()))
            self.slider(name)
        except (ValueError,tk.TclError) as e:
            self.update_card(name,self.levels[name]);self.error(e)

    def preset(self,name,index):
        self.stop(quiet=True);p=self.data['presets'][index]
        self.update_card(name,Level(p['kelvin'],self.levels[name].brightness if p['brightness'] is None else p['brightness']))
        self.send([name])

    def toggle_light(self,name):
        self.stop(quiet=True)
        level=self.levels[name]
        self.update_card(name,Level(level.kelvin,0 if level.brightness else self.restore_brightness.get(name,20)))
        self.send([name])

    def apply_selected(self):
        self.stop(quiet=True);self.send(self.selected())

    def master_changed(self,_=None):
        self.master_label.configure(text=f'{round(self.master.get())}%');self.send(list(self.levels))

    def toggle_blackout(self):
        self.stop(quiet=True);self.blackout=not self.blackout
        self.blackout_button.configure(text='RESTORE LIGHT' if self.blackout else 'BLACKOUT')
        self.send(list(self.levels));self.status.set('Blackout requested · base levels retained' if self.blackout else 'Restoring base levels through current master')

    def set_busy(self,value):
        self.busy=value
        for b in (self.connect_button,self.disconnect_button):b.configure(state='disabled' if value else 'normal')

    def connect(self):
        if self.busy:return
        self.set_busy(True)
        future=self.ble.submit(self.ble.connect(list(self.levels)))
        future.add_done_callback(lambda f:self.ble.emit('ready','',''))
        self.status.set('Connecting configured lights · no settings are applied automatically')

    def disconnect(self):
        self.stop(quiet=True)
        if self.busy:return
        self.set_busy(True)
        future=self.ble.submit(self.ble.disconnect())
        future.add_done_callback(lambda f:self.ble.emit('ready','',''))
        self.status.set('Disconnecting · lights retain their last received values')

    def scan(self):
        if self.busy:return
        self.status.set('Scanning for Magic-* advertisements…');self.ble.submit(self.ble.scan())

    def add_dialog(self,names):
        dialog=tk.Toplevel(self.root);dialog.title('Add a light');dialog.transient(self.root)
        ttk.Label(dialog,text='Advertised name (exact)').grid(row=0,column=0,padx=12,pady=8)
        name=tk.StringVar(value=names[0] if names else '')
        ttk.Combobox(dialog,textvariable=name,values=names,width=30).grid(row=0,column=1,padx=12)
        ttk.Label(dialog,text='Local label').grid(row=1,column=0,padx=12,pady=8)
        label=tk.StringVar();ttk.Entry(dialog,textvariable=label,width=30).grid(row=1,column=1,padx=12)
        def add():
            try:
                n,l=name.get().strip(),label.get().strip()
                if not n or not l or n in self.levels or any(x['label']==l for x in self.config['lamps']):
                    raise ValueError('Provide a unique device name and label')
                candidate=copy.deepcopy(self.config);candidate['lamps'].append({'name':n,'label':l})
                if not self.args.preview:
                    # Validate the old file before overwrite; retain its other metadata.
                    import os,tempfile
                    self.args.config.parent.mkdir(parents=True,exist_ok=True)
                    fd,p=tempfile.mkstemp(dir=self.args.config.parent,prefix='lamps.')
                    try:
                        with os.fdopen(fd,'w',encoding='utf-8') as f:json.dump(candidate,f,indent=2,ensure_ascii=False)
                        os.replace(p,self.args.config)
                    finally:
                        if Path(p).exists():Path(p).unlink()
                self.stop(quiet=True);self.config=candidate;self.levels[n]=Level();self.draw_cards();dialog.destroy()
                self.status.set('Light added · connect explicitly before applying settings')
            except Exception as e:self.error(e)
        ttk.Button(dialog,text='Add',command=add).grid(row=2,column=1,pady=12)

    def refresh_scenes(self):
        for child in self.scene_buttons.winfo_children():child.destroy()
        self.scene_actions={}
        if not self.data['scenes']:
            ttk.Label(self.scene_buttons,text='No saved scenes yet. Set your lights, then Save new…',padding=10).pack(anchor='w')
            return
        for col in range(2):self.scene_buttons.columnconfigure(col,weight=1,uniform='scene')
        for i,scene in enumerate(self.data['scenes']):
            name=scene['name']
            row=ttk.Frame(self.scene_buttons);row.grid(row=i//2,column=i%2,sticky='ew',padx=2,pady=3)
            row.columnconfigure(0,weight=1)
            apply=ttk.Button(row,text=name,command=lambda n=name:self.activate_scene(n),style='Accent.TButton')
            apply.grid(row=0,column=0,sticky='ew')
            fade=ttk.Button(row,text='Fade',width=5,command=lambda n=name:self.activate_scene(n,True))
            fade.grid(row=0,column=1,padx=(3,0))
            self.scene_actions[name]={'apply':apply,'fade':fade}

    def activate_scene(self,name,fade=False):
        self.scene_name.set(name)
        self.recall(fade)

    def manage_scenes(self):
        dialog=tk.Toplevel(self.root);dialog.title('Manage saved scenes');dialog.transient(self.root)
        ttk.Label(dialog,text='Select a scene to edit. Applying scenes uses the main scene buttons.',padding=10).pack()
        picker=ttk.Combobox(dialog,textvariable=self.scene_name,state='readonly',values=[s['name'] for s in self.data['scenes']],width=32)
        picker.pack(padx=10,pady=6)
        ttk.Button(dialog,text='Replace with current levels',command=self.update_scene).pack(fill='x',padx=10,pady=4)
        def delete():
            self.delete_scene();picker.configure(values=[s['name'] for s in self.data['scenes']])
        ttk.Button(dialog,text='Delete scene…',command=delete).pack(fill='x',padx=10,pady=4)
        ttk.Button(dialog,text='Close',command=dialog.destroy).pack(pady=10)

    def scene(self):
        return next((s for s in self.data['scenes'] if s['name']==self.scene_name.get()),None)

    def snapshot(self):
        return {n:v.json() for n,v in self.levels.items()}

    def save_scene(self):
        name=simpledialog.askstring('Save scene','Scene name:',parent=self.root)
        if not name:return
        try:
            if not self.levels:raise ValueError('Add at least one light')
            candidate=copy.deepcopy(self.data);candidate['scenes'].append({'name':name.strip(),'levels':self.snapshot()})
            self.persist(candidate);self.refresh_scenes();self.scene_name.set(name.strip())
        except Exception as e:self.error(e)

    def update_scene(self):
        scene=self.scene()
        if not scene:return
        if not messagebox.askyesno('Update scene','Replace this scene with the current base levels?',parent=self.root):return
        try:
            candidate=copy.deepcopy(self.data)
            next(s for s in candidate['scenes'] if s['name']==scene['name'])['levels']=self.snapshot()
            self.persist(candidate)
        except Exception as e:self.error(e)

    def delete_scene(self):
        scene=self.scene()
        if scene and messagebox.askyesno('Delete scene','Delete this saved scene?',parent=self.root):
            try:
                candidate=copy.deepcopy(self.data);candidate['scenes']=[s for s in candidate['scenes'] if s['name']!=scene['name']]
                self.persist(candidate);self.scene_name.set('');self.refresh_scenes()
            except Exception as e:self.error(e)

    def recall(self,fade):
        scene=self.scene()
        if not scene:return
        try:
            end={n:Level(**v) for n,v in scene['levels'].items() if n in self.levels}
            if not end:raise ValueError('None of this scene’s lights are configured')
            was_blackout=self.blackout
            start={n:Level(self.levels[n].kelvin,0) if was_blackout else self.levels[n] for n in end}
            transition=Transition(start,end,float(self.scene_seconds.get()),time.monotonic()) if fade else None
            self.stop(quiet=True)
            if was_blackout:
                self.blackout=False
                self.blackout_button.configure(text='BLACKOUT')
            if fade:
                self.transition=transition
                for n,v in start.items():self.update_card(n,v)
            else:
                for n,v in end.items():self.update_card(n,v)
                self.send(end)
            if was_blackout:self.send(list(self.levels))
            self.scene_last.configure(text=f'Last recalled: {scene["name"]}')
            missing=set(scene['levels'])-set(end)
            self.status.set(f'Scene {scene["name"]}: {len(end)} targets; {len(missing)} missing; other lights unchanged')
        except Exception as e:self.error(e)

    def edit_presets(self):
        dialog=tk.Toplevel(self.root);dialog.title('Five persistent presets');dialog.transient(self.root)
        for col,text in enumerate(['Name','Kelvin','Brightness (blank = preserve)']):ttk.Label(dialog,text=text).grid(row=0,column=col,padx=8,pady=8)
        rows=[]
        for i,p in enumerate(self.data['presets'],1):
            values=[tk.StringVar(value=p['name']),tk.StringVar(value=str(p['kelvin'])),tk.StringVar(value='' if p['brightness'] is None else str(p['brightness']))]
            for col,v in enumerate(values):ttk.Entry(dialog,textvariable=v,width=24 if col==0 else 16).grid(row=i,column=col,padx=8,pady=4)
            rows.append(values)
        def save():
            try:
                candidate=copy.deepcopy(self.data)
                candidate['presets']=[{'name':n.get().strip(),'kelvin':int(k.get()),'brightness':int(b.get()) if b.get().strip() else None} for n,k,b in rows]
                self.persist(candidate);self.stop(quiet=True);self.draw_cards();dialog.destroy()
                self.status.set('Five presets saved · no light settings changed')
            except Exception as e:self.error(e)
        ttk.Button(dialog,text='Save presets',command=save).grid(row=6,column=2,pady=12)

    def stop(self,quiet=False):
        if self.transition is not None:self.ble.discard_pending()
        self.transition=None
        if hasattr(self,'effect_status'):self.effect_status.configure(text='Stopped · current base levels held')
        if not quiet:self.status.set('Transition stopped · already-sent Bluetooth packets cannot be recalled')

    def run_effect(self,mode):
        self.mode.set(mode)
        self.start_effect()

    def start_effect(self):
        try:
            if self.blackout:raise ValueError('Restore from blackout before starting a transition')
            names=self.selected()
            if not names:raise ValueError('Select at least one light')
            a=Level(int(self.start_k.get()),int(self.start_b.get()));b=Level(int(self.end_k.get()),int(self.end_b.get()))
            mode=self.mode.get()
            start={n:a for n in names};end={n:b for n in names}
            if mode=='Fade in':start={n:Level(self.levels[n].kelvin,0) for n in names};end={n:self.levels[n] for n in names}
            elif mode=='Fade out':start={n:self.levels[n] for n in names};end={n:Level(self.levels[n].kelvin,0) for n in names}
            self.transition=Transition(start,end,float(self.duration.get()),time.monotonic(),int(self.repeats.get()),self.bounce.get() or mode=='Breathing',float(self.hold.get()))
            for n,v in start.items():self.update_card(n,v)
            self.send(names)
            self.status.set(f'{mode} started for {len(names)} selected lights')
        except Exception as e:self.error(e)

    def tick(self):
        if self.transition:
            levels,done=self.transition.sample(time.monotonic())
            changed=[]
            for n,v in levels.items():
                if self.levels[n]!=v:self.update_card(n,v);changed.append(n)
            if changed:self.send(changed)
            self.effect_status.configure(text='Complete' if done else 'Running · linear / quantized to device steps')
            if done:self.transition=None
        while True:
            try:kind,name,message=self.ble.events.get_nowait()
            except queue.Empty:break
            if kind in ('status','sent') and name in self.cards:self.cards[name]['state'].set(message)
            elif kind=='scan':self.add_dialog(message)
            elif kind=='ready':self.set_busy(False)
            elif kind=='error':self.status.set(f'Bluetooth: {message}')
        self.root.after(100,self.tick)

    def close(self):
        self.transition=None;self.ble.close()
        self.status.set('Closing Bluetooth connections…')
        self._close_deadline=time.monotonic()+7
        self._wait_close()

    def _wait_close(self):
        if not self.ble.thread.is_alive() or time.monotonic()>self._close_deadline:self.root.destroy()
        else:self.root.after(100,self._wait_close)


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--config',type=Path,default=Path('lamps.json'))
    parser.add_argument('--store',type=Path,help='Persistent presets/scenes; defaults to studio.json (preview-studio.json in preview)')
    parser.add_argument('--preview',action='store_true',help='Eight virtual lights; never access Bluetooth')
    args=parser.parse_args()
    if args.store is None:args.store=Path('preview-studio.json' if args.preview else 'studio.json')
    root=tk.Tk()
    try:
        Studio(root,args)
    except Exception as e:
        messagebox.showerror('Cannot open studio',str(e),parent=root);root.destroy();return 1
    root.mainloop()
    return 0

if __name__=='__main__':raise SystemExit(main())
