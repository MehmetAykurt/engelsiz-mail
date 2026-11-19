# -*- coding: utf-8 -*-
"""Engelsiz Mail için güvenli SQLite bağlantı ve şema yönetimi."""

import contextlib
import datetime
import os
import threading
import time

from .database_schema import MIGRATIONS, SCHEMA_VERSION
from .logger import hata_kaydet, uyari_kaydet
from .paths import VERITABANI_DOSYASI
from .sqlite_compat import sqlite3


SQLITE_BUSY_TIMEOUT_MS = 5000
_SEMA_KILIDI = threading.RLock()
_HAZIR_VERITABANLARI = {}


def _veritabani_dosya_kimligi(yol):
    """Dosya değişimini, aynı inode yeniden kullanılsa bile algılayan imza döndürür."""
    try:
        durum = os.stat(yol)
        return (
            int(durum.st_dev),
            int(durum.st_ino),
            int(durum.st_size),
            int(getattr(durum, "st_mtime_ns", int(durum.st_mtime * 1_000_000_000))),
        )
    except OSError:
        return None


class SemaUyumsuzlugu(sqlite3.DatabaseError):
    """Surum numarasi ile gercek SQLite yapisi birbiriyle uyusmadiginda."""


def _yapisal_goc_hatasi_mi(hata):
    metin = str(hata or "").lower()
    return any(
        belirti in metin
        for belirti in (
            "already exists",
            "duplicate column name",
            "no such table",
            "no column named",
        )
    )


def _veritabani_yolunu_hazirla(veritabani_yolu):
    yol = os.path.abspath(os.fspath(veritabani_yolu or VERITABANI_DOSYASI))
    klasor = os.path.dirname(yol)
    if klasor:
        os.makedirs(klasor, exist_ok=True)
    return yol


def _baglanti_ac(veritabani_yolu=None):
    yol = _veritabani_yolunu_hazirla(veritabani_yolu)
    baglanti = sqlite3.connect(
        yol,
        timeout=SQLITE_BUSY_TIMEOUT_MS / 1000.0,
        isolation_level=None,
    )
    try:
        baglanti.row_factory = sqlite3.Row
        baglanti.execute("PRAGMA foreign_keys = ON")
        baglanti.execute(f"PRAGMA busy_timeout = {SQLITE_BUSY_TIMEOUT_MS}")
        baglanti.execute("PRAGMA journal_mode = WAL")
        baglanti.execute("PRAGMA synchronous = NORMAL")
        baglanti.execute("PRAGMA temp_store = MEMORY")
        return baglanti
    except Exception:
        baglanti.close()
        raise


def _sema_surumu_al(baglanti):
    satir = baglanti.execute("PRAGMA user_version").fetchone()
    return int(satir[0]) if satir else 0


def _sema_goclerini_uygula(baglanti):
    mevcut_surum = _sema_surumu_al(baglanti)
    if mevcut_surum > SCHEMA_VERSION:
        raise sqlite3.DatabaseError(
            f"Veritabanı şeması bu eklenti sürümünden daha yeni: {mevcut_surum}."
        )

    for hedef_surum in range(mevcut_surum + 1, SCHEMA_VERSION + 1):
        komutlar = MIGRATIONS.get(hedef_surum)
        if not komutlar:
            raise sqlite3.DatabaseError(f"Eksik veritabanı göçü: {hedef_surum}.")
        simdi = int(time.time())
        baglanti.execute("BEGIN IMMEDIATE")
        try:
            for komut in komutlar:
                baglanti.execute(komut)
            baglanti.execute(
                "INSERT INTO schema_migrations(version, applied_at) VALUES (?, ?)",
                (hedef_surum, simdi),
            )
            baglanti.execute(f"PRAGMA user_version = {hedef_surum}")
            baglanti.commit()
        except Exception as e:
            baglanti.rollback()
            if isinstance(e, sqlite3.DatabaseError) and _yapisal_goc_hatasi_mi(e):
                raise SemaUyumsuzlugu(
                    f"Veritabani gocu mevcut yapiyla uyusmuyor: {hedef_surum}."
                ) from e
            raise


def _sema_yapisini_dogrula(baglanti):
    zorunlu_tablolar = {
        "accounts", "folders", "messages", "folder_messages",
        "message_bodies", "attachments", "sync_state", "schema_migrations",
        "pending_deletions", "pending_bulk_operations",
    }
    mevcut_tablolar = {
        str(satir[0])
        for satir in baglanti.execute(
            "SELECT name FROM sqlite_master WHERE type='table'"
        ).fetchall()
    }
    eksik_tablolar = sorted(zorunlu_tablolar - mevcut_tablolar)
    if eksik_tablolar:
        raise SemaUyumsuzlugu(
            "Eksik veritabani tablolari: " + ", ".join(eksik_tablolar)
        )
    zorunlu_sutunlar = {
        "messages": {"date_header"},
        "message_bodies": {"attachments_cached", "parser_version"},
        "folders": {"is_selectable", "message_count", "unseen_count"},
        "pending_deletions": {
            "operation_type", "source_folder", "source_uid", "gmail_message_id",
            "source_uidvalidity", "trash_folder", "attempt_count", "last_error",
            "permanent_delete_started", "request_token", "bulk_operation_id",
            "remote_completed", "remote_completed_at", "remote_verified",
        },
        "pending_bulk_operations": {
            "operation_type", "source_folder", "source_category",
            "deletion_type", "trash_folder", "snapshot_complete",
            "source_uidvalidity", "attempt_count", "last_error",
            "request_token", "settlement_verified_at",
        },
    }
    for tablo, beklenenler in zorunlu_sutunlar.items():
        mevcutlar = {
            str(satir[1]) for satir in baglanti.execute(f"PRAGMA table_info({tablo})")
        }
        eksikler = sorted(beklenenler - mevcutlar)
        if eksikler:
            raise SemaUyumsuzlugu(
                f"{tablo} tablosunda eksik sutunlar: " + ", ".join(eksikler)
            )
    uygulanan = {
        int(satir[0])
        for satir in baglanti.execute("SELECT version FROM schema_migrations").fetchall()
    }
    beklenen = set(range(1, SCHEMA_VERSION + 1))
    if not beklenen.issubset(uygulanan):
        raise SemaUyumsuzlugu("Veritabani goc kayitlari eksik.")


def _bozulma_hatasi_mi(hata):
    hata_adi = str(getattr(hata, "sqlite_errorname", "") or "").upper()
    if hata_adi in ("SQLITE_CORRUPT", "SQLITE_NOTADB"):
        return True
    metin = str(hata or "").lower()
    return any(
        belirti in metin
        for belirti in (
            "database disk image is malformed",
            "file is not a database",
            "database corruption",
        )
    )


def bozuk_veritabanini_yedekle(veritabani_yolu=None):
    """Bozuk ana dosyayı ve yan WAL dosyalarını silmeden benzersiz bir ada taşır."""
    yol = os.path.abspath(os.fspath(veritabani_yolu or VERITABANI_DOSYASI))
    with _SEMA_KILIDI:
        _HAZIR_VERITABANLARI.pop(os.path.normcase(yol), None)
    if not os.path.exists(yol):
        return None
    zaman = datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
    temel_yedek = f"{yol}.bozuk-{zaman}"
    yedek = temel_yedek
    sayac = 1
    while os.path.exists(yedek):
        sayac += 1
        yedek = f"{temel_yedek}-{sayac}"
    os.replace(yol, yedek)
    for uzanti in ("-wal", "-shm"):
        yan_dosya = yol + uzanti
        if os.path.exists(yan_dosya):
            os.replace(yan_dosya, yedek + uzanti)
    return yedek


def _veritabanini_bir_kez_hazirla(veritabani_yolu):
    baglanti = _baglanti_ac(veritabani_yolu)
    try:
        _sema_goclerini_uygula(baglanti)
        _sema_yapisini_dogrula(baglanti)
    finally:
        baglanti.close()


def veritabani_hazirla(veritabani_yolu=None):
    """Veritabanını oluşturur, bağlantı ayarlarını ve bekleyen göçleri uygular."""
    yol = os.path.abspath(os.fspath(veritabani_yolu or VERITABANI_DOSYASI))
    hazirlik_anahtari = os.path.normcase(yol)
    with _SEMA_KILIDI:
        mevcut_kimlik = _veritabani_dosya_kimligi(yol)
        if (
            mevcut_kimlik is not None
            and _HAZIR_VERITABANLARI.get(hazirlik_anahtari) == mevcut_kimlik
        ):
            return yol
        try:
            _veritabanini_bir_kez_hazirla(yol)
        except sqlite3.DatabaseError as e:
            if not (_bozulma_hatasi_mi(e) or isinstance(e, SemaUyumsuzlugu)):
                hata_kaydet("Veritabanı hazırlanamadı.", e)
                raise
            yedek = bozuk_veritabanini_yedekle(yol)
            uyari_kaydet(f"Bozuk veritabanı yedeklendi: {yedek}", e)
            _veritabanini_bir_kez_hazirla(yol)
        except Exception as e:
            hata_kaydet("Veritabanı hazırlanamadı.", e)
            raise
        _HAZIR_VERITABANLARI[hazirlik_anahtari] = _veritabani_dosya_kimligi(yol)
    return yol


@contextlib.contextmanager
def veritabani_baglantisi(veritabani_yolu=None, yazma=False):
    """Her çağrıda thread'e bağlı olmayan kısa ömürlü bir bağlantı sağlar."""
    yol = _veritabani_yolunu_hazirla(veritabani_yolu)
    veritabani_hazirla(yol)
    baglanti = _baglanti_ac(yol)
    try:
        if yazma:
            baglanti.execute("BEGIN IMMEDIATE")
        yield baglanti
        if yazma:
            baglanti.commit()
    except Exception:
        if yazma:
            baglanti.rollback()
        raise
    finally:
        acik_dosya_kimligi = _veritabani_dosya_kimligi(yol)
        baglanti.close()
        kapanis_dosya_kimligi = _veritabani_dosya_kimligi(yol)
        hazirlik_anahtari = os.path.normcase(yol)
        with _SEMA_KILIDI:
            if (
                acik_dosya_kimligi is not None
                and kapanis_dosya_kimligi is not None
                and acik_dosya_kimligi[:2] == kapanis_dosya_kimligi[:2]
            ):
                _HAZIR_VERITABANLARI[hazirlik_anahtari] = kapanis_dosya_kimligi
            else:
                _HAZIR_VERITABANLARI.pop(hazirlik_anahtari, None)


def veritabani_butunluk_denetle(veritabani_yolu=None):
    """SQLite hızlı bütünlük denetimini çalıştırır ve sonucu döndürür."""
    with veritabani_baglantisi(veritabani_yolu) as baglanti:
        satirlar = baglanti.execute("PRAGMA quick_check").fetchall()
        yabanci_anahtar_hatalari = baglanti.execute(
            "PRAGMA foreign_key_check"
        ).fetchall()
    sonuclar = [str(satir[0]) for satir in satirlar]
    for satir in yabanci_anahtar_hatalari:
        sonuclar.append(
            "foreign_key:table={0},rowid={1},parent={2},constraint={3}".format(
                satir[0], satir[1], satir[2], satir[3]
            )
        )
    return sonuclar == ["ok"], sonuclar
