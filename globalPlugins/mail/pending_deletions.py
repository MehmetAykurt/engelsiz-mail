# -*- coding: utf-8 -*-
"""Çevrimdışı silme isteklerini kalıcı SQLite kuyruğunda yönetir."""

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
YENIDEN_DENEME_ARALIGI_MS = 60000
_ISLEME_KILIDI = threading.Lock()
_SON_BAGLANTI_UYARISI = 0
BAGLANTI_UYARI_ARALIGI_SANIYE = 30 * 60


def _simdi():
    return int(time.time())


def _klasor_sayaclarini_guncelle(db, klasor_idleri):
    for klasor_id in set(int(deger) for deger in klasor_idleri or []):
        db.execute(
            """UPDATE folders SET
                   message_count = (SELECT COUNT(*) FROM folder_messages
                       WHERE folder_id = ? AND is_present = 1 AND is_deleted = 0),
                   unseen_count = (SELECT COUNT(*) FROM folder_messages
                       WHERE folder_id = ? AND is_present = 1
                         AND is_deleted = 0 AND is_seen = 0),
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
):
    """Silme isteğini ve yerel gizlemeyi aynı SQL işlemi içinde kaydeder."""
    eposta = str(eposta or "").strip().lower()
    kaynak_klasor = str(kaynak_klasor or "").strip()
    cop_klasoru = str(cop_klasoru or "").strip()
    islem_turu = str(islem_turu or "").strip().lower()
    temiz_uidler = sorted({int(uid) for uid in uidler or [] if str(uid).isdigit() and int(uid) > 0})
    if not eposta or not kaynak_klasor or not cop_klasoru or not temiz_uidler:
        raise ValueError("Silme kuyruğu için hesap, klasör ve UID zorunludur.")
    if islem_turu not in ("trash", "permanent"):
        raise ValueError("Geçersiz silme işlemi türü.")

    simdi = _simdi()
    with veritabani_baglantisi(yazma=True) as db:
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
        kaynak_uidvalidity = int(klasor["uidvalidity"] or 0) if klasor else 0
        etkilenen_klasorler = set()

        for uid in temiz_uidler:
            istek_kimligi = os.urandom(16).hex()
            mesaj = None
            if klasor_id is not None:
                mesaj = db.execute(
                    """SELECT m.id, m.gmail_message_id
                       FROM folder_messages fm JOIN messages m ON m.id = fm.message_id
                       WHERE fm.folder_id = ? AND fm.uid = ?
                         AND fm.uidvalidity = ?
                       ORDER BY fm.updated_at DESC LIMIT 1""",
                    (klasor_id, uid, kaynak_uidvalidity),
                ).fetchone()
            gmail_id = str(mesaj["gmail_message_id"] or "").strip() if mesaj else ""
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
                       remove_source_label, request_token, created_at, updated_at
                   ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
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
                       last_error = NULL,
                       created_at = excluded.created_at,
                       updated_at = excluded.updated_at""",
                (
                    hesap_id, islem_turu, kaynak_klasor, str(kaynak_kategori or ""),
                    uid, gmail_id or None, kaynak_uidvalidity or None,
                    cop_klasoru, str(kaynak_etiketi or ""),
                    int(bool(kaynak_etiketi_kaldir)), istek_kimligi, simdi, simdi,
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
            elif klasor_id is not None:
                etkilenen_klasorler.add(klasor_id)
                db.execute(
                    """UPDATE folder_messages SET is_present = 0, updated_at = ?
                       WHERE folder_id = ? AND uidvalidity = ? AND uid = ?""",
                    (simdi, klasor_id, kaynak_uidvalidity, uid),
                )

        _klasor_sayaclarini_guncelle(db, etkilenen_klasorler)
    return len(temiz_uidler)


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


def _bekleyenleri_al(eposta):
    with veritabani_baglantisi() as db:
        return [dict(satir) for satir in db.execute(
            """SELECT pd.*, a.email FROM pending_deletions pd
               JOIN accounts a ON a.id = pd.account_id
               WHERE a.email = ? COLLATE NOCASE ORDER BY pd.created_at, pd.id""",
            (str(eposta or "").strip(),),
        ).fetchall()]


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
    imap_ok_mu(tip, "Silme için klasör açılamadı.")
    if gmail_id and str(gmail_id).isdigit():
        tip, veri = imap.uid("SEARCH", "X-GM-MSGID", str(gmail_id))
        imap_ok_mu(tip, "E-posta sunucuda aranamadı.")
        return imap_uid_search_sonucu_uidleri_al(veri)
    if yedek_uid and str(yedek_uid).isdigit():
        gecerli_uidvalidity = imap_uidvalidity_al(imap)
        try:
            beklenen_uidvalidity = int(beklenen_uidvalidity or 0)
        except (TypeError, ValueError):
            beklenen_uidvalidity = 0
        if beklenen_uidvalidity <= 0 or gecerli_uidvalidity != beklenen_uidvalidity:
            raise MailHatasi(
                "Silme kuyruğundaki UID artık güvenle doğrulanamıyor; işlem durduruldu."
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
    imap_ok_mu(tip, "Çöp Kutusu açılamadı.")
    tip, veri = imap.uid("SEARCH", "X-GM-MSGID", str(gmail_id))
    imap_ok_mu(tip, "Çöp Kutusu denetlenemedi.")
    return bool(imap_uid_search_sonucu_uidleri_al(veri))


def _kalici_silme_baslatildi_isaretle(kuyruk_id, istek_kimligi):
    """Belirsiz bağlantı sonucunda kalıcı silmeyi tekrar güvenli kılan işareti yazar."""
    with veritabani_baglantisi(yazma=True) as db:
        db.execute(
            """UPDATE pending_deletions SET permanent_delete_started = 1,
               updated_at = ? WHERE id = ? AND request_token = ?""",
            (_simdi(), int(kuyruk_id), str(istek_kimligi or "")),
        )


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
            raise MailHatasi("Silinecek e-posta kaynak klasörde bulunamadı.")
        imap_gmail_etiket_destegini_dogrula(imap)
        uid_kumesi = uid_kumesi_hazirla(uidler, "Silinecek e-posta bulunamadı.")
        imap_gmail_etiket_store(
            imap, uid_kumesi, "+", "\\Trash", "E-posta Çöp Kutusu'na taşınamadı."
        )
        if kayit.get("remove_source_label") and kayit.get("source_label"):
            imap_gmail_etiket_store(
                imap, uid_kumesi, "-", kayit["source_label"],
                "E-posta kaynak etiketinden kaldırılamadı."
            )
        return

    if not gmail_id:
        raise MailHatasi("Kalıcı silme için Gmail ileti kimliği bulunamadı.")
    if str(kayit["source_folder"]) != str(kayit["trash_folder"]) and uidler:
        imap_gmail_etiket_destegini_dogrula(imap)
        imap_gmail_etiket_store(
            imap, uid_kumesi_hazirla(uidler), "+", "\\Trash",
            "E-posta kalıcı silme için Çöp Kutusu'na taşınamadı."
        )
    if not _copte_var_mi(imap, kayit["trash_folder"], gmail_id):
        if bool(kayit.get("permanent_delete_started")):
            # Önceki çağrı sunucuda tamamlanmış, ancak NVDA yerel temizlikten
            # önce kapanmış olabilir. Kalıcı silme bu durumda idempotenttir.
            return
        raise MailHatasi(
            "E-posta kalıcı silme için henüz Çöp Kutusu'nda doğrulanamadı."
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


def bekleyen_silmeleri_isle(ayarlar=None, eposta=None):
    """Kuyruğu sessizce işler; bağlantı hatalarında kayıtları sonraki denemeye bırakır."""
    if not _ISLEME_KILIDI.acquire(False):
        return {"islenen": 0, "bekleyen": bekleyen_silme_sayisi(eposta)}
    posta_kilidi_alindi = False
    try:
        posta_kilidi_alindi = POSTA_DURUM_KILIDI.acquire(False)
        if not posta_kilidi_alindi:
            return {"islenen": 0, "bekleyen": bekleyen_silme_sayisi(eposta)}
        veritabani_hazirla()
        ayarlar = dict(ayarlar or ayarlari_yukle())
        hesap = str(eposta or ayarlar.get("eposta", "") or "").strip().lower()
        if not hesap or not str(ayarlar.get("sifre", "") or "").strip():
            return {"islenen": 0, "bekleyen": bekleyen_silme_sayisi(hesap or None)}
        kayitlar = _bekleyenleri_al(hesap)
        if not kayitlar:
            return {"islenen": 0, "bekleyen": 0}
        islenen = 0
        try:
            with ImapBaglantisi(ayarlar) as imap:
                for kayit in kayitlar:
                    try:
                        _sunucuda_isle(imap, kayit)
                        # Sunucu işlemi doğrulandıktan sonra yerel kalıcı veriyi temizle.
                        _basarili_kaydi_temizle(kayit)
                        islenen += 1
                    except Exception as e:
                        deneme = _hata_kaydet(
                            kayit["id"], kayit.get("request_token"), e
                        )
                        if deneme in (1, 2, 4, 8) or (deneme > 0 and deneme % 20 == 0):
                            uyari_kaydet(
                                "Bekleyen silme işlemi tamamlanamadı; yeniden denenecek.",
                                e,
                            )
        except Exception as e:
            # Bağlantı yokken kullanıcıya konuşma/ileti gönderilmez.
            _baglanti_uyarisini_sinirli_kaydet(e)
        return {"islenen": islenen, "bekleyen": bekleyen_silme_sayisi(hesap)}
    finally:
        if posta_kilidi_alindi:
            POSTA_DURUM_KILIDI.release()
        _ISLEME_KILIDI.release()


class BekleyenSilmeYoneticisi:
    """NVDA açıkken bekleyen silmeleri düzenli ve sessiz biçimde yeniden dener."""

    def __init__(self, ilk_gecikme_ms=ILK_DENEME_GECIKMESI_MS):
        self._iptal = threading.Event()
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

    def _calistir(self):
        try:
            bekleyen_silmeleri_isle()
        finally:
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
