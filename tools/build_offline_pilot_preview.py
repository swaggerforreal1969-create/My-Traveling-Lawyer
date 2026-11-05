"""Build an inspectable, experimental offline-only Python pilot ZIP.

This is NOT an installer, a signed release, independent custody, or permission
to distribute missing restricted originals. It bundles only an explicit
transitive import closure from the already published experimental modules.
"""
from __future__ import annotations
import argparse
import ast
from hashlib import sha256
import json
from pathlib import Path
from zipfile import ZipFile, ZipInfo, ZIP_DEFLATED

ROOT = Path(__file__).resolve().parent.parent
ENTRY = 'offline_pilot'
ROOT_NAME = 'mtl-fictional-preview'
# These are not allowed into the fictional offline bundle.
FORBIDDEN = {
    # mobile_preview_gateway is an in-memory, script-free renderer; it has\n    # no listener or network transport and is part of the real local path.\n    'server', 'legacy_server_DISABLED', 'readiness_loopback_http',
    'readiness_json_http',
    'ai_outbound_boundary', 'pinned_https_custody_adapter',
    'v2_custody_transport',
}
LAUNCHER = r'''"""Run only the locally extracted, fictional offline preview."""
import hashlib
import json
from pathlib import Path
import sys

BASE = Path(__file__).resolve().parent
manifest = json.loads((BASE / 'MANIFEST.json').read_text(encoding='utf-8'))
if manifest.get('purpose') != 'FICTIONAL OFFLINE PREVIEW':
    raise SystemExit('Pilot integrity denied: unrecognized purpose')
expected = manifest.get('sha256', {})
if not isinstance(expected, dict) or not expected:
    raise SystemExit('Pilot integrity denied: empty manifest')
for name, digest in sorted(expected.items()):
    parts = Path(name)
    if (parts.is_absolute() or '..' in parts.parts
            or parts.suffix != '.py'
            or (parts.parts[0] != 'src' or len(parts.parts) != 2)):
        raise SystemExit('Pilot integrity denied: unexpected source path')
    file = BASE / parts
    if file.is_symlink() or not file.is_file():
        raise SystemExit('Pilot integrity denied: missing or linked source')
    if hashlib.sha256(file.read_bytes()).hexdigest() != digest:
        raise SystemExit('Pilot integrity denied: published source changed')
actual = {str(p.relative_to(BASE)).replace('\\', '/')
          for p in (BASE / 'src').iterdir() if p.is_file()}
if actual != set(expected):
    raise SystemExit('Pilot integrity denied: unexpected source content')
print('FICTIONAL OFFLINE PREVIEW; not for real legal work', file=sys.stderr)
if len(sys.argv) == 2 and sys.argv[1] == '--verify':
    print('Local pilot package SHA-256 check: PASS')
else:
    from src.offline_pilot import main
    raise SystemExit(main())
'''


def dependencies(module: str) -> set[str]:
    file = ROOT / 'src' / (module + '.py')
    if not file.is_file():
        raise ValueError('Unpublished or absent required module: ' + module)
    tree = ast.parse(file.read_text(encoding='utf-8'), filename=str(file))
    names = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom):
            if node.level and node.module:
                names.add(node.module.split('.')[0])
            elif node.level and not node.module:
                for alias in node.names:
                    names.add(alias.name.split('.')[0])
            elif node.module and node.module.startswith('src.'):
                names.add(node.module.split('.')[1])
        elif isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name.startswith('src.'):
                    names.add(alias.name.split('.')[1])
    # Package-level imports can include non-module names (symbols). Only
    # candidate imports from src count; do NOT invent absent protected files.
    return {n for n in names if (ROOT / 'src' / (n + '.py')).is_file()}


def collect() -> dict[str, bytes]:
    pending = [ENTRY, 'local_operator_gui', 'private_attorney_operator']
    visited = set()
    while pending:
        name = pending.pop()
        if name in visited:
            continue
        if name in FORBIDDEN or name.endswith('_http'):
            raise ValueError('Network or disabled module prohibited: ' + name)
        visited.add(name)
        pending.extend(sorted(dependencies(name) - visited))
    result = {}
    for name in sorted(visited):
        path = ROOT / 'src' / (name + '.py')
        if path.is_symlink():
            raise ValueError('Symlinked source prohibited: ' + name)
        result['src/' + name + '.py'] = path.read_bytes()
    return result


def build(output: Path) -> dict:
    output = Path(output)
    if output.exists() or output.is_symlink():
        raise FileExistsError('Refusing to overwrite existing pilot archive')
    if not output.parent.is_dir():
        raise FileNotFoundError('Destination folder missing')
    source = collect()
    manifest = {'purpose': 'FICTIONAL OFFLINE PREVIEW',
                'source_count': len(source),
                'sha256': {k: sha256(v).hexdigest() for k,v in sorted(source.items())},
                'independent_security_approval': False,
                'production_use': False}
    assets = {'run_pilot.py': LAUNCHER.encode('utf-8'),
              'start_pilot.py': (ROOT / 'tools' / 'portable_desktop_start.py').read_bytes(),
              'MANIFEST.json': (json.dumps(manifest,sort_keys=True,indent=2)+'\n').encode(),
              'README.txt': (
                 'FICTIONAL OFFLINE PREVIEW ONLY — NO CLIENT INFORMATION.\n'
                 'Python 3.11+ and working Tk installation required.\n'
                 'Extract the ZIP locally, do not run it within the archive.\n'
                 'Check integrity: python run_pilot.py --verify\n'
                 'Interactive start: python start_pilot.py\n'
                 'Setup: python run_pilot.py init --database new-fictional.sqlite3\n'
                 'Open: python run_pilot.py open --database new-fictional.sqlite3\n'
                 'Token is entered hidden; keep it out of logs and chats.\n'
                 'No public deployment, external provider, custody claim or real matter.\n'
                 'This incomplete experimental distribution does not pass the\n'
                 'original 42-file release gate or independent review.\n'
              ).encode('utf-8'),
              **source}
    # Exclusive creation protects an existing package. No user state or
    # credentials are ever included; timestamps are deterministic.
    with output.open('xb') as handle:
        with ZipFile(handle, 'w', compression=ZIP_DEFLATED) as archive:
            for name,data in sorted(assets.items()):
                info=ZipInfo(ROOT_NAME+'/'+name, date_time=(2020,1,1,0,0,0))
                info.compress_type=ZIP_DEFLATED
                info.external_attr=0o644 << 16
                archive.writestr(info,data)
    return {'archive_sha256': sha256(output.read_bytes()).hexdigest(),
            'source_count': len(source), 'archive': str(output)}


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args(argv)
    print(json.dumps(build(args.output),sort_keys=True))


if __name__ == '__main__':
    main()
