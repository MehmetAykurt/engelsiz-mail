# -*- coding: utf-8 -*-
"""E-posta başlıkları için SQLite kayıt ve sorgu hizmeti."""

import time

from .database import veritabani_baglantisi
from .database_schema import BODY_PARSER_VERSION


def _simdi():
    return int(time.time())


def _klasor_sayaclarini_guncelle(db, klasor_id):
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
               )
           WHERE id = ?""",
        (int(klasor_id), int(klasor_id), int(klasor_id)),
    )


def hesap_ve_klasor_hazirla(eposta, imap_klasoru, gorunen_ad, uidvalidity):
    eposta = str(eposta or "").strip().lower()
    imap_klasoru = str(imap_klasoru or "").strip()
    if not eposta or not imap_klasoru or int(uidvalidity or 0) <= 0:
        raise ValueError("Hesap, klasör ve UIDVALIDITY zorunludur.")
    simdi = _simdi()
    with veritabani_baglantisi(yazma=True) as db:
        db.execute(
            """
            INSERT INTO accounts(email, provider, created_at, updated_at)
            VALUES (?, 'gmail', ?, ?)
            ON CONFLICT(email) DO UPDATE SET updated_at = excluded.updated_at
            """,
            (eposta, simdi, simdi),
        )
        hesap_id = db.execute("SELECT id FROM accounts WHERE email = ?", (eposta,)).fetchone()[0]
        mevcut = db.execute(
            "SELECT id, uidvalidity FROM folders WHERE account_id = ? AND imap_name = ?",
            (hesap_id, imap_klasoru),
        ).fetchone()
        uid_degisti = bool(mevcut and int(mevcut["uidvalidity"] or 0) != int(uidvalidity))
        db.execute(
            """
            INSERT INTO folders(
                account_id, imap_name, display_name, uidvalidity, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?)
            ON CONFLICT(account_id, imap_name) DO UPDATE SET
                display_name = excluded.display_name,
                uidvalidity = excluded.uidvalidity,
                is_selectable = 1,
                updated_at = excluded.updated_at
            """,
            (hesap_id, imap_klasoru, gorunen_ad or imap_klasoru, int(uidvalidity), simdi, simdi),
        )
        klasor_id = db.execute(
            "SELECT id FROM folders WHERE account_id = ? AND imap_name = ?",
            (hesap_id, imap_klasoru),
        ).fetchone()[0]
        if uid_degisti:
            db.execute(
                """UPDATE messages SET updated_at = ? WHERE id IN (
                       SELECT message_id FROM folder_messages WHERE folder_id = ?
                   )""",
                (simdi, klasor_id),
            )
            db.execute("DELETE FROM folder_messages WHERE folder_id = ?", (klasor_id,))
            db.execute("DELETE FROM sync_state WHERE folder_id = ?", (klasor_id,))
    return hesap_id, klasor_id, uid_degisti


def klasor_yerel_onbellegi_var_mi(eposta, imap_klasoru):
    """Klasör daha önce SQLite envanterine girdiyse True döndürür."""
    eposta = str(eposta or "").strip()
    imap_klasoru = str(imap_klasoru or "").strip()
    if not eposta or not imap_klasoru:
        return False
    with veritabani_baglantisi() as db:
        satir = db.execute(
            """
            SELECT 1
            FROM accounts AS a
            JOIN folders AS f ON f.account_id = a.id
            WHERE a.email = ? COLLATE NOCASE
              AND f.imap_name = ?
              AND f.is_selectable = 1
            LIMIT 1
            """,
            (eposta, imap_klasoru),
        ).fetchone()
    return satir is not None


def hesap_klasor_envanterini_uzlastir(eposta, aktif_imap_klasorleri):
    """LIST sonucunda bulunmayan eski klasorleri veri kaybetmeden pasiflestirir."""
    eposta = str(eposta or "").strip().lower()
    aktifler = {
        str(klasor or "").strip()
        for klasor in (aktif_imap_klasorleri or [])
        if str(klasor or "").strip()
    }
    if not eposta:
        return {"aktif": 0, "pasif": 0, "pasif_uyelik": 0}
    simdi = _simdi()
    with veritabani_baglantisi(yazma=True) as db:
        hesap = db.execute(
            "SELECT id FROM accounts WHERE email = ? COLLATE NOCASE", (eposta,)
        ).fetchone()
        if not hesap:
            return {"aktif": 0, "pasif": 0, "pasif_uyelik": 0}
        klasorler = db.execute(
            "SELECT id, imap_name FROM folders WHERE account_id = ?", (hesap[0],)
        ).fetchall()
        aktif_idler = [satir["id"] for satir in klasorler if satir["imap_name"] in aktifler]
        pasif_idler = [satir["id"] for satir in klasorler if satir["imap_name"] not in aktifler]
        for klasor_id in aktif_idler:
            db.execute(
                "UPDATE folders SET is_selectable = 1, updated_at = ? WHERE id = ?",
                (simdi, klasor_id),
            )
        pasif_uyelik = 0
        for klasor_id in pasif_idler:
            db.execute(
                """UPDATE folders SET is_selectable = 0, message_count = 0,
                   unseen_count = 0, updated_at = ? WHERE id = ?""",
                (simdi, klasor_id),
            )
            imlec = db.execute(
                """UPDATE folder_messages SET is_present = 0, updated_at = ?
                   WHERE folder_id = ? AND is_present = 1""",
                (simdi, klasor_id),
            )
            pasif_uyelik += max(0, imlec.rowcount)
    return {
        "aktif": len(aktif_idler),
        "pasif": len(pasif_idler),
        "pasif_uyelik": pasif_uyelik,
    }


def klasoru_yerelde_pasif_yap(eposta, imap_klasoru):
    """Silinen veya yeniden adlandirilan tek klasoru guvenle pasiflestirir."""
    simdi = _simdi()
    with veritabani_baglantisi(yazma=True) as db:
        klasor = db.execute(
            """SELECT f.id FROM accounts AS a JOIN folders AS f ON f.account_id = a.id
               WHERE a.email = ? COLLATE NOCASE AND f.imap_name = ?""",
            (str(eposta or "").strip(), str(imap_klasoru or "").strip()),
        ).fetchone()
        if not klasor:
            return 0
        klasor_id = int(klasor[0])
        db.execute(
            """UPDATE folders SET is_selectable = 0, message_count = 0,
               unseen_count = 0, updated_at = ? WHERE id = ?""",
            (simdi, klasor_id),
        )
        imlec = db.execute(
            """UPDATE folder_messages SET is_present = 0, updated_at = ?
               WHERE folder_id = ? AND is_present = 1""",
            (simdi, klasor_id),
        )
    return max(0, imlec.rowcount)


def kayitli_uidleri_al(klasor_id, uidvalidity):
    with veritabani_baglantisi() as db:
        satirlar = db.execute(
            "SELECT uid FROM folder_messages WHERE folder_id = ? AND uidvalidity = ?",
            (int(klasor_id), int(uidvalidity)),
        ).fetchall()
    return {str(satir[0]) for satir in satirlar}


def bayrak_paketini_kaydet(klasor_id, uidvalidity, kayitlar):
    simdi = _simdi()
    with veritabani_baglantisi(yazma=True) as db:
        for kayit in kayitlar or []:
            bayraklar = set(kayit.get("flags") or [])
            kucuk_bayraklar = {str(bayrak).lower() for bayrak in bayraklar}
            db.execute(
                """
                UPDATE folder_messages SET flags = ?, is_seen = ?, is_flagged = ?,
                    is_answered = ?, is_draft = ?, is_deleted = ?,
                    last_seen_at = ?, updated_at = ?
                WHERE folder_id = ? AND uidvalidity = ? AND uid = ?
                """,
                (
                    " ".join(sorted(bayraklar)), int("\\seen" in kucuk_bayraklar),
                    int("\\flagged" in kucuk_bayraklar), int("\\answered" in kucuk_bayraklar),
                    int("\\draft" in kucuk_bayraklar), int("\\deleted" in kucuk_bayraklar),
                    simdi, simdi, int(klasor_id), int(uidvalidity), int(kayit["uid"]),
                ),
            )


def klasor_uidlerini_pasif_yap(eposta, imap_klasoru, uidler):
    uidler = sorted({int(uid) for uid in uidler or [] if str(uid).isdigit()})
    if not uidler:
        return 0
    simdi = _simdi()
    toplam = 0
    with veritabani_baglantisi(yazma=True) as db:
        klasor = db.execute(
            """SELECT f.id FROM accounts AS a JOIN folders AS f ON f.account_id = a.id
               WHERE a.email = ? COLLATE NOCASE AND f.imap_name = ?""",
            (str(eposta or "").strip(), str(imap_klasoru or "").strip()),
        ).fetchone()
        if not klasor:
            return 0
        klasor_id = int(klasor[0])
        for baslangic in range(0, len(uidler), 500):
            parca = uidler[baslangic:baslangic + 500]
            yerler = ",".join("?" for _ in parca)
            imlec = db.execute(
                f"""
                UPDATE folder_messages SET is_present = 0, updated_at = ?
                WHERE folder_id = ? AND uid IN ({yerler})
                """,
                (simdi, klasor_id, *parca),
            )
            toplam += max(0, imlec.rowcount)
        _klasor_sayaclarini_guncelle(db, klasor_id)
    return toplam


def gmail_mesajlarini_yerelde_pasif_yap(eposta, gmail_mesaj_idleri):
    """Kalici silinen Gmail iletilerini hesabin tum klasorlerinde pasiflestirir."""
    eposta = str(eposta or "").strip().lower()
    gmail_idleri = sorted({
        str(gmail_id or "").strip()
        for gmail_id in (gmail_mesaj_idleri or [])
        if str(gmail_id or "").strip()
    })
    if not eposta or not gmail_idleri:
        return 0
    simdi = _simdi()
    toplam = 0
    etkilenen_klasorler = set()
    with veritabani_baglantisi(yazma=True) as db:
        for baslangic in range(0, len(gmail_idleri), 400):
            parca = gmail_idleri[baslangic:baslangic + 400]
            yerler = ",".join("?" for _ in parca)
            kosul_parametreleri = (eposta, *parca)
            etkilenen_klasorler.update(
                int(satir[0])
                for satir in db.execute(
                    f"""SELECT DISTINCT fm.folder_id
                        FROM folder_messages AS fm
                        JOIN messages AS m ON m.id = fm.message_id
                        JOIN accounts AS a ON a.id = m.account_id
                        WHERE a.email = ? COLLATE NOCASE
                          AND m.gmail_message_id IN ({yerler})""",
                    kosul_parametreleri,
                ).fetchall()
            )
            imlec = db.execute(
                f"""UPDATE folder_messages SET is_present = 0, updated_at = ?
                    WHERE message_id IN (
                        SELECT m.id FROM messages AS m
                        JOIN accounts AS a ON a.id = m.account_id
                        WHERE a.email = ? COLLATE NOCASE
                          AND m.gmail_message_id IN ({yerler})
                    ) AND is_present = 1""",
                (simdi, *kosul_parametreleri),
            )
            toplam += max(0, imlec.rowcount)
        for klasor_id in etkilenen_klasorler:
            _klasor_sayaclarini_guncelle(db, klasor_id)
    return toplam


def klasor_basliklarini_listele(eposta, imap_klasoru, sinir):
    """Bir klasörün güncel başlıklarını en yeni UID önce olacak şekilde döndürür."""
    try:
        sinir = max(1, int(sinir))
    except (TypeError, ValueError):
        sinir = 25
    with veritabani_baglantisi() as db:
        satirlar = db.execute(
            """
            SELECT
                fm.uid, fm.is_seen, m.sender, m.recipients_to, m.subject,
                m.preview, m.has_attachments, m.gmail_thread_id,
                m.gmail_message_id, m.internal_date, m.date_header
            FROM accounts AS a
            JOIN folders AS f ON f.account_id = a.id
            JOIN folder_messages AS fm ON fm.folder_id = f.id
            JOIN messages AS m ON m.id = fm.message_id
            WHERE a.email = ? COLLATE NOCASE
              AND f.imap_name = ?
              AND fm.is_present = 1
              AND fm.is_deleted = 0
              AND NOT EXISTS (
                  SELECT 1 FROM pending_deletions pd
                  WHERE pd.account_id = a.id AND (
                      (pd.gmail_message_id IS NOT NULL
                       AND pd.gmail_message_id = m.gmail_message_id)
                      OR (pd.source_folder = f.imap_name
                          AND pd.source_uid = fm.uid
                          AND pd.source_uidvalidity = fm.uidvalidity)
                  )
              )
              AND NOT EXISTS (
                  SELECT 1 FROM pending_bulk_operations pbo
                  WHERE pbo.account_id = a.id
                    AND pbo.source_folder = f.imap_name
                    AND pbo.snapshot_complete = 0
              )
            ORDER BY fm.uid DESC
            LIMIT ?
            """,
            (str(eposta or "").strip(), str(imap_klasoru or "").strip(), sinir),
        ).fetchall()
    return [dict(satir) for satir in satirlar]


def klasor_konusma_basliklarini_listele(eposta, imap_klasoru, konusma_siniri):
    """En yeni konuşmaları ve bu konuşmaların klasördeki bütün iletilerini döndürür."""
    try:
        konusma_siniri = max(1, int(konusma_siniri))
    except (TypeError, ValueError):
        konusma_siniri = 25
    with veritabani_baglantisi() as db:
        satirlar = db.execute(
            """
            WITH uygun AS (
                SELECT
                    fm.uid, fm.is_seen, m.sender, m.recipients_to, m.subject,
                    m.preview, m.has_attachments, m.gmail_thread_id,
                    m.gmail_message_id, m.internal_date, m.date_header,
                    CASE
                        WHEN COALESCE(m.gmail_thread_id, '') <> '' THEN (
                            SELECT COUNT(*)
                            FROM messages AS tum_m
                            WHERE tum_m.account_id = m.account_id
                              AND tum_m.gmail_thread_id = m.gmail_thread_id
                              AND EXISTS (
                                  SELECT 1
                                  FROM folder_messages AS tum_fm
                                  JOIN folders AS tum_f
                                    ON tum_f.id = tum_fm.folder_id
                                  WHERE tum_fm.message_id = tum_m.id
                                    AND tum_fm.uidvalidity = tum_f.uidvalidity
                                    AND tum_fm.is_present = 1
                                    AND tum_fm.is_deleted = 0
                              )
                        )
                        ELSE 1
                    END AS toplam_ileti_sayisi,
                    CASE
                        WHEN COALESCE(m.gmail_thread_id, '') <> ''
                            THEN 'thread:' || m.gmail_thread_id
                        ELSE 'uid:' || CAST(fm.uid AS TEXT)
                    END AS konusma_anahtari,
                    COALESCE(m.internal_date, fm.uid, 0) AS siralama
                FROM accounts AS a
                JOIN folders AS f ON f.account_id = a.id
                JOIN folder_messages AS fm ON fm.folder_id = f.id
                JOIN messages AS m ON m.id = fm.message_id
                WHERE a.email = ? COLLATE NOCASE
                  AND f.imap_name = ?
                  AND fm.uidvalidity = f.uidvalidity
                  AND fm.is_present = 1
                  AND fm.is_deleted = 0
                  AND NOT EXISTS (
                      SELECT 1 FROM pending_deletions pd
                      WHERE pd.account_id = a.id AND (
                          (pd.gmail_message_id IS NOT NULL
                           AND pd.gmail_message_id = m.gmail_message_id)
                          OR (pd.source_folder = f.imap_name
                              AND pd.source_uid = fm.uid
                              AND pd.source_uidvalidity = fm.uidvalidity)
                      )
                  )
                  AND NOT EXISTS (
                      SELECT 1 FROM pending_bulk_operations pbo
                      WHERE pbo.account_id = a.id
                        AND pbo.source_folder = f.imap_name
                        AND pbo.snapshot_complete = 0
                  )
            ), son_konusmalar AS (
                SELECT konusma_anahtari, MAX(siralama) AS son_siralama
                FROM uygun
                GROUP BY konusma_anahtari
                ORDER BY son_siralama DESC
                LIMIT ?
            )
            SELECT uygun.*
            FROM uygun
            JOIN son_konusmalar USING (konusma_anahtari)
            ORDER BY son_konusmalar.son_siralama DESC, uygun.siralama DESC,
                     uygun.uid DESC
            """,
            (
                str(eposta or "").strip(),
                str(imap_klasoru or "").strip(),
                konusma_siniri,
            ),
        ).fetchall()
    return [dict(satir) for satir in satirlar]


def konusma_mesajlarini_listele(eposta, imap_klasoru, gmail_thread_id):
    """Geçerli klasördeki bir Gmail konuşmasının iletilerini en yeniden eskiye döndürür."""
    thread_id = str(gmail_thread_id or "").strip()
    if not thread_id:
        return []
    with veritabani_baglantisi() as db:
        satirlar = db.execute(
            """
            SELECT fm.uid, fm.is_seen, m.id AS message_id, m.gmail_message_id,
                   m.gmail_thread_id, m.rfc_message_id, m.in_reply_to,
                   m.references_header, m.subject, m.sender, m.recipients_to,
                   m.recipients_cc, m.reply_to, m.date_header, m.internal_date, m.preview,
                   m.has_attachments, b.plain_text, b.attachments_cached,
                   b.parser_version
            FROM accounts AS a
            JOIN folders AS f ON f.account_id = a.id
            JOIN folder_messages AS fm ON fm.folder_id = f.id
            JOIN messages AS m ON m.id = fm.message_id
            LEFT JOIN message_bodies AS b ON b.message_id = m.id
            WHERE a.email = ? COLLATE NOCASE AND f.imap_name = ?
              AND m.gmail_thread_id = ? AND fm.uidvalidity = f.uidvalidity
              AND fm.is_present = 1 AND fm.is_deleted = 0
              AND NOT EXISTS (
                  SELECT 1 FROM pending_deletions pd
                  WHERE pd.account_id = a.id AND (
                      (pd.gmail_message_id IS NOT NULL AND pd.gmail_message_id = m.gmail_message_id)
                      OR (pd.source_folder = f.imap_name AND pd.source_uid = fm.uid
                          AND pd.source_uidvalidity = fm.uidvalidity)
                  )
              )
              AND NOT EXISTS (
                  SELECT 1 FROM pending_bulk_operations pbo
                  WHERE pbo.account_id = a.id
                    AND pbo.source_folder = f.imap_name
                    AND pbo.snapshot_complete = 0
              )
            ORDER BY COALESCE(m.internal_date, 0) DESC, fm.uid DESC
            """,
            (str(eposta or "").strip(), str(imap_klasoru or "").strip(), thread_id),
        ).fetchall()
    return [dict(satir) for satir in satirlar]


def klasor_onizleme_haritasi_al(eposta, imap_klasoru, uidler):
    temiz_uidler = [int(uid) for uid in uidler or [] if str(uid).isdigit()]
    if not temiz_uidler:
        return {}
    sonuc = {}
    with veritabani_baglantisi() as db:
        for baslangic in range(0, len(temiz_uidler), 500):
            parca = temiz_uidler[baslangic:baslangic + 500]
            yerler = ",".join("?" for _ in parca)
            satirlar = db.execute(
                f"""
                SELECT fm.uid, m.preview
                FROM accounts AS a
                JOIN folders AS f ON f.account_id = a.id
                JOIN folder_messages AS fm ON fm.folder_id = f.id
                JOIN messages AS m ON m.id = fm.message_id
                WHERE a.email = ? COLLATE NOCASE
                  AND f.imap_name = ?
                  AND fm.uidvalidity = f.uidvalidity
                  AND fm.is_present = 1
                  AND fm.is_deleted = 0
                  AND fm.uid IN ({yerler})
                """,
                (str(eposta or "").strip(), str(imap_klasoru or "").strip(), *parca),
            ).fetchall()
            for satir in satirlar:
                sonuc[str(satir["uid"])] = str(satir["preview"] or "")
    return sonuc


def onizlemesi_eksik_uidleri_al(eposta, imap_klasoru, uidler):
    temiz_uidler = []
    gorulen = set()
    for uid in uidler or []:
        uid_metni = str(uid or "").strip()
        if not uid_metni.isdigit():
            continue
        uid_sayisi = int(uid_metni)
        if uid_sayisi <= 0 or uid_sayisi in gorulen:
            continue
        gorulen.add(uid_sayisi)
        temiz_uidler.append(uid_sayisi)
    if not temiz_uidler:
        return []

    eksikler = set()
    with veritabani_baglantisi() as db:
        for baslangic in range(0, len(temiz_uidler), 500):
            parca = temiz_uidler[baslangic:baslangic + 500]
            yerler = ",".join("?" for _ in parca)
            satirlar = db.execute(
                f"""
                SELECT fm.uid
                FROM accounts AS a
                JOIN folders AS f ON f.account_id = a.id
                JOIN folder_messages AS fm ON fm.folder_id = f.id
                JOIN messages AS m ON m.id = fm.message_id
                WHERE a.email = ? COLLATE NOCASE
                  AND f.imap_name = ?
                  AND fm.uidvalidity = f.uidvalidity
                  AND fm.is_present = 1
                  AND fm.is_deleted = 0
                  AND COALESCE(m.preview, '') = ''
                  AND fm.uid IN ({yerler})
                """,
                (str(eposta or "").strip(), str(imap_klasoru or "").strip(), *parca),
            ).fetchall()
            eksikler.update(int(satir[0]) for satir in satirlar)
    return [str(uid) for uid in temiz_uidler if uid in eksikler]


def mesaj_govdesini_al(eposta, imap_klasoru, uid):
    """UID bağlamı doğrulanmış, önbelleğe alınmış ileti gövdesini döndürür."""
    with veritabani_baglantisi() as db:
        satir = db.execute(
            """
            SELECT
                fm.message_id, fm.is_seen, m.sender, m.recipients_to,
                m.recipients_cc, m.reply_to, m.subject, m.date_header,
                m.rfc_message_id, m.references_header,
                m.has_attachments, b.plain_text, b.raw_size_bytes, b.fetched_at,
                b.attachments_cached, b.parser_version
            FROM accounts AS a
            JOIN folders AS f ON f.account_id = a.id
            JOIN folder_messages AS fm ON fm.folder_id = f.id
            JOIN messages AS m ON m.id = fm.message_id
            JOIN message_bodies AS b ON b.message_id = m.id
            WHERE a.email = ? COLLATE NOCASE AND f.imap_name = ?
              AND fm.uid = ? AND fm.uidvalidity = f.uidvalidity
              AND fm.is_present = 1
              AND NOT EXISTS (
                  SELECT 1 FROM pending_deletions pd
                  WHERE pd.account_id = a.id AND (
                      (pd.gmail_message_id IS NOT NULL
                       AND pd.gmail_message_id = m.gmail_message_id)
                      OR (pd.source_folder = f.imap_name
                          AND pd.source_uid = fm.uid
                          AND pd.source_uidvalidity = fm.uidvalidity)
                  )
              )
              AND NOT EXISTS (
                  SELECT 1 FROM pending_bulk_operations pbo
                  WHERE pbo.account_id = a.id
                    AND pbo.source_folder = f.imap_name
                    AND pbo.snapshot_complete = 0
              )
            """,
            (str(eposta or "").strip(), str(imap_klasoru or "").strip(), int(uid)),
        ).fetchone()
    return dict(satir) if satir else None


def govdesi_eksik_uidleri_al(eposta, imap_klasoru, uidler):
    """Başlığı kayıtlı ancak gövdesi henüz önbelleğe alınmamış UID'leri döndürür."""
    temiz_uidler = []
    gorulen = set()
    for uid in uidler or []:
        uid_metni = str(uid or "").strip()
        if not uid_metni.isdigit():
            continue
        uid_sayisi = int(uid_metni)
        if uid_sayisi <= 0 or uid_sayisi in gorulen:
            continue
        gorulen.add(uid_sayisi)
        temiz_uidler.append(uid_sayisi)
    if not temiz_uidler:
        return []

    eksikler = set()
    eposta = str(eposta or "").strip()
    imap_klasoru = str(imap_klasoru or "").strip()
    with veritabani_baglantisi() as db:
        for baslangic in range(0, len(temiz_uidler), 500):
            parca = temiz_uidler[baslangic:baslangic + 500]
            yerler = ",".join("?" for _ in parca)
            satirlar = db.execute(
                f"""
                SELECT fm.uid
                FROM accounts AS a
                JOIN folders AS f ON f.account_id = a.id
                JOIN folder_messages AS fm ON fm.folder_id = f.id
                JOIN messages AS m ON m.id = fm.message_id
                LEFT JOIN message_bodies AS b ON b.message_id = m.id
                WHERE a.email = ? COLLATE NOCASE
                  AND f.imap_name = ?
                  AND fm.uidvalidity = f.uidvalidity
                  AND fm.is_present = 1
                  AND fm.is_deleted = 0
                  AND (b.message_id IS NULL OR b.parser_version < ?)
                  AND NOT EXISTS (
                      SELECT 1 FROM pending_deletions pd
                      WHERE pd.account_id = a.id AND (
                          (pd.gmail_message_id IS NOT NULL
                           AND pd.gmail_message_id = m.gmail_message_id)
                          OR (pd.source_folder = f.imap_name
                              AND pd.source_uid = fm.uid
                              AND pd.source_uidvalidity = fm.uidvalidity)
                      )
                  )
                  AND NOT EXISTS (
                      SELECT 1 FROM pending_bulk_operations pbo
                      WHERE pbo.account_id = a.id
                        AND pbo.source_folder = f.imap_name
                        AND pbo.snapshot_complete = 0
                  )
                  AND fm.uid IN ({yerler})
                """,
                (eposta, imap_klasoru, BODY_PARSER_VERSION, *parca),
            ).fetchall()
            eksikler.update(int(satir[0]) for satir in satirlar)
    return [str(uid) for uid in temiz_uidler if uid in eksikler]


def mesaj_onbellek_kimligini_al(eposta, imap_klasoru, uid):
    with veritabani_baglantisi() as db:
        satir = db.execute(
            """
            SELECT fm.message_id, fm.uidvalidity
            FROM accounts AS a
            JOIN folders AS f ON f.account_id = a.id
            JOIN folder_messages AS fm ON fm.folder_id = f.id
            WHERE a.email = ? COLLATE NOCASE AND f.imap_name = ?
              AND fm.uid = ? AND fm.uidvalidity = f.uidvalidity AND fm.is_present = 1
            """,
            (str(eposta or "").strip(), str(imap_klasoru or "").strip(), int(uid)),
        ).fetchone()
    return dict(satir) if satir else None


def ek_kayitlarini_kaydet(mesaj_id, kayitlar, tamamlandi):
    simdi = _simdi()
    with veritabani_baglantisi(yazma=True) as db:
        db.execute("DELETE FROM attachments WHERE message_id = ?", (int(mesaj_id),))
        for kayit in kayitlar or []:
            db.execute(
                """
                INSERT INTO attachments(
                    message_id, part_path, file_name, content_type, size_bytes,
                    sha256, local_path, download_state, downloaded_at, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, 'downloaded', ?, ?, ?)
                """,
                (
                    int(mesaj_id), str(kayit["part_path"]), str(kayit["file_name"]),
                    str(kayit.get("content_type") or "application/octet-stream"),
                    int(kayit.get("size_bytes") or 0), str(kayit.get("sha256") or ""),
                    str(kayit["local_path"]), simdi, simdi, simdi,
                ),
            )
        imlec = db.execute(
            "UPDATE message_bodies SET attachments_cached = ?, updated_at = ? WHERE message_id = ?",
            (int(bool(tamamlandi)), simdi, int(mesaj_id)),
        )
        if imlec.rowcount != 1:
            raise ValueError("Ekler kaydedilmeden once e-posta govdesi kaydedilmelidir.")


def ek_kayitlarini_al(mesaj_id):
    with veritabani_baglantisi() as db:
        satirlar = db.execute(
            """SELECT part_path, file_name, content_type, size_bytes, sha256, local_path
               FROM attachments WHERE message_id = ? AND download_state = 'downloaded'
               ORDER BY id""",
            (int(mesaj_id),),
        ).fetchall()
    return [dict(satir) for satir in satirlar]


def mesaj_govdesini_kaydet(
    eposta, imap_klasoru, uid, duz_metin, ham_boyut, tarih_basligi=None
):
    """Başlığı kayıtlı iletiye ayrıştırılmış düz metin gövdesini atomik kaydeder."""
    simdi = _simdi()
    with veritabani_baglantisi(yazma=True) as db:
        satir = db.execute(
            """
            SELECT fm.message_id
            FROM accounts AS a
            JOIN folders AS f ON f.account_id = a.id
            JOIN folder_messages AS fm ON fm.folder_id = f.id
            WHERE a.email = ? COLLATE NOCASE AND f.imap_name = ?
              AND fm.uid = ? AND fm.uidvalidity = f.uidvalidity
              AND fm.is_present = 1
            """,
            (str(eposta or "").strip(), str(imap_klasoru or "").strip(), int(uid)),
        ).fetchone()
        if not satir:
            return False
        mesaj_id = satir[0]
        db.execute(
            """
            INSERT INTO message_bodies(
                message_id, plain_text, raw_size_bytes, fetched_at, updated_at,
                parser_version
            ) VALUES (?, ?, ?, ?, ?, ?)
            ON CONFLICT(message_id) DO UPDATE SET
                plain_text = excluded.plain_text,
                raw_size_bytes = excluded.raw_size_bytes,
                fetched_at = excluded.fetched_at,
                parser_version = excluded.parser_version,
                attachments_cached = 0,
                updated_at = excluded.updated_at
            """,
            (
                mesaj_id, str(duz_metin or ""), int(ham_boyut or 0), simdi, simdi,
                BODY_PARSER_VERSION,
            ),
        )
        onizleme = " ".join(str(duz_metin or "").split())[:300]
        db.execute(
            """UPDATE messages SET preview = ?,
               date_header = COALESCE(?, date_header), updated_at = ? WHERE id = ?""",
            (onizleme, str(tarih_basligi or "").strip() or None, simdi, mesaj_id),
        )
    return True


def mesaj_onizlemesini_kaydet(eposta, imap_klasoru, uid, onizleme):
    onizleme = str(onizleme or "").strip()
    if not onizleme:
        return False
    simdi = _simdi()
    with veritabani_baglantisi(yazma=True) as db:
        satir = db.execute(
            """
            SELECT fm.message_id
            FROM accounts AS a
            JOIN folders AS f ON f.account_id = a.id
            JOIN folder_messages AS fm ON fm.folder_id = f.id
            WHERE a.email = ? COLLATE NOCASE AND f.imap_name = ?
              AND fm.uid = ? AND fm.uidvalidity = f.uidvalidity
              AND fm.is_present = 1
            """,
            (str(eposta or "").strip(), str(imap_klasoru or "").strip(), int(uid)),
        ).fetchone()
        if not satir:
            return False
        imlec = db.execute(
            "UPDATE messages SET preview = ?, updated_at = ? WHERE id = ?",
            (onizleme, simdi, int(satir[0])),
        )
    return imlec.rowcount > 0


def mesaji_yerelde_okundu_yap(eposta, imap_klasoru, uid):
    simdi = _simdi()
    with veritabani_baglantisi(yazma=True) as db:
        uyelik = db.execute(
            """SELECT fm.message_id
               FROM accounts AS a
               JOIN folders AS f ON f.account_id = a.id
               JOIN folder_messages AS fm ON fm.folder_id = f.id
               WHERE a.email = ? COLLATE NOCASE AND f.imap_name = ?
                 AND fm.uid = ? AND fm.uidvalidity = f.uidvalidity
                 AND fm.is_present = 1 AND fm.is_deleted = 0""",
            (
                str(eposta or "").strip(),
                str(imap_klasoru or "").strip(),
                int(uid),
            ),
        ).fetchone()
        if not uyelik:
            return False
        mesaj_id = int(uyelik[0])
        etkilenen_klasorler = [
            int(satir[0])
            for satir in db.execute(
                """SELECT DISTINCT fm.folder_id
                   FROM folder_messages AS fm
                   JOIN folders AS f ON f.id = fm.folder_id
                   WHERE fm.message_id = ? AND fm.uidvalidity = f.uidvalidity
                     AND fm.is_present = 1 AND fm.is_deleted = 0
                     AND fm.is_seen = 0""",
                (mesaj_id,),
            ).fetchall()
        ]
        imlec = db.execute(
            """UPDATE folder_messages SET is_seen = 1, updated_at = ?
               WHERE message_id = ? AND is_present = 1 AND is_deleted = 0
                 AND is_seen = 0
                 AND uidvalidity = (
                     SELECT uidvalidity FROM folders
                     WHERE folders.id = folder_messages.folder_id
                 )""",
            (simdi, mesaj_id),
        )
        for klasor_id in etkilenen_klasorler:
            _klasor_sayaclarini_guncelle(db, klasor_id)
    return imlec.rowcount > 0


def baslik_paketini_kaydet(hesap_id, klasor_id, uidvalidity, kayitlar):
    simdi = _simdi()
    with veritabani_baglantisi(yazma=True) as db:
        for kayit in kayitlar or []:
            uid = int(kayit["uid"])
            uyelik = db.execute(
                """SELECT message_id FROM folder_messages
                   WHERE folder_id = ? AND uidvalidity = ? AND uid = ?""",
                (klasor_id, uidvalidity, uid),
            ).fetchone()
            mesaj_id = uyelik[0] if uyelik else None
            gmail_id = kayit.get("gmail_message_id") or None
            if mesaj_id is None and gmail_id:
                satir = db.execute(
                    "SELECT id FROM messages WHERE account_id = ? AND gmail_message_id = ?",
                    (hesap_id, gmail_id),
                ).fetchone()
                mesaj_id = satir[0] if satir else None
            if mesaj_id is None:
                imlec = db.execute(
                    "INSERT INTO messages(account_id, created_at, updated_at) VALUES (?, ?, ?)",
                    (hesap_id, simdi, simdi),
                )
                mesaj_id = imlec.lastrowid

            db.execute(
                """
                UPDATE messages SET
                    gmail_message_id = ?, gmail_thread_id = ?, rfc_message_id = ?,
                    in_reply_to = ?, references_header = ?, subject = ?, sender = ?,
                    recipients_to = ?, recipients_cc = ?, reply_to = ?, sent_at = ?,
                    internal_date = ?, date_header = ?, size_bytes = ?,
                    preview = CASE
                        WHEN ? <> '' THEN ?
                        ELSE preview
                    END,
                    has_attachments = ?,
                    headers_complete = 1, updated_at = ?
                WHERE id = ?
                """,
                (
                    gmail_id, kayit.get("gmail_thread_id"), kayit.get("rfc_message_id"),
                    kayit.get("in_reply_to"), kayit.get("references_header"),
                    kayit.get("subject", ""), kayit.get("sender", ""),
                    kayit.get("recipients_to", ""), kayit.get("recipients_cc", ""),
                    kayit.get("reply_to", ""), kayit.get("sent_at"),
                    kayit.get("internal_date"), kayit.get("date_header"), kayit.get("size_bytes"),
                    kayit.get("preview", ""), kayit.get("preview", ""),
                    int(bool(kayit.get("has_attachments"))),
                    simdi, mesaj_id,
                ),
            )
            bayraklar = set(kayit.get("flags") or [])
            kucuk_bayraklar = {str(bayrak).lower() for bayrak in bayraklar}
            mevcut_mesaj_uyeligi = db.execute(
                "SELECT id FROM folder_messages WHERE folder_id = ? AND message_id = ?",
                (klasor_id, mesaj_id),
            ).fetchone()
            parametreler = (
                " ".join(sorted(bayraklar)), int("\\seen" in kucuk_bayraklar),
                int("\\flagged" in kucuk_bayraklar), int("\\answered" in kucuk_bayraklar),
                int("\\draft" in kucuk_bayraklar), int("\\deleted" in kucuk_bayraklar),
                simdi, simdi,
            )
            if mevcut_mesaj_uyeligi:
                db.execute(
                    """UPDATE folder_messages SET uidvalidity = ?, uid = ?, flags = ?,
                       is_seen = ?, is_flagged = ?, is_answered = ?, is_draft = ?,
                       is_deleted = ?, is_present = 1, last_seen_at = ?, updated_at = ?
                       WHERE id = ?""",
                    (int(uidvalidity), uid, *parametreler, mevcut_mesaj_uyeligi[0]),
                )
                continue
            db.execute(
                """
                INSERT INTO folder_messages(
                    folder_id, message_id, uidvalidity, uid, flags, is_seen, is_flagged,
                    is_answered, is_draft, is_deleted, is_present, last_seen_at,
                    created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 1, ?, ?, ?)
                ON CONFLICT(folder_id, uidvalidity, uid) DO UPDATE SET
                    message_id = excluded.message_id, flags = excluded.flags,
                    is_seen = excluded.is_seen, is_flagged = excluded.is_flagged,
                    is_answered = excluded.is_answered, is_draft = excluded.is_draft,
                    is_deleted = excluded.is_deleted, is_present = 1,
                    last_seen_at = excluded.last_seen_at, updated_at = excluded.updated_at
                """,
                (
                    klasor_id, mesaj_id, int(uidvalidity), uid, *parametreler, simdi,
                ),
            )


def klasor_senkronizasyonunu_tamamla(klasor_id, uidvalidity, sunucu_uidleri):
    uidler = sorted({int(uid) for uid in sunucu_uidleri or []})
    simdi = _simdi()
    with veritabani_baglantisi(yazma=True) as db:
        db.execute(
            "UPDATE folder_messages SET is_present = 0, updated_at = ? WHERE folder_id = ?",
            (simdi, klasor_id),
        )
        for baslangic in range(0, len(uidler), 500):
            parca = uidler[baslangic:baslangic + 500]
            yer_tutucular = ",".join("?" for _ in parca)
            db.execute(
                f"""UPDATE folder_messages SET is_present = 1, last_seen_at = ?, updated_at = ?
                    WHERE folder_id = ? AND uidvalidity = ? AND uid IN ({yer_tutucular})""",
                (simdi, simdi, klasor_id, uidvalidity, *parca),
            )
        son_uid = max(uidler) if uidler else 0
        db.execute(
            """
            INSERT INTO sync_state(
                folder_id, last_seen_uid, initial_sync_complete, last_completed_at, updated_at
            ) VALUES (?, ?, 1, ?, ?)
            ON CONFLICT(folder_id) DO UPDATE SET
                last_seen_uid = excluded.last_seen_uid, initial_sync_complete = 1,
                last_completed_at = excluded.last_completed_at, last_error = NULL,
                updated_at = excluded.updated_at
            """,
            (klasor_id, son_uid, simdi, simdi),
        )
        _klasor_sayaclarini_guncelle(db, klasor_id)
        db.execute(
            "UPDATE folders SET last_synced_at = ?, updated_at = ? WHERE id = ?",
            (simdi, simdi, klasor_id),
        )
