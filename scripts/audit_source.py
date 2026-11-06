#!/usr/bin/env python3
"""Generate source-wide host-path evidence report; flag drift without altering host files.

This is only a static risk index, NOT proof of runtime write containment.
"""
import argparse
from pathlib import Path
import json
import re

PATTERNS = {
    'windows_profile_path_reference': re.compile(r'(?i)LOCALAPPDATA|APPDATA|ProgramData|USERPROFILE|os\.path\.expanduser|Path\.home|QStandardPaths|\.config[\\/]'),
    'shell_registration_reference': re.compile(r'(?i)winreg|CreateShortcut|Start.Menu|startup|AppUserModelId|CLS[Ii]D|schtasks|shell:startup'),
    'external_process_reference': re.compile(r'(?i)subprocess\.|QProcess\.|os\.system\('),
}

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--source', type=Path, required=True)
    ap.add_argument('--out', type=Path, required=True)
    a = ap.parse_args()
    findings=[]
    for p in sorted((a.source/'src').rglob('*.py')):
        for i,line in enumerate(p.read_text(encoding='utf-8',errors='replace').splitlines(),1):
            if line.lstrip().startswith('#'):
                continue
            for category,pat in PATTERNS.items():
                if pat.search(line):
                    findings.append({'kind':category,'file':str(p.relative_to(a.source)).replace('\\','/'),'line':i,'excerpt':line.strip()[:250]})
    a.out.parent.mkdir(parents=True,exist_ok=True)
    a.out.write_text(json.dumps(findings,indent=2,ensure_ascii=False)+'\n', encoding='utf-8')
    print(f'Source review index: {len(findings)} matches; inspect for additional app-owned writes before claiming full portability.')

if __name__ == '__main__':
    main()
