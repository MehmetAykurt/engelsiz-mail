# -*- coding: utf-8 -*-
"""SQLite FTS5 destekli, güvenli geri dönüşlü e-posta araması."""

import re

from .database import veritabani_baglantisi
from .logger import uyari_kaydet
from .sqlite_compat import sqlite3


def fts5_hazirla():
    try:
        with veritabani_baglantisi(yazma=True) as db:
            mevcut = db.execute(
                "SELECT 1 FROM sqlite_master WHERE type='table' AND name='message_search'"
            ).fetchone()
            db.execute(
                """CREATE VIRTUAL TABLE IF NOT EXISTS message_search USING fts5(
                    message_id UNINDEXED, subject, sender, recipients, body,
                    tokenize='unicode61 remove_diacritics 2'
                )"""
            )
            if not mevcut:
                db.execute(
                    """INSERT INTO message_search(message_id, subject, sender, recipients, body)
                       SELECT m.id, m.subject, m.sender, m.recipients_to || ' ' || m.recipients_cc,
                              COALESCE(b.plain_text, '')
                       FROM messages m LEFT JOIN message_bodies b ON b.message_id=m.id"""
                )
            db.execute("""CREATE TRIGGER IF NOT EXISTS message_search_message_ai AFTER INSERT ON messages BEGIN
                INSERT INTO message_search(message_id,subject,sender,recipients,body)
                VALUES(new.id,new.subject,new.sender,new.recipients_to||' '||new.recipients_cc,''); END""")
            db.execute("""CREATE TRIGGER IF NOT EXISTS message_search_message_au AFTER UPDATE ON messages BEGIN
                DELETE FROM message_search WHERE message_id=old.id;
                INSERT INTO message_search(message_id,subject,sender,recipients,body)
                VALUES(new.id,new.subject,new.sender,new.recipients_to||' '||new.recipients_cc,
                    COALESCE((SELECT plain_text FROM message_bodies WHERE message_id=new.id),'')); END""")
            db.execute("""CREATE TRIGGER IF NOT EXISTS message_search_message_ad AFTER DELETE ON messages BEGIN
                DELETE FROM message_search WHERE message_id=old.id; END""")
            db.execute("""CREATE TRIGGER IF NOT EXISTS message_search_body_ai AFTER INSERT ON message_bodies BEGIN
                DELETE FROM message_search WHERE message_id=new.message_id;
                INSERT INTO message_search(message_id,subject,sender,recipients,body)
                SELECT m.id,m.subject,m.sender,m.recipients_to||' '||m.recipients_cc,new.plain_text
                FROM messages m WHERE m.id=new.message_id; END""")
            db.execute("""CREATE TRIGGER IF NOT EXISTS message_search_body_au AFTER UPDATE OF plain_text ON message_bodies BEGIN
                UPDATE message_search SET body=new.plain_text WHERE message_id=new.message_id; END""")
            db.execute("""CREATE TRIGGER IF NOT EXISTS message_search_body_ad AFTER DELETE ON message_bodies BEGIN
                UPDATE message_search SET body='' WHERE message_id=old.message_id; END""")
            # Yalnizca tablonun adina guvenme; MATCH ve FTS yardimci fonksiyonlari
            # gercekten calisiyor mu dogrula. Bozuk/sahte tablo SQL geri donusunu tetikler.
            db.execute(
                """SELECT COUNT(*) FROM message_search
                   WHERE message_search MATCH '"__engelsiz_mail_fts_probe__"'"""
            ).fetchone()
        return True
    except sqlite3.DatabaseError as e:
        uyari_kaydet("FTS5 kullanılamıyor; normal SQL araması kullanılacak.", e)
        return False


METIN_ARAMA_TURLERI = ("gonderen", "konu", "icerik")
OKUNMA_DURUMU_ARAMA_TURLERI = {"okunmamis": 0, "okunmus": 1}
ARAMA_TURLERI = METIN_ARAMA_TURLERI + tuple(OKUNMA_DURUMU_ARAMA_TURLERI)
FTS_ALANLARI = {"gonderen": "sender", "konu": "subject", "icerik": "body"}


def _fts_sorgusu(metin, arama_turu):
    kelimeler = re.findall(r"[^\s\"']+", str(metin or ""), flags=re.UNICODE)
    alan = FTS_ALANLARI[arama_turu]
    return " AND ".join(
        alan + ':"' + kelime.replace('"', '""') + '"' for kelime in kelimeler
    )


def epostalarda_ara(eposta, aranan, arama_turu="gonderen", sinir=100, fts_kullan=True):
    aranan = str(aranan or "").strip()
    arama_turu = str(arama_turu or "").strip().lower()
    if arama_turu not in ARAMA_TURLERI:
        raise ValueError("Geçersiz arama türü.")
    if arama_turu in METIN_ARAMA_TURLERI and not aranan:
        return []
    try:
        sinir = max(1, min(501, int(sinir or 100)))
    except (TypeError, ValueError):
        sinir = 100
    okunma_durumu = OKUNMA_DURUMU_ARAMA_TURLERI.get(arama_turu)
    fts_ifadesi = (
        _fts_sorgusu(aranan, arama_turu)
        if arama_turu in METIN_ARAMA_TURLERI
        else ""
    )
    fts_var = bool(fts_kullan and fts_ifadesi and fts5_hazirla())
    with veritabani_baglantisi() as db:
        if okunma_durumu is not None:
            satirlar = db.execute(
                """WITH eslesen AS (
                       SELECT m.id, fm.uid, f.imap_name, f.display_name,
                              m.subject, m.sender, m.recipients_to,
                              m.internal_date, m.date_header, '' AS excerpt,
                              ROW_NUMBER() OVER (
                                  PARTITION BY m.id
                                  ORDER BY CASE WHEN f.imap_name='INBOX' THEN 0 ELSE 1 END,
                                           fm.id
                              ) AS sira
                       FROM messages m
                       JOIN folder_messages fm ON fm.message_id=m.id
                           AND fm.is_present=1 AND fm.is_deleted=0 AND fm.is_draft=0
                       JOIN folders f ON f.id=fm.folder_id
                           AND fm.uidvalidity=f.uidvalidity
                       JOIN accounts a ON a.id=m.account_id
                       WHERE a.email=? COLLATE NOCASE AND fm.is_seen=?
                         AND NOT EXISTS (
                             SELECT 1 FROM pending_deletions pd
                             WHERE pd.account_id=a.id AND (
                                 (pd.gmail_message_id IS NOT NULL
                                  AND pd.gmail_message_id=m.gmail_message_id)
                                 OR (pd.source_folder=f.imap_name
                                     AND pd.source_uid=fm.uid
                                     AND pd.source_uidvalidity=fm.uidvalidity)
                             )
                         )
                   )
                   SELECT id, uid, imap_name, display_name, subject, sender,
                          recipients_to, internal_date, date_header, excerpt
                   FROM eslesen WHERE sira=1
                   ORDER BY internal_date DESC, id DESC LIMIT ?""",
                (str(eposta or "").strip(), okunma_durumu, sinir),
            ).fetchall()
        elif fts_var:
            satirlar = db.execute(
                f"""WITH eslesen AS (
                       SELECT m.id, fm.uid, f.imap_name, f.display_name,
                              m.subject, m.sender, m.recipients_to,
                              m.internal_date, m.date_header, '' AS excerpt,
                              ROW_NUMBER() OVER (
                                  PARTITION BY m.id
                                  ORDER BY CASE WHEN f.imap_name='INBOX' THEN 0 ELSE 1 END,
                                           fm.id
                              ) AS sira
                       FROM message_search
                       JOIN messages m ON m.id=message_search.message_id
                       JOIN folder_messages fm ON fm.message_id=m.id
                           AND fm.is_present=1 AND fm.is_deleted=0 AND fm.is_draft=0
                       JOIN folders f ON f.id=fm.folder_id
                           AND fm.uidvalidity=f.uidvalidity
                       JOIN accounts a ON a.id=m.account_id
                       WHERE a.email=? COLLATE NOCASE AND message_search MATCH ?
                         AND NOT EXISTS (
                             SELECT 1 FROM pending_deletions pd
                             WHERE pd.account_id=a.id AND (
                                 (pd.gmail_message_id IS NOT NULL
                                  AND pd.gmail_message_id=m.gmail_message_id)
                                 OR (pd.source_folder=f.imap_name
                                     AND pd.source_uid=fm.uid
                                     AND pd.source_uidvalidity=fm.uidvalidity)
                             )
                         )
                   )
                   SELECT id, uid, imap_name, display_name, subject, sender,
                          recipients_to, internal_date, date_header, excerpt
                   FROM eslesen WHERE sira=1
                   ORDER BY internal_date DESC, id DESC LIMIT ?""",
                (str(eposta or "").strip(), fts_ifadesi, sinir),
            ).fetchall()
        else:
            desen = "%" + aranan.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_") + "%"
            alan_ifadesi = {
                "gonderen": "m.sender LIKE ? ESCAPE '\\'",
                "konu": "m.subject LIKE ? ESCAPE '\\'",
                "icerik": "COALESCE(b.plain_text,'') LIKE ? ESCAPE '\\'",
            }[arama_turu]
            satirlar = db.execute(
                f"""WITH eslesen AS (
                       SELECT m.id, fm.uid, f.imap_name, f.display_name,
                              m.subject, m.sender, m.recipients_to,
                              m.internal_date, m.date_header,
                              substr(COALESCE(b.plain_text,''),1,300) AS excerpt,
                              ROW_NUMBER() OVER (
                                  PARTITION BY m.id
                                  ORDER BY CASE WHEN f.imap_name='INBOX' THEN 0 ELSE 1 END,
                                           fm.id
                              ) AS sira
                       FROM messages m
                       LEFT JOIN message_bodies b ON b.message_id=m.id
                       JOIN folder_messages fm ON fm.message_id=m.id
                           AND fm.is_present=1 AND fm.is_deleted=0 AND fm.is_draft=0
                       JOIN folders f ON f.id=fm.folder_id
                           AND fm.uidvalidity=f.uidvalidity
                       JOIN accounts a ON a.id=m.account_id
                       WHERE a.email=? COLLATE NOCASE AND {alan_ifadesi}
                         AND NOT EXISTS (
                             SELECT 1 FROM pending_deletions pd
                             WHERE pd.account_id=a.id AND (
                                 (pd.gmail_message_id IS NOT NULL
                                  AND pd.gmail_message_id=m.gmail_message_id)
                                 OR (pd.source_folder=f.imap_name
                                     AND pd.source_uid=fm.uid
                                     AND pd.source_uidvalidity=fm.uidvalidity)
                             )
                         )
                   )
                   SELECT id, uid, imap_name, display_name, subject, sender,
                          recipients_to, internal_date, date_header, excerpt
                   FROM eslesen WHERE sira=1
                   ORDER BY internal_date DESC, id DESC LIMIT ?""",
                (str(eposta or "").strip(), desen, sinir),
            ).fetchall()
    return [dict(satir) for satir in satirlar]
