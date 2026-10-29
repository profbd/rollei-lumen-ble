"""Local BLE control for tested Rollei Lumen Pocket Bi-Color V2 lights."""
import argparse
import asyncio
import json
import sys
from pathlib import Path

WRITE_UUID = '0000ffc1-0000-1000-8000-00805f9b34fb'
NOTIFY_UUID = '0000ffc2-0000-1000-8000-00805f9b34fb'


def command(kelvin, brightness):
    """Encode the observed CCT frame; bounds are a conservative CLI policy."""
    if not 3200 <= kelvin <= 5500 or kelvin % 100:
        raise ValueError('Kelvin must be 3200..5500 in steps of 100')
    if not 0 <= brightness <= 100:
        raise ValueError('Brightness must be 0..100 percent')
    return bytes([0x28, 0, 0, 0, kelvin // 100, brightness, 0, 0x0f, 0x29])


def targets(args):
    if args.name:
        return [args.name]
    config = json.loads(args.config.read_text(encoding='utf-8'))
    lamps = config['lamps']
    if not isinstance(lamps, list) or not lamps:
        raise ValueError('Config must contain a nonempty lamps list')
    names, labels = [], []
    for lamp in lamps:
        name, label = lamp['name'], lamp['label']
        if not isinstance(name, str) or not name.strip() or not isinstance(label, str) or not label.strip():
            raise ValueError('Every lamp needs nonempty name and label strings')
        names.append(name)
        labels.append(label)
    if len(set(names)) != len(names) or len(set(labels)) != len(labels):
        raise ValueError('Config names and labels must be unique')
    if args.all:
        return names
    if args.label not in labels:
        raise ValueError(f'Unknown label: {args.label}')
    return [names[labels.index(args.label)]]


async def discover(name, timeout):
    from bleak import BleakScanner
    # Scan the full interval so duplicate advertised names cannot pick a random lamp.
    devices = await BleakScanner.discover(timeout=timeout, return_adv=True)
    matches = [d for d, a in devices.values() if (a.local_name or d.name) == name]
    if len(matches) != 1:
        raise ValueError(f'Expected exactly one device named {name}; found {len(matches)}')
    return matches[0]


async def operate(args, names):
    from bleak import BleakClient
    payload = command(args.kelvin, args.brightness) if args.action == 'set' else None
    for name in names:  # Explicit --all is sequential; it is not an atomic group update.
        device = await discover(name, args.timeout)
        async with BleakClient(device, timeout=args.timeout) as client:
            write = client.services.get_characteristic(WRITE_UUID)
            notify = client.services.get_characteristic(NOTIFY_UUID)
            if not write or 'write-without-response' not in write.properties:
                raise ValueError(f'{name}: expected writable FFC1 characteristic missing')
            if not notify or 'notify' not in notify.properties:
                raise ValueError(f'{name}: expected FFC2 notification characteristic missing')
            if payload is None:
                print(json.dumps({'name': name, 'services': [
                    {'uuid': s.uuid, 'characteristics': [
                        {'uuid': c.uuid, 'properties': c.properties} for c in s.characteristics]}
                    for s in client.services]}, indent=2))
                continue
            await client.start_notify(notify, lambda _c, _data: None)
            try:
                await client.write_gatt_char(write, payload, response=False)
                print(f'{name}: sent {args.kelvin} K / {args.brightness}% ({payload.hex()}); verify on light', flush=True)
                await asyncio.sleep(1)
            finally:
                await client.stop_notify(notify)


async def scan(args):
    from bleak import BleakScanner
    devices = await BleakScanner.discover(timeout=args.timeout, return_adv=True)
    for device, adv in devices.values():
        name = adv.local_name or device.name or ''
        if name.startswith('Magic-'):
            print(json.dumps({'name': name, 'rssi': adv.rssi}))
    # Magic is a discovery hint, not proof that a device is a compatible Rollei light.


def parser():
    p = argparse.ArgumentParser(description=__doc__)
    sub = p.add_subparsers(dest='action', required=True)
    s = sub.add_parser('scan', help='List Magic-* advertisements; does not change lights')
    s.add_argument('--timeout', type=float, default=8)
    for action in ('inspect', 'set'):
        s = sub.add_parser(action)
        choice = s.add_mutually_exclusive_group(required=True)
        choice.add_argument('--name', help='Exact advertised BLE name')
        choice.add_argument('--label', help='Label from local config')
        choice.add_argument('--all', action='store_true', help='Use every light in local config, sequentially')
        s.add_argument('--config', type=Path, default=Path('lamps.json'))
        s.add_argument('--timeout', type=float, default=8)
        if action == 'set':
            s.add_argument('--kelvin', type=int, required=True)
            s.add_argument('--brightness', type=int, required=True, help='0..100; 0 = light off')
            s.add_argument('--dry-run', action='store_true', help='Validate and print command without using Bluetooth')
    return p


def main(argv=None):
    p = parser()
    args = p.parse_args(argv)
    try:
        if not 0 < args.timeout <= 120:
            raise ValueError('Timeout must be >0 and <=120 seconds')
        if args.action == 'scan':
            asyncio.run(scan(args))
        else:
            names = targets(args)
            if args.action == 'set':
                payload = command(args.kelvin, args.brightness)
                if args.dry_run:
                    print(json.dumps({'names': names, 'hex': payload.hex(), 'bluetooth_used': False}))
                    return 0
            asyncio.run(operate(args, names))
    except (ValueError, KeyError, TypeError, OSError) as error:
        print(f'Error: {error}', file=sys.stderr)
        return 1
    except ImportError:
        print('Install dependencies first: python -m pip install .', file=sys.stderr)
        return 1
    except Exception as error:
        print(f'Bluetooth operation failed: {error}. Check permissions, power and other connected apps. Group updates may be partial.', file=sys.stderr)
        return 1
    except KeyboardInterrupt:
        return 130
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
