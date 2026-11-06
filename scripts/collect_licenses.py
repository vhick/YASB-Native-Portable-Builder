#!/usr/bin/env python3
"""Record installed dependency license metadata and legally provided license files.

Conservative: copy only files from installed Python distributions, never invent
license text. Output is additional attribution, not a legal compliance guarantee.
"""
from __future__ import annotations
import argparse
import hashlib
import importlib.metadata as meta
import json
from pathlib import Path
import re
import shutil

LICENSE_NAME = re.compile(r'(?i)^(?:licen[cs]e(?:[._-].*)?|copying(?:[._-].*)?|notice(?:[._-].*)?|copyright(?:[._-].*)?)$')


def main():
    p=argparse.ArgumentParser()
    p.add_argument('--out',type=Path,required=True)
    a=p.parse_args()
    a.out.mkdir(parents=True,exist_ok=False)
    manifest=[]
    for d in sorted(meta.distributions(),key=lambda d:(d.metadata.get('Name','').casefold(), d.version)):
        name=d.metadata.get('Name','unnamed')
        slug=re.sub('[^a-zA-Z0-9_.-]','_',name)[:80]
        record={'distribution':name,'version':d.version,'license_expression':d.metadata.get('License-Expression') or d.metadata.get('License') or 'UNKNOWN',
                'license_files':[],'license_file_paths':d.metadata.get_all('License-File') or []}
        for f in d.files or []:
            parts=f.parts
            if not parts or not LICENSE_NAME.match(parts[-1]):
                continue
            if len(parts)>6 or f.is_absolute() or '..' in parts:
                continue
            full=d.locate_file(f)
            if not full.is_file() or full.stat().st_size>3_000_000:
                continue
            blob=full.read_bytes()
            digest=hashlib.sha256(blob).hexdigest()
            target=a.out/slug/(digest[:12]+'-'+Path(parts[-1]).name)
            target.parent.mkdir(parents=True,exist_ok=True)
            if not target.exists():target.write_bytes(blob)
            record['license_files'].append({'file':str(target.relative_to(a.out)).replace('\\','/'),'sha256':digest})
        manifest.append(record)
    (a.out/'DEPENDENCY-LICENSE-MANIFEST.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(f'Collected license metadata for {len(manifest)} installed distributions; redistribution audit still required.')

if __name__=='__main__':main()
