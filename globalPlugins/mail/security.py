# -*- coding: utf-8 -*-


# NVDA eklenti çevirilerini bu modül için etkinleştir.
try:
    import addonHandler
    addonHandler.initTranslation()
except (ImportError, AttributeError):
    # NVDA dışındaki otomatik testlerde Türkçe kaynak metni aynen kullan.
    _ = lambda metin: metin

import base64
import ctypes
from ctypes import wintypes
import os

from .errors import MailHatasi


EKLENTI_ADI = "Engelsiz Mail"
SIFRE_DPAPI_ON_EK = "dpapi-v1:"


class _DATA_BLOB(ctypes.Structure):
    _fields_ = [
        ("cbData", wintypes.DWORD),
        ("pbData", ctypes.c_void_p),
    ]


def _dpapi_modullerini_al():
    """Windows DPAPI işlevlerini döndürür."""
    if os.name != "nt" or not hasattr(ctypes, "WinDLL"):
        raise MailHatasi(_("Windows DPAPI bu ortamda kullanılamıyor."))

    crypt32 = ctypes.WinDLL("crypt32", use_last_error=True)
    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)

    crypt32.CryptProtectData.argtypes = [
        ctypes.POINTER(_DATA_BLOB),
        wintypes.LPCWSTR,
        ctypes.POINTER(_DATA_BLOB),
        ctypes.c_void_p,
        ctypes.c_void_p,
        wintypes.DWORD,
        ctypes.POINTER(_DATA_BLOB),
    ]
    crypt32.CryptProtectData.restype = wintypes.BOOL

    crypt32.CryptUnprotectData.argtypes = [
        ctypes.POINTER(_DATA_BLOB),
        ctypes.POINTER(wintypes.LPWSTR),
        ctypes.POINTER(_DATA_BLOB),
        ctypes.c_void_p,
        ctypes.c_void_p,
        wintypes.DWORD,
        ctypes.POINTER(_DATA_BLOB),
    ]
    crypt32.CryptUnprotectData.restype = wintypes.BOOL

    kernel32.LocalFree.argtypes = [ctypes.c_void_p]
    kernel32.LocalFree.restype = ctypes.c_void_p
    return crypt32, kernel32


def _blob_olustur(veri):
    tampon = ctypes.create_string_buffer(veri)
    blob = _DATA_BLOB(len(veri), ctypes.cast(tampon, ctypes.c_void_p))
    return blob, tampon


def _windows_hatasi(mesaj):
    hata_kodu = ctypes.get_last_error()
    if hata_kodu:
        return f"{mesaj} Windows hata kodu: {hata_kodu}."
    return mesaj


def uygulama_sifresini_sifrele(sifre):
    """Google uygulama şifresini Windows kullanıcı hesabına bağlı biçimde şifreler."""
    sifre = str(sifre or "").strip().replace(" ", "")
    if not sifre:
        return ""

    crypt32, kernel32 = _dpapi_modullerini_al()
    veri = sifre.encode("utf-8")
    giris_blob, _tampon = _blob_olustur(veri)
    cikis_blob = _DATA_BLOB()

    sonuc = crypt32.CryptProtectData(
        ctypes.byref(giris_blob),
        EKLENTI_ADI,
        None,
        None,
        None,
        0,
        ctypes.byref(cikis_blob),
    )
    if not sonuc:
        raise MailHatasi(_windows_hatasi("Uygulama şifresi şifrelenemedi."))

    try:
        sifreli_veri = ctypes.string_at(cikis_blob.pbData, cikis_blob.cbData)
    finally:
        if cikis_blob.pbData:
            kernel32.LocalFree(cikis_blob.pbData)

    return SIFRE_DPAPI_ON_EK + base64.b64encode(sifreli_veri).decode("ascii")


def uygulama_sifresini_coz(sifreli_deger):
    """Windows DPAPI ile saklanan Google uygulama şifresini çözer."""
    sifreli_deger = str(sifreli_deger or "").strip()
    if not sifreli_deger:
        return ""
    if not sifreli_deger.startswith(SIFRE_DPAPI_ON_EK):
        raise MailHatasi(_("Uygulama şifresi desteklenmeyen bir biçimde saklanmış."))

    try:
        sifreli_veri = base64.b64decode(sifreli_deger[len(SIFRE_DPAPI_ON_EK):].encode("ascii"), validate=True)
    except Exception as e:
        raise MailHatasi(_("Kayıtlı uygulama şifresi okunamadı.")) from e

    crypt32, kernel32 = _dpapi_modullerini_al()
    giris_blob, _tampon = _blob_olustur(sifreli_veri)
    cikis_blob = _DATA_BLOB()

    sonuc = crypt32.CryptUnprotectData(
        ctypes.byref(giris_blob),
        None,
        None,
        None,
        None,
        0,
        ctypes.byref(cikis_blob),
    )
    if not sonuc:
        raise MailHatasi(_windows_hatasi("Kayıtlı uygulama şifresi çözülemedi."))

    try:
        duz_veri = ctypes.string_at(cikis_blob.pbData, cikis_blob.cbData)
    finally:
        if cikis_blob.pbData:
            kernel32.LocalFree(cikis_blob.pbData)

    return duz_veri.decode("utf-8", errors="replace").strip().replace(" ", "")
