# -*- coding: utf-8 -*-
"""IMAP başlıklarını paketler halinde yerel SQLite veritabanına eşitler."""

# NVDA eklenti çevirilerini bu modül için etkinleştir.
try:
    import addonHandler
    addonHandler.initTranslation()
except (ImportError, AttributeError):
    # NVDA dışındaki otomatik testlerde Türkçe kaynak metni aynen kullan.
    _ = lambda metin: metin


import email
import email.utils
import re
from email import policy as email_policy

from .errors import MailHatasi
from .imap_client import (
    fetch_sonuclarini_uidlere_ayir,
    imap_uidvalidity_al,
    uid_listesini_parcala,
    uidleri_ayristir,
)
from .mail_store import (
    bayrak_paketini_kaydet,
    baslik_paketini_kaydet,
    hesap_ve_klasor_hazirla,
    kayitli_uidleri_al,
    klasor_senkronizasyonunu_tamamla,
)
from .message_parser import fetch_sonucunda_ek_var_mi, ham_mesaj_verisi_al
from .text_utils import guvenli_coz
from .mailbox_state import POSTA_DURUM_KILIDI


# Eski testler/yardımcı çağrılar için ad korunur; gerçek kilit bütün posta
# durumu işlemlerince paylaşılan ortak nesnedir.
_SENKRONIZASYON_KILIDI = POSTA_DURUM_KILIDI


BASLIK_PAKET_BOYUTU = 100
BASLIK_FETCH_KOMUTU = (
    "(X-GM-MSGID X-GM-THRID FLAGS INTERNALDATE RFC822.SIZE BODYSTRUCTURE "
    "BODY.PEEK[HEADER.FIELDS (FROM TO CC REPLY-TO SUBJECT DATE MESSAGE-ID IN-REPLY-TO REFERENCES)])"
)


def _fetch_metin(fetch_sonucu):
    parcalar = []
    for parca in fetch_sonucu or []:
        baslik = parca[0] if isinstance(parca, tuple) and parca else parca
        if isinstance(baslik, bytes):
            parcalar.append(baslik.decode("ascii", errors="ignore"))
        elif baslik is not None:
            parcalar.append(str(baslik))
    return " ".join(parcalar)


def _bayrak_fetch_sonuclarini_uidlere_ayir(fetch_sonucu):
    harita = {}
    for parca in fetch_sonucu or []:
        baslik = parca[0] if isinstance(parca, tuple) and parca else parca
        if isinstance(baslik, bytes):
            ham = baslik
        else:
            ham = str(baslik or "").encode("ascii", errors="ignore")
        eslesme = re.search(br"\bUID\s+(\d+)\b", ham, re.IGNORECASE)
        if eslesme:
            uid = eslesme.group(1).decode("ascii")
            harita.setdefault(uid, []).append(parca)
    return harita


def _sayisal_alan(metin, alan):
    eslesme = re.search(rf"\b{re.escape(alan)}\s+(\d+)\b", metin, re.IGNORECASE)
    return eslesme.group(1) if eslesme else None


def _tarih_damgasi(deger):
    try:
        tarih = email.utils.parsedate_to_datetime(str(deger or ""))
        if tarih is None:
            return None
        if tarih.tzinfo is None:
            tarih = tarih.replace(tzinfo=email.utils.localtime().tzinfo)
        return int(tarih.timestamp())
    except (TypeError, ValueError, OverflowError):
        return None


def _bayrak_kaydi_hazirla(uid, fetch_sonucu):
    metin = _fetch_metin(fetch_sonucu)
    eslesme = re.search(r"\bFLAGS\s+\(([^)]*)\)", metin, re.IGNORECASE)
    return {"uid": str(uid), "flags": eslesme.group(1).split() if eslesme else []}


def baslik_kaydini_hazirla(uid, fetch_sonucu):
    ham_baslik = ham_mesaj_verisi_al(fetch_sonucu)
    if not ham_baslik:
        raise MailHatasi(_('E-posta başlığı boş döndü: UID {0}.').format(uid))
    mesaj = email.message_from_bytes(ham_baslik, policy=email_policy.default)
    metin = _fetch_metin(fetch_sonucu)
    flags_eslesme = re.search(r"\bFLAGS\s+\(([^)]*)\)", metin, re.IGNORECASE)
    flags = flags_eslesme.group(1).split() if flags_eslesme else []
    internal_eslesme = re.search(r'\bINTERNALDATE\s+"([^"]+)"', metin, re.IGNORECASE)
    return {
        "uid": str(uid),
        "gmail_message_id": _sayisal_alan(metin, "X-GM-MSGID"),
        "gmail_thread_id": _sayisal_alan(metin, "X-GM-THRID"),
        "rfc_message_id": str(mesaj.get("Message-ID", "") or "").strip() or None,
        "in_reply_to": str(mesaj.get("In-Reply-To", "") or "").strip() or None,
        "references_header": str(mesaj.get("References", "") or "").strip() or None,
        "subject": guvenli_coz(mesaj.get("Subject", "")),
        "sender": guvenli_coz(mesaj.get("From", "")),
        "recipients_to": guvenli_coz(mesaj.get("To", "")),
        "recipients_cc": guvenli_coz(mesaj.get("Cc", "")),
        "reply_to": guvenli_coz(mesaj.get("Reply-To", "")),
        "sent_at": _tarih_damgasi(mesaj.get("Date", "")),
        "date_header": str(mesaj.get("Date", "") or "").strip() or None,
        "internal_date": _tarih_damgasi(internal_eslesme.group(1) if internal_eslesme else ""),
        "size_bytes": int(_sayisal_alan(metin, "RFC822.SIZE") or 0),
        "has_attachments": fetch_sonucunda_ek_var_mi(fetch_sonucu),
        "flags": flags,
    }


def klasor_basliklarini_senkronize_et(
    imap,
    eposta,
    kategori_adi,
    imap_klasoru,
    sunucu_uidleri=None,
    iptal_edildi_mi=None,
):
    """Aynı anda yalnızca bir klasör eşitlemesine izin verir."""
    if not POSTA_DURUM_KILIDI.acquire(blocking=False):
        return {"atlandi": True, "iptal_edildi": False, "kaydedilen": 0}
    try:
        return _klasor_basliklarini_senkronize_et(
            imap,
            eposta,
            kategori_adi,
            imap_klasoru,
            sunucu_uidleri,
            iptal_edildi_mi,
        )
    finally:
        POSTA_DURUM_KILIDI.release()


def _klasor_basliklarini_senkronize_et(
    imap,
    eposta,
    kategori_adi,
    imap_klasoru,
    sunucu_uidleri=None,
    iptal_edildi_mi=None,
):
    uidvalidity = imap_uidvalidity_al(imap)
    if uidvalidity <= 0:
        raise MailHatasi(_("Klasör UIDVALIDITY bilgisi alınamadığı için güvenli eşitleme başlatılamadı."))
    if sunucu_uidleri is None:
        tip, arama_verisi = imap.uid("SEARCH", "ALL")
        if tip != "OK":
            raise MailHatasi(_("E-posta UID listesi alınamadı."))
        sunucu_uidleri = uidleri_ayristir(arama_verisi)
    else:
        sunucu_uidleri = [str(uid) for uid in sunucu_uidleri if str(uid).isdigit()]
    # Bozuk/tekrarlanan SEARCH cevaplari sayimlari ve paketleri saptirmasin.
    sunucu_uidleri = list(dict.fromkeys(
        uid for uid in sunucu_uidleri if int(uid) > 0
    ))
    hesap_id, klasor_id, uid_degisti = hesap_ve_klasor_hazirla(
        eposta, imap_klasoru, kategori_adi, uidvalidity
    )
    kayitli_uidler = kayitli_uidleri_al(klasor_id, uidvalidity)
    mevcut_uidler = [uid for uid in sunucu_uidleri if uid in kayitli_uidler]
    for uid_parcasi in uid_listesini_parcala(mevcut_uidler, BASLIK_PAKET_BOYUTU):
        if callable(iptal_edildi_mi) and iptal_edildi_mi():
            return {
                "toplam": len(sunucu_uidleri), "kaydedilen": 0,
                "zaten_kayitli": len(kayitli_uidler), "uidvalidity": uidvalidity,
                "uidvalidity_degisti": uid_degisti, "klasor_id": klasor_id,
                "iptal_edildi": True,
            }
        tip, fetch_verisi = imap.uid("FETCH", ",".join(uid_parcasi), "(FLAGS)")
        if tip != "OK":
            raise MailHatasi(_("E-posta durum bayrakları sunucudan alınamadı."))
        harita = _bayrak_fetch_sonuclarini_uidlere_ayir(fetch_verisi)
        if any(uid not in harita for uid in uid_parcasi):
            raise MailHatasi(_("Bazı e-posta durumları sunucudan eksik döndü."))
        bayrak_paketini_kaydet(
            klasor_id,
            uidvalidity,
            [_bayrak_kaydi_hazirla(uid, harita[uid]) for uid in uid_parcasi],
        )
    eksik_uidler = [uid for uid in sunucu_uidleri if uid not in kayitli_uidler]
    kaydedilen = 0
    for uid_parcasi in uid_listesini_parcala(eksik_uidler, BASLIK_PAKET_BOYUTU):
        if callable(iptal_edildi_mi) and iptal_edildi_mi():
            return {
                "toplam": len(sunucu_uidleri),
                "kaydedilen": kaydedilen,
                "zaten_kayitli": len(kayitli_uidler),
                "uidvalidity": uidvalidity,
                "uidvalidity_degisti": uid_degisti,
                "klasor_id": klasor_id,
                "iptal_edildi": True,
            }
        tip, fetch_verisi = imap.uid("FETCH", ",".join(uid_parcasi), BASLIK_FETCH_KOMUTU)
        if tip != "OK":
            raise MailHatasi(_("E-posta başlıkları sunucudan alınamadı."))
        harita = fetch_sonuclarini_uidlere_ayir(fetch_verisi)
        eksik_yanitlar = [uid for uid in uid_parcasi if uid not in harita]
        if eksik_yanitlar:
            raise MailHatasi(_("Bazı e-posta başlıkları sunucudan eksik döndü; eşitleme daha sonra sürdürülecek."))
        kayitlar = [baslik_kaydini_hazirla(uid, harita[uid]) for uid in uid_parcasi]
        baslik_paketini_kaydet(hesap_id, klasor_id, uidvalidity, kayitlar)
        kaydedilen += len(kayitlar)
    klasor_senkronizasyonunu_tamamla(klasor_id, uidvalidity, sunucu_uidleri)
    return {
        "toplam": len(sunucu_uidleri),
        "kaydedilen": kaydedilen,
        "zaten_kayitli": len(sunucu_uidleri) - kaydedilen,
        "uidvalidity": uidvalidity,
        "uidvalidity_degisti": uid_degisti,
        "klasor_id": klasor_id,
        "iptal_edildi": False,
    }
