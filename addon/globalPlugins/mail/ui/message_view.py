# -*- coding: utf-8 -*-
# Engelsiz Mail - E-posta okuma penceresi


# NVDA eklenti çevirilerini bu modül için etkinleştir.
try:
    import addonHandler
    addonHandler.initTranslation()
except (ImportError, AttributeError):
    # NVDA dışındaki otomatik testlerde Türkçe kaynak metni aynen kullan.
    _ = lambda metin: metin

import html
import os
import re
import webbrowser
from urllib.parse import urlsplit

import wx
import ui

try:
    import wx.html2
    HTML_DESTEKLENIYOR = True
except Exception:
    HTML_DESTEKLENIYOR = False

from ..config import eposta_gorunumu_yukle, eposta_icerigi_oldugu_gibi_yukle, EPOSTA_GORUNUMU_HTML

from ..attachments import benzersiz_yol
from ..logger import hata_kaydet
from ..message_center import mesaj_soyle_ve_sonra_calistir
from ..message_parser import ad_ve_adresi_goster, yanit_basliklari_hazirla
from ..text_utils import (
    duz_metni_ekran_okuyucu_icin_temizle,
    guvenli_dosya_adi,
    guvenli_baglanti_mi,
    html_guvenli_hale_getir,
    http_baglantilarini_bul,
    konu_gosterimini_duzenle,
)
from ..ui_helpers import guvenli_call_after, guvenli_modal_goster, gorunum_denetime_uygula, arka_planda_calistir
from .compose_window import YeniPostaPenceresi

URL_DESENI = re.compile(r'(https?://[^\s<>"]+)')


def duz_metni_htmle_donustur(metin):
    """Düz metindeki URL'leri tıklanabilir köprülere ve paragraflara çevirir."""
    guvenli = html.escape(metin or "")
    linkli = URL_DESENI.sub(r'<a href="\1">\1</a>', guvenli)
    paragraflar = linkli.split("\n\n")
    html_parcalar = []
    for p in paragraflar:
        p_temiz = p.replace("\n", "<br>\n")
        html_parcalar.append(f"<p>{p_temiz}</p>")
    return "\n".join(html_parcalar)


class MesajOkumaPenceresi(wx.Dialog):
    def __init__(self, parent, mesaj_verisi, ebeveyn_pencere):
        stil = wx.DEFAULT_DIALOG_STYLE | wx.RESIZE_BORDER | wx.MAXIMIZE_BOX | wx.MINIMIZE_BOX
        super().__init__(parent, title=_("E-posta"), style=stil)
        self.mesaj_verisi = mesaj_verisi
        self.ebeveyn = ebeveyn_pencere
        self._kapatildi = False
        self.Bind(wx.EVT_CLOSE, self._pencere_kapaniyor)
        self.Bind(wx.EVT_WINDOW_DESTROY, self._pencere_yok_ediliyor)
        self.Bind(wx.EVT_ACTIVATE, self._pencere_aktiflesme)
        self.Bind(wx.EVT_CHAR_HOOK, self.tus_yakalandi)

        # Gelen HTML güvenilmezdir: WebView'a verilmeden önce izin listesiyle temizlenir.
        # "Olduğu gibi göster" seçeneği açıksa resimler ve biçim korunur; betikler yine atılır.
        self._icerigi_oldugu_gibi = eposta_icerigi_oldugu_gibi_yukle()
        self.html_icerik = html_guvenli_hale_getir(mesaj_verisi.get("html_icerik"), uzak_icerik=self._icerigi_oldugu_gibi).strip()
        if not self.html_icerik:
            ham_metin = str(mesaj_verisi.get("icerik") or "").strip()
            if ham_metin:
                self.html_icerik = duz_metni_htmle_donustur(ham_metin)
        self.html_var = bool(self.html_icerik)

        duzen = wx.BoxSizer(wx.VERTICAL)
        ek_sayisi = len(mesaj_verisi.get("ekler", []))
        ek_var = ek_sayisi or bool(mesaj_verisi.get("has_attachments"))
        ek_notu = _('\nBu e-postada {0} ek dosya var.\n').format(ek_sayisi) if ek_sayisi else ""
        if mesaj_verisi.get("ekler_eksik"):
            ek_notu += _("Bazı ekler çevrim dışı önbellekte bulunmuyor.\n")
        kime_satiri = _('Kime: {0}\n').format(mesaj_verisi.get('kime', '')) if mesaj_verisi.get("kime") else ""
        bilgi_satiri = _('Bilgi: {0}\n').format(mesaj_verisi.get('bilgi', '')) if mesaj_verisi.get("bilgi") else ""
        kimden_gosterimi = ad_ve_adresi_goster(
            mesaj_verisi.get("kimden_tam", ""),
            mesaj_verisi.get("kimden_adres", ""),
            _("Bilinmiyor"),
        )
        ust_bilgi = "".join((
            _("Kimden: {0}\n").format(kimden_gosterimi),
            kime_satiri, bilgi_satiri,
            _("Tarih: {0}\n").format(mesaj_verisi.get("tarih", "")),
            _("Konu: {0}\n").format(konu_gosterimini_duzenle(mesaj_verisi.get("konu", ""))),
            ek_notu + '-' * 50 + "\n\n",
        ))
        mesaj_icerigi = duz_metni_ekran_okuyucu_icin_temizle(
            mesaj_verisi.get('icerik', '')
        )
        icerik = ust_bilgi + mesaj_icerigi
        self.icerik_baslangic_indeksi = len(ust_bilgi)
        self.txt_icerik = wx.TextCtrl(self, value=icerik, style=wx.TE_MULTILINE | wx.TE_READONLY | wx.TE_RICH2)
        denetim_icerigi = self.txt_icerik.GetValue()
        self.baglanti_konumlari = http_baglantilarini_bul(denetim_icerigi)
        konusma_baslik_deseni = re.escape(_("{0}. ileti")).replace(re.escape("{0}"), r"\d+")
        self.konusma_ileti_konumlari = (
            [
                eslesme.start()
                for eslesme in re.finditer(
                    r"(?m)^" + konusma_baslik_deseni + r"\r?\n", denetim_icerigi
                )
            ]
            if mesaj_verisi.get("konusma_mi") else []
        )
        if self.konusma_ileti_konumlari:
            self.icerik_baslangic_indeksi = self.konusma_ileti_konumlari[0]
        self.txt_icerik.SetName(_("E-posta içeriği"))
        duzen.Add(self.txt_icerik, 1, wx.ALL | wx.EXPAND, 10)
        gorunum_denetime_uygula(self.txt_icerik)

        self.web_gorunum = None
        kime_html = html.escape(str(mesaj_verisi.get("kime", "") or ""))
        bilgi_html = html.escape(str(mesaj_verisi.get("bilgi", "") or ""))
        kimden_html = html.escape(str(kimden_gosterimi or ""))
        konu_html = html.escape(str(konu_gosterimini_duzenle(mesaj_verisi.get("konu", "")) or ""))
        tarih_html = html.escape(str(mesaj_verisi.get("tarih", "") or ""))
        ek_notu_html = html.escape(str(ek_notu.strip() or ""))

        ust_bilgi_html = f'''
        <div class="ust-satir"><strong>{_("Kimden:")}</strong> {kimden_html}</div>
        {f'<div class="ust-satir"><strong>{_("Kime:")}</strong> {kime_html}</div>' if kime_html else ''}
        {f'<div class="ust-satir"><strong>{_("Bilgi:")}</strong> {bilgi_html}</div>' if bilgi_html else ''}
        <div class="ust-satir"><strong>{_("Tarih:")}</strong> {tarih_html}</div>
        <div class="ust-satir"><strong>{_("Konu:")}</strong> {konu_html}</div>
        {f'<div class="ust-satir" style="color: #666;"><em>{ek_notu_html}</em></div>' if ek_notu_html else ''}
        '''
        if self._icerigi_oldugu_gibi:
            csp_icerigi = (
                "default-src 'none'; style-src 'unsafe-inline' http: https:; img-src http: https: data:; "
                "font-src http: https: data:; script-src 'none'; form-action 'none'; frame-src 'none'"
            )
        else:
            csp_icerigi = (
                "default-src 'none'; style-src 'unsafe-inline'; img-src 'none'; "
                "script-src 'none'; form-action 'none'; frame-src 'none'"
            )
        self.tam_html = f'''<!DOCTYPE html>
<html lang="tr">
<head>
<meta charset="utf-8">
<meta http-equiv="Content-Security-Policy" content="{csp_icerigi}">
<base target="_blank">
<style>
body {{
    font-family: Arial, sans-serif;
    font-size: 13pt;
    line-height: 1.6;
    color: #111;
    background-color: #fff;
    margin: 16px;
}}
.ust-bilgi {{
    border-bottom: 2px solid #555;
    padding-bottom: 12px;
    margin-bottom: 16px;
}}
.ust-satir {{
    margin: 4px 0;
}}
.icerik {{
    margin-top: 10px;
}}
table {{
    border-collapse: collapse;
    width: 100%;
    margin: 10px 0;
}}
th, td {{
    border: 1px solid #ccc;
    padding: 6px 10px;
}}
th {{
    background-color: #f2f2f2;
}}
a {{
    color: #0066cc;
    text-decoration: underline;
}}
</style>
</head>
<body>
<div class="ust-bilgi" role="region" aria-label="{_('E-posta üst bilgileri')}">
{ust_bilgi_html}
</div>
<div class="icerik" role="region" aria-label="{_('E-posta içeriği')}">
{self.html_icerik}
</div>
</body>
</html>'''

        # WebView (Edge/IE motoru) ağır bir bileşendir. Varsayılan görünüm metinse her
        # e-posta açılışında oluşturmak pencereyi yavaşlatır ve kapanışta takılma riski
        # taşır; bu yüzden yalnızca HTML görünümü gerçekten gerektiğinde oluşturulur.
        self._ana_duzen = duzen
        varsayilan_html = (eposta_gorunumu_yukle() == EPOSTA_GORUNUMU_HTML) and self.html_var
        if varsayilan_html:
            self._web_gorunumu_olustur()
        if varsayilan_html and self.web_gorunum:
            self.aktif_gorunum = "html"
            self.txt_icerik.Hide()
            self.web_gorunum.Show()
        else:
            self.aktif_gorunum = "metin"
            self.txt_icerik.Show()
            if self.web_gorunum:
                self.web_gorunum.Hide()

        btn_duzen = wx.BoxSizer(wx.HORIZONTAL)
        if ek_var:
            etiket = _('&Ekleri kaydet ({0})').format(ek_sayisi) if ek_sayisi else _("&Ekleri kaydet")
            ek_btn = wx.Button(self, label=etiket)
            ek_btn.Bind(wx.EVT_BUTTON, self.ekleri_kaydet)
            btn_duzen.Add(ek_btn, 0, wx.ALL, 5)

        yanitla_btn = wx.Button(self, label=_("&Yanıtla"))
        yanitla_btn.Bind(wx.EVT_BUTTON, self.mesaji_yanitla)
        btn_duzen.Add(yanitla_btn, 0, wx.ALL, 5)

        ilet_btn = wx.Button(self, label=_("İ&let"))
        ilet_btn.Bind(wx.EVT_BUTTON, self.mesaji_ilet)
        btn_duzen.Add(ilet_btn, 0, wx.ALL, 5)

        arsiv_btn = wx.Button(self, label=_("A&rşivle"))
        arsiv_btn.Bind(wx.EVT_BUTTON, self.mesaji_arsivle_ve_kapat)
        btn_duzen.Add(arsiv_btn, 0, wx.ALL, 5)

        sil_btn = wx.Button(self, label=_("&Sil"))
        sil_btn.Bind(wx.EVT_BUTTON, self.mesaji_sil_ve_kapat)
        btn_duzen.Add(sil_btn, 0, wx.ALL, 5)

        if self.html_var and (self.web_gorunum or self._web_gorunumu_kullanilabilir_mi()):
            etiket = _("&Metin Görünümüne Geç (F7)") if self.aktif_gorunum == "html" else _("&HTML Görünümüne Geç (F7)")
            self.gecis_btn = wx.Button(self, label=etiket)
            self.gecis_btn.Bind(wx.EVT_BUTTON, lambda event: self.gorunumu_degistir())
            btn_duzen.Add(self.gecis_btn, 0, wx.ALL, 5)

        def _kapat_tiklandi(event):
            self._kapatildi = True
            self.EndModal(wx.ID_OK)

        kapat_btn = wx.Button(self, label=_("&Kapat"))
        kapat_btn.Bind(wx.EVT_BUTTON, _kapat_tiklandi)
        btn_duzen.Add(kapat_btn, 0, wx.ALL, 5)

        duzen.Add(btn_duzen, 0, wx.CENTER | wx.BOTTOM, 10)
        self.SetSizer(duzen)
        self.SetSize((860, 660))
        self.CenterOnParent()
        if self.aktif_gorunum == "html" and self.web_gorunum:
            wx.CallAfter(self.web_gorunum.SetFocus)
        else:
            wx.CallAfter(self.icerik_baslangicina_odaklan)

    def _web_gorunumu_kullanilabilir_mi(self):
        if not HTML_DESTEKLENIYOR:
            return False
        try:
            return bool(wx.html2.WebView.IsBackendAvailable(wx.html2.WebViewBackendDefault))
        except Exception:
            return False

    def _web_gorunumu_olustur(self):
        """HTML WebView'unu oluşturur ve içeriği yükler; başarılıysa True döndürür."""
        if self.web_gorunum:
            return True
        if not self.html_var or not self._web_gorunumu_kullanilabilir_mi():
            return False
        try:
            if wx.html2.WebView.IsBackendAvailable(wx.html2.WebViewBackendDefault):
                self.web_gorunum = wx.html2.WebView.New(self)
                try:
                    self.web_gorunum.Bind(wx.html2.EVT_WEBVIEW_NAVIGATING, self._web_baglanti_tiklandi)
                except Exception:
                    pass
                try:
                    if hasattr(wx.html2, "EVT_WEBVIEW_NEWWINDOW"):
                        self.web_gorunum.Bind(wx.html2.EVT_WEBVIEW_NEWWINDOW, self._web_baglanti_tiklandi)
                except Exception:
                    pass
                self.web_gorunum.SetPage(self.tam_html, "")
                indeks = None
                for sira, oge in enumerate(self._ana_duzen.GetChildren()):
                    if oge.GetWindow() is self.txt_icerik:
                        indeks = sira + 1
                        break
                if indeks is None:
                    indeks = self._ana_duzen.GetItemCount()
                self._ana_duzen.Insert(indeks, self.web_gorunum, 1, wx.ALL | wx.EXPAND, 10)
                return True
        except Exception as e:
            hata_kaydet("HTML web görünümü oluşturulamadı.", e)
            self.web_gorunum = None
        return False

    def icerik_baslangicina_odaklan(self):
        try:
            self.txt_icerik.SetFocus()
            konum = max(0, int(getattr(self, "icerik_baslangic_indeksi", 0)))
            self.txt_icerik.SetInsertionPoint(konum)
            try:
                self.txt_icerik.SetSelection(konum, konum)
            except Exception:
                pass
            try:
                self.txt_icerik.ShowPosition(konum)
            except Exception:
                pass
        except Exception as e:
            hata_kaydet("E-posta içeriği başlangıcına odaklanılamadı.", e)

    def _pencere_kapaniyor(self, event):
        self._kapatildi = True
        self.EndModal(wx.ID_CANCEL)

    def _pencere_yok_ediliyor(self, event):
        if event.GetEventObject() is self:
            self._kapatildi = True
        event.Skip()

    def _pencere_aktiflesme(self, event):
        if event.GetActive():
            wx.CallAfter(self.odagi_tazele)
        event.Skip()

    def odagi_tazele(self):
        try:
            if self._kapatildi or not self:
                return
            if self.aktif_gorunum == "html" and self.web_gorunum:
                self.web_gorunum.SetFocus()
            elif hasattr(self, "txt_icerik") and self.txt_icerik:
                self.txt_icerik.SetFocus()
        except Exception:
            pass

    def _web_baglanti_tiklandi(self, event):
        url = str(event.GetURL() or "").strip()
        if not url:
            return
        url_kucuk = url.lower()
        if url_kucuk.startswith(("about:", "data:", "javascript:")):
            return
        if url_kucuk.startswith("#"):
            return

        try:
            event.Veto()
        except Exception:
            pass

        # Yalnızca http, https ve mailto bağlantıları dış uygulamada açılır.
        if not guvenli_baglanti_mi(url):
            hata_kaydet("Güvenli olmayan bağlantı şeması engellendi.")
            return

        try:
            if hasattr(self, "_baglantiyi_varsayilan_tarayıcıda_ac"):
                try:
                    wx.CallAfter(self._baglantiyi_varsayilan_tarayıcıda_ac, url)
                except Exception:
                    self._baglantiyi_varsayilan_tarayıcıda_ac(url)
            else:
                webbrowser.open(url)
        except Exception as e:
            hata_kaydet("Bağlantı varsayılan tarayıcıda açılamadı.", e)

    def gorunumu_degistir(self):
        if not self.html_var:
            mesaj_soyle_ve_sonra_calistir(
                _("Bu e-postada HTML görünümü bulunmuyor."),
                lambda: self.txt_icerik.SetFocus(),
                ad="HTML görünüm yok uyarısı",
            )
            return

        if not self.web_gorunum and not self._web_gorunumu_olustur():
            mesaj_soyle_ve_sonra_calistir(
                _("HTML görünümü bu sistemde kullanılamıyor."),
                lambda: self.txt_icerik.SetFocus(),
                ad="HTML görünümü kullanılamıyor uyarısı",
            )
            return

        if self.aktif_gorunum == "html":
            self.aktif_gorunum = "metin"
            self.web_gorunum.Hide()
            self.txt_icerik.Show()
            if hasattr(self, "gecis_btn"):
                self.gecis_btn.SetLabel(_("&HTML Görünümüne Geç (F7)"))
            self.Layout()
            mesaj_soyle_ve_sonra_calistir(
                _("Metin görünümüne geçildi."),
                lambda: self.icerik_baslangicina_odaklan(),
                ad="Metin görünümüne geçiş",
            )
        else:
            self.aktif_gorunum = "html"
            self.txt_icerik.Hide()
            self.web_gorunum.Show()
            if hasattr(self, "gecis_btn"):
                self.gecis_btn.SetLabel(_("&Metin Görünümüne Geç (F7)"))
            self.Layout()
            mesaj_soyle_ve_sonra_calistir(
                _("HTML görünümüne geçildi."),
                lambda: self.web_gorunum.SetFocus(),
                ad="HTML görünümüne geçiş",
            )

    def tus_yakalandi(self, event):
        tus = event.GetKeyCode()
        if tus == wx.WXK_ESCAPE:
            self._kapatildi = True
            self.EndModal(wx.ID_OK)
            return
        if tus == getattr(wx, "WXK_F7", 346):
            self.gorunumu_degistir()
            return
        metin_odakta = self.FindFocus() is self.txt_icerik
        degistirici_yok = not event.ControlDown() and not event.AltDown()
        if metin_odakta and degistirici_yok and tus in (ord("L"), ord("l")):
            self.baglantilar_arasinda_gezin(ileri=not event.ShiftDown())
            return
        if metin_odakta and degistirici_yok and tus in (ord("C"), ord("c")):
            self.uzerindeki_baglantiyi_kopyala()
            return
        if metin_odakta and degistirici_yok and tus in (ord("T"), ord("t")):
            self.uzerindeki_baglantiyi_ac()
            return
        if (
            self.konusma_ileti_konumlari
            and metin_odakta and degistirici_yok
            and tus in (ord("N"), ord("P"), ord("n"), ord("p"))
        ):
            self.konusmada_gezin(ileri=(tus in (ord("N"), ord("n"))))
            return
        event.Skip()

    def _uzerindeki_baglanti_indeksi(self):
        if not self.baglanti_konumlari:
            return None
        try:
            secim_basi, secim_sonu = self.txt_icerik.GetSelection()
            if secim_sonu > secim_basi:
                for indeks, (baslangic, bitis, _adres) in enumerate(self.baglanti_konumlari):
                    if secim_basi < bitis and secim_sonu > baslangic:
                        return indeks
            konum = self.txt_icerik.GetInsertionPoint()
            for indeks, (baslangic, bitis, _adres) in enumerate(self.baglanti_konumlari):
                if baslangic <= konum <= bitis:
                    return indeks
        except Exception as e:
            hata_kaydet("İmlecin üzerindeki bağlantı belirlenemedi.", e)
        return None

    def baglantilar_arasinda_gezin(self, ileri=True):
        """L ve Shift+L ile e-postadaki HTTP bağlantıları arasında dolaşır."""
        if not self.baglanti_konumlari:
            ui.message(_("Bu e-postada bağlantı bulunmuyor."))
            return
        try:
            mevcut_indeks = self._uzerindeki_baglanti_indeksi()
            if mevcut_indeks is not None:
                hedef_indeks = (
                    (mevcut_indeks + 1) % len(self.baglanti_konumlari)
                    if ileri
                    else (mevcut_indeks - 1) % len(self.baglanti_konumlari)
                )
            else:
                konum = self.txt_icerik.GetInsertionPoint()
                if ileri:
                    adaylar = [
                        indeks
                        for indeks, (baslangic, _bitis, _adres) in enumerate(self.baglanti_konumlari)
                        if baslangic > konum
                    ]
                    hedef_indeks = adaylar[0] if adaylar else 0
                else:
                    adaylar = [
                        indeks
                        for indeks, (baslangic, _bitis, _adres) in enumerate(self.baglanti_konumlari)
                        if baslangic < konum
                    ]
                    hedef_indeks = adaylar[-1] if adaylar else len(self.baglanti_konumlari) - 1
            baslangic, bitis, adres = self.baglanti_konumlari[hedef_indeks]
            self.txt_icerik.SetFocus()
            self.txt_icerik.SetInsertionPoint(baslangic)
            self.txt_icerik.SetSelection(baslangic, bitis)
            self.txt_icerik.ShowPosition(baslangic)
            ui.message(
                _('Bağlantı {0} bölü {1}. {2}').format(hedef_indeks + 1, len(self.baglanti_konumlari), adres)
            )
        except Exception as e:
            hata_kaydet("E-postadaki bağlantılar arasında gezinilemedi.", e)
            ui.message(_("Bağlantıya gidilemedi."))

    def _uzerindeki_baglanti(self):
        indeks = self._uzerindeki_baglanti_indeksi()
        if indeks is None:
            ui.message(_("İmlecin bulunduğu yerde bağlantı yok."))
            return ""
        return self.baglanti_konumlari[indeks][2]

    def uzerindeki_baglantiyi_kopyala(self):
        adres = self._uzerindeki_baglanti()
        if not adres:
            return
        try:
            if not wx.TheClipboard.Open():
                raise RuntimeError(_("Pano açılamadı."))
            try:
                veri = wx.TextDataObject(adres)
                if not wx.TheClipboard.SetData(veri):
                    raise RuntimeError(_("Bağlantı panoya yazılamadı."))
                try:
                    wx.TheClipboard.Flush()
                except Exception:
                    pass
            finally:
                wx.TheClipboard.Close()
            ui.message(_("Bağlantı panoya kopyalandı."))
        except Exception as e:
            hata_kaydet("Bağlantı panoya kopyalanamadı.", e)
            ui.message(_("Bağlantı panoya kopyalanamadı."))

    def uzerindeki_baglantiyi_ac(self):
        adres = self._uzerindeki_baglanti()
        if not adres:
            return
        try:
            parcalar = urlsplit(adres)
            if parcalar.scheme.lower() not in ("http", "https") or not parcalar.netloc:
                raise ValueError(_("Geçersiz HTTP bağlantısı."))
            mesaj_soyle_ve_sonra_calistir(
                _("Bağlantı varsayılan tarayıcıda açılıyor."),
                lambda: self._baglantiyi_varsayilan_tarayıcıda_ac(adres),
                ad="E-posta bağlantısını açma",
            )
        except Exception as e:
            hata_kaydet("Bağlantı varsayılan tarayıcıda açılamadı.", e)
            ui.message(_("Bağlantı açılamadı."))

    def _baglantiyi_varsayilan_tarayıcıda_ac(self, adres):
        adres = str(adres or "").strip()
        if not guvenli_baglanti_mi(adres):
            hata_kaydet("Güvenli olmayan bağlantı şeması engellendi.")
            ui.message(_("Bağlantı açılamadı."))
            return
        try:
            ui.message(_("Bağlantı varsayılan tarayıcıda açılıyor."))
            try:
                os.startfile(adres)
            except Exception:
                if not webbrowser.open(adres, new=2):
                    raise RuntimeError(_("Varsayılan tarayıcı açılamadı."))
        except Exception as e:
            hata_kaydet("Bağlantı varsayılan tarayıcıda açılamadı.", e)
            ui.message(_("Bağlantı açılamadı."))

    def konusmada_gezin(self, ileri=True):
        """N ve P ile konuşmadaki sonraki veya önceki e-posta başlığına gider."""
        if not self.konusma_ileti_konumlari:
            return
        try:
            mevcut = self.txt_icerik.GetInsertionPoint()
            if ileri:
                adaylar = [konum for konum in self.konusma_ileti_konumlari if konum > mevcut]
                hedef = adaylar[0] if adaylar else self.konusma_ileti_konumlari[-1]
            else:
                mevcut_indeks = 0
                for indeks, konum in enumerate(self.konusma_ileti_konumlari):
                    if konum <= mevcut:
                        mevcut_indeks = indeks
                    else:
                        break
                hedef = self.konusma_ileti_konumlari[max(0, mevcut_indeks - 1)]
            self.txt_icerik.SetFocus()
            self.txt_icerik.SetSelection(hedef, hedef)
            self.txt_icerik.SetInsertionPoint(hedef)
            self.txt_icerik.ShowPosition(hedef)
        except Exception as e:
            hata_kaydet("Konuşmadaki e-postalar arasında gezinilemedi.", e)

    def ekleri_kaydet(self, event):
        konu = guvenli_dosya_adi(self.mesaj_verisi.get("konu", "Konusuz"), "Konusuz")
        indirilenler = os.path.join(os.path.expanduser("~"), "Downloads")
        varsayilan_klasor = indirilenler if os.path.isdir(indirilenler) else os.path.expanduser("~")
        dlg = wx.DirDialog(
            self,
            _("Eklerin kaydedileceği klasörü seçin:"),
            defaultPath=varsayilan_klasor,
            style=wx.DD_DEFAULT_STYLE | wx.DD_DIR_MUST_EXIST,
        )
        try:
            if dlg.ShowModal() != wx.ID_OK:
                return
            hedef_klasor = os.path.join(dlg.GetPath(), _("E-posta_Ekleri_{0}").format(konu))
            os.makedirs(hedef_klasor, exist_ok=True)
            ekleri_indirici = self.mesaj_verisi.get("ekleri_indirici")
            if (not self.mesaj_verisi.get("ekler") or self.mesaj_verisi.get("ekler_eksik")) and callable(ekleri_indirici):
                ekleri_indirici(self.mesaj_verisi, hedef_klasor)
                ui.message(_("Ekler indiriliyor."))
                return
            kaydedilen = 0
            for dosya_adi, veri in self.mesaj_verisi.get("ekler", []):
                temiz_ad = guvenli_dosya_adi(dosya_adi, "ek_dosya")
                hedef_yol = benzersiz_yol(hedef_klasor, temiz_ad)
                with open(hedef_yol, "wb") as dosya:
                    dosya.write(veri)
                kaydedilen += 1
            if kaydedilen:
                ui.message(_('{0} ek dosya kaydedildi. Klasör: {1}').format(kaydedilen, hedef_klasor))
            else:
                ui.message(_("Kaydedilecek ek dosya bulunamadı."))
        except Exception as e:
            hata_kaydet("Ek dosyalar kaydedilemedi.", e)
            ui.message(_("Ekler kaydedilemedi. Lütfen dosya izinlerini denetleyin."))
        finally:
            try:
                dlg.Destroy()
            except Exception:
                pass

    def mesaji_yanitla(self, event):
        kime = self.mesaj_verisi.get("yanit_adresi") or self.mesaj_verisi.get("kimden_adres", "")
        konu = self.mesaj_verisi.get("konu", "")
        if not konu.lower().startswith("re:"):
            konu = "Re: " + konu
        # Konuşmada yanıt her zaman en son iletiye verilir.
        asil_icerik = self.mesaj_verisi.get("son_icerik", self.mesaj_verisi.get("icerik", ""))
        icerik = _('\n\n\n--- Orijinal E-posta ---\n{0}').format(asil_icerik)
        pencere = YeniPostaPenceresi(
            self,
            varsayilan_kime=kime,
            varsayilan_konu=konu,
            varsayilan_icerik=icerik,
            yanit_basliklari=yanit_basliklari_hazirla(self.mesaj_verisi),
            taslak_kaydet_callback=lambda: self.ebeveyn.taslak_kaydedildi(),
            taslak_otokayit_sil_callback=lambda kimlik, klasor: self.ebeveyn.taslak_gonderildi(kimlik.get("uid"), klasor, kimlik),
            taslak_klasor_adaylari=self.ebeveyn.taslak_klasor_adaylari(),
        )
        hedef_odak = self.web_gorunum if (self.aktif_gorunum == "html" and self.web_gorunum) else self.txt_icerik
        guvenli_modal_goster(pencere, hedef_odak, self)

    def mesaji_ilet(self, event):
        # Use the opened message's identity, never the main list's current selection.
        mail_id = self.mesaj_verisi.get("id")
        klasor = self.mesaj_verisi.get("klasor")
        if not mail_id or not klasor:
            ui.message(_("İletilecek e-postanın kimliği bulunamadı."))
            return
        arka_planda_calistir(self.ebeveyn.sunucudan_yanit_veya_ilet_hazirla, mail_id, klasor, "ilet")
        ui.message(_("İletilecek e-posta hazırlanıyor."))

    def mesaji_arsivle_ve_kapat(self, event):
        self._kapatildi = True
        uidler = self.mesaj_verisi.get("ids") or [self.mesaj_verisi["id"]]
        self.EndModal(wx.ID_OK)
        guvenli_call_after(
            self.ebeveyn,
            self.ebeveyn.arsiv_secim_goster,
            uidler,
            self.mesaj_verisi.get("klasor"),
        )

    def mesaji_sil_ve_kapat(self, event):
        uidler = self.mesaj_verisi.get("ids") or [self.mesaj_verisi["id"]]
        if self.ebeveyn.konusma_sil(
            uidler,
            self.mesaj_verisi.get("klasor"),
            self.mesaj_verisi.get("konu"),
        ):
            self._kapatildi = True
            self.EndModal(wx.ID_OK)
