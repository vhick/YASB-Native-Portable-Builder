"""Read-only Komorebi UDS detection + discovery of a portable komorebic.exe.

YASB still uses its upstream named-pipe event subscription. The Komorebi daemon
speaks UDS for commands; we only connect to the UDS to detect liveness.
No Komorebi configuration, registration, or application files are changed.
"""
from __future__ import annotations
import ctypes
from ctypes import wintypes
import logging
import os
from pathlib import Path
import shutil
import socket
import time


def socket_path() -> Path | None:
    custom = os.getenv('YASB_KOMOREBI_SOCK_PATH', '').strip().strip('"')
    if custom:
        return Path(custom)
    local = os.getenv('LOCALAPPDATA')
    return Path(local) / 'komorebi' / 'komorebi.sock' if local else None


def socket_is_online(timeout: float = 0.25) -> bool:
    """Probe the local Unix-domain socket without sending any state-changing command."""
    path = socket_path()
    if not path or not path.exists() or not hasattr(socket, 'AF_UNIX'):
        return False
    try:
        with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as sock:
            sock.settimeout(timeout)
            sock.connect(str(path))
            return True
    except (OSError, ValueError):
        return False


class PROCESSENTRY32W(ctypes.Structure):
    _fields_ = [
        ('dwSize', wintypes.DWORD), ('cntUsage', wintypes.DWORD),
        ('th32ProcessID', wintypes.DWORD), ('th32DefaultHeapID', ctypes.c_size_t),
        ('th32ModuleID', wintypes.DWORD), ('cntThreads', wintypes.DWORD),
        ('th32ParentProcessID', wintypes.DWORD), ('pcPriClassBase', wintypes.LONG),
        ('dwFlags', wintypes.DWORD), ('szExeFile', wintypes.WCHAR * 260),
    ]


def _sibling_of_running_komorebi() -> str | None:
    """Locate komorebic.exe next to an actual running komorebi.exe without PATH edits."""
    if os.name != 'nt':
        return None
    k = ctypes.WinDLL('kernel32', use_last_error=True)
    k.CreateToolhelp32Snapshot.argtypes = (wintypes.DWORD, wintypes.DWORD)
    k.CreateToolhelp32Snapshot.restype = wintypes.HANDLE
    k.Process32FirstW.argtypes = (wintypes.HANDLE, ctypes.POINTER(PROCESSENTRY32W))
    k.Process32FirstW.restype = wintypes.BOOL
    k.Process32NextW.argtypes = (wintypes.HANDLE, ctypes.POINTER(PROCESSENTRY32W))
    k.Process32NextW.restype = wintypes.BOOL
    k.OpenProcess.argtypes = (wintypes.DWORD, wintypes.BOOL, wintypes.DWORD)
    k.OpenProcess.restype = wintypes.HANDLE
    k.QueryFullProcessImageNameW.argtypes = (wintypes.HANDLE, wintypes.DWORD, wintypes.LPWSTR, ctypes.POINTER(wintypes.DWORD))
    k.QueryFullProcessImageNameW.restype = wintypes.BOOL
    k.CloseHandle.argtypes = (wintypes.HANDLE,)
    k.CloseHandle.restype = wintypes.BOOL
    snap = k.CreateToolhelp32Snapshot(0x2, 0)
    invalid = ctypes.c_void_p(-1).value
    if snap in (None, invalid):
        return None
    try:
        pe = PROCESSENTRY32W()
        pe.dwSize = ctypes.sizeof(pe)
        okay = k.Process32FirstW(snap, ctypes.byref(pe))
        while okay:
            if pe.szExeFile.lower() == 'komorebi.exe':
                proc = k.OpenProcess(0x1000, False, pe.th32ProcessID)
                if proc:
                    try:
                        buf = ctypes.create_unicode_buffer(32768)
                        length = wintypes.DWORD(len(buf))
                        if k.QueryFullProcessImageNameW(proc, 0, buf, ctypes.byref(length)):
                            candidate = Path(buf.value).parent / 'komorebic.exe'
                            if candidate.is_file():
                                return str(candidate)
                    finally:
                        k.CloseHandle(proc)
            okay = k.Process32NextW(snap, ctypes.byref(pe))
    except (OSError, ValueError) as exc:
        logging.debug('Komorebi process discovery: %s', exc)
    finally:
        k.CloseHandle(snap)
    return None


_last_scan = 0.0
_last_found: str | None = None


def discover_komorebic(current: str = 'komorebic.exe') -> str:
    """Explicit override > running Komorebi sibling > existing full path > PATH.

    A disconnected socket is not automatically an error: portable Komorebi may
    expose a different socket location, which can be specified in Data/Config/.env.
    """
    global _last_scan, _last_found
    custom = os.getenv('YASB_KOMOREBIC_PATH', '').strip().strip('"')
    if custom and Path(custom).is_file() and Path(custom).name.lower() == 'komorebic.exe':
        return str(Path(custom).resolve())
    if current.lower() != 'komorebic.exe' and Path(current).is_file():
        return current
    now = time.monotonic()
    if now - _last_scan > 3:
        _last_scan = now
        _last_found = _sibling_of_running_komorebi()
    if _last_found and Path(_last_found).is_file():
        return _last_found
    return shutil.which('komorebic.exe') or current
