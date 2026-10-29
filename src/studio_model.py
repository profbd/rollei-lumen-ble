"""Hardware-independent studio state, scene storage and linear transitions."""
import json
import math
import os
import tempfile
from dataclasses import dataclass
from pathlib import Path
from rollei_lumen import command


@dataclass(frozen=True)
class Level:
    kelvin: int = 4000
    brightness: int = 20

    def __post_init__(self):
        if type(self.kelvin) is not int or type(self.brightness) is not int:
            raise ValueError('Levels must be integers')
        command(self.kelvin, self.brightness)

    def json(self):
        return {'kelvin': self.kelvin, 'brightness': self.brightness}


def interpolate(start, end, fraction):
    f = max(0, min(1, fraction))
    k = round((start.kelvin + (end.kelvin-start.kelvin)*f)/100)*100
    b = round(start.brightness + (end.brightness-start.brightness)*f)
    return Level(k, b)


def effective(level, master, blackout):
    if not math.isfinite(master) or not 0 <= master <= 100:
        raise ValueError('Master must be 0..100')
    return Level(level.kelvin, 0 if blackout else round(level.brightness*master/100))


class Transition:
    """One transition or repeated fade. Each cycle includes both endpoint holds."""
    def __init__(self, start, end, duration, now, repeats=1, bounce=False, hold=0):
        if not start or set(start) != set(end):
            raise ValueError('Transition endpoints must contain the same lights')
        if not all(math.isfinite(x) for x in (duration, now, hold)) or duration <= 0 or hold < 0:
            raise ValueError('Duration must be positive; hold cannot be negative')
        if type(repeats) is not int or repeats < 0:
            raise ValueError('Repeats must be a nonnegative integer; zero means continuous')
        self.start, self.end = dict(start), dict(end)
        self.duration, self.now = duration, now
        self.repeats, self.bounce, self.hold = repeats, bounce, hold

    def sample(self, now):
        elapsed = max(0, now-self.now)
        leg = self.duration+self.hold
        cycle = leg * (2 if self.bounce else 1)
        if self.repeats and elapsed >= cycle*self.repeats:
            return dict(self.start if self.bounce else self.end), True
        phase = elapsed % cycle
        reverse = self.bounce and phase >= leg
        fraction = min(1, (phase-leg if reverse else phase)/self.duration)
        if reverse:
            fraction = 1-fraction
        return {name: interpolate(self.start[name], self.end[name], fraction) for name in self.start}, False


def default_data():
    return {'version': 1, 'presets': [
        {'name': f'{k} K', 'kelvin': k, 'brightness': None}
        for k in (3200, 4000, 4500, 5000, 5500)], 'scenes': []}


def validate_data(data):
    if not isinstance(data, dict) or data.get('version') != 1:
        raise ValueError('Unsupported studio file version')
    if not isinstance(data.get('presets'), list) or len(data['presets']) != 5:
        raise ValueError('Studio file requires exactly five presets')
    for preset in data['presets']:
        if not isinstance(preset['name'], str) or not preset['name'].strip():
            raise ValueError('Preset names cannot be empty')
        Level(preset['kelvin'], 20 if preset['brightness'] is None else preset['brightness'])
    scenes = data.get('scenes')
    if not isinstance(scenes, list):
        raise ValueError('Scenes must be a list')
    scene_names = set()
    for scene in scenes:
        name = scene['name']
        if not isinstance(name, str) or not name.strip() or name in scene_names:
            raise ValueError('Scene names must be nonempty and unique')
        scene_names.add(name)
        if not isinstance(scene['levels'], dict) or not scene['levels']:
            raise ValueError('Scene needs at least one light')
        for device, level in scene['levels'].items():
            if not isinstance(device, str) or not device.strip():
                raise ValueError('Scene device names cannot be empty')
            Level(**level)
    return data


def load_data(path):
    return validate_data(json.loads(path.read_text(encoding='utf-8'))) if path.exists() else default_data()


def save_data(path, data):
    """Validate before replacing; a failed save preserves the previous file."""
    validate_data(data)
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary = tempfile.mkstemp(prefix=path.name+'.', dir=path.parent)
    try:
        with os.fdopen(fd, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
            f.write('\n')
            f.flush()
            os.fsync(f.fileno())
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)
