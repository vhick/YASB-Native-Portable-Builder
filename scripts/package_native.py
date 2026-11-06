#!/usr/bin/env python3
"""Stage real source-built cx_Freeze binaries and make an independent native ZIP."""
from __future__ import annotations
import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import struct
import zipfile

REQUIRED_EXES = ['yasb.exe','yasbc.exe','yasb_themes.exe','yasb_cloud.exe']
FORBIDDEN_NATIVE = ['App/AppInfo/appinfo.ini','App/DefaultData','AppNamePortable.exe','Other/Source','Data/TraceGuard']


def sha256(path):
    digest=hashlib.sha256()
    with open(path,'rb') as stream:
        for b in iter(lambda: stream.read(1024*1024),b''):
            digest.update(b)
    return digest.hexdigest()


def machine(path: Path):
    with path.open('rb') as handle:
        hdr=handle.read(64)
        if len(hdr)<64 or hdr[:2]!=b'MZ':
            raise ValueError('Not a Windows PE executable: '+str(path))
        offset=struct.unpack_from('<I',hdr,0x3c)[0]
        if offset<64 or offset>path.stat().st_size-24:
            raise ValueError('Invalid PE offset: '+str(path))
        handle.seek(offset)
        if handle.read(4)!=b'PE\x00\x00':
            raise ValueError('Missing PE signature: '+str(path))
        return struct.unpack('<H',handle.read(2))[0]


def validate(stage: Path):
    for exe in REQUIRED_EXES:
        path=stage/exe
        if not path.is_file() or machine(path)!=0x8664:
            raise ValueError(f'{exe} absent or not a compiled x64 Windows PE')
    if not (stage/'lib').is_dir():
        raise ValueError('cx_Freeze lib folder missing')
    if not (stage/'lib'/'library.zip').is_file():
        raise ValueError('cx_Freeze Python library.zip missing')
    if not (stage/'assets'/'images'/'app_icon.png').is_file():
        raise ValueError('YASB icon asset missing')
    for p in ('Data/Config','Data/State','LICENSES','SOURCE-IDENTITY.json','UPSTREAM-PATCHES.json','DEPENDENCIES-PINNED.txt','LICENSES/DEPENDENCY-LICENSE-MANIFEST.json'):
        if not (stage/p).exists():
            raise ValueError('Required native package entry missing: '+p)
    for p in FORBIDDEN_NATIVE:
        if (stage/p).exists():
            raise ValueError('Wrong-mode PortableApps content: '+p)
    forbidden = [p for p in stage.rglob('*.msi')]
    if forbidden:
        raise ValueError('MSI installer included in native package')


def package(args):
    if args.stage.exists():
        raise FileExistsError('Refusing to overwrite existing staging: '+str(args.stage))
    frozen = args.upstream/'src'/'dist'
    if not frozen.is_dir():
        raise FileNotFoundError('cx_Freeze did not produce src/dist: '+str(frozen))
    shutil.copytree(frozen,args.stage)
    for folder in ('Data/Config','Data/State','LICENSES'):
        (args.stage/folder).mkdir(parents=True,exist_ok=True)
    identity=json.loads(args.identity.read_text(encoding='utf-8'))
    (args.stage/'SOURCE-IDENTITY.json').write_text(json.dumps(identity,indent=2)+'\n',encoding='utf-8')
    shutil.copy2(args.patch_manifest,args.stage/'UPSTREAM-PATCHES.json')
    shutil.copy2(args.audit,args.stage/'SOURCE-STATIC-AUDIT.json')
    shutil.copy2(args.pip_freeze,args.stage/'DEPENDENCIES-PINNED.txt')
    shutil.copytree(args.licenses,args.stage/'LICENSES'/'Dependencies',dirs_exist_ok=True)
    shutil.copy2(args.licenses/'DEPENDENCY-LICENSE-MANIFEST.json',args.stage/'LICENSES'/'DEPENDENCY-LICENSE-MANIFEST.json')
    shutil.copy2(args.upstream/'LICENSE',args.stage/'LICENSES'/'YASB-MIT-LICENSE.txt')
    (args.stage/'README.txt').write_text('''YASB Native Portable (unofficial source-built application)\n\n1. Run yasb.exe DIRECTLY. Do not run any MSI or installer.\n2. Edit Data\\Config\\config.yaml and Data\\Config\\styles.css after first-run wizard.\n3. All known YASB-owned config, logs and state are redirected in source\n   under Data\\Config and Data\\State. Never delete the Data folder.\n4. Optional Komorebi: starts/disconnects independently, detected via SOCK\n   and matching running komorebi.exe. Events remain on YASB named pipes.\n   For nonstandard paths set YASB_KOMOREBIC_PATH and\n   YASB_KOMOREBI_SOCK_PATH in Data\\Config\\.env.\n5. Keep all runtime folders and DLLs beside yasb.exe.\n6. Upgrade: fully exit YASB; back up entire folder; replace everything\n   EXCEPT Data; do not overwrite Data or a running executable.\n7. The bundled yasbc.exe supports start/stop/reload and an opt-in HKCU
   startup entry. Global-force-stop, installed-MSI update/channel switching,
   reset, task-based startup and machine-wide crash-dump commands are blocked.
   Disable startup before moving; if already moved, repair manually after
   verifying ownership. Do not overwrite another startup entry.
8. Cloud session/vault files live in Data/State/cloud, but DPAPI binds
   encrypted credentials to the original Windows account/machine. Moving
   to another PC may require signing in again. Cloud optional scheduled
   backups create an intentional Windows task only if user opts in.
9. This build is unsigned, unofficial, not certified and untested in a\n   live interactive Windows desktop until you perform acceptance tests.\n10. Windows may independently store OS-managed caches, toast, clipboard,\n   credential-vault and Explorer state. Optional third-party widgets may\n   create their own files outside YASB's Data folder.\n''',encoding='utf-8')
    validate(args.stage)
    manifest={}
    for path in sorted(args.stage.rglob('*')):
        if path.is_file():
            manifest[path.relative_to(args.stage).as_posix()]=sha256(path)
    (args.stage/'FILE-SHA256.json').write_text(json.dumps(manifest,indent=2)+'\n',encoding='utf-8')
    args.output.parent.mkdir(parents=True,exist_ok=True)
    with zipfile.ZipFile(args.output,'w',compression=zipfile.ZIP_DEFLATED,compresslevel=6,allowZip64=True) as z:
        for folder in ('Data/','Data/Config/','Data/State/'):
            z.writestr(args.stage.name+'/'+folder,'')
        for path in sorted(args.stage.rglob('*')):
            if path.is_file():
                z.write(path,(Path(args.stage.name)/path.relative_to(args.stage)).as_posix())
    verify_zip(args.output,args.stage.name)
    print('READY_NATIVE_ZIP: '+str(args.output))
    print('SHA256: '+sha256(args.output))
    print('WARNING: desktop startup/profile containment still require manual Windows validation.')


def verify_zip(path:Path, name:str):
    with zipfile.ZipFile(path) as z:
        if z.testzip():
            raise RuntimeError('ZIP integrity error')
        entries=set(z.namelist())
        if len(entries)!=len(z.namelist()):
            raise ValueError('Duplicate archive members')
        for exe in REQUIRED_EXES:
            if name+'/'+exe not in entries:
                raise ValueError('Missing exe from ZIP: '+exe)
        if name+'/Data/Config/' not in entries or name+'/Data/State/' not in entries:
            raise ValueError('Empty portable Data directories not preserved')
        if any('..' in Path(x).parts for x in entries):
            raise ValueError('Unsafe archive member')
        for bad in ('appinfo.ini','Portable.exe','.paf.exe'):
            if any(item.endswith(bad) for item in entries):
                raise ValueError('PortableApps/installer entry in native archive')
        for exe in REQUIRED_EXES:
            blob=z.read(name+'/'+exe)
            if blob[:2]!=b'MZ':
                raise ValueError('PE missing in ZIP: '+exe)
    return True


def main():
    p=argparse.ArgumentParser()
    p.add_argument('--upstream',type=Path,required=True)
    p.add_argument('--identity',type=Path,required=True)
    p.add_argument('--patch-manifest',type=Path,required=True)
    p.add_argument('--audit',type=Path,required=True)
    p.add_argument('--pip-freeze',type=Path,required=True)
    p.add_argument('--licenses',type=Path,required=True)
    p.add_argument('--stage',type=Path,required=True)
    p.add_argument('--output',type=Path,required=True)
    a=p.parse_args()
    package(a)

if __name__=='__main__':
    main()
