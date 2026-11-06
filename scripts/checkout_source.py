#!/usr/bin/env python3
"""Clone exact upstream tag and fail if it does not match GitHub's published commit."""
import argparse
import json
from pathlib import Path
import re
import subprocess


def run(*args, cwd=None):
    p = subprocess.run(list(args), cwd=cwd, capture_output=True, encoding='utf-8', check=True)
    return p.stdout.strip()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--identity', type=Path, required=True)
    ap.add_argument('--out', type=Path, required=True)
    args = ap.parse_args()
    record = json.loads(args.identity.read_text(encoding='utf-8'))
    tag, expected = record['tag'], record['upstream_commit']
    if not re.fullmatch(r'v?\d+\.\d+\.\d+', tag) or not re.fullmatch('[a-f0-9]{40}', expected):
        raise RuntimeError('Invalid source version or SHA')
    if args.out.exists():
        raise FileExistsError('Refusing to reuse a previous checkout: ' + str(args.out))
    args.out.parent.mkdir(parents=True, exist_ok=True)
    run('git', 'clone', '--depth', '1', '--branch', tag, '--single-branch', '--',
        'https://github.com/amnweb/yasb.git', str(args.out))
    got = run('git', 'rev-parse', 'HEAD', cwd=args.out)
    if got.lower() != expected:
        raise RuntimeError(f'Upstream commit mismatch: API={expected}, checkout={got}')
    # Protect build integrity: dependency and source are from the same verified checkout.
    for name in ('pyproject.toml', 'src/settings.py', 'src/build.py', 'src/main.py', 'LICENSE'):
        if not (args.out / name).is_file():
            raise RuntimeError('Required upstream file absent: ' + name)
    print(f'Verified source checkout: {tag} {got}')

if __name__ == '__main__':
    main()
