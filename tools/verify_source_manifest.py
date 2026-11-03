"""Fail-closed immutable source acceptance: original v1.4 files only.

Usage: python tools/verify_source_manifest.py [repository-root]
Requires SOURCE_V14_SHA256.json in repository root.
"""
from __future__ import annotations
import hashlib
import json
import sys
from pathlib import Path


def verify(root: Path) -> list[str]:
    root = root.resolve()
    manifest = json.loads((root / 'SOURCE_V14_SHA256.json').read_text(encoding='utf-8'))
    if manifest.get('schema') != 'mtl-source-v14-sha256-v1':
        raise ValueError('Unsupported manifest schema')
    files = manifest['files']
    if len(files) != 42 or len(set(files)) != 42:
        raise ValueError('Expected exactly 42 unique original files')
    errors = []
    for name, expected in sorted(files.items()):
        target = root / name
        if Path(name).is_absolute() or '..' in Path(name).parts or target.is_symlink() or not target.is_file():
            errors.append(f'{name}: missing/unsafe file')
            continue
        if not isinstance(expected, str) or len(expected) != 64 or any(c not in '0123456789abcdef' for c in expected):
            errors.append(f'{name}: invalid digest')
            continue
        if hashlib.sha256(target.read_bytes()).hexdigest() != expected:
            errors.append(f'{name}: SHA-256 mismatch')
    return errors


def main() -> int:
    root = Path(sys.argv[1]) if len(sys.argv) > 1 else Path.cwd()
    try:
        errors = verify(root)
    except (OSError, ValueError, TypeError, KeyError, json.JSONDecodeError) as exc:
        print(f'SOURCE ACCEPTANCE FAILED: {type(exc).__name__}: {exc}')
        return 1
    if errors:
        print('SOURCE ACCEPTANCE FAILED:')
        print('\n'.join(errors))
        return 1
    print('SOURCE ACCEPTANCE PASSED: 42/42 SHA-256 matches preserved v1.4 archive')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())