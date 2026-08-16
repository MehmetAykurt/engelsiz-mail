# -*- coding: utf-8 -*-
# Engelsiz Mail - ek dosya yardımcıları


# NVDA eklenti çevirilerini bu modül için etkinleştir.
try:
    import addonHandler
    addonHandler.initTranslation()
except (ImportError, AttributeError):
    # NVDA dışındaki otomatik testlerde Türkçe kaynak metni aynen kullan.
    _ = lambda metin: metin

import mimetypes
import os
from email import policy as email_policy
from email.errors import MissingHeaderBodySeparatorDefect
from email.parser import BytesParser

from .errors import MailHatasi
from .logger import hata_kaydet
from .text_utils import (
    duz_metni_ekran_okuyucu_icin_temizle,
    eposta_baytlarini_metne_coz,
    guvenli_coz,
    html_icerik_gibi_gorunuyor_mu,
    html_temizle,
)

AZAMI_TEK_EK_BOYUTU = 10 * 1024 * 1024
AZAMI_TOPLAM_EK_BOYUTU = 10 * 1024 * 1024
AZAMI_EML_DOSYA_BOYUTU = 50 * 1024 * 1024
AZAMI_EPOSTA_ISLEME_BOYUTU = 30 * 1024 * 1024
AZAMI_EK_ONBELLEK_TEK_BOYUTU = 12 * 1024 * 1024
AZAMI_EK_ONBELLEK_TOPLAM_BOYUTU = 20 * 1024 * 1024
EML_MESAJ_BASLIKLARI = {
    "from",
    "to",
    "cc",
    "bcc",
    "subject",
    "date",
    "message-id",
    "sender",
    "reply-to",
}


def benzersiz_yol(klasor, dosya_adi):
    ad, uzanti = os.path.splitext(dosya_adi)
    aday = os.path.join(klasor, dosya_adi)
    sayac = 1
    while os.path.exists(aday):
        aday = os.path.join(klasor, f"{ad}_{sayac}{uzanti}")
        sayac += 1
    return aday


def ek_icerik_turu_bul(dosya_adi):
    ctype, encoding = mimetypes.guess_type(dosya_adi or "")
    if ctype is None or encoding is not None or "/" not in ctype:
        ctype = "application/octet-stream"
    return ctype.split("/", 1)


def _parca_ek_mi(parca):
    dosya_adi = parca.get_filename()
    icerik_duzeni = str(parca.get("Content-Disposition", "")).lower()
    return bool(dosya_adi or "attachment" in icerik_duzeni)


def _mesaj_parcalarini_dolas(parca):
    """Ek olarak işaretlenmiş MIME parçalarının alt gövdelerine inmeden dolaşır."""
    yield parca
    if _parca_ek_mi(parca) or not parca.is_multipart():
        return
    alt_parcalar = parca.get_payload()
    if not isinstance(alt_parcalar, list):
        return
    for alt_parca in alt_parcalar:
        yield from _mesaj_parcalarini_dolas(alt_parca)


def _ek_verisini_al(parca):
    veri = parca.get_payload(decode=True)
    if veri is not None:
        return veri
    if parca.get_content_type() != "message/rfc822":
        return b""
    alt_mesajlar = parca.get_payload()
    if not isinstance(alt_mesajlar, list):
        return b""
    return b"\r\n".join(
        alt_mesaj.as_bytes(policy=email_policy.default)
        for alt_mesaj in alt_mesajlar
        if hasattr(alt_mesaj, "as_bytes")
    )


def _metin_parcasini_coz(parca):
    try:
        icerik = parca.get_content()
        if isinstance(icerik, str) and "�" not in icerik:
            return icerik
    except Exception:
        pass

    veri = parca.get_payload(decode=True)
    if veri is None:
        return str(parca.get_payload() or "")
    return eposta_baytlarini_metne_coz(veri, parca.get_content_charset() or "utf-8")


def mesaj_metni_ve_ekleri_cikar(mesaj, ayrintili=False):
    duz_metinler = []
    html_metinler = []
    ekler = []
    atlanan_ekler = []
    toplam_ek_boyutu = 0

    parcalar = _mesaj_parcalarini_dolas(mesaj)
    for parca in parcalar:
        try:
            icerik_turu = parca.get_content_type()
            dosya_adi = parca.get_filename()

            if _parca_ek_mi(parca):
                veri = _ek_verisini_al(parca)
                if veri:
                    varsayilan_ad = "ek_dosya.eml" if icerik_turu == "message/rfc822" else "ek_dosya"
                    temiz_ad = guvenli_coz(dosya_adi or varsayilan_ad)
                    boyut = len(veri)
                    if boyut > AZAMI_EK_ONBELLEK_TEK_BOYUTU:
                        atlanan_ekler.append(
                            _('{0} ({1}): tek ek güvenlik sınırını aşıyor').format(temiz_ad, dosya_boyutu_metni(boyut))
                        )
                        continue
                    if toplam_ek_boyutu + boyut > AZAMI_EK_ONBELLEK_TOPLAM_BOYUTU:
                        atlanan_ekler.append(
                            _('{0} ({1}): toplam ek güvenlik sınırını aşıyor').format(temiz_ad, dosya_boyutu_metni(boyut))
                        )
                        continue
                    ekler.append((temiz_ad, veri))
                    toplam_ek_boyutu += boyut
                continue

            if icerik_turu not in ("text/plain", "text/html"):
                continue

            icerik = _metin_parcasini_coz(parca)

            if icerik_turu == "text/plain":
                duz_metinler.append(icerik)
            else:
                html_metinler.append(icerik)
        except Exception as e:
            hata_kaydet("E-posta parçası okunamadı.", e)

    duz_metin = "\n".join(metin.strip() for metin in duz_metinler if metin.strip())
    html_metin = "\n".join(metin.strip() for metin in html_metinler if metin.strip())

    if duz_metin and html_icerik_gibi_gorunuyor_mu(duz_metin):
        duz_metin = html_temizle(duz_metin)
    if not duz_metin.strip() and html_metin:
        duz_metin = html_temizle(html_metin)

    duz_metin = duz_metni_ekran_okuyucu_icin_temizle(duz_metin)
    if atlanan_ekler:
        ek_notu = [
            "",
            _("Not: Bazı ekler çok büyük olduğu için belleğe yüklenmedi ve bu pencereden kaydedilemez ya da iletilemez."),
            _('Tek ek sınırı: {0}.').format(dosya_boyutu_metni(AZAMI_EK_ONBELLEK_TEK_BOYUTU)),
            _('Toplam ek sınırı: {0}.').format(dosya_boyutu_metni(AZAMI_EK_ONBELLEK_TOPLAM_BOYUTU)),
            _("Atlanan ekler:"),
        ]
        ek_notu.extend(f"- {satir}" for satir in atlanan_ekler[:20])
        if len(atlanan_ekler) > 20:
            ek_notu.append(_('- Ayrıca {0} ek daha atlandı.').format(len(atlanan_ekler) - 20))
        duz_metin = (duz_metin + "\n" + "\n".join(ek_notu)).strip()

    if ayrintili:
        return duz_metin, ekler, len(atlanan_ekler)
    return duz_metin, ekler


def dosya_boyutu_metni(boyut):
    """Bayt cinsinden dosya boyutunu kısa okunabilir metne çevirir."""
    try:
        boyut = int(boyut)
    except Exception:
        boyut = 0
    if boyut >= 1024 * 1024:
        return f"{boyut / (1024 * 1024):.1f} MB"
    if boyut >= 1024:
        return f"{boyut / 1024:.1f} KB"
    return f"{boyut} bayt"


def ham_eposta_boyutunu_denetle(ham_veri, islem_adi="E-posta"):
    """Aşırı büyük ham e-postaların NVDA'yı veya belleği zorlamasını engeller."""
    boyut = len(ham_veri or b"")
    if boyut <= 0:
        raise MailHatasi(_("E-posta içeriği boş döndü."))
    if boyut > AZAMI_EPOSTA_ISLEME_BOYUTU:
        raise MailHatasi(
            _('{0} çok büyük. Bu işlem için en çok {1} boyutunda e-posta işlenebilir. E-postayı Gmail web arayüzünden veya başka bir posta istemcisinden açmayı deneyin.').format(islem_adi, dosya_boyutu_metni(AZAMI_EPOSTA_ISLEME_BOYUTU))
        )
    return boyut


def eml_dosya_boyutunu_denetle(dosya_yolu):
    """EML içe aktarmada aşırı büyük veya boş dosyaları belleğe almadan önce denetler."""
    try:
        boyut = os.path.getsize(dosya_yolu)
    except OSError as e:
        raise MailHatasi(_("EML dosya boyutu okunamadı.")) from e
    if boyut <= 0:
        raise MailHatasi(_("EML dosyası boş görünüyor."))
    if boyut > AZAMI_EML_DOSYA_BOYUTU:
        raise MailHatasi(
            _('EML dosyası çok büyük. En çok {0} boyutunda EML dosyası açılabilir.').format(dosya_boyutu_metni(AZAMI_EML_DOSYA_BOYUTU))
        )
    return boyut


def eml_verisini_dogrula(ham_veri):
    """Ham verinin başlıkları bulunan gerçek bir EML ileti olduğunu doğrular."""
    if not isinstance(ham_veri, (bytes, bytearray)) or not bytes(ham_veri).strip():
        raise MailHatasi(_("EML dosyası boş görünüyor."))
    try:
        mesaj = BytesParser(policy=email_policy.default).parsebytes(bytes(ham_veri))
    except Exception as e:
        raise MailHatasi(_("EML dosyası okunamadı veya geçerli bir e-posta dosyası değil.")) from e

    if any(isinstance(kusur, MissingHeaderBodySeparatorDefect) for kusur in mesaj.defects):
        raise MailHatasi(_("EML dosyası okunamadı veya geçerli bir e-posta dosyası değil."))
    basliklar = {str(ad or "").strip().lower() for ad in mesaj.keys()}
    if not basliklar.intersection(EML_MESAJ_BASLIKLARI):
        raise MailHatasi(_("EML dosyası okunamadı veya geçerli bir e-posta dosyası değil."))
    return mesaj


def ek_kayitlari_boyutunu_denetle(ek_kayitlari):
    """Gönderilecek veya taslak kaydedilecek eklerin boyutunu Gmail sınırı için denetler."""
    toplam = 0
    for kayit in ek_kayitlari or []:
        if isinstance(kayit, str):
            kayit = {"tur": "dosya", "yol": kayit}
        if not isinstance(kayit, dict):
            raise MailHatasi(
                _("Ek kaydı geçersiz. Lütfen eki kaldırıp yeniden ekleyin.")
            )

        tur = kayit.get("tur")
        if tur == "hazir":
            ad = guvenli_coz(kayit.get("ad") or "ek_dosya")
            veri = kayit.get("veri") or b""
            if not isinstance(veri, (bytes, bytearray)):
                raise MailHatasi(
                    _('Ek verisi geçersiz: {0}. Lütfen eki kaldırıp yeniden ekleyin.').format(ad)
                )
            boyut = len(veri)
        else:
            yol = str(kayit.get("yol", "") or "").strip()
            if not yol or not os.path.isfile(yol):
                continue
            ad = os.path.basename(yol)
            try:
                boyut = os.path.getsize(yol)
            except OSError as e:
                raise MailHatasi(_('Ek dosya boyutu okunamadı: {0}').format(ad)) from e

        if boyut > AZAMI_TEK_EK_BOYUTU:
            raise MailHatasi(
                _('Ek dosya çok büyük: {0}. Tek ek en çok {1} olabilir.').format(ad, dosya_boyutu_metni(AZAMI_TEK_EK_BOYUTU))
            )
        toplam += boyut

    if toplam > AZAMI_TOPLAM_EK_BOYUTU:
        raise MailHatasi(
            _('Ek dosyaların toplam boyutu çok büyük. Toplam ek boyutu en çok {0} olabilir.').format(dosya_boyutu_metni(AZAMI_TOPLAM_EK_BOYUTU))
        )
