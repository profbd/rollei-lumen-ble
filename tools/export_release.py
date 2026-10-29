"""Create a public source ZIP from an explicit allowlist; never publishes it."""
import hashlib
import json
import re
import zipfile
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
FILES=[
    '.github/ISSUE_TEMPLATE/bug_report.yml','docs/RELEASE-NOTES.md','Start Studio.command','README.md','LICENSE','CHANGELOG.md','CONTRIBUTING.md','.gitignore',
    'pyproject.toml','requirements-macos.lock.txt',
    'src/rollei_lumen.py','src/analyze_capture.py',
    'src/studio_model.py','src/studio_ble.py','src/studio_gui.py',
    'docs/images/studio-three-lights.png','docs/DEVELOPMENT.md','docs/STUDIO.md','docs/PROTOCOL.md','docs/TESTING.md','docs/CAPTURE.md','docs/RELEASING.md',
    'examples/lamps.example.json','tests/test_control.py','tests/test_capture.py',
    'tests/test_studio.py','tools/gui_smoke.py',
    'tools/export_release.py','.github/workflows/tests.yml',
]


def main():
    content={}
    for name in FILES:
        path=ROOT/name
        if path.is_symlink():raise ValueError(f'Symlinks are not allowed: {name}')
        data=path.read_bytes()
        if path.suffix == '.png':
            if not data.startswith(b'\x89PNG\r\n\x1a\n'):raise ValueError('Invalid PNG screenshot')
            content[name]=data
            continue
        text=data.decode('utf-8')
        if re.search(r'Magic-[0-9a-fA-F]{12}|/[U]sers/|/[V]olumes/|[0-9a-fA-F]{8}(?:-[0-9a-fA-F]{4}){3}-[0-9a-fA-F]{12}',text):
            # Standard GATT UUIDs are public protocol constants, not local IDs.
            cleaned=re.sub(r'[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-1000-8000-00805f9b34fb','',text)
            if re.search(r'Magic-[0-9a-fA-F]{12}|/[U]sers/|/[V]olumes/|[0-9a-fA-F]{8}(?:-[0-9a-fA-F]{4}){3}-[0-9a-fA-F]{12}',cleaned):
                raise ValueError(f'Possible local identifier/path in {name}')
        content[name]=data
    release=ROOT/'release';release.mkdir(exist_ok=True)
    archive=release/'rollei-lumen-ble-0.2.0-source.zip'
    manifest={name:hashlib.sha256(data).hexdigest() for name,data in content.items()}
    with zipfile.ZipFile(archive,'w',zipfile.ZIP_DEFLATED) as z:
        for name,data in content.items():
            entry=zipfile.ZipInfo('rollei-lumen-ble/'+name)
            entry.compress_type=zipfile.ZIP_DEFLATED
            entry.external_attr=(0o100755 if name.endswith('.command') else 0o100644)<<16
            z.writestr(entry,data)
        z.writestr('rollei-lumen-ble/SOURCE-MANIFEST.json',json.dumps(manifest,indent=2)+'\n')
    with zipfile.ZipFile(archive) as z:
        assert z.testzip() is None
        assert len(z.namelist())==len(FILES)+1
    print(f'Created {archive.name}: {len(FILES)} allowlisted source files plus hash manifest')
    print('SHA256',hashlib.sha256(archive.read_bytes()).hexdigest())

if __name__=='__main__':main()
