# -*- coding: utf-8 -*-
"""Engelsiz Mail veritabanı için engellemeyen bakım ve istatistik işlemleri."""

import os
import shutil
import time

from .database import veritabani_baglantisi, veritabani_butunluk_denetle, veritabani_hazirla
from .paths import EKLER_KLASORU, VERITABANI_DOSYASI
from .attachment_cache import EK_ONBELLEK_KILIDI, _guvenli_tam_yol
from .mailbox_state import POSTA_DURUM_KILIDI


YETIM_MESAJ_BEKLEME_SANIYESI = 30 * 24 * 60 * 60
YETIM_DOSYA_BEKLEME_SANIYESI = 7 * 24 * 60 * 60


def _dosya_boyutunu_guvenle_al(yol):
    try:
        return os.path.getsize(yol) if os.path.isfile(yol) else 0
    except OSError:
        return 0


def veritabani_istatistikleri():
    with veritabani_baglantisi() as db:
        sonuc = {
            "accounts": db.execute("SELECT COUNT(*) FROM accounts").fetchone()[0],
            "folders": db.execute("SELECT COUNT(*) FROM folders").fetchone()[0],
            "messages": db.execute("SELECT COUNT(*) FROM messages").fetchone()[0],
            "bodies": db.execute("SELECT COUNT(*) FROM message_bodies").fetchone()[0],
            "attachments": db.execute("SELECT COUNT(*) FROM attachments").fetchone()[0],
        }
    sonuc["database_bytes"] = _dosya_boyutunu_guvenle_al(VERITABANI_DOSYASI)
    sonuc["attachment_bytes"] = sum(
        _dosya_boyutunu_guvenle_al(os.path.join(kok, ad))
        for kok, _klasorler, adlar in os.walk(EKLER_KLASORU)
        for ad in adlar
    ) if os.path.isdir(EKLER_KLASORU) else 0
    return sonuc


def _yetim_onbellegi_temizle(simdi=None):
    simdi = int(simdi or time.time())
    mesaj_esigi = simdi - YETIM_MESAJ_BEKLEME_SANIYESI
    silinecek_yollar = []
    silinen_mesaj = 0
    silinen_klasor = 0
    silinen_hesap = 0
    with veritabani_baglantisi(yazma=True) as db:
        mesajlar = db.execute(
            """SELECT m.id FROM messages m
               WHERE MAX(
                   m.updated_at,
                   COALESCE((SELECT MAX(fm2.updated_at) FROM folder_messages fm2 WHERE fm2.message_id=m.id), 0)
               ) < ? AND NOT EXISTS (
                   SELECT 1 FROM folder_messages fm
                   WHERE fm.message_id=m.id AND fm.is_present=1
               ) AND NOT EXISTS (
                   SELECT 1 FROM pending_deletions pd
                   WHERE pd.account_id = m.account_id AND (
                       (pd.gmail_message_id IS NOT NULL
                        AND pd.gmail_message_id = m.gmail_message_id)
                       OR EXISTS (
                           SELECT 1 FROM folder_messages fm3
                           JOIN folders f3 ON f3.id = fm3.folder_id
                           WHERE fm3.message_id = m.id
                             AND f3.imap_name = pd.source_folder
                             AND fm3.uid = pd.source_uid
                             AND fm3.uidvalidity = pd.source_uidvalidity
                       )
                   )
               )""",
            (mesaj_esigi,),
        ).fetchall()
        mesaj_idleri = [int(satir[0]) for satir in mesajlar]
        for baslangic in range(0, len(mesaj_idleri), 500):
            parca = mesaj_idleri[baslangic:baslangic + 500]
            yerler = ",".join("?" for _ in parca)
            silinecek_yollar.extend(
                str(satir[0]) for satir in db.execute(
                    f"SELECT local_path FROM attachments WHERE message_id IN ({yerler}) AND local_path IS NOT NULL",
                    parca,
                ).fetchall()
            )
            silinen_mesaj += db.execute(
                f"DELETE FROM messages WHERE id IN ({yerler})", parca
            ).rowcount
        silinen_klasor = db.execute(
            """DELETE FROM folders
               WHERE is_selectable = 0 AND updated_at < ?
                 AND NOT EXISTS (
                     SELECT 1 FROM folder_messages fm WHERE fm.folder_id = folders.id
                 )""",
            (mesaj_esigi,),
        ).rowcount
        silinen_hesap = db.execute(
            """DELETE FROM accounts
               WHERE updated_at < ?
                 AND NOT EXISTS (SELECT 1 FROM folders f WHERE f.account_id = accounts.id)
                  AND NOT EXISTS (SELECT 1 FROM messages m WHERE m.account_id = accounts.id)
                  AND NOT EXISTS (SELECT 1 FROM pending_deletions pd WHERE pd.account_id = accounts.id)
                  AND NOT EXISTS (
                      SELECT 1 FROM pending_bulk_operations pbo
                      WHERE pbo.account_id = accounts.id
                  )""",
            (mesaj_esigi,),
        ).rowcount
        kayitli_yollar = {
            os.path.normcase(os.path.normpath(str(satir[0])))
            for satir in db.execute(
                "SELECT local_path FROM attachments WHERE local_path IS NOT NULL"
            ).fetchall()
        }

    silinen_dosya = 0
    for goreli_yol in silinecek_yollar:
        try:
            tam_yol = _guvenli_tam_yol(goreli_yol)
            if os.path.isfile(tam_yol):
                os.remove(tam_yol)
                silinen_dosya += 1
        except (OSError, ValueError):
            pass

    dosya_esigi = simdi - YETIM_DOSYA_BEKLEME_SANIYESI
    if os.path.isdir(EKLER_KLASORU):
        for kok, _klasorler, dosyalar in os.walk(EKLER_KLASORU):
            for ad in dosyalar:
                tam_yol = os.path.join(kok, ad)
                try:
                    goreli = os.path.normcase(os.path.normpath(os.path.relpath(tam_yol, EKLER_KLASORU)))
                    if goreli in kayitli_yollar or os.path.getmtime(tam_yol) >= dosya_esigi:
                        continue
                    _guvenli_tam_yol(goreli)
                    os.remove(tam_yol)
                    silinen_dosya += 1
                except (OSError, ValueError):
                    continue
    return {
        "deleted_messages": max(0, silinen_mesaj),
        "deleted_folders": max(0, silinen_klasor),
        "deleted_accounts": max(0, silinen_hesap),
        "deleted_files": silinen_dosya,
    }


def yetim_onbellegi_temizle(simdi=None):
    # Dosya yazma + SQL metadata kaydi ile temizligin birbirini yarida
    # kesmesini engeller. RLock ayni thread'deki guvenli yol cagrisina izin verir.
    with EK_ONBELLEK_KILIDI:
        return _yetim_onbellegi_temizle(simdi=simdi)


def temel_bakim_yap(temizlik=False):
    butunluk, ayrinti = veritabani_butunluk_denetle()
    with veritabani_baglantisi() as db:
        checkpoint = tuple(db.execute("PRAGMA wal_checkpoint(PASSIVE)").fetchone())
    sonuc = {"integrity_ok": butunluk, "integrity_details": ayrinti, "wal_checkpoint": checkpoint}
    if temizlik and butunluk:
        sonuc.update(yetim_onbellegi_temizle())
    return sonuc


def veritabanini_sikistir():
    with veritabani_baglantisi() as db:
        db.execute("VACUUM")
    return True


def gmail_mesajlarini_yerelden_sil(eposta, gmail_mesaj_idleri):
    """Sunucuda kalıcı silindiği doğrulanan Gmail iletilerini ve eklerini kaldırır."""
    eposta = str(eposta or "").strip().lower()
    gmail_idleri = sorted({str(x or "").strip() for x in gmail_mesaj_idleri or [] if str(x or "").strip()})
    if not eposta or not gmail_idleri:
        return {"deleted_messages": 0, "deleted_files": 0}
    silinecek_yollar = []
    silinen_mesaj = 0
    with EK_ONBELLEK_KILIDI:
        with veritabani_baglantisi(yazma=True) as db:
            hesap = db.execute("SELECT id FROM accounts WHERE email = ? COLLATE NOCASE", (eposta,)).fetchone()
            if not hesap:
                return {"deleted_messages": 0, "deleted_files": 0}
            for baslangic in range(0, len(gmail_idleri), 500):
                parca = gmail_idleri[baslangic:baslangic + 500]
                yerler = ",".join("?" for _ in parca)
                mesaj_idleri = [int(s[0]) for s in db.execute(
                    f"SELECT id FROM messages WHERE account_id = ? AND gmail_message_id IN ({yerler})",
                    (int(hesap[0]), *parca),
                ).fetchall()]
                if not mesaj_idleri:
                    continue
                mesaj_yerleri = ",".join("?" for _ in mesaj_idleri)
                silinecek_yollar.extend(str(s[0]) for s in db.execute(
                    f"SELECT local_path FROM attachments WHERE message_id IN ({mesaj_yerleri}) AND local_path IS NOT NULL",
                    mesaj_idleri,
                ).fetchall())
                silinen_mesaj += db.execute(
                    f"DELETE FROM messages WHERE id IN ({mesaj_yerleri})", mesaj_idleri
                ).rowcount
        silinen_dosya = 0
        for goreli_yol in silinecek_yollar:
            try:
                tam_yol = _guvenli_tam_yol(goreli_yol)
                if os.path.isfile(tam_yol):
                    os.remove(tam_yol)
                    silinen_dosya += 1
            except (OSError, ValueError):
                continue
    return {"deleted_messages": max(0, silinen_mesaj), "deleted_files": silinen_dosya}


def yerel_veritabanini_sifirla():
    """Posta veritabanını ve ek önbelleğini silip boş şemayı yeniden kurar."""
    if not POSTA_DURUM_KILIDI.acquire(False):
        raise RuntimeError("Başka bir e-posta işlemi devam ediyor. Lütfen işlem bittikten sonra yeniden deneyin.")
    try:
        with EK_ONBELLEK_KILIDI:
            if os.path.isfile(VERITABANI_DOSYASI):
                with veritabani_baglantisi() as db:
                    bekleyen = int(
                        db.execute(
                            """SELECT
                                   (SELECT COUNT(*) FROM pending_deletions)
                                 + (SELECT COUNT(*) FROM pending_bulk_operations)"""
                        ).fetchone()[0]
                        or 0
                    )
                if bekleyen:
                    raise RuntimeError(f"{bekleyen} bekleyen silme işlemi bulunduğu için yerel veritabanı sıfırlanmadı.")
            for yol in (VERITABANI_DOSYASI, VERITABANI_DOSYASI + "-wal", VERITABANI_DOSYASI + "-shm"):
                try:
                    if os.path.exists(yol):
                        os.remove(yol)
                except OSError as hata:
                    raise RuntimeError("Yerel veritabanı dosyaları silinemedi.") from hata
            try:
                if os.path.isdir(EKLER_KLASORU):
                    shutil.rmtree(EKLER_KLASORU)
                os.makedirs(EKLER_KLASORU, exist_ok=True)
            except OSError as hata:
                raise RuntimeError("Yerel ek önbelleği temizlenemedi.") from hata
            veritabani_hazirla()
        return True
    finally:
        POSTA_DURUM_KILIDI.release()
