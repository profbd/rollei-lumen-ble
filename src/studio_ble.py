"""Persistent BLE connections on a worker thread; Tk never touches this loop."""
import asyncio
import queue
import threading
from rollei_lumen import WRITE_UUID, NOTIFY_UUID, command


class StudioBLE:
    def __init__(self, preview=False):
        self.preview = preview
        self.events = queue.Queue()
        self.clients, self.pending = {}, {}
        self.closed = False
        self.loop = asyncio.new_event_loop()
        self.thread = threading.Thread(target=self._run, daemon=True)
        self.thread.start()

    def _run(self):
        asyncio.set_event_loop(self.loop)
        self.pump = self.loop.create_task(self._pump())
        self.loop.run_forever()
        self.loop.close()

    def emit(self, kind, name, message):
        self.events.put((kind, name, message))

    def submit(self, coroutine):
        if not self.closed:
            return asyncio.run_coroutine_threadsafe(coroutine, self.loop)
        coroutine.close()

    async def scan(self):
        try:
            if self.preview:
                names = [f'Magic-DEMO-{i+1}' for i in range(8)]
            else:
                from bleak import BleakScanner
                ads = await BleakScanner.discover(timeout=6, return_adv=True)
                names = [(a.local_name or d.name or '') for d, a in ads.values()]
                names = sorted({n for n in names if n.startswith('Magic-')})
            self.emit('scan', '', names)
        except Exception as e:
            self.emit('error', '', str(e))

    async def connect(self, names):
        """One scan, sequential connection setup. No settings sent on connection."""
        try:
            if self.preview:
                for name in names:
                    self.clients[name] = None
                    self.emit('status', name, 'Preview connected')
                return
            from bleak import BleakScanner, BleakClient
            ads = await BleakScanner.discover(timeout=6, return_adv=True)
            for name in names:
                if name in self.clients:
                    continue
                matches = [d for d, a in ads.values() if (a.local_name or d.name) == name]
                if len(matches) != 1:
                    self.emit('status', name, f'Not unique / not found ({len(matches)})')
                    continue
                client = BleakClient(matches[0], timeout=15,
                    disconnected_callback=lambda c, n=name: self._disconnected(n, c))
                try:
                    self.emit('status', name, 'Connecting…')
                    await client.connect()
                    write = client.services.get_characteristic(WRITE_UUID)
                    notify = client.services.get_characteristic(NOTIFY_UUID)
                    if not write or 'write-without-response' not in write.properties or not notify or 'notify' not in notify.properties:
                        raise ValueError('Expected FFC1/FFC2 interface missing')
                    await client.start_notify(notify, lambda c, d: None)
                    self.clients[name] = client
                    self.emit('status', name, 'Connected · no values sent')
                except asyncio.CancelledError:
                    await client.disconnect()
                    raise
                except Exception as e:
                    await client.disconnect()
                    self.emit('status', name, f'Connection failed: {e}')
        except Exception as e:
            self.emit('error', '', str(e))

    def _disconnected(self, name, client):
        if self.clients.get(name) is client:
            self.clients.pop(name, None)
            self.pending.pop(name, None)
            self.emit('status', name, 'Disconnected · reconnect manually')

    def set_levels(self, levels):
        # Coalesce on the event-loop thread. Never replay queued settings on reconnect.
        def update():
            for name, level in levels.items():
                if name in self.clients:
                    self.pending[name] = level
                else:
                    self.emit('status', name, 'Offline · draft only')
        if not self.closed:
            self.loop.call_soon_threadsafe(update)

    def discard_pending(self):
        if not self.closed:self.loop.call_soon_threadsafe(lambda: self.pending.clear())

    async def _write(self, name, level):
        if name not in self.clients:
            return
        try:
            if not self.preview:
                await asyncio.wait_for(self.clients[name].write_gatt_char(
                    WRITE_UUID, command(level.kelvin, level.brightness), response=False), timeout=2)
            self.emit('sent', name, f'{level.kelvin} K · {level.brightness}% sent')
        except Exception as e:
            self.pending.pop(name, None)
            client = self.clients.pop(name, None)
            if client:
                try:
                    await client.disconnect()
                except Exception:
                    pass
            self.emit('status', name, f'Write failed: {e}')

    async def _pump(self):
        while True:
            batch, self.pending = self.pending, {}
            await asyncio.gather(*(self._write(n, v) for n, v in batch.items()))
            await asyncio.sleep(.2)  # At most five updates per second per light.

    async def disconnect(self):
        self.pending.clear()
        clients, self.clients = self.clients, {}
        async def one(name, client):
            try:
                if client:
                    await asyncio.wait_for(client.disconnect(),timeout=3)
                self.emit('status', name, 'Disconnected')
            except Exception as e:
                self.emit('status', name, f'Disconnect warning: {e}')
        await asyncio.gather(*(one(n,c) for n,c in clients.items()))

    def close(self):
        if self.closed:
            return
        async def shutdown():
            others=[t for t in asyncio.all_tasks() if t is not asyncio.current_task()]
            for task in others:task.cancel()
            await asyncio.gather(*others, return_exceptions=True)
            await self.disconnect()
            self.loop.call_soon(self.loop.stop)
        self.submit(shutdown())
        self.closed = True
