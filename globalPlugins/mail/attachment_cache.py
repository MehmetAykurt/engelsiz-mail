# -*- coding: utf-8 -*-
"""İndirilen ekleri ayar dizininde atomik ve doğrulanabilir biçimde saklar."""

import hashlib
import mimetypes
import os
import tempfile
import threading

from .mail_store import (
    ek_kayitlarini_al,
    ek_kayitlarini_kaydet,
    mesaj_onbellek_kimligini_al,
)
from .paths import EKLER_KLASORU
from .text_utils import guvenli_dosya_adi


EK_ONBELLEK_KILIDI = threading.RLock()


def _kisa_hash(metin):
    return hashlib.sha256(str(metin or "").encode("utf-8")).hexdigest()[:16]


def _guvenli_tam_yol(goreli_yol):
    kok = os.path.realpath(EKLER_KLASORU)
    tam_yol = os.path.realpath(os.path.join(kok, str(goreli_yol or "")))
    if os.path.commonpath((kok, tam_yol)) != kok:
        raise ValueError("Ek önbellek yolu güvenli dizinin dışına çıkıyor.")
    return tam_yol


def _atomik_bayt_yaz(hedef_yol, veri):
    os.makedirs(os.path.dirname(hedef_yol), exist_ok=True)
    fd, gecici_yol = tempfile.mkstemp(prefix="ek_", suffix=".tmp", dir=os.path.dirname(hedef_yol))
    try:
        with os.fdopen(fd, "wb") as dosya:
            dosya.write(veri)
            dosya.flush()
            try:
                os.fsync(dosya.fileno())
            except OSError:
                pass
        os.replace(gecici_yol, hedef_yol)
    except Exception:
        try:
            os.remove(gecici_yol)
        except OSError:
            pass
        raise


def _ekleri_onbellege_kaydet(eposta, imap_klasoru, uid, ekler, tamamlandi=True):
    kimlik = mesaj_onbellek_kimligini_al(eposta, imap_klasoru, uid)
    if not kimlik:
        return False
    temel = os.path.join(
        _kisa_hash(str(eposta).lower()),
        _kisa_hash(imap_klasoru),
        f"{int(kimlik['uidvalidity'])}_{int(uid)}",
    )
    db_kayitlari = []
    yeni_olusturulan_yollar = []
    try:
        for sira, (dosya_adi, veri) in enumerate(ekler or [], 1):
            veri = bytes(veri or b"")
            temiz_ad = guvenli_dosya_adi(dosya_adi, "ek_dosya")
            ozet = hashlib.sha256(veri).hexdigest()
            goreli_yol = os.path.join(temel, f"{sira:03d}_{ozet[:12]}_{temiz_ad}")
            hedef_yol = _guvenli_tam_yol(goreli_yol)
            daha_once_vardi = os.path.exists(hedef_yol)
            _atomik_bayt_yaz(hedef_yol, veri)
            if not daha_once_vardi:
                yeni_olusturulan_yollar.append(hedef_yol)
            icerik_turu = mimetypes.guess_type(temiz_ad)[0] or "application/octet-stream"
            db_kayitlari.append(
                {
                    "part_path": str(sira),
                    "file_name": temiz_ad,
                    "content_type": icerik_turu,
                    "size_bytes": len(veri),
                    "sha256": ozet,
                    "local_path": goreli_yol,
                }
            )
        ek_kayitlarini_kaydet(kimlik["message_id"], db_kayitlari, tamamlandi)
        return True
    except Exception:
        for yol in yeni_olusturulan_yollar:
            try:
                os.remove(yol)
            except OSError:
                pass
        raise


def ekleri_onbellege_kaydet(eposta, imap_klasoru, uid, ekler, tamamlandi=True):
    with EK_ONBELLEK_KILIDI:
        return _ekleri_onbellege_kaydet(
            eposta, imap_klasoru, uid, ekler, tamamlandi=tamamlandi
        )


def _ekleri_onbellekten_al(mesaj_id):
    sonuc = []
    for kayit in ek_kayitlarini_al(mesaj_id):
        tam_yol = _guvenli_tam_yol(kayit.get("local_path"))
        try:
            if not os.path.isfile(tam_yol):
                return None
            beklenen_boyut = int(kayit.get("size_bytes") or 0)
            if os.path.getsize(tam_yol) != beklenen_boyut:
                return None
            with open(tam_yol, "rb") as dosya:
                veri = dosya.read()
            if hashlib.sha256(veri).hexdigest() != str(kayit.get("sha256") or ""):
                return None
            sonuc.append((str(kayit.get("file_name") or "ek_dosya"), veri))
        except OSError:
            return None
    return sonuc


def ekleri_onbellekten_al(mesaj_id):
    with EK_ONBELLEK_KILIDI:
        return _ekleri_onbellekten_al(mesaj_id)
