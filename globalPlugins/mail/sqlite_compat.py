# -*- coding: utf-8 -*-
"""NVDA sqlite3 modulu sunmadiginda paketlenmis CPython surucusunu yukler."""

import importlib.util
import os
import sys


_DLL_DIRECTORY_HANDLE = None


def _yerel_sqlite_modulunu_yukle():
    global _DLL_DIRECTORY_HANDLE
    yerel_dizin = os.path.join(os.path.dirname(__file__), "vendor", "sqlite_native")
    pyd_yolu = os.path.join(yerel_dizin, "_sqlite3.pyd")
    dll_yolu = os.path.join(yerel_dizin, "sqlite3.dll")
    if not os.path.isfile(pyd_yolu) or not os.path.isfile(dll_yolu):
        raise ModuleNotFoundError(
            "NVDA sqlite3 sunmuyor ve Engelsiz Mail yerel SQLite bilesenleri eksik."
        )
    if hasattr(os, "add_dll_directory"):
        _DLL_DIRECTORY_HANDLE = os.add_dll_directory(yerel_dizin)
    spec = importlib.util.spec_from_file_location("_sqlite3", pyd_yolu)
    if spec is None or spec.loader is None:
        raise ImportError("Paketlenmis SQLite surucusu yukleme tanimi olusturulamadi.")
    modul = importlib.util.module_from_spec(spec)
    sys.modules["_sqlite3"] = modul
    try:
        spec.loader.exec_module(modul)
    except Exception:
        sys.modules.pop("_sqlite3", None)
        raise
    return modul


try:
    import sqlite3 as sqlite3
except (ImportError, ModuleNotFoundError):
    # Kullanilan DB-API ozellikleri (connect, Row ve hata siniflari) dogrudan
    # CPython'in _sqlite3 uzantisinda bulunur; NVDA icin tam stdlib paketi gerekmez.
    sqlite3 = _yerel_sqlite_modulunu_yukle()

