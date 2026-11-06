#!/usr/bin/env python3
"""Resolve real stable YASB GitHub Releases and immutable tag commit identity."""
from __future__ import annotations
import argparse
import json
import os
from pathlib import Path
import re
import subprocess
import urllib.error
import urllib.request

API = 'https://api.github.com/repos/amnweb/yasb'
STABLE = re.compile(r'^v?(\d+)\.(\d+)\.(\d+)$')
HEX = re.compile(r'^[a-f0-9]{40}$')


def request(endpoint: str, missing_ok=False):
    req = urllib.request.Request(API + endpoint, headers={
        'Accept': 'application/vnd.github+json',
        'User-Agent': 'YASB-NativePortable-Builder',
        **({'Authorization': 'Bearer ' + os.environ['GITHUB_TOKEN']} if os.getenv('GITHUB_TOKEN') else {}),
        'X-GitHub-Api-Version': '2022-11-28',
    })
    try:
        with urllib.request.urlopen(req, timeout=35) as r:
            return json.load(r)
    except urllib.error.HTTPError as exc:
        if exc.code == 404 and missing_ok:
            return None
        raise RuntimeError(f'GitHub API error HTTP {exc.code} at {endpoint}') from exc


def releases():
    for page in range(1, 11):
        batch = request(f'/releases?per_page=100&page={page}')
        if not isinstance(batch, list):
            raise RuntimeError('GitHub Releases API did not return a list')
        yield from batch
        if len(batch) < 100:
            break
    else:
        raise RuntimeError('More than 1000 releases; refusing incomplete stable version sorting')


def choose(tag: str):
    candidates = []
    for release in releases():
        t = release.get('tag_name', '')
        match = STABLE.fullmatch(t)
        if not match or release.get('draft') or release.get('prerelease'):
            continue
        candidates.append((tuple(map(int, match.groups())), release))
    if not candidates:
        raise RuntimeError('No suitable published stable release')
    if tag == 'latest':
        return max(candidates, key=lambda r: r[0])[1]
    found = [r for _, r in candidates if r['tag_name'].lstrip('v') == tag.lstrip('v')]
    if len(found) != 1:
        raise RuntimeError(f'Tag {tag!r} is not a published stable release')
    return found[0]


def resolve_tag_commit(tag: str):
    ref = request('/git/ref/tags/' + tag)
    obj = ref['object']
    for _ in range(3):
        if obj['type'] == 'commit':
            sha = obj['sha'].lower()
            if not HEX.fullmatch(sha):
                raise ValueError('Invalid upstream SHA')
            return sha
        if obj['type'] != 'tag':
            raise RuntimeError(f'Unexpected Git tag object type: {obj["type"]}')
        obj = request('/git/tags/' + obj['sha'])['object']
    raise RuntimeError('Cannot peel nested upstream tags safely')


def verify_css_sha(sha: str) -> str:
    """Prove an explicitly requested SHA is in the official CSS repository."""
    url = 'https://api.github.com/repos/Video-Nomad/qt-css-engine/commits/' + sha
    req = urllib.request.Request(url, headers={
        'Accept': 'application/vnd.github+json',
        'User-Agent': 'YASB-NativePortable-Builder',
        **({'Authorization': 'Bearer ' + os.environ['GITHUB_TOKEN']} if os.getenv('GITHUB_TOKEN') else {}),
    })
    try:
        with urllib.request.urlopen(req, timeout=30) as response:
            data = json.load(response)
    except urllib.error.HTTPError as error:
        raise RuntimeError(f'CSS source commit could not be verified: HTTP {error.code}') from error
    if data.get('sha','').lower() != sha:
        raise RuntimeError('CSS commit API returned another SHA')
    return sha


def css_commit(requested: str):
    if requested and requested.lower() != 'auto':
        if not HEX.fullmatch(requested.lower()):
            raise ValueError('css-sha must be exactly 40 hex characters')
        return verify_css_sha(requested.lower())
    result = subprocess.run(['git', 'ls-remote', '--exit-code', 'https://github.com/Video-Nomad/qt-css-engine.git',
        'refs/heads/dev'], capture_output=True, encoding='utf-8', check=True)
    sha = result.stdout.strip().split()[0].lower()
    if not HEX.fullmatch(sha):
        raise ValueError('Could not resolve immutable qt-css-engine commit')
    return verify_css_sha(sha)


def resolve(selection: str, css: str, revision: str, builder_commit: str):
    release = choose(selection)
    tag = release['tag_name']
    upstream = resolve_tag_commit(tag)
    css = css_commit(css)
    if not re.fullmatch(r'r[1-9]\d*', revision):
        raise ValueError('Revision must be r1, r2, etc.')
    version = tag.lstrip('v')
    builder_suffix = re.sub(r'[^a-f0-9]', '', builder_commit.lower())[:10] if HEX.fullmatch(builder_commit.lower()) else 'local'
    release_tag = f'portable-yasb-native-v{version}-{revision}-{upstream[:10]}-css{css[:10]}-b{builder_suffix}'
    return {
        'mode': 'NATIVE', 'upstream_repository': 'amnweb/yasb', 'tag': tag,
        'version': version, 'upstream_commit': upstream,
        'css_engine_repository': 'Video-Nomad/qt-css-engine', 'css_engine_commit': css,
        'builder_commit': builder_commit,
        'package_revision': revision, 'release_tag': release_tag,
        'python': '3.14', 'architecture': 'x64',
        'source_release_url': release['html_url'], 'source_release_id': release['id'],
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--version', default='latest')
    ap.add_argument('--css-sha', default='auto')
    ap.add_argument('--revision', default='r2')
    ap.add_argument('--out', type=Path, required=True)
    a = ap.parse_args()
    builder = os.environ.get('GITHUB_SHA', 'local-uncommitted')
    record = resolve(a.version.strip(), a.css_sha.strip(), a.revision, builder)
    a.out.parent.mkdir(parents=True, exist_ok=True)
    a.out.write_text(json.dumps(record, indent=2) + '\n', encoding='utf-8')
    outputs = os.environ.get('GITHUB_OUTPUT')
    if outputs:
        with open(outputs, 'a', encoding='utf-8', newline='\n') as f:
            for k in ('tag', 'version', 'upstream_commit', 'css_engine_commit', 'release_tag'):
                f.write(k + '=' + str(record[k]) + '\n')
    print('Resolved: ' + json.dumps(record, indent=2))

if __name__ == '__main__':
    main()
