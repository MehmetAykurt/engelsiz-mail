# -*- coding: utf-8 -*-
"""Çevrimdışı silme isteklerini kalıcı SQLite kuyruğunda yönetir."""

# NVDA eklenti çevirilerini bu modül için etkinleştir.
try:
    import addonHandler
    addonHandler.initTranslation()
except (ImportError, AttributeError):
    # NVDA dışındaki otomatik testlerde Türkçe kaynak metni aynen kullan.
    _ = lambda metin: metin


import contextlib
import os
import threading
import time

import wx

from .attachment_cache import EK_ONBELLEK_KILIDI, _guvenli_tam_yol
from .config import ayarlari_yukle
from .database import veritabani_baglantisi, veritabani_hazirla
from .errors import MailHatasi
from .imap_client import (
    ImapBaglantisi,
    imap_gmail_etiket_destegini_dogrula,
    imap_gmail_etiket_store,
    imap_gmail_msgidleri_kalici_sil,
    imap_uidvalidity_al,
    imap_ok_mu,
    imap_uid_search_sonucu_uidleri_al,
    imap_x_gm_msgid_haritasi_al,
    uid_kumesi_hazirla,
)
from .logger import hata_kaydet, uyari_kaydet
from .mailbox_state import POSTA_DURUM_KILIDI
from .ui_helpers import arka_planda_calistir


ILK_DENEME_GECIKMESI_MS = 15000
YENIDEN_DENEME_ARALIGI_MS = 5000
TOPLU_YERLESME_BEKLEME_SANIYESI = 5
_ISLEME_KILIDI = threading.Lock()
_SON_BAGLANTI_UYARISI = 0
BAGLANTI_UYARI_ARALIGI_SANIYE = 30 * 60


def _simdi():
    return int(time.time())


def _klasor_sayaclarini_guncelle(db, klasor_idleri):
    for klasor_id in set(int(deger) for deger in klasor_idleri or []):
        db.execute(
            """UPDATE folders SET
                   message_count = (
                       SELECT COUNT(*) FROM folder_messages fm
                       JOIN messages m ON m.id = fm.message_id
                       JOIN folders f ON f.id = fm.folder_id
                       WHERE fm.folder_id = ? AND fm.is_present = 1 AND fm.is_deleted = 0
                         AND NOT EXISTS (
                             SELECT 1 FROM pending_deletions pd
                             WHERE pd.account_id = m.account_id
                               AND (
                                   (pd.gmail_message_id IS NOT NULL
                                    AND pd.gmail_message_id = m.gmail_message_id)
                                   OR (
                                       pd.source_folder = f.imap_name
                                       AND pd.source_uid = fm.uid
                                       AND (
                                           pd.source_uidvalidity IS NULL
                                           OR pd.source_uidvalidity = fm.uidvalidity
                                       )
                                   )
                               )
                         )
                         AND NOT EXISTS (
                             SELECT 1 FROM pending_bulk_operations pbo
                             WHERE pbo.account_id = m.account_id
                               AND pbo.source_folder = f.imap_name
                               AND pbo.snapshot_complete = 0
                         )
                   ),
                   unseen_count = (
                       SELECT COUNT(*) FROM folder_messages fm
                       JOIN messages m ON m.id = fm.message_id
                       JOIN folders f ON f.id = fm.folder_id
                       WHERE fm.folder_id = ? AND fm.is_present = 1
                         AND fm.is_deleted = 0 AND fm.is_seen = 0
                         AND NOT EXISTS (
                             SELECT 1 FROM pending_deletions pd
                             WHERE pd.account_id = m.account_id
                               AND (
                                   (pd.gmail_message_id IS NOT NULL
                                    AND pd.gmail_message_id = m.gmail_message_id)
                                   OR (
                                       pd.source_folder = f.imap_name
                                       AND pd.source_uid = fm.uid
                                       AND (
                                           pd.source_uidvalidity IS NULL
                                           OR pd.source_uidvalidity = fm.uidvalidity
                                       )
                                   )
                               )
                         )
                         AND NOT EXISTS (
                             SELECT 1 FROM pending_bulk_operations pbo
                             WHERE pbo.account_id = m.account_id
                               AND pbo.source_folder = f.imap_name
                               AND pbo.snapshot_complete = 0
                         )
                   ),
                   updated_at = ?
               WHERE id = ?""",
            (klasor_id, klasor_id, _simdi(), klasor_id),
        )


def silme_isteklerini_kuyruga_al(
    eposta,
    kaynak_klasor,
    kaynak_kategori,
    uidler,
    islem_turu,
    cop_klasoru,
    kaynak_etiketi="",
    kaynak_etiketi_kaldir=False,
    toplu_islem_id=None,
    kaynak_uidvalidity_override=None,
    gmail_id_haritasi=None,
    _db=None,
):
    """Silme isteğini ve yerel gizlemeyi aynı SQL işlemi içinde kaydeder."""
    eposta = str(eposta or "").strip().lower()
    kaynak_klasor = str(kaynak_klasor or "").strip()
    cop_klasoru = str(cop_klasoru or "").strip()
    islem_turu = str(islem_turu or "").strip().lower()
    ham_uidler = list(uidler or [])
    gecersiz_uidler = [
        uid for uid in ham_uidler
        if not str(uid or "").strip().isdigit() or int(str(uid).strip()) <= 0
    ]
    if gecersiz_uidler:
        raise ValueError("Silme kuyruğunda geçersiz e-posta UID değeri bulundu.")
    temiz_uidler = sorted({int(str(uid).strip()) for uid in ham_uidler})
    if not eposta or not kaynak_klasor or not cop_klasoru or not temiz_uidler:
        raise ValueError("Silme kuyruğu için hesap, klasör ve UID zorunludur.")
    if islem_turu not in ("trash", "permanent"):
        raise ValueError("Geçersiz silme işlemi türü.")
    try:
        toplu_islem_id = int(toplu_islem_id) if toplu_islem_id is not None else None
    except (TypeError, ValueError):
        toplu_islem_id = None
    try:
        kaynak_uidvalidity_override = int(kaynak_uidvalidity_override or 0)
    except (TypeError, ValueError):
        kaynak_uidvalidity_override = 0
    gmail_id_haritasi = {
        str(uid): str(gmail_id or "").strip()
        for uid, gmail_id in dict(gmail_id_haritasi or {}).items()
    }

    simdi = _simdi()
    baglanti_baglami = (
        contextlib.nullcontext(_db)
        if _db is not None
        else veritabani_baglantisi(yazma=True)
    )
    with baglanti_baglami as db:
        db.execute(
            """INSERT INTO accounts(email, provider, created_at, updated_at)
               VALUES (?, 'gmail', ?, ?)
               ON CONFLICT(email) DO UPDATE SET updated_at = excluded.updated_at""",
            (eposta, simdi, simdi),
        )
        hesap_id = int(db.execute(
            "SELECT id FROM accounts WHERE email = ? COLLATE NOCASE", (eposta,)
        ).fetchone()[0])
        klasor = db.execute(
            "SELECT id, uidvalidity FROM folders WHERE account_id = ? AND imap_name = ?",
            (hesap_id, kaynak_klasor),
        ).fetchone()
        klasor_id = int(klasor[0]) if klasor else None
        yerel_uidvalidity = int(klasor["uidvalidity"] or 0) if klasor else 0
        kaynak_uidvalidity = kaynak_uidvalidity_override or yerel_uidvalidity
        etkilenen_klasorler = set()

        for uid in temiz_uidler:
            istek_kimligi = os.urandom(16).hex()
            mesaj = None
            if klasor_id is not None and yerel_uidvalidity == kaynak_uidvalidity:
                mesaj = db.execute(
                    """SELECT m.id, m.gmail_message_id
                       FROM folder_messages fm JOIN messages m ON m.id = fm.message_id
                       WHERE fm.folder_id = ? AND fm.uid = ?
                         AND fm.uidvalidity = ?
                       ORDER BY fm.updated_at DESC LIMIT 1""",
                    (klasor_id, uid, yerel_uidvalidity),
                ).fetchone()
            gmail_id = str(mesaj["gmail_message_id"] or "").strip() if mesaj else ""
            if not gmail_id:
                gmail_id = gmail_id_haritasi.get(str(uid), "")
            if not gmail_id and kaynak_uidvalidity <= 0:
                raise ValueError(
                    "Gmail ileti kimliği bulunmayan silme isteği UIDVALIDITY olmadan kaydedilemez."
                )

            if islem_turu == "permanent":
                if gmail_id:
                    db.execute(
                        "DELETE FROM pending_deletions WHERE account_id = ? AND gmail_message_id = ?",
                        (hesap_id, gmail_id),
                    )
                else:
                    db.execute(
                        """DELETE FROM pending_deletions
                           WHERE account_id = ? AND source_folder = ? AND source_uid = ?""",
                        (hesap_id, kaynak_klasor, uid),
                    )

            db.execute(
                """INSERT INTO pending_deletions(
                       account_id, operation_type, source_folder, source_category,
                       source_uid, gmail_message_id, source_uidvalidity,
                       trash_folder, source_label,
                       remove_source_label, request_token, bulk_operation_id,
                       created_at, updated_at
                   ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                   ON CONFLICT(account_id, operation_type, source_folder, source_uid)
                   DO UPDATE SET gmail_message_id = excluded.gmail_message_id,
                       source_category = excluded.source_category,
                       source_uidvalidity = excluded.source_uidvalidity,
                       trash_folder = excluded.trash_folder,
                       source_label = excluded.source_label,
                       remove_source_label = excluded.remove_source_label,
                        request_token = excluded.request_token,
                        attempt_count = 0,
                        permanent_delete_started = 0,
                        remote_completed = 0,
                        remote_completed_at = NULL,
                        remote_verified = 0,
                        last_error = NULL,
                       bulk_operation_id = COALESCE(
                           excluded.bulk_operation_id,
                           pending_deletions.bulk_operation_id
                       ),
                       created_at = excluded.created_at,
                       updated_at = excluded.updated_at""",
                (
                    hesap_id, islem_turu, kaynak_klasor, str(kaynak_kategori or ""),
                    uid, gmail_id or None, kaynak_uidvalidity or None,
                    cop_klasoru, str(kaynak_etiketi or ""),
                    int(bool(kaynak_etiketi_kaldir)), istek_kimligi,
                    toplu_islem_id, simdi, simdi,
                ),
            )

            if islem_turu == "permanent" and mesaj:
                klasorler = db.execute(
                    "SELECT DISTINCT folder_id FROM folder_messages WHERE message_id = ?",
                    (int(mesaj["id"]),),
                ).fetchall()
                etkilenen_klasorler.update(int(satir[0]) for satir in klasorler)
                db.execute(
                    "UPDATE folder_messages SET is_present = 0, updated_at = ? WHERE message_id = ?",
                    (simdi, int(mesaj["id"])),
                )
            elif klasor_id is not None and yerel_uidvalidity == kaynak_uidvalidity:
                etkilenen_klasorler.add(klasor_id)
                db.execute(
                    """UPDATE folder_messages SET is_present = 0, updated_at = ?
                       WHERE folder_id = ? AND uidvalidity = ? AND uid = ?""",
                    (simdi, klasor_id, yerel_uidvalidity, uid),
                )

        _klasor_sayaclarini_guncelle(db, etkilenen_klasorler)
    return len(temiz_uidler)


def toplu_silme_istegini_kuyruga_al(
    eposta,
    islem_turu,
    kaynak_klasor,
    kaynak_kategori,
    silme_turu,
    cop_klasoru,
    kaynak_etiketi="",
    kaynak_etiketi_kaldir=False,
):
    """Toplu işi kalıcılaştırır ve bilinen yerel iletileri hemen gizler."""
    eposta = str(eposta or "").strip().lower()
    islem_turu = str(islem_turu or "").strip().lower()
    kaynak_klasor = str(kaynak_klasor or "").strip()
    kaynak_kategori = str(kaynak_kategori or "").strip()
    silme_turu = str(silme_turu or "").strip().lower()
    cop_klasoru = str(cop_klasoru or "").strip()
    if not eposta or not kaynak_klasor or not kaynak_kategori or not cop_klasoru:
        raise ValueError("Toplu işlem için hesap ve klasör bilgileri zorunludur.")
    if islem_turu not in ("empty_trash", "empty_spam", "sent_to_trash"):
        raise ValueError("Geçersiz toplu işlem türü.")
    if silme_turu not in ("trash", "permanent"):
        raise ValueError("Geçersiz toplu silme türü.")

    simdi = _simdi()
    istek_kimligi = os.urandom(16).hex()
    with veritabani_baglantisi(yazma=True) as db:
        db.execute(
            """INSERT INTO accounts(email, provider, created_at, updated_at)
               VALUES (?, 'gmail', ?, ?)
               ON CONFLICT(email) DO UPDATE SET updated_at = excluded.updated_at""",
            (eposta, simdi, simdi),
        )
        hesap_id = int(
            db.execute(
                "SELECT id FROM accounts WHERE email = ? COLLATE NOCASE",
                (eposta,),
            ).fetchone()[0]
        )
        mevcut = db.execute(
            """SELECT id, snapshot_complete FROM pending_bulk_operations
               WHERE account_id = ? AND operation_type = ? AND source_folder = ?""",
            (hesap_id, islem_turu, kaynak_klasor),
        ).fetchone()
        if mevcut:
            return {
                "toplu_islem_id": int(mevcut["id"]),
                "yerel_uidler": [],
                "yerel_adet": 0,
                "zaten_devam_ediyor": True,
                "anlik_goruntu_hazir": bool(mevcut["snapshot_complete"]),
            }
        imlec = db.execute(
            """INSERT INTO pending_bulk_operations(
                   account_id, operation_type, source_folder, source_category,
                   deletion_type, trash_folder, source_label,
                   remove_source_label, request_token, created_at, updated_at
               ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                hesap_id,
                islem_turu,
                kaynak_klasor,
                kaynak_kategori,
                silme_turu,
                cop_klasoru,
                str(kaynak_etiketi or ""),
                int(bool(kaynak_etiketi_kaldir)),
                istek_kimligi,
                simdi,
                simdi,
            ),
        )
        toplu_islem_id = int(imlec.lastrowid)

        klasor = db.execute(
            """SELECT id, uidvalidity FROM folders
               WHERE account_id = ? AND imap_name = ?""",
            (hesap_id, kaynak_klasor),
        ).fetchone()
        if klasor:
            yerel_uidler = [
                int(satir[0])
                for satir in db.execute(
                    """SELECT uid FROM folder_messages
                       WHERE folder_id = ? AND uidvalidity = ?
                         AND is_present = 1 AND is_deleted = 0
                       ORDER BY uid""",
                    (int(klasor["id"]), int(klasor["uidvalidity"] or 0)),
                ).fetchall()
            ]
        else:
            yerel_uidler = []

        if yerel_uidler:
            silme_isteklerini_kuyruga_al(
                eposta,
                kaynak_klasor,
                kaynak_kategori,
                yerel_uidler,
                silme_turu,
                cop_klasoru,
                kaynak_etiketi,
                kaynak_etiketi_kaldir,
                toplu_islem_id,
                _db=db,
            )
    return {
        "toplu_islem_id": toplu_islem_id,
        "yerel_uidler": yerel_uidler,
        "yerel_adet": len(yerel_uidler),
        "zaten_devam_ediyor": False,
        "anlik_goruntu_hazir": False,
    }


def bekleyen_toplu_klasor_bilgileri(eposta=None):
    """Bekleyen tekli ve toplu silmelerin sayaç düzeltmesini kategori bazında döndürür."""
    with veritabani_baglantisi() as db:
        if eposta:
            satirlar = db.execute(
                """SELECT
                       pbo.source_category,
                       pbo.snapshot_complete,
                       (
                           SELECT COUNT(*) FROM pending_deletions pd
                           WHERE pd.bulk_operation_id = pbo.id
                       ) AS pending_count,
                       (
                           SELECT COUNT(*)
                           FROM pending_deletions pd
                           JOIN folders f
                             ON f.account_id = pbo.account_id
                            AND f.imap_name = pbo.source_folder
                           JOIN folder_messages fm
                             ON fm.folder_id = f.id
                            AND fm.uid = pd.source_uid
                            AND (
                                pd.source_uidvalidity IS NULL
                                OR fm.uidvalidity = pd.source_uidvalidity
                            )
                           WHERE pd.bulk_operation_id = pbo.id
                             AND fm.is_seen = 0
                       ) AS known_unseen_count
                   FROM pending_bulk_operations pbo
                   JOIN accounts a ON a.id = pbo.account_id
                   WHERE a.email = ? COLLATE NOCASE""",
                (str(eposta or "").strip(),),
            ).fetchall()
        else:
            satirlar = db.execute(
                """SELECT
                       pbo.source_category,
                       pbo.snapshot_complete,
                       (
                           SELECT COUNT(*) FROM pending_deletions pd
                           WHERE pd.bulk_operation_id = pbo.id
                       ) AS pending_count,
                       0 AS known_unseen_count
                   FROM pending_bulk_operations pbo"""
            ).fetchall()
    sonuc = {}
    for satir in satirlar:
        kategori = str(satir["source_category"] or "").strip()
        if not kategori:
            continue
        sonuc[kategori] = {
            "snapshot_complete": bool(satir["snapshot_complete"]),
            "pending_count": max(0, int(satir["pending_count"] or 0)),
            "known_unseen_count": max(
                0, int(satir["known_unseen_count"] or 0)
            ),
        }
    with veritabani_baglantisi() as db:
        if eposta:
            tekli_satirlar = db.execute(
                """SELECT
                       pd.source_category,
                       COUNT(*) AS pending_count,
                       SUM(CASE WHEN fm.is_seen = 0 THEN 1 ELSE 0 END)
                           AS known_unseen_count
                   FROM pending_deletions pd
                   JOIN accounts a ON a.id = pd.account_id
                   LEFT JOIN folders f
                     ON f.account_id = pd.account_id
                    AND f.imap_name = pd.source_folder
                   LEFT JOIN folder_messages fm
                     ON fm.folder_id = f.id
                    AND fm.uid = pd.source_uid
                    AND (
                        pd.source_uidvalidity IS NULL
                        OR fm.uidvalidity = pd.source_uidvalidity
                    )
                   WHERE a.email = ? COLLATE NOCASE
                     AND pd.bulk_operation_id IS NULL
                   GROUP BY pd.source_category""",
                (str(eposta or "").strip(),),
            ).fetchall()
        else:
            tekli_satirlar = db.execute(
                """SELECT source_category, COUNT(*) AS pending_count,
                          0 AS known_unseen_count
                   FROM pending_deletions
                   WHERE bulk_operation_id IS NULL
                   GROUP BY source_category"""
            ).fetchall()
    for satir in tekli_satirlar:
        kategori = str(satir["source_category"] or "").strip()
        if not kategori:
            continue
        mevcut = sonuc.setdefault(
            kategori,
            {
                "snapshot_complete": True,
                "pending_count": 0,
                "known_unseen_count": 0,
            },
        )
        mevcut["pending_count"] += max(0, int(satir["pending_count"] or 0))
        mevcut["known_unseen_count"] += max(
            0, int(satir["known_unseen_count"] or 0)
        )
    return sonuc


def bekleyen_silme_sayisi(eposta=None):
    with veritabani_baglantisi() as db:
        if eposta:
            return int(db.execute(
                """SELECT COUNT(*) FROM pending_deletions pd
                   JOIN accounts a ON a.id = pd.account_id
                   WHERE a.email = ? COLLATE NOCASE""",
                (str(eposta).strip(),),
            ).fetchone()[0])
        return int(db.execute("SELECT COUNT(*) FROM pending_deletions").fetchone()[0])


def bekleyen_kaynak_uidleri(eposta, kaynak_klasor=None, kaynak_kategori=None):
    """Bir klasörde arayüzden gizlenmesi gereken kalıcı kuyruk UID'lerini döndürür."""
    eposta = str(eposta or "").strip()
    kaynak_klasor = str(kaynak_klasor or "").strip()
    kaynak_kategori = str(kaynak_kategori or "").strip()
    if not eposta or (not kaynak_klasor and not kaynak_kategori):
        return set()
    kosullar = ["a.email = ? COLLATE NOCASE"]
    degerler = [eposta]
    if kaynak_klasor:
        kosullar.append("pd.source_folder = ?")
        degerler.append(kaynak_klasor)
    elif kaynak_kategori:
        kosullar.append("pd.source_category = ?")
        degerler.append(kaynak_kategori)
    with veritabani_baglantisi() as db:
        satirlar = db.execute(
            """SELECT pd.source_uid FROM pending_deletions pd
               JOIN accounts a ON a.id = pd.account_id
               WHERE """ + " AND ".join(kosullar),
            tuple(degerler),
        ).fetchall()
    return {str(satir[0]) for satir in satirlar}


def _bekleyenleri_al(eposta):
    with veritabani_baglantisi() as db:
        return [dict(satir) for satir in db.execute(
            """SELECT pd.*, a.email FROM pending_deletions pd
               JOIN accounts a ON a.id = pd.account_id
               WHERE a.email = ? COLLATE NOCASE ORDER BY pd.created_at, pd.id""",
            (str(eposta or "").strip(),),
        ).fetchall()]


def _bekleyen_toplu_islemleri_al(eposta):
    with veritabani_baglantisi() as db:
        return [
            dict(satir)
            for satir in db.execute(
                """SELECT pbo.*, a.email
                   FROM pending_bulk_operations pbo
                   JOIN accounts a ON a.id = pbo.account_id
                   WHERE a.email = ? COLLATE NOCASE
                   ORDER BY pbo.created_at, pbo.id""",
                (str(eposta or "").strip(),),
            ).fetchall()
        ]


def _toplu_islem_hatasi_kaydet(kayit, hata):
    with veritabani_baglantisi(yazma=True) as db:
        db.execute(
            """UPDATE pending_bulk_operations
               SET attempt_count = attempt_count + 1,
                   last_error = ?, updated_at = ?
               WHERE id = ? AND request_token = ?""",
            (
                str(hata or "")[:1000],
                _simdi(),
                int(kayit["id"]),
                str(kayit.get("request_token") or ""),
            ),
        )


def _toplu_islem_anlik_goruntusunu_hazirla(imap, kayit):
    """Sunucudaki kaynak klasörü bir kez görüntüleyip tekli kalıcı kuyruğa bağlar."""
    if bool(kayit.get("snapshot_complete")):
        return
    tip, _veri = imap.select(kayit["source_folder"], readonly=False)
    imap_ok_mu(tip, _("Toplu işlem için kaynak klasör açılamadı."))
    kaynak_uidvalidity = imap_uidvalidity_al(imap)
    if kaynak_uidvalidity <= 0:
        raise MailHatasi(_("Toplu işlem için UIDVALIDITY alınamadı."))
    tip, veri = imap.uid("SEARCH", None, "ALL")
    imap_ok_mu(tip, _("Toplu işlem için klasör içeriği alınamadı."))
    uidler = imap_uid_search_sonucu_uidleri_al(veri)
    gmail_id_haritasi = {}
    if uidler:
        gmail_id_haritasi = imap_x_gm_msgid_haritasi_al(imap, uidler)
    # İlk yerel anlık gizleme, son eşitlemeden kalmış UID'ler içerebilir.
    # Sunucu görüntüsü doğrulandıktan sonra bu işe bağlı tekli kuyruğu güncel
    # görüntüden yeniden kurmak, artık var olmayan UID'lerin işi kilitlemesini önler.
    with veritabani_baglantisi(yazma=True) as db:
        db.execute(
            "DELETE FROM pending_deletions WHERE bulk_operation_id = ?",
            (int(kayit["id"]),),
        )
    if uidler:
        silme_isteklerini_kuyruga_al(
            kayit["email"],
            kayit["source_folder"],
            kayit["source_category"],
            uidler,
            kayit["deletion_type"],
            kayit["trash_folder"],
            kayit.get("source_label") or "",
            bool(kayit.get("remove_source_label")),
            int(kayit["id"]),
            kaynak_uidvalidity,
            gmail_id_haritasi,
        )
    with veritabani_baglantisi(yazma=True) as db:
        db.execute(
            """UPDATE pending_bulk_operations
               SET snapshot_complete = 1, source_uidvalidity = ?,
                   last_error = NULL, updated_at = ?
               WHERE id = ? AND request_token = ?""",
            (
                kaynak_uidvalidity,
                _simdi(),
                int(kayit["id"]),
                str(kayit.get("request_token") or ""),
            ),
        )


def _tamamlanan_toplu_islemleri_temizle(eposta):
    """Doğrulanan toplu işi ikinci denetime kadar kalıcı tutup sonra temizler."""
    simdi = _simdi()
    with veritabani_baglantisi() as db:
        adaylar = [
            dict(satir)
            for satir in db.execute(
                """SELECT pbo.*
                   FROM pending_bulk_operations pbo
                   JOIN accounts a ON a.id = pbo.account_id
                   WHERE a.email = ? COLLATE NOCASE
                     AND pbo.snapshot_complete = 1
                     AND NOT EXISTS (
                         SELECT 1 FROM pending_deletions pd
                         WHERE pd.bulk_operation_id = pbo.id
                           AND pd.remote_verified = 0
                     )""",
                (str(eposta or "").strip(),),
            ).fetchall()
        ]
    temizlenen = 0
    for toplu_islem in adaylar:
        dogrulama_zamani = int(toplu_islem.get("settlement_verified_at") or 0)
        if dogrulama_zamani <= 0:
            with veritabani_baglantisi(yazma=True) as db:
                db.execute(
                    """UPDATE pending_bulk_operations
                       SET settlement_verified_at = ?, updated_at = ?
                       WHERE id = ? AND request_token = ?""",
                    (
                        simdi,
                        simdi,
                        int(toplu_islem["id"]),
                        str(toplu_islem.get("request_token") or ""),
                    ),
                )
            continue
        if simdi - dogrulama_zamani < TOPLU_YERLESME_BEKLEME_SANIYESI:
            continue
        with veritabani_baglantisi() as db:
            kayitlar = [
                dict(satir)
                for satir in db.execute(
                    "SELECT * FROM pending_deletions WHERE bulk_operation_id = ?",
                    (int(toplu_islem["id"]),),
                ).fetchall()
            ]
        for kayit in kayitlar:
            _basarili_kaydi_temizle(kayit)
        with veritabani_baglantisi(yazma=True) as db:
            temizlenen += max(
                0,
                db.execute(
                    """DELETE FROM pending_bulk_operations
                       WHERE id = ? AND request_token = ?
                         AND NOT EXISTS (
                             SELECT 1 FROM pending_deletions pd
                             WHERE pd.bulk_operation_id = pending_bulk_operations.id
                         )""",
                    (
                        int(toplu_islem["id"]),
                        str(toplu_islem.get("request_token") or ""),
                    ),
                ).rowcount,
            )
    return temizlenen


def _kuyruk_msgid_guncelle(kuyruk_id, istek_kimligi, gmail_id):
    with veritabani_baglantisi(yazma=True) as db:
        db.execute(
            """UPDATE pending_deletions SET gmail_message_id = ?, updated_at = ?
               WHERE id = ? AND request_token = ?""",
            (str(gmail_id), _simdi(), int(kuyruk_id), str(istek_kimligi or "")),
        )


def _hata_kaydet(kuyruk_id, istek_kimligi, hata):
    with veritabani_baglantisi(yazma=True) as db:
        db.execute(
            """UPDATE pending_deletions SET attempt_count = attempt_count + 1,
               last_error = ?, updated_at = ? WHERE id = ? AND request_token = ?""",
            (
                str(hata or "")[:1000], _simdi(), int(kuyruk_id),
                str(istek_kimligi or ""),
            ),
        )
        satir = db.execute(
            """SELECT attempt_count FROM pending_deletions
               WHERE id = ? AND request_token = ?""",
            (int(kuyruk_id), str(istek_kimligi or "")),
        ).fetchone()
    return int(satir[0]) if satir else 0


def _baglanti_uyarisini_sinirli_kaydet(hata):
    global _SON_BAGLANTI_UYARISI
    simdi = _simdi()
    if simdi - int(_SON_BAGLANTI_UYARISI or 0) < BAGLANTI_UYARI_ARALIGI_SANIYE:
        return
    _SON_BAGLANTI_UYARISI = simdi
    uyari_kaydet(
        "Bekleyen silme kuyruğu sunucuya bağlanamadı; sessizce yeniden denenecek.",
        hata,
    )


def _klasorde_uid_bul(
    imap, klasor, gmail_id, yedek_uid=None, beklenen_uidvalidity=None
):
    tip, _veri = imap.select(klasor, readonly=False)
    imap_ok_mu(tip, _("Silme için klasör açılamadı."))
    if gmail_id and str(gmail_id).isdigit():
        tip, veri = imap.uid("SEARCH", "X-GM-MSGID", str(gmail_id))
        imap_ok_mu(tip, _("E-posta sunucuda aranamadı."))
        return imap_uid_search_sonucu_uidleri_al(veri)
    if yedek_uid and str(yedek_uid).isdigit():
        gecerli_uidvalidity = imap_uidvalidity_al(imap)
        try:
            beklenen_uidvalidity = int(beklenen_uidvalidity or 0)
        except (TypeError, ValueError):
            beklenen_uidvalidity = 0
        if beklenen_uidvalidity <= 0 or gecerli_uidvalidity != beklenen_uidvalidity:
            raise MailHatasi(
                _("Silme kuyruğundaki UID artık güvenle doğrulanamıyor; işlem durduruldu.")
            )
        try:
            harita = imap_x_gm_msgid_haritasi_al(imap, [str(yedek_uid)])
            return [str(yedek_uid)], harita.get(str(yedek_uid))
        except MailHatasi:
            return [], None
    return []


def _copte_var_mi(imap, cop_klasoru, gmail_id):
    if not gmail_id:
        return False
    tip, _veri = imap.select(cop_klasoru, readonly=False)
    imap_ok_mu(tip, _("Çöp Kutusu açılamadı."))
    tip, veri = imap.uid("SEARCH", "X-GM-MSGID", str(gmail_id))
    imap_ok_mu(tip, _("Çöp Kutusu denetlenemedi."))
    return bool(imap_uid_search_sonucu_uidleri_al(veri))


def _kalici_silme_baslatildi_isaretle(kuyruk_id, istek_kimligi):
    """Belirsiz bağlantı sonucunda kalıcı silmeyi tekrar güvenli kılan işareti yazar."""
    with veritabani_baglantisi(yazma=True) as db:
        db.execute(
            """UPDATE pending_deletions SET permanent_delete_started = 1,
               updated_at = ? WHERE id = ? AND request_token = ?""",
            (_simdi(), int(kuyruk_id), str(istek_kimligi or "")),
        )


def _sunucu_islemi_tamamlandi_isaretle(kuyruk_id, istek_kimligi):
    """IMAP komutu tamamlandıktan sonra kaydı yansıma doğrulamasına geçirir."""
    simdi = _simdi()
    with veritabani_baglantisi(yazma=True) as db:
        db.execute(
            """UPDATE pending_deletions
               SET remote_completed = 1, remote_completed_at = ?,
                   last_error = NULL, updated_at = ?
               WHERE id = ? AND request_token = ?""",
            (
                simdi,
                simdi,
                int(kuyruk_id),
                str(istek_kimligi or ""),
            ),
        )


def _sunucu_yansima_durumunu_isaretle(kuyruk_id, istek_kimligi, dogrulandi):
    with veritabani_baglantisi(yazma=True) as db:
        db.execute(
            """UPDATE pending_deletions
               SET remote_verified = ?, updated_at = ?
               WHERE id = ? AND request_token = ?""",
            (
                int(bool(dogrulandi)),
                _simdi(),
                int(kuyruk_id),
                str(istek_kimligi or ""),
            ),
        )
        if not dogrulandi:
            db.execute(
                """UPDATE pending_bulk_operations
                   SET settlement_verified_at = NULL, updated_at = ?
                   WHERE id = (
                       SELECT bulk_operation_id FROM pending_deletions
                       WHERE id = ? AND request_token = ?
                   )""",
                (
                    _simdi(),
                    int(kuyruk_id),
                    str(istek_kimligi or ""),
                ),
            )


def _sunucu_yansimasi_dogrulandi_mi(imap, kayit):
    """İşlemin Gmail klasör görünümüne gerçekten yansıdığını kimlikle doğrular."""
    gmail_id = str(kayit.get("gmail_message_id") or "").strip()
    if not gmail_id:
        bulunan = _klasorde_uid_bul(
            imap,
            kayit["source_folder"],
            "",
            kayit.get("source_uid"),
            kayit.get("source_uidvalidity"),
        )
        uidler = bulunan[0] if isinstance(bulunan, tuple) else bulunan
        return not bool(uidler)

    if kayit["operation_type"] == "permanent":
        return not _copte_var_mi(imap, kayit["trash_folder"], gmail_id)

    kaynakta = _klasorde_uid_bul(
        imap,
        kayit["source_folder"],
        gmail_id,
        kayit.get("source_uid"),
        kayit.get("source_uidvalidity"),
    )
    kaynak_uidleri = kaynakta[0] if isinstance(kaynakta, tuple) else kaynakta
    if kaynak_uidleri:
        return False
    return _copte_var_mi(imap, kayit["trash_folder"], gmail_id)


def _sunucuda_isle(imap, kayit):
    gmail_id = str(kayit.get("gmail_message_id") or "").strip()
    bulunan = _klasorde_uid_bul(
        imap,
        kayit["source_folder"],
        gmail_id,
        kayit.get("source_uid"),
        kayit.get("source_uidvalidity"),
    )
    if isinstance(bulunan, tuple):
        uidler, bulunan_gmail_id = bulunan
        if bulunan_gmail_id:
            gmail_id = str(bulunan_gmail_id)
            kayit["gmail_message_id"] = gmail_id
            _kuyruk_msgid_guncelle(
                kayit["id"], kayit.get("request_token"), gmail_id
            )
    else:
        uidler = bulunan

    if kayit["operation_type"] == "trash":
        if not uidler:
            if _copte_var_mi(imap, kayit["trash_folder"], gmail_id):
                return
            raise MailHatasi(_("Silinecek e-posta kaynak klasörde bulunamadı."))
        imap_gmail_etiket_destegini_dogrula(imap)
        uid_kumesi = uid_kumesi_hazirla(uidler, "Silinecek e-posta bulunamadı.")
        imap_gmail_etiket_store(
            imap, uid_kumesi, "+", "\\Trash", "E-posta Çöp Kutusuna taşınamadı."
        )
        if kayit.get("remove_source_label") and kayit.get("source_label"):
            imap_gmail_etiket_store(
                imap, uid_kumesi, "-", kayit["source_label"],
                "E-posta kaynak etiketinden kaldırılamadı."
            )
        return

    if not gmail_id:
        raise MailHatasi(_("Kalıcı silme için Gmail ileti kimliği bulunamadı."))
    if str(kayit["source_folder"]) != str(kayit["trash_folder"]) and uidler:
        imap_gmail_etiket_destegini_dogrula(imap)
        imap_gmail_etiket_store(
            imap, uid_kumesi_hazirla(uidler), "+", "\\Trash",
            "E-posta kalıcı silme için Çöp Kutusuna taşınamadı."
        )
    if not _copte_var_mi(imap, kayit["trash_folder"], gmail_id):
        if bool(kayit.get("permanent_delete_started")):
            # Önceki çağrı sunucuda tamamlanmış, ancak NVDA yerel temizlikten
            # önce kapanmış olabilir. Kalıcı silme bu durumda idempotenttir.
            return
        raise MailHatasi(
            _("E-posta kalıcı silme için henüz Çöp Kutusunda doğrulanamadı.")
        )
    _kalici_silme_baslatildi_isaretle(
        kayit["id"], kayit.get("request_token")
    )
    imap_gmail_msgidleri_kalici_sil(
        imap, [gmail_id], kayit["trash_folder"], "E-posta kalıcı olarak silinemedi."
    )


def _basarili_kaydi_temizle(kayit):
    silinecek_yollar = []
    with EK_ONBELLEK_KILIDI:
        with veritabani_baglantisi(yazma=True) as db:
            if kayit["operation_type"] == "permanent":
                gmail_id = str(kayit.get("gmail_message_id") or "").strip()
                if gmail_id:
                    mesajlar = db.execute(
                        "SELECT id FROM messages WHERE account_id = ? AND gmail_message_id = ?",
                        (int(kayit["account_id"]), gmail_id),
                    ).fetchall()
                else:
                    mesajlar = db.execute(
                        """SELECT m.id FROM messages m JOIN folder_messages fm ON fm.message_id = m.id
                           JOIN folders f ON f.id = fm.folder_id
                           WHERE m.account_id = ? AND f.imap_name = ? AND fm.uid = ?
                             AND fm.uidvalidity = ?""",
                        (
                            int(kayit["account_id"]), kayit["source_folder"],
                            int(kayit["source_uid"]), int(kayit.get("source_uidvalidity") or 0),
                        ),
                    ).fetchall()
                mesaj_idleri = [int(satir[0]) for satir in mesajlar]
                for mesaj_id in mesaj_idleri:
                    silinecek_yollar.extend(
                        str(satir[0]) for satir in db.execute(
                            "SELECT local_path FROM attachments WHERE message_id = ? AND local_path IS NOT NULL",
                            (mesaj_id,),
                        ).fetchall()
                    )
                    db.execute("DELETE FROM messages WHERE id = ?", (mesaj_id,))
            elif kayit["operation_type"] == "trash":
                gmail_id = str(kayit.get("gmail_message_id") or "").strip()
                if gmail_id:
                    mesajlar = db.execute(
                        "SELECT id FROM messages WHERE account_id = ? AND gmail_message_id = ?",
                        (int(kayit["account_id"]), gmail_id),
                    ).fetchall()
                else:
                    mesajlar = db.execute(
                        """SELECT m.id FROM messages m
                           JOIN folder_messages fm ON fm.message_id = m.id
                           JOIN folders f ON f.id = fm.folder_id
                           WHERE m.account_id = ? AND f.imap_name = ?
                             AND fm.uid = ? AND fm.uidvalidity = ?""",
                        (
                            int(kayit["account_id"]),
                            kayit["source_folder"],
                            int(kayit["source_uid"]),
                            int(kayit.get("source_uidvalidity") or 0),
                        ),
                    ).fetchall()
                etkilenen_klasorler = set()
                for mesaj_id in (int(satir[0]) for satir in mesajlar):
                    etkilenen_klasorler.update(
                        int(satir[0])
                        for satir in db.execute(
                            """SELECT DISTINCT fm.folder_id
                               FROM folder_messages fm
                               JOIN folders f ON f.id = fm.folder_id
                               WHERE fm.message_id = ? AND f.imap_name <> ?""",
                            (mesaj_id, str(kayit["trash_folder"])),
                        ).fetchall()
                    )
                    db.execute(
                        """UPDATE folder_messages SET is_present = 0, updated_at = ?
                           WHERE message_id = ? AND folder_id IN (
                               SELECT id FROM folders WHERE imap_name <> ?
                           )""",
                        (_simdi(), mesaj_id, str(kayit["trash_folder"])),
                    )
                _klasor_sayaclarini_guncelle(db, etkilenen_klasorler)
            db.execute(
                "DELETE FROM pending_deletions WHERE id = ? AND request_token = ?",
                (int(kayit["id"]), str(kayit.get("request_token") or "")),
            )

        for goreli_yol in silinecek_yollar:
            try:
                tam_yol = _guvenli_tam_yol(goreli_yol)
                if os.path.isfile(tam_yol):
                    os.remove(tam_yol)
            except (OSError, ValueError) as e:
                hata_kaydet("Kalıcı silinen e-postanın ek dosyası temizlenemedi.", e)


def bekleyen_silmeleri_isle(
    ayarlar=None,
    eposta=None,
    iptal_edildi_mi=None,
    baglanti_bildir=None,
):
    """Kuyruğu sessizce işler; bağlantı hatalarında kayıtları sonraki denemeye bırakır."""
    if not _ISLEME_KILIDI.acquire(False):
        return {
            "islenen": 0,
            "bekleyen": bekleyen_silme_sayisi(eposta),
            "kilitli": True,
        }
    posta_kilidi_alindi = False
    try:
        posta_kilidi_alindi = POSTA_DURUM_KILIDI.acquire(False)
        if not posta_kilidi_alindi:
            return {
                "islenen": 0,
                "bekleyen": bekleyen_silme_sayisi(eposta),
                "kilitli": True,
            }
        if iptal_edildi_mi and iptal_edildi_mi():
            return {
                "islenen": 0,
                "bekleyen": bekleyen_silme_sayisi(eposta),
                "kilitli": False,
                "iptal_edildi": True,
            }
        veritabani_hazirla()
        ayarlar = dict(ayarlar or ayarlari_yukle())
        hesap = str(eposta or ayarlar.get("eposta", "") or "").strip().lower()
        if not hesap or not str(ayarlar.get("sifre", "") or "").strip():
            return {
                "islenen": 0,
                "bekleyen": bekleyen_silme_sayisi(hesap or None),
                "kilitli": False,
            }
        kayitlar = _bekleyenleri_al(hesap)
        toplu_islemler = _bekleyen_toplu_islemleri_al(hesap)
        if not kayitlar and not toplu_islemler:
            return {"islenen": 0, "bekleyen": 0, "kilitli": False}
        islenen = 0
        iptal_edildi = False
        baglanti = ImapBaglantisi(ayarlar)
        if baglanti_bildir:
            baglanti_bildir(baglanti)
        try:
            with baglanti as imap:
                for toplu_islem in toplu_islemler:
                    if iptal_edildi_mi and iptal_edildi_mi():
                        iptal_edildi = True
                        break
                    try:
                        _toplu_islem_anlik_goruntusunu_hazirla(
                            imap,
                            toplu_islem,
                        )
                    except Exception as e:
                        _toplu_islem_hatasi_kaydet(toplu_islem, e)
                        uyari_kaydet(
                            "Bekleyen toplu silme işlemi hazırlanamadı; yeniden denenecek.",
                            e,
                        )
                if not iptal_edildi:
                    kayitlar = _bekleyenleri_al(hesap)
                    for kayit in kayitlar:
                        if iptal_edildi_mi and iptal_edildi_mi():
                            iptal_edildi = True
                            break
                        try:
                            if not bool(kayit.get("remote_completed")):
                                _sunucuda_isle(imap, kayit)
                                _sunucu_islemi_tamamlandi_isaretle(
                                    kayit["id"], kayit.get("request_token")
                                )
                                kayit["remote_completed"] = 1
                                islenen += 1
                            # Gmail'in klasör görünümü IMAP komutundan sonra gecikebilir.
                            # Kalıcı gizleme, sunucudaki yansıma doğrulanana kadar korunur.
                            dogrulandi = _sunucu_yansimasi_dogrulandi_mi(imap, kayit)
                            _sunucu_yansima_durumunu_isaretle(
                                kayit["id"], kayit.get("request_token"), dogrulandi
                            )
                            if dogrulandi and not kayit.get("bulk_operation_id"):
                                _basarili_kaydi_temizle(kayit)
                        except Exception as e:
                            deneme = _hata_kaydet(
                                kayit["id"], kayit.get("request_token"), e
                            )
                            if deneme in (1, 2, 4, 8) or (deneme > 0 and deneme % 20 == 0):
                                uyari_kaydet(
                                    "Bekleyen silme işlemi tamamlanamadı; yeniden denenecek.",
                                    e,
                                )
                _tamamlanan_toplu_islemleri_temizle(hesap)
        except Exception as e:
            # Kapanış sırasında bağlantının kesilmesi beklenen bir iptal yoludur.
            if iptal_edildi_mi and iptal_edildi_mi():
                iptal_edildi = True
            else:
                # Bağlantı yokken kullanıcıya konuşma/ileti gönderilmez.
                _baglanti_uyarisini_sinirli_kaydet(e)
        finally:
            if baglanti_bildir:
                baglanti_bildir(None)
        return {
            "islenen": islenen,
            "bekleyen": bekleyen_silme_sayisi(hesap),
            "kilitli": False,
            "iptal_edildi": iptal_edildi,
        }
    finally:
        if posta_kilidi_alindi:
            POSTA_DURUM_KILIDI.release()
        _ISLEME_KILIDI.release()


class BekleyenSilmeYoneticisi:
    """NVDA açıkken bekleyen silmeleri düzenli ve sessiz biçimde yeniden dener."""

    def __init__(self, ilk_gecikme_ms=ILK_DENEME_GECIKMESI_MS):
        self._iptal = threading.Event()
        self._baglanti_kilidi = threading.Lock()
        self._aktif_baglanti = None
        self._zamanlayici = None
        self._zamanla(ilk_gecikme_ms)

    def _zamanla(self, gecikme_ms):
        if self._iptal.is_set():
            return
        try:
            self._zamanlayici = wx.CallLater(max(0, int(gecikme_ms)), self._baslat)
        except Exception as e:
            hata_kaydet("Bekleyen silme zamanlayıcısı oluşturulamadı.", e)

    def _baslat(self):
        self._zamanlayici = None
        if self._iptal.is_set():
            return
        arka_planda_calistir(self._calistir)

    def _aktif_baglantiyi_ayarla(self, baglanti):
        with self._baglanti_kilidi:
            self._aktif_baglanti = baglanti

    def _calistir(self):
        try:
            bekleyen_silmeleri_isle(
                iptal_edildi_mi=self._iptal.is_set,
                baglanti_bildir=self._aktif_baglantiyi_ayarla,
            )
        finally:
            self._aktif_baglantiyi_ayarla(None)
            if not self._iptal.is_set():
                wx.CallAfter(self._zamanla, YENIDEN_DENEME_ARALIGI_MS)

    def durdur(self):
        self._iptal.set()
        zamanlayici = self._zamanlayici
        self._zamanlayici = None
        if zamanlayici:
            try:
                zamanlayici.Stop()
            except Exception as e:
                hata_kaydet("Bekleyen silme zamanlayıcısı durdurulamadı.", e)
        with self._baglanti_kilidi:
            aktif_baglanti = self._aktif_baglanti
        if aktif_baglanti is not None:
            try:
                aktif_baglanti.shutdown()
            except Exception as e:
                hata_kaydet("Bekleyen silme işleminin etkin IMAP bağlantısı kapatılamadı.", e)
