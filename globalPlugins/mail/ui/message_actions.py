# -*- coding: utf-8 -*-
# Engelsiz Mail - mesaj açma, yanıtlama, iletme ve kaydetme işlemleri

import email
import email.utils
from email import policy as email_policy
import os

import gui
import ui
import wx

from .folder_view import LISTE_MODU_EPOSTA
from .compose_window import YeniPostaPenceresi
from .message_view import MesajOkumaPenceresi
from ..attachments import (
    AZAMI_EPOSTA_ISLEME_BOYUTU,
    mesaj_metni_ve_ekleri_cikar,
    ham_eposta_boyutunu_denetle,
    eml_dosya_boyutunu_denetle,
    eml_verisini_dogrula,
)
from ..config import ayarlari_yukle, imza_yukle
from ..errors import MailHatasi
from ..imap_client import ImapBaglantisi, imap_eposta_boyutunu_denetle, imap_ok_mu
from ..logger import hata_kaydet
from ..cache_limits import onbellek_kotasi_denetle
from ..database_schema import BODY_PARSER_VERSION
from ..message_center import mesaj_soyle_ve_sonra_calistir
from ..mail_store import (
    mesaj_govdesini_al,
    mesaj_govdesini_kaydet,
    mesaji_yerelde_okundu_yap,
    konusma_mesajlarini_listele,
)
from ..body_sync import (
    klasor_govdelerini_senkronize_et,
    secili_govdeleri_dogrudan_senkronize_et,
)
from ..attachment_cache import ekleri_onbellege_kaydet, ekleri_onbellekten_al
from ..message_parser import (
    adres_basligini_duzenle,
    adres_basligini_gosterime_hazirla,
    gonderen_gosterimini_al,
    gonderen_basligini_gosterime_hazirla,
    grup_araci_adresini_temizle,
    yanit_adresini_bul,
    ham_mesaj_verisi_al,
    yanit_basliklari_hazirla,
)
from ..text_utils import (
    guvenli_coz,
    eposta_basligi_tek_satir_yap,
    konu_gosterimini_duzenle,
    turkce_tarih_yap,
    guvenli_dosya_adi,
)
from ..ui_helpers import (
    pencere_kullanilabilir_mi,
    guvenli_call_after,
    guvenli_modal_goster,
    arka_planda_calistir,
)


def eml_dosyasi_sec(self):
    dlg = wx.FileDialog(
        self,
        "Lütfen daha önce kaydettiğiniz EML dosyasını seçiniz.",
        wildcard="EML dosyaları (*.eml)|*.eml",
        style=wx.FD_OPEN | wx.FD_FILE_MUST_EXIST,
    )
    try:
        if dlg.ShowModal() != wx.ID_OK:
            return None
        return dlg.GetPath()
    finally:
        dlg.Destroy()

def eml_dosyasini_ac(self, event=None):
    dosya_yolu = self.eml_dosyasi_sec()
    if not dosya_yolu:
        self.liste.SetFocus()
        return

    if not str(dosya_yolu).lower().endswith(".eml"):
        ui.message("Lütfen EML uzantılı bir dosya seçin.")
        self.liste.SetFocus()
        return

    try:
        eml_dosya_boyutunu_denetle(dosya_yolu)
    except MailHatasi as e:
        ui.message(str(e))
        self.liste.SetFocus()
        return

    cevap = gui.messageBox(
        "Seçtiğiniz EML dosyası Gelen Kutusuna eklenecektir. "
        "Bu işlem e-postayı yeniden göndermez; yalnızca Gmail hesabınıza bir kopya olarak ekler. "
        "Devam etmek istiyor musunuz?",
        "EML Dosyasını Aç",
        wx.YES_NO | wx.ICON_QUESTION,
    )
    if cevap != wx.YES:
        self.liste.SetFocus()
        return

    mesaj_soyle_ve_sonra_calistir(
        "EML dosyası açılıyor.",
        lambda: arka_planda_calistir(self.sunucudan_eml_dosyasini_ac, dosya_yolu),
        ad="EML dosyası açma",
    )

def sunucudan_eml_dosyasini_ac(self, dosya_yolu):
    ayarlar = ayarlari_yukle()
    try:
        dosya_yolu = str(dosya_yolu or "").strip()
        if not dosya_yolu or not os.path.exists(dosya_yolu):
            raise MailHatasi("EML dosyası bulunamadı.")
        if not dosya_yolu.lower().endswith(".eml"):
            raise MailHatasi("Lütfen EML uzantılı bir dosya seçin.")

        eml_dosya_boyutunu_denetle(dosya_yolu)
        with open(dosya_yolu, "rb") as dosya:
            ham_veri = dosya.read()

        if not ham_veri.strip():
            raise MailHatasi("EML dosyası boş görünüyor.")

        eml_verisini_dogrula(ham_veri)

        with ImapBaglantisi(ayarlar) as imap:
            hedef_klasor = self.klasor_haritasi.get("Gelen Kutusu", "INBOX")
            tip, _veri = imap.append(hedef_klasor, None, None, ham_veri)
            if tip != "OK":
                raise MailHatasi("EML dosyası Gelen Kutusuna eklenemedi.")

        guvenli_call_after(self, ui.message, "EML dosyası Gelen Kutusuna eklendi.")
        guvenli_call_after(
            self,
            self.yenilemeyi_gecikmeli_tetikle,
            "Gelen Kutusu yenileniyor...",
            "Gelen Kutusu",
            None,
            None,
            False,
        )
    except MailHatasi as e:
        hata_kaydet(str(e))
        guvenli_call_after(self, ui.message, str(e))
    except Exception as e:
        hata_kaydet("EML dosyası açılamadı.", e)
        guvenli_call_after(self, ui.message, "EML dosyası açılırken bir hata oluştu. Lütfen dosyayı, bağlantınızı ve hesap bilgilerinizi kontrol edin.")
    finally:
        guvenli_call_after(self, self.liste.SetFocus)

def secili_epostayi_kaydet(self, event=None):
    mail_id = self.secili_eposta_idini_al()
    if not mail_id:
        if getattr(self, "liste_modu", LISTE_MODU_EPOSTA) != LISTE_MODU_EPOSTA:
            ui.message("Kaydetmek için önce bir klasöre girin ve e-posta seçin.")
        else:
            ui.message("Kaydetmek için e-posta seçin.")
        return

    varsayilan_ad = "eposta"
    indeks = self.liste.GetFocusedItem()
    if 0 <= indeks < len(self.mailler):
        eposta = self.mailler[indeks]
        konu = guvenli_dosya_adi(eposta.get("konu", "Konusuz"), "Konusuz", 60)
        varsayilan_ad = konu

    dlg = wx.FileDialog(
        self,
        "E-postayı kaydet",
        defaultDir=wx.StandardPaths.Get().GetDocumentsDir(),
        defaultFile=varsayilan_ad,
        wildcard="EML dosyaları (*.eml)|*.eml|TXT dosyaları (*.txt)|*.txt",
        style=wx.FD_SAVE | wx.FD_OVERWRITE_PROMPT,
    )
    try:
        dlg.SetFilterIndex(0)
        if dlg.ShowModal() != wx.ID_OK:
            self.liste.SetFocus()
            return
        hedef_yol = dlg.GetPath()
        bicim = "eml" if dlg.GetFilterIndex() == 0 else "txt"
    finally:
        dlg.Destroy()

    uzanti = os.path.splitext(hedef_yol)[1]
    if uzanti.lower() in (".eml", ".txt"):
        bicim = uzanti[1:].lower()
    else:
        hedef_yol = f"{hedef_yol}.{bicim}"

    if not hedef_yol:
        self.liste.SetFocus()
        return
    kaynak_klasor = self.aktif_klasor()
    mesaj_soyle_ve_sonra_calistir(
        f"E-posta {bicim.upper()} olarak kaydediliyor.",
        lambda: arka_planda_calistir(
            self.sunucudan_epostayi_kaydet,
            mail_id,
            kaynak_klasor,
            hedef_yol,
            bicim,
        ),
        ad="E-posta kaydetme",
    )

def txt_kayit_metni_olustur(self, mesaj, icerik, ekler, kaynak_klasor):
    hesap_ayarlari = ayarlari_yukle()
    kimden = gonderen_basligini_gosterime_hazirla(
        mesaj.get("From", "Bilinmiyor"), "Bilinmiyor"
    )
    kime = adres_basligini_gosterime_hazirla(
        mesaj.get("To", ""), "", hesap_ayarlari.get("eposta", ""),
        hesap_ayarlari.get("gorunen_ad", "")
    )
    cc = adres_basligini_gosterime_hazirla(
        mesaj.get("Cc", ""), "", hesap_ayarlari.get("eposta", ""),
        hesap_ayarlari.get("gorunen_ad", "")
    )
    konu = konu_gosterimini_duzenle(
        guvenli_coz(mesaj.get("Subject", "Konusuz")) or "Konusuz"
    )
    tarih = turkce_tarih_yap(mesaj.get("Date", ""))
    ek_adlari = [guvenli_coz(ad or "ek_dosya") for ad, _veri in ekler]
    satirlar = [
        f"Kimden: {kimden}",
        f"Kime: {kime}",
    ]
    if cc:
        satirlar.append(f"Bilgi: {cc}")
    satirlar.extend(
        [
            f"Konu: {konu}",
            f"Tarih: {tarih}",
            f"Klasör: {self.secili_kategori}",
            f"IMAP klasörü: {kaynak_klasor}",
            f"Ek sayısı: {len(ek_adlari)}",
        ]
    )
    if ek_adlari:
        satirlar.append("Ekler:")
        for ek_adi in ek_adlari:
            satirlar.append(f"- {ek_adi}")
    satirlar.extend(["-" * 50, "", icerik or ""])
    return "\n".join(satirlar).strip() + "\n"

def sunucudan_epostayi_kaydet(self, mail_id, kaynak_klasor, hedef_yol, bicim):
    ayarlar = ayarlari_yukle()
    try:
        if bicim not in ("txt", "eml"):
            raise MailHatasi("Desteklenmeyen kaydetme biçimi.")

        with ImapBaglantisi(ayarlar) as imap:
            tip, _veri = imap.select(kaynak_klasor, readonly=True)
            if tip != "OK":
                raise MailHatasi("Seçili klasör açılamadı.")

            imap_eposta_boyutunu_denetle(
                imap,
                mail_id,
                AZAMI_EPOSTA_ISLEME_BOYUTU,
                "Kaydedilecek e-posta",
            )
            tip, veri = imap.uid("FETCH", str(mail_id), "(BODY.PEEK[])")
            if tip != "OK":
                raise MailHatasi("E-posta sunucudan alınamadı.")
            ham_veri = ham_mesaj_verisi_al(veri)
            if not ham_veri:
                raise MailHatasi("E-posta içeriği alınamadı.")
            ham_eposta_boyutunu_denetle(ham_veri, "Kaydedilecek e-posta")

            mesaj = email.message_from_bytes(ham_veri, policy=email_policy.default)
            try:
                if bicim == "eml":
                    with open(hedef_yol, "wb") as dosya:
                        dosya.write(ham_veri)
                else:
                    icerik, ekler = mesaj_metni_ve_ekleri_cikar(mesaj)
                    kayit_metni = self.txt_kayit_metni_olustur(mesaj, icerik, ekler, kaynak_klasor)
                    with open(hedef_yol, "w", encoding="utf-8") as dosya:
                        dosya.write(kayit_metni)
            except OSError as e:
                raise MailHatasi(
                    f"E-posta dosyaya yazılamadı: {os.path.basename(hedef_yol)}. "
                    "Seçilen klasör yazma korumalı olabilir, disk dolu olabilir "
                    "veya güvenlik yazılımı dosyayı kilitlemiş olabilir."
                ) from e

        guvenli_call_after(self, kaydetme_sonuc_penceresi_goster, self, bicim, hedef_yol)
    except MailHatasi as e:
        hata_kaydet(str(e))
        guvenli_call_after(self, ui.message, str(e))
        guvenli_call_after(self, self.liste.SetFocus)
    except Exception as e:
        hata_kaydet("Kaydetme işlemi başarısız oldu.", e)
        guvenli_call_after(self, ui.message, "Kaydetme işlemi sırasında bir hata oluştu. Lütfen dosya izinlerini ve bağlantınızı kontrol edin.")
        guvenli_call_after(self, self.liste.SetFocus)

class KaydetmeSonucPenceresi(wx.Dialog):
    def __init__(self, parent, bicim, hedef_yol):
        super().__init__(parent, title="E-posta Kaydedildi")
        self.hedef_yol = str(hedef_yol or "").strip()
        self.hedef_klasor = os.path.dirname(self.hedef_yol) or self.hedef_yol

        duzen = wx.BoxSizer(wx.VERTICAL)
        mesaj = (
            f"E-postanız {str(bicim).upper()} formatında kaydedilmiştir.\n\n"
            f"Klasör: {self.hedef_klasor}"
        )
        metin = wx.StaticText(self, label=mesaj)
        duzen.Add(metin, 0, wx.ALL | wx.EXPAND, 10)

        dugmeler = wx.BoxSizer(wx.HORIZONTAL)
        self.klasor_ac_btn = wx.Button(self, wx.ID_OPEN, label="Klasörü Aç")
        self.kapat_btn = wx.Button(self, wx.ID_CLOSE, label="Kapat")
        self.klasor_ac_btn.Bind(wx.EVT_BUTTON, self.klasoru_ac)
        self.kapat_btn.Bind(wx.EVT_BUTTON, lambda event: self.EndModal(wx.ID_CLOSE))
        dugmeler.Add(self.klasor_ac_btn, 0, wx.ALL, 5)
        dugmeler.Add(self.kapat_btn, 0, wx.ALL, 5)
        duzen.Add(dugmeler, 0, wx.ALIGN_CENTER | wx.BOTTOM, 5)

        self.SetSizerAndFit(duzen)
        self.SetMinSize((520, -1))
        self.Fit()
        self.CenterOnParent()
        self.klasor_ac_btn.SetDefault()
        wx.CallAfter(self.klasor_ac_btn.SetFocus)

    def klasoru_ac(self, event=None):
        if not self.hedef_klasor or not os.path.isdir(self.hedef_klasor):
            ui.message("Kaydedilen klasör bulunamadı.")
            return
        try:
            os.startfile(self.hedef_klasor)
            self.EndModal(wx.ID_OPEN)
        except Exception as e:
            hata_kaydet("Kaydedilen klasör açılamadı.", e)
            ui.message("Kaydedilen klasör açılamadı.")


def kaydetme_sonuc_penceresi_goster(self, bicim, hedef_yol):
    pencere = KaydetmeSonucPenceresi(self, bicim, hedef_yol)
    sonuc = wx.ID_CLOSE
    try:
        sonuc = pencere.ShowModal()
    finally:
        try:
            pencere.Destroy()
        except Exception as e:
            hata_kaydet("Kaydetme sonucu penceresi kapatılamadı.", e)
    if sonuc != wx.ID_OPEN:
        try:
            self.liste.SetFocus()
        except Exception:
            pass

def yeni_posta_yaz(self, event=None):
    try:
        imza = imza_yukle()
        pencere = YeniPostaPenceresi(
            self,
            varsayilan_icerik=("\n\n" + imza) if imza else "",
            gonderildi_callback=lambda: self.yeni_eposta_gonderildi(),
            taslak_kaydet_callback=lambda: self.taslak_kaydedildi(),
            taslak_klasor_adaylari=self.taslak_klasor_adaylari(),
        )
        if imza:
            pencere.txt_icerik.SetInsertionPoint(0)
        guvenli_modal_goster(pencere, self.liste, self)
    except Exception as e:
        hata_kaydet("E-posta yazma penceresi açılamadı.", e)
        try:
            gui.messageBox(
                "E-posta yazma penceresi açılamadı.",
                "E-posta Yazma Hatası",
                wx.OK | wx.ICON_ERROR,
                self,
            )
        except Exception as hata:
            hata_kaydet("E-posta yazma hatası penceresi gösterilemedi.", hata)
            ui.message("E-posta yazma penceresi açılamadı.")

def secili_mesaji_yanitla(self, event=None):
    self.secili_mesaji_yanitla_veya_ilet("yanitla")

def secili_mesaji_ilet(self, event=None):
    self.secili_mesaji_yanitla_veya_ilet("ilet")


def _yanit_veya_ilet_onbellek_verisi(ayarlar, mail_id, kaynak_klasor, islem):
    """Yanıt/iletme verisini uygunsa ağ bağlantısı kurmadan yerel önbellekten hazırlar."""
    onbellek = mesaj_govdesini_al(
        ayarlar.get("eposta", ""), kaynak_klasor, mail_id
    )
    if not onbellek:
        return None
    if int(onbellek.get("parser_version") or 0) < BODY_PARSER_VERSION:
        return None

    ekler = []
    if islem == "ilet" and bool(onbellek.get("has_attachments")):
        if not bool(onbellek.get("attachments_cached")):
            return None
        ekler = ekleri_onbellekten_al(onbellek.get("message_id"))
        if ekler is None:
            return None

    kimden = str(onbellek.get("sender", "") or "Bilinmiyor")
    _ad, adres = email.utils.parseaddr(kimden)
    adres_goster = grup_araci_adresini_temizle(adres)
    yanit_basligi = str(onbellek.get("reply_to", "") or kimden)
    return {
        "id": str(mail_id),
        "klasor": kaynak_klasor,
        "kimden_tam": gonderen_gosterimini_al(kimden, "Bilinmiyor"),
        "kimden_adres": adres_goster or adres or kimden,
        "yanit_adresi": adres_basligini_duzenle(yanit_basligi),
        "kime": adres_basligini_gosterime_hazirla(
            onbellek.get("recipients_to", ""), "", ayarlar.get("eposta", ""),
            ayarlar.get("gorunen_ad", "")
        ),
        "konu": guvenli_coz(onbellek.get("subject", "") or "Konusuz") or "Konusuz",
        "tarih": turkce_tarih_yap(onbellek.get("date_header", "")),
        "message_id": str(onbellek.get("rfc_message_id", "") or ""),
        "references": str(onbellek.get("references_header", "") or ""),
        "icerik": str(onbellek.get("plain_text", "") or ""),
        "ekler": ekler,
    }


def secili_mesaji_yanitla_veya_ilet(self, islem):
    if self.yukleniyor:
        ui.message("Devam eden işlem tamamlandıktan sonra yeniden deneyin.")
        return
    indeks = self.liste.GetFocusedItem()
    if indeks == -1 or indeks >= len(self.mailler):
        ui.message("Lütfen işlem yapmak istediğiniz e-postayı seçin.")
        return
    mail_id = self.mailler[indeks].get("id")
    kaynak_klasor = self.aktif_klasor()
    mesaj_soyle_ve_sonra_calistir(
        "Yanıt hazırlanıyor." if islem == "yanitla"
        else "İletilecek e-posta hazırlanıyor.",
        lambda: arka_planda_calistir(
            self.sunucudan_yanit_veya_ilet_hazirla,
            mail_id,
            kaynak_klasor,
            islem,
        ),
        ad="Yanıt veya ilet hazırlama",
    )

def sunucudan_yanit_veya_ilet_hazirla(self, mail_id, kaynak_klasor, islem):
    ayarlar = ayarlari_yukle()
    try:
        onbellek_verisi = _yanit_veya_ilet_onbellek_verisi(
            ayarlar, mail_id, kaynak_klasor, islem
        )
        if onbellek_verisi is not None:
            guvenli_call_after(
                self, self.yanit_veya_ilet_penceresini_ac, onbellek_verisi, islem
            )
            return

        with ImapBaglantisi(ayarlar) as imap:
            tip, _veri = imap.select(kaynak_klasor, readonly=False)
            imap_ok_mu(tip, "Seçili klasör açılamadı.")
            imap_eposta_boyutunu_denetle(
                imap,
                mail_id,
                AZAMI_EPOSTA_ISLEME_BOYUTU,
                "Yanıt veya iletme için e-posta",
            )
            tip, veri = imap.uid("FETCH", str(mail_id), "(BODY.PEEK[])")
            imap_ok_mu(tip, "E-posta içeriği alınamadı.")
            ham_veri = ham_mesaj_verisi_al(veri)
            if not ham_veri:
                raise MailHatasi("E-posta içeriği boş döndü.")
            ham_eposta_boyutunu_denetle(ham_veri, "Yanıt veya iletme için e-posta")

        mesaj = email.message_from_bytes(ham_veri, policy=email_policy.default)
        icerik, ekler, atlanan_ek_sayisi = mesaj_metni_ve_ekleri_cikar(
            mesaj, ayrintili=True
        )
        kimden = guvenli_coz(mesaj.get("From", "Bilinmiyor"))
        _ad, adres = email.utils.parseaddr(kimden)
        adres_goster = grup_araci_adresini_temizle(adres)
        veri = {
            "id": str(mail_id),
            "klasor": kaynak_klasor,
            "kimden_tam": gonderen_gosterimini_al(kimden, "Bilinmiyor"),
            "kimden_adres": adres_goster or adres or kimden,
            "yanit_adresi": yanit_adresini_bul(mesaj),
            "kime": adres_basligini_gosterime_hazirla(
                mesaj.get("To", ""), "", ayarlar.get("eposta", ""),
                ayarlar.get("gorunen_ad", "")
            ),
            "konu": guvenli_coz(mesaj.get("Subject", "Konusuz")) or "Konusuz",
            "tarih": turkce_tarih_yap(mesaj.get("Date", "")),
            "message_id": eposta_basligi_tek_satir_yap(mesaj.get("Message-ID", "")),
            "references": eposta_basligi_tek_satir_yap(mesaj.get("References", "")),
            "icerik": icerik or "",
            "ekler": ekler if islem == "ilet" else [],
        }
        try:
            onbellek_kotasi_denetle(len(ham_veri))
            mesaj_govdesini_kaydet(
                ayarlar.get("eposta", ""), kaynak_klasor, mail_id,
                icerik or "", len(ham_veri), mesaj.get("Date", ""),
            )
            if ekler or atlanan_ek_sayisi:
                ekleri_onbellege_kaydet(
                    ayarlar.get("eposta", ""), kaynak_klasor, mail_id, ekler,
                    tamamlandi=(atlanan_ek_sayisi == 0),
                )
        except Exception as e:
            hata_kaydet("Yanıt/ilet içeriği yerel önbelleğe kaydedilemedi.", e)
        guvenli_call_after(self, self.yanit_veya_ilet_penceresini_ac, veri, islem)
    except MailHatasi as e:
        hata_kaydet(str(e))
        guvenli_call_after(self, ui.message, str(e))
    except Exception as e:
        hata_kaydet("Yanıt/ilet hazırlığı başarısız oldu.", e)
        guvenli_call_after(self, ui.message, "E-posta hazırlanırken bir hata oluştu.")

def yanit_veya_ilet_penceresini_ac(self, veri, islem):
    if not pencere_kullanilabilir_mi(self):
        return
    konu = veri.get("konu", "")
    if islem == "yanitla":
        if not konu.lower().startswith("re:"):
            konu = "Re: " + konu
        icerik = f"\n\n\n--- Orijinal E-posta ---\n{veri.get('icerik', '')}"
        kime = veri.get("yanit_adresi") or veri.get("kimden_adres", "")
        yanit_basliklari = yanit_basliklari_hazirla(veri)
    else:
        if not konu.lower().startswith("fwd:"):
            konu = "Fwd: " + konu
        icerik = f"\n\n\n--- İletilen E-posta ---\n{veri.get('icerik', '')}"
        kime = ""
        yanit_basliklari = {}

    pencere = YeniPostaPenceresi(
        self,
        varsayilan_kime=kime,
        varsayilan_konu=konu,
        varsayilan_icerik=icerik,
        yanit_basliklari=yanit_basliklari,
        taslak_kaydet_callback=lambda: self.taslak_kaydedildi(),
        taslak_klasor_adaylari=self.taslak_klasor_adaylari(),
        hazir_ekler=veri.get("ekler", []) if islem == "ilet" else None,
    )
    guvenli_modal_goster(pencere, self.liste, self)

def mesaj_oku(self, event):
    if getattr(self, "liste_modu", LISTE_MODU_EPOSTA) != LISTE_MODU_EPOSTA:
        return
    indeks = event.GetIndex()
    if indeks == -1 or indeks >= len(self.mailler):
        return
    secili_mesaj = self.mailler[indeks]
    mail_id = secili_mesaj["id"]
    kaynak_klasor = self.aktif_klasor()
    konusma_ids = [str(uid) for uid in secili_mesaj.get("ids", []) if str(uid)]
    if secili_mesaj.get("thread_id") and len(konusma_ids) > 1 and not self.taslak_klasoru_mu(kaynak_klasor):
        arka_planda_calistir(
            self.sunucudan_konusma_icerigi_indir, secili_mesaj.get("thread_id"),
            konusma_ids, kaynak_klasor,
        )
        return
    baslat = lambda: arka_planda_calistir(self.sunucudan_icerik_indir, mail_id, kaynak_klasor)
    mesaj = "Taslak düzenleniyor." if self.taslak_klasoru_mu(kaynak_klasor) else "E-posta görüntüleniyor."
    mesaj_soyle_ve_sonra_calistir(
        mesaj,
        baslat,
        ad="E-posta açma",
        bekleme_ms=0,
    )


def sunucudan_konusma_icerigi_indir(self, thread_id, uidler, kaynak_klasor):
    """Bir Gmail konuşmasını en yeni ileti başta olacak biçimde tek okuma verisine dönüştürür."""
    ayarlar = ayarlari_yukle()
    eposta = str(ayarlar.get("eposta", "") or "").strip()
    try:
        satirlar = konusma_mesajlarini_listele(eposta, kaynak_klasor, thread_id)
        eksik = [
            str(s.get("uid")) for s in satirlar
            if int(s.get("parser_version") or 0) < BODY_PARSER_VERSION
        ]
        if eksik:
            with ImapBaglantisi(ayarlar) as imap:
                tip, _secim = imap.select(kaynak_klasor, readonly=False)
                imap_ok_mu(tip, "Konuşmanın bulunduğu klasör açılamadı.")
                sonuc = klasor_govdelerini_senkronize_et(
                    imap, eposta, kaynak_klasor, eksik
                )
                if sonuc.get("atlandi"):
                    secili_govdeleri_dogrudan_senkronize_et(
                        imap, eposta, kaynak_klasor, eksik
                    )
        satirlar = konusma_mesajlarini_listele(eposta, kaynak_klasor, thread_id)
        if not satirlar:
            raise MailHatasi("Konuşmadaki e-postalar bulunamadı.")
        bolumler, tum_ekler = [], []
        ekler_eksik = False
        for sira, satir in enumerate(satirlar, 1):
            kimden = gonderen_gosterimini_al(satir.get("sender", ""), "Bilinmiyor")
            kime = adres_basligini_gosterime_hazirla(satir.get("recipients_to", ""), "", eposta, ayarlar.get("gorunen_ad", ""))
            bilgi = adres_basligini_gosterime_hazirla(satir.get("recipients_cc", ""), "", eposta, ayarlar.get("gorunen_ad", ""))
            bilgi_satiri = f"Bilgi: {bilgi}\n" if bilgi else ""
            tarih = turkce_tarih_yap(satir.get("date_header", ""))
            govde = str(satir.get("plain_text") or "İleti gövdesi önbelleğe alınamadı.")
            bolumler.append(
                f"{sira}. ileti\nKimden: {kimden}\nKime: {kime}\n{bilgi_satiri}Tarih: {tarih}\n"
                f"Konu: {konu_gosterimini_duzenle(guvenli_coz(satir.get('subject', '') or 'Konusuz'))}\n{'-' * 50}\n{govde}"
            )
            if satir.get("has_attachments"):
                ekler = ekleri_onbellekten_al(satir.get("message_id"))
                if ekler is None:
                    ekler_eksik = True
                else:
                    tum_ekler.extend(ekler)
        son = satirlar[0]
        son_kimden = str(son.get("sender") or "Bilinmiyor")
        _ad, son_adres = email.utils.parseaddr(son_kimden)
        veri = {
            "id": str(son.get("uid")), "ids": [str(s.get("uid")) for s in satirlar],
            "thread_id": str(thread_id), "konusma_mi": True, "klasor": kaynak_klasor,
            "kimden_tam": gonderen_gosterimini_al(son_kimden, "Bilinmiyor"),
            "kimden_adres": son_adres or son_kimden,
            "yanit_adresi": str(son.get("reply_to") or son_adres or son_kimden),
            "kime": adres_basligini_gosterime_hazirla(son.get("recipients_to", ""), "", eposta, ayarlar.get("gorunen_ad", "")),
            "bilgi": adres_basligini_gosterime_hazirla(son.get("recipients_cc", ""), "", eposta, ayarlar.get("gorunen_ad", "")),
            "konu": guvenli_coz(son.get("subject", "") or "Konusuz") or "Konusuz",
            "tarih": turkce_tarih_yap(son.get("date_header", "")),
            "message_id": str(son.get("rfc_message_id") or ""),
            "references": str(son.get("references_header") or ""),
            "son_icerik": str(son.get("plain_text") or ""),
            "icerik": ("\n\n" + "=" * 60 + "\n\n").join(bolumler),
            "ekler": tum_ekler, "ekler_eksik": ekler_eksik, "taslak_mi": False,
        }
        for uid in veri["ids"]:
            mesaji_yerelde_okundu_yap(eposta, kaynak_klasor, uid)
        guvenli_call_after(self, self.mesaji_listede_okundu_yap, veri["id"])
        try:
            with ImapBaglantisi(ayarlar) as imap:
                tip, _secim = imap.select(kaynak_klasor, readonly=False)
                if tip == "OK":
                    imap.uid("STORE", ",".join(veri["ids"]), "+FLAGS.SILENT", "(\\Seen)")
        except Exception as e:
            hata_kaydet("Konuşma sunucuda okundu yapılamadı.", e)
        guvenli_call_after(self, self.okuma_penceresini_ac, veri)
    except MailHatasi as e:
        hata_kaydet(str(e))
        guvenli_call_after(self, ui.message, str(e))
    except Exception as e:
        hata_kaydet("Konuşma açılamadı.", e)
        guvenli_call_after(self, ui.message, "Konuşma açılırken bir hata oluştu.")

def sunucudan_icerik_indir(self, mail_id, kaynak_klasor, acma_callback=None):
    ayarlar = ayarlari_yukle()
    okuma_callback = acma_callback if callable(acma_callback) else self.okuma_penceresini_ac
    try:
        klasor = kaynak_klasor or self.aktif_klasor()
        liste_guncellensin = str(self.aktif_klasor()) == str(klasor)
        taslak_mi = self.taslak_klasoru_mu(klasor)
        if not taslak_mi:
            onbellek = mesaj_govdesini_al(ayarlar.get("eposta", ""), klasor, mail_id)
            # Büyük olduğu için bilinçli olarak atlanan ekler gövdenin çevrimdışı
            # okunmasını engellemez. Kayıtlı bir ek bozuk/eksikse sunucuya dönülür.
            onbellek_ekleri = None
            if onbellek and bool(onbellek.get("has_attachments")):
                onbellek_ekleri = ekleri_onbellekten_al(onbellek.get("message_id"))
            onbellek_kullanilabilir = bool(onbellek) and (
                not bool(onbellek.get("has_attachments")) or onbellek_ekleri is not None
            ) and int(onbellek.get("parser_version") or 0) >= BODY_PARSER_VERSION
            if onbellek_kullanilabilir:
                kimden = str(onbellek.get("sender", "") or "Bilinmiyor")
                _ad, adres = email.utils.parseaddr(kimden)
                adres_goster = grup_araci_adresini_temizle(adres)
                veri = {
                    "id": str(mail_id),
                    "klasor": klasor,
                    "kimden_tam": gonderen_gosterimini_al(kimden, "Bilinmiyor"),
                    "kimden_adres": adres_goster or adres or kimden,
                    "yanit_adresi": str(onbellek.get("reply_to", "") or adres or kimden),
                    "kime": adres_basligini_gosterime_hazirla(
                        onbellek.get("recipients_to", ""), "",
                        ayarlar.get("eposta", ""), ayarlar.get("gorunen_ad", "")
                    ),
                    "bilgi": adres_basligini_gosterime_hazirla(
                        onbellek.get("recipients_cc", ""), "",
                        ayarlar.get("eposta", ""), ayarlar.get("gorunen_ad", "")
                    ),
                    "konu": guvenli_coz(onbellek.get("subject", "") or "Konusuz") or "Konusuz",
                    "tarih": turkce_tarih_yap(onbellek.get("date_header", "")),
                    "message_id": str(onbellek.get("rfc_message_id", "") or ""),
                    "references": str(onbellek.get("references_header", "") or ""),
                    "icerik": str(onbellek.get("plain_text", "") or ""),
                    "ekler": onbellek_ekleri or [],
                    "ekler_eksik": bool(onbellek.get("has_attachments"))
                    and not bool(onbellek.get("attachments_cached")),
                    "taslak_mi": False,
                }
                mesaji_yerelde_okundu_yap(ayarlar.get("eposta", ""), klasor, mail_id)
                if liste_guncellensin:
                    guvenli_call_after(self, self.mesaji_listede_okundu_yap, mail_id)
                guvenli_call_after(self, okuma_callback, veri)
                try:
                    with ImapBaglantisi(ayarlar) as imap:
                        tip, _secim = imap.select(klasor, readonly=False)
                        if tip == "OK":
                            imap.uid("STORE", str(mail_id), "+FLAGS.SILENT", "(\\Seen)")
                except Exception as e:
                    hata_kaydet("Önbellekten açılan e-posta sunucuda okundu yapılamadı.", e)
                return
        with ImapBaglantisi(ayarlar) as imap:
            tip, _veri = imap.select(klasor, readonly=False)
            if tip != "OK":
                raise MailHatasi("Seçili klasör açılamadı.")
            beklenen_boyut = imap_eposta_boyutunu_denetle(
                imap,
                mail_id,
                AZAMI_EPOSTA_ISLEME_BOYUTU,
                "Görüntülenecek e-posta",
            )
            tip, veri = imap.uid("FETCH", str(mail_id), "(BODY.PEEK[])")
            if tip != "OK":
                raise MailHatasi("E-posta içeriği alınamadı.")
            ham_veri = ham_mesaj_verisi_al(veri)
            if not ham_veri:
                raise MailHatasi("E-posta içeriği boş döndü.")
            ham_eposta_boyutunu_denetle(ham_veri, "Görüntülenecek e-posta")

            mesaj = email.message_from_bytes(ham_veri, policy=email_policy.default)
            icerik, ekler, atlanan_ek_sayisi = mesaj_metni_ve_ekleri_cikar(
                mesaj, ayrintili=True
            )
            kimden = guvenli_coz(mesaj.get("From", "Bilinmiyor"))
            _ad, adres = email.utils.parseaddr(kimden)
            adres_goster = grup_araci_adresini_temizle(adres)
            kime_basligi = mesaj.get("To", "")
            bilgi_basligi = mesaj.get("Cc", "")
            gizli_basligi = mesaj.get("Bcc", "")
            veri = {
                "id": str(mail_id),
                "klasor": klasor,
                "kimden_tam": gonderen_gosterimini_al(kimden, "Bilinmiyor"),
                "kimden_adres": adres_goster or adres or kimden,
                "yanit_adresi": yanit_adresini_bul(mesaj),
                "kime": (
                    adres_basligini_duzenle(kime_basligi)
                    if taslak_mi
                    else adres_basligini_gosterime_hazirla(
                        kime_basligi, "", ayarlar.get("eposta", ""),
                        ayarlar.get("gorunen_ad", "")
                    )
                ),
                "bilgi": (
                    adres_basligini_duzenle(bilgi_basligi)
                    if taslak_mi
                    else adres_basligini_gosterime_hazirla(
                        bilgi_basligi, "", ayarlar.get("eposta", ""),
                        ayarlar.get("gorunen_ad", "")
                    )
                ),
                "gizli": adres_basligini_duzenle(gizli_basligi) if taslak_mi else "",
                "konu": guvenli_coz(mesaj.get("Subject", "Konusuz")) or "Konusuz",
                "tarih": turkce_tarih_yap(mesaj.get("Date", "")),
                "message_id": eposta_basligi_tek_satir_yap(mesaj.get("Message-ID", "")),
                "references": eposta_basligi_tek_satir_yap(mesaj.get("References", "")),
                "icerik": icerik or "",
                "ekler": ekler,
                "taslak_mi": taslak_mi,
            }
            if not taslak_mi:
                try:
                    onbellek_kotasi_denetle(beklenen_boyut)
                    mesaj_govdesini_kaydet(
                        ayarlar.get("eposta", ""),
                        klasor,
                        mail_id,
                        icerik or "",
                        len(ham_veri),
                        mesaj.get("Date", ""),
                    )
                    mesaji_yerelde_okundu_yap(
                        ayarlar.get("eposta", ""), klasor, mail_id
                    )
                    if ekler or atlanan_ek_sayisi:
                        ekleri_onbellege_kaydet(
                            ayarlar.get("eposta", ""),
                            klasor,
                            mail_id,
                            ekler,
                            tamamlandi=(atlanan_ek_sayisi == 0),
                        )
                except Exception as e:
                    hata_kaydet("E-posta gövdesi yerel veritabanına kaydedilemedi.", e)
                imap.uid("STORE", str(mail_id), "+FLAGS.SILENT", "(\\Seen)")
        if veri.get("taslak_mi"):
            guvenli_call_after(self, self.taslak_penceresini_ac, veri)
        else:
            if liste_guncellensin:
                guvenli_call_after(self, self.mesaji_listede_okundu_yap, mail_id)
            guvenli_call_after(self, okuma_callback, veri)
    except MailHatasi as e:
        hata_kaydet(str(e))
        guvenli_call_after(self, ui.message, str(e))
        if callable(acma_callback):
            guvenli_call_after(self, acma_callback, None)
    except Exception as e:
        hata_kaydet("E-posta içeriği indirilemedi.", e)
        guvenli_call_after(self, ui.message, "E-posta açılırken bir hata oluştu.")
        if callable(acma_callback):
            guvenli_call_after(self, acma_callback, None)

def okuma_penceresini_ac(self, veri):
    if not pencere_kullanilabilir_mi(self):
        return
    pencere = MesajOkumaPenceresi(self, veri, self)
    guvenli_modal_goster(pencere, self.liste, self)
