# -*- coding: utf-8 -*-
"""IMAP gövdelerini paketler halinde yerel SQLite önbelleğine eşitler."""

import email
import threading
from email import policy as email_policy

from .attachment_cache import ekleri_onbellege_kaydet
from .attachments import (
    AZAMI_EPOSTA_ISLEME_BOYUTU,
    ham_eposta_boyutunu_denetle,
    mesaj_metni_ve_ekleri_cikar,
)
from .errors import MailHatasi
from .imap_client import imap_eposta_boyutunu_denetle, uid_listesini_parcala
from .logger import hata_kaydet
from .mail_store import govdesi_eksik_uidleri_al, mesaj_govdesini_kaydet
from .message_parser import ham_mesaj_verisi_al
from .cache_limits import onbellek_kotasi_denetle


GOVDE_PAKET_BOYUTU = 100
_GOVDE_SENKRONIZASYON_KILIDI = threading.Lock()


def _govdeyi_indir_ve_kaydet(imap, eposta, imap_klasoru, uid):
    beklenen_boyut = imap_eposta_boyutunu_denetle(
        imap,
        uid,
        AZAMI_EPOSTA_ISLEME_BOYUTU,
        "Önbelleğe alınacak e-posta",
    )
    onbellek_kotasi_denetle(beklenen_boyut)
    tip, veri = imap.uid("FETCH", str(uid), "(BODY.PEEK[])")
    if tip != "OK":
        raise MailHatasi("E-posta gövdesi sunucudan alınamadı.")
    ham_veri = ham_mesaj_verisi_al(veri)
    if not ham_veri:
        raise MailHatasi("E-posta gövdesi boş döndü.")
    ham_eposta_boyutunu_denetle(ham_veri, "Önbelleğe alınacak e-posta")

    mesaj = email.message_from_bytes(ham_veri, policy=email_policy.default)
    icerik, ekler, atlanan_ek_sayisi = mesaj_metni_ve_ekleri_cikar(
        mesaj, ayrintili=True
    )
    kaydedildi = mesaj_govdesini_kaydet(
        eposta,
        imap_klasoru,
        uid,
        icerik or "",
        len(ham_veri),
        mesaj.get("Date", ""),
    )
    if kaydedildi and (ekler or atlanan_ek_sayisi):
        ekleri_onbellege_kaydet(
            eposta,
            imap_klasoru,
            uid,
            ekler,
            tamamlandi=(atlanan_ek_sayisi == 0),
        )
    return bool(kaydedildi)


def klasor_govdelerini_senkronize_et(
    imap,
    eposta,
    imap_klasoru,
    sunucu_uidleri,
    iptal_edildi_mi=None,
):
    """Başlığı kayıtlı iletilerin eksik gövdelerini 100'lük paketlerle önbelleğe alır."""
    if not _GOVDE_SENKRONIZASYON_KILIDI.acquire(blocking=False):
        return {"atlandi": True, "iptal_edildi": False, "kaydedilen": 0, "hatali": 0}
    try:
        eksik_uidler = govdesi_eksik_uidleri_al(eposta, imap_klasoru, sunucu_uidleri)
        kaydedilen = 0
        hatali = 0
        for uid_parcasi in uid_listesini_parcala(eksik_uidler, GOVDE_PAKET_BOYUTU):
            if callable(iptal_edildi_mi) and iptal_edildi_mi():
                return {
                    "toplam": len(eksik_uidler),
                    "kaydedilen": kaydedilen,
                    "hatali": hatali,
                    "iptal_edildi": True,
                }
            for uid in uid_parcasi:
                if callable(iptal_edildi_mi) and iptal_edildi_mi():
                    return {
                        "toplam": len(eksik_uidler),
                        "kaydedilen": kaydedilen,
                        "hatali": hatali,
                        "iptal_edildi": True,
                    }
                try:
                    if _govdeyi_indir_ve_kaydet(imap, eposta, imap_klasoru, uid):
                        kaydedilen += 1
                except Exception as e:
                    hatali += 1
                    hata_kaydet(f"E-posta gövdesi önbelleğe alınamadı: UID {uid}", e)
        return {
            "toplam": len(eksik_uidler),
            "kaydedilen": kaydedilen,
            "hatali": hatali,
            "iptal_edildi": False,
        }
    finally:
        _GOVDE_SENKRONIZASYON_KILIDI.release()


def secili_govdeleri_dogrudan_senkronize_et(imap, eposta, imap_klasoru, uidler):
    """Genel eşitleme meşgulse kullanıcı tarafından açılan iletileri bekletmeden indirir."""
    eksik_uidler = govdesi_eksik_uidleri_al(eposta, imap_klasoru, uidler)
    kaydedilen = 0
    hatali = 0
    for uid in eksik_uidler:
        try:
            if _govdeyi_indir_ve_kaydet(imap, eposta, imap_klasoru, uid):
                kaydedilen += 1
        except Exception as e:
            hatali += 1
            hata_kaydet(f"Açılan konuşmanın e-posta gövdesi alınamadı: UID {uid}", e)
    return {
        "toplam": len(eksik_uidler),
        "kaydedilen": kaydedilen,
        "hatali": hatali,
        "iptal_edildi": False,
    }
