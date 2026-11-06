"""Read-only source-side check of the native YASB instance mutex.

Never kill a process by basename or inspect/alter an installed YASB.
"""
from __future__ import annotations
import ctypes
from ctypes import wintypes
import os

MUTEX_NAME = "yasb_native_portable"

def native_instance_running() -> bool:
    if os.name != 'nt':
        return False
    kernel = ctypes.WinDLL('kernel32', use_last_error=True)
    kernel.OpenMutexW.argtypes = (wintypes.DWORD, wintypes.BOOL, wintypes.LPCWSTR)
    kernel.OpenMutexW.restype = wintypes.HANDLE
    kernel.CloseHandle.argtypes = (wintypes.HANDLE,)
    kernel.CloseHandle.restype = wintypes.BOOL
    # SYNCHRONIZE access: read-only open, not a state-changing CreateMutex.
    h = kernel.OpenMutexW(0x00100000, False, MUTEX_NAME)
    if h:
        kernel.CloseHandle(h)
        return True
    return False
