# -*- coding: utf-8 -*-
"""IMAP ön izlemelerini paketler halinde yerel SQLite önbelleğine eşitler."""

import threading

from .imap_client import imap_toplu_uid_fetch, uid_listesini_parcala
from .logger import hata_kaydet
from .mail_store import mesaj_onizlemesini_kaydet, onizlemesi_eksik_uidleri_al
from .message_parser import ham_mesaj_verisi_al
from .preview import onizleme_metni_olustur


ONIZLEME_PAKET_BOYUTU = 100
ONIZLEME_FETCH_BOYUTU = 12000
_ONIZLEME_SENKRONIZASYON_KILIDI = threading.Lock()


def klasor_onizlemelerini_senkronize_et(
    imap,
    eposta,
    imap_klasoru,
    sunucu_uidleri,
    iptal_edildi_mi=None,
    kilidi_bekle=False,
):
    """Başlığı kayıtlı iletilerin eksik ön izlemelerini 100'lük paketlerle önbelleğe alır."""
    kilit_alindi = False
    if kilidi_bekle:
        while not kilit_alindi:
            if callable(iptal_edildi_mi) and iptal_edildi_mi():
                return {
                    "atlandi": False,
                    "iptal_edildi": True,
                    "kaydedilen": 0,
                    "hatali": 0,
                }
            kilit_alindi = _ONIZLEME_SENKRONIZASYON_KILIDI.acquire(timeout=0.25)
    else:
        kilit_alindi = _ONIZLEME_SENKRONIZASYON_KILIDI.acquire(blocking=False)
        if not kilit_alindi:
            return {"atlandi": True, "iptal_edildi": False, "kaydedilen": 0, "hatali": 0}
    try:
        eksik_uidler = onizlemesi_eksik_uidleri_al(eposta, imap_klasoru, sunucu_uidleri)
        kaydedilen = 0
        hatali = 0
        for uid_parcasi in uid_listesini_parcala(eksik_uidler, ONIZLEME_PAKET_BOYUTU):
            if callable(iptal_edildi_mi) and iptal_edildi_mi():
                return {
                    "toplam": len(eksik_uidler),
                    "kaydedilen": kaydedilen,
                    "hatali": hatali,
                    "iptal_edildi": True,
                }
            try:
                onizleme_haritasi = imap_toplu_uid_fetch(
                    imap,
                    uid_parcasi,
                    f"(BODY.PEEK[TEXT]<0.{ONIZLEME_FETCH_BOYUTU}>)",
                    parca_boyutu=ONIZLEME_PAKET_BOYUTU,
                )
            except Exception as e:
                hatali += len(uid_parcasi)
                hata_kaydet("E-posta ön izleme paketi alınamadı.", e)
                continue

            for uid in uid_parcasi:
                if callable(iptal_edildi_mi) and iptal_edildi_mi():
                    return {
                        "toplam": len(eksik_uidler),
                        "kaydedilen": kaydedilen,
                        "hatali": hatali,
                        "iptal_edildi": True,
                    }
                try:
                    ham = ham_mesaj_verisi_al(onizleme_haritasi.get(str(uid), []))
                    onizleme = onizleme_metni_olustur(ham)
                    if onizleme and mesaj_onizlemesini_kaydet(
                        eposta,
                        imap_klasoru,
                        uid,
                        onizleme,
                    ):
                        kaydedilen += 1
                except Exception as e:
                    hatali += 1
                    hata_kaydet(f"E-posta ön izlemesi önbelleğe alınamadı: UID {uid}", e)
        return {
            "toplam": len(eksik_uidler),
            "kaydedilen": kaydedilen,
            "hatali": hatali,
            "iptal_edildi": False,
        }
    finally:
        if kilit_alindi:
            _ONIZLEME_SENKRONIZASYON_KILIDI.release()
