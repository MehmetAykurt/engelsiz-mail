# -*- coding: utf-8 -*-
"""Arayüzden bağımsız IMAP e-posta listesi hazırlama hizmeti."""

import email
from email import policy as email_policy

from .errors import MailHatasi
from .imap_client import (
    ImapBaglantisi,
    imap_status_sayilarini_ayristir,
    imap_toplu_uid_fetch,
    uidleri_ayristir,
)
from .logger import hata_kaydet
from .header_sync import klasor_basliklarini_senkronize_et
from .mail_store import (
    klasor_basliklarini_listele,
    klasor_konusma_basliklarini_listele,
    klasor_onizleme_haritasi_al,
    klasor_yerel_onbellegi_var_mi,
)
from .message_parser import (
    adres_basligini_gosterime_hazirla,
    fetch_sonucunda_ek_var_mi,
    gonderen_gosterimini_al,
    ham_mesaj_verisi_al,
    seen_bayragi_var_mi,
)
from .text_utils import guvenli_coz
from .config import konusmalari_grupla_ayari_yukle
from .conversation import epostalari_konusmalara_grupla


def yerel_eposta_listesi_hazirla(ayarlar, kategori_adi, kaynak_klasor, mesaj_sayisi):
    """Ağ bağlantısı kurmadan SQLite'taki son başlıkları arayüz biçimine getirir."""
    eposta = str((ayarlar or {}).get("eposta", "") or "").strip()
    kaynak_klasor = str(kaynak_klasor or "").strip()
    if not eposta or not kaynak_klasor:
        return None
    if not klasor_yerel_onbellegi_var_mi(eposta, kaynak_klasor):
        return None
    # Birden fazla taslak aynı Gmail konuşma kimliğini taşıyabilir; düzenlenebilir
    # taslakların yanlışlıkla tek satırda birleşmemesi gerekir.
    gruplama = konusmalari_grupla_ayari_yukle() and kategori_adi != "Taslaklar"
    satirlar = (
        klasor_konusma_basliklarini_listele(eposta, kaynak_klasor, mesaj_sayisi)
        if gruplama
        else klasor_basliklarini_listele(eposta, kaynak_klasor, mesaj_sayisi)
    )
    gonderilen_turu = kategori_adi in ("Gönderilen E-postalar", "Taslaklar")
    sonuc = []
    for satir in satirlar:
        kimden = gonderen_gosterimini_al(satir.get("sender", ""), "Bilinmiyor")
        kime = adres_basligini_gosterime_hazirla(
            satir.get("recipients_to", ""),
            "Alıcı yok",
            ayarlar.get("eposta", ""),
            ayarlar.get("gorunen_ad", ""),
        )
        liste_gosterim = kime if gonderilen_turu else kimden
        if not bool(satir.get("is_seen")):
            kimden = "[Okunmadı] " + kimden
            liste_gosterim = "[Okunmadı] " + liste_gosterim
        sonuc.append(
            {
                "id": str(satir.get("uid")),
                "kimden": kimden,
                "kime": kime,
                "liste_gosterim": liste_gosterim,
                "konu": guvenli_coz(satir.get("subject", "") or "Konusuz") or "Konusuz",
                "onizleme": str(satir.get("preview", "") or ""),
                "ek_var": bool(satir.get("has_attachments")),
                "thread_id": str(satir.get("gmail_thread_id") or ""),
                "gmail_message_id": str(satir.get("gmail_message_id") or ""),
                "is_seen": bool(satir.get("is_seen")),
                "internal_date": int(satir.get("internal_date") or 0),
            }
        )
    if gruplama:
        return epostalari_konusmalara_grupla(sonuc, mesaj_sayisi)
    return sonuc


def eposta_listesi_hazirla(
    ayarlar,
    kategori_adi,
    kaynak_klasor,
    klasor_haritasini_hazirla,
    mesaj_sayisi,
    onizleme_etkin,
):
    """IMAP üzerinden liste verisini hazırlar; wx denetimlerine dokunmaz."""
    with ImapBaglantisi(ayarlar) as imap:
        yeni_harita, yeni_ozeller = klasor_haritasini_hazirla(imap)
        hedef_kategori = kategori_adi or "Gelen Kutusu"
        if hedef_kategori in yeni_harita:
            aktif_klasor = yeni_harita.get(hedef_kategori, kaynak_klasor or "INBOX")
        elif kaynak_klasor:
            aktif_klasor = kaynak_klasor
        else:
            hedef_kategori = "Gelen Kutusu"
            aktif_klasor = yeni_harita.get(hedef_kategori, "INBOX")

        klasor_bilgisi = {}
        try:
            tip_status, status_verisi = imap.status(aktif_klasor, "(MESSAGES UNSEEN)")
            if tip_status == "OK":
                klasor_bilgisi = imap_status_sayilarini_ayristir(status_verisi)
        except Exception as e:
            hata_kaydet("Klasör toplam/okunmamış bilgisi alınamadı.", e)

        tip, _veri = imap.select(aktif_klasor, readonly=False)
        if tip != "OK":
            hata_kaydet(f"Klasör açılamadı: kategori={hedef_kategori}, imap={aktif_klasor}")
            raise MailHatasi("Seçili klasör açılamadı.")
        tip, veri = imap.uid("SEARCH", "ALL")
        if tip != "OK":
            raise MailHatasi("E-posta listesi alınamadı.")
        uidler = uidleri_ayristir(veri)
        try:
            klasor_basliklarini_senkronize_et(
                imap,
                ayarlar.get("eposta", ""),
                hedef_kategori,
                aktif_klasor,
                sunucu_uidleri=uidler,
            )
        except Exception as e:
            # Yerel önbellek sorunu mevcut çevrim içi posta listesini engellememeli.
            hata_kaydet("E-posta başlıkları yerel veritabanına eşitlenemedi.", e)
        if "messages" not in klasor_bilgisi:
            klasor_bilgisi["messages"] = len(uidler)
        if "unseen" not in klasor_bilgisi:
            try:
                tip_unseen, unseen_veri = imap.uid("SEARCH", "UNSEEN")
                if tip_unseen == "OK":
                    klasor_bilgisi["unseen"] = len(uidleri_ayristir(unseen_veri))
            except Exception as e:
                hata_kaydet("Okunmamış e-posta sayısı alınamadı.", e)

        if konusmalari_grupla_ayari_yukle():
            yerel_mailler = yerel_eposta_listesi_hazirla(
                ayarlar, hedef_kategori, aktif_klasor, mesaj_sayisi
            )
            if yerel_mailler is not None:
                return {
                    "mailler": yerel_mailler,
                    "klasor_haritasi": yeni_harita,
                    "ozel_klasorler": yeni_ozeller,
                    "hedef_kategori": hedef_kategori,
                    "klasor_bilgisi": klasor_bilgisi,
                }

        yeni_mailler = []
        secili_uidler = [str(uid) for uid in reversed(uidler[-mesaj_sayisi:])]
        baslik_haritasi = imap_toplu_uid_fetch(
            imap,
            secili_uidler,
            "(FLAGS BODYSTRUCTURE BODY.PEEK[HEADER.FIELDS (FROM TO SUBJECT DATE)])",
        )
        onizleme_haritasi = (
            klasor_onizleme_haritasi_al(
                ayarlar.get("eposta", ""),
                aktif_klasor,
                secili_uidler,
            )
            if onizleme_etkin and secili_uidler
            else {}
        )

        for uid_str in secili_uidler:
            baslik_verisi = baslik_haritasi.get(uid_str, [])
            if not baslik_verisi:
                try:
                    tip, baslik_verisi = imap.uid(
                        "FETCH",
                        uid_str,
                        "(FLAGS BODYSTRUCTURE BODY.PEEK[HEADER.FIELDS (FROM TO SUBJECT DATE)])",
                    )
                    if tip != "OK":
                        continue
                except Exception as e:
                    hata_kaydet(f"E-posta başlığı alınamadı: UID {uid_str}", e)
                    continue

            ham_baslik = ham_mesaj_verisi_al(baslik_verisi)
            mesaj = email.message_from_bytes(ham_baslik, policy=email_policy.default)
            kimden = guvenli_coz(mesaj.get("From", "Bilinmiyor"))
            kimden_goster = gonderen_gosterimini_al(kimden, "Bilinmiyor")
            kime_goster = adres_basligini_gosterime_hazirla(
                mesaj.get("To", ""),
                "Alıcı yok",
                ayarlar.get("eposta", ""),
                ayarlar.get("gorunen_ad", ""),
            )
            liste_gosterim = kime_goster if hedef_kategori in ("Gönderilen E-postalar", "Taslaklar") else kimden_goster
            if not seen_bayragi_var_mi(baslik_verisi):
                kimden_goster = "[Okunmadı] " + kimden_goster
                liste_gosterim = "[Okunmadı] " + liste_gosterim

            ek_var = fetch_sonucunda_ek_var_mi(baslik_verisi)

            yeni_mailler.append(
                {
                    "id": uid_str,
                    "kimden": kimden_goster,
                    "kime": kime_goster,
                    "liste_gosterim": liste_gosterim,
                    "konu": guvenli_coz(mesaj.get("Subject", "Konusuz")) or "Konusuz",
                    "onizleme": onizleme_haritasi.get(uid_str, "") if onizleme_etkin else "",
                    "ek_var": ek_var,
                    "thread_id": "",
                    "is_seen": seen_bayragi_var_mi(baslik_verisi),
                }
            )
    return {
        "mailler": yeni_mailler,
        "klasor_haritasi": yeni_harita,
        "ozel_klasorler": yeni_ozeller,
        "hedef_kategori": hedef_kategori,
        "klasor_bilgisi": klasor_bilgisi,
    }
