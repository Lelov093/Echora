"""Small Windows DPAPI helper shared by bootstrap and runtime configuration."""

from __future__ import annotations

import base64
import ctypes
import json
import os
from ctypes import wintypes
from pathlib import Path


class LocalProtectedStoreError(Exception):
    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code


class _DATA_BLOB(ctypes.Structure):
    _fields_ = [("cbData", wintypes.DWORD), ("pbData", ctypes.POINTER(ctypes.c_byte))]


def protect_local_secret(value: str) -> str:
    if os.name != "nt":
        raise LocalProtectedStoreError(
            "LOCAL_SECRET_PROTECTION_UNAVAILABLE",
            "Protected local secret storage requires Windows DPAPI.",
        )
    raw = value.encode("utf-8")
    source_buffer = ctypes.create_string_buffer(raw)
    source = _DATA_BLOB(len(raw), ctypes.cast(source_buffer, ctypes.POINTER(ctypes.c_byte)))
    output = _DATA_BLOB()
    if not ctypes.windll.crypt32.CryptProtectData(
        ctypes.byref(source), None, None, None, None, 0, ctypes.byref(output)
    ):
        raise LocalProtectedStoreError(
            "LOCAL_SECRET_PROTECTION_FAILED",
            "Windows could not protect the secret.",
        )
    try:
        encrypted = ctypes.string_at(output.pbData, output.cbData)
        return base64.b64encode(encrypted).decode("ascii")
    finally:
        ctypes.windll.kernel32.LocalFree(output.pbData)


def unprotect_local_secret(value: str) -> str:
    if os.name != "nt":
        raise LocalProtectedStoreError(
            "LOCAL_SECRET_PROTECTION_UNAVAILABLE",
            "Protected local secret storage requires Windows DPAPI.",
        )
    encrypted = base64.b64decode(value)
    source_buffer = ctypes.create_string_buffer(encrypted)
    source = _DATA_BLOB(len(encrypted), ctypes.cast(source_buffer, ctypes.POINTER(ctypes.c_byte)))
    output = _DATA_BLOB()
    if not ctypes.windll.crypt32.CryptUnprotectData(
        ctypes.byref(source), None, None, None, None, 0, ctypes.byref(output)
    ):
        raise LocalProtectedStoreError(
            "LOCAL_SECRET_UNPROTECT_FAILED",
            "Windows could not unlock the local secret.",
        )
    try:
        return ctypes.string_at(output.pbData, output.cbData).decode("utf-8")
    finally:
        ctypes.windll.kernel32.LocalFree(output.pbData)


def read_local_protected_value(secret_path: Path, key: str) -> str | None:
    if not secret_path.exists():
        return None
    try:
        document = json.loads(secret_path.read_text(encoding="utf-8"))
        ciphertext = (document.get("values") or {}).get(key)
        if not isinstance(ciphertext, str) or not ciphertext:
            return None
        return unprotect_local_secret(ciphertext)
    except (OSError, ValueError, TypeError, json.JSONDecodeError, LocalProtectedStoreError):
        return None
