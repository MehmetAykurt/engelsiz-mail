# -*- coding: utf-8 -*-
# Engelsiz Mail - E-posta okuma penceresi

import os
import re
import webbrowser
from urllib.parse import urlsplit

import wx
import ui

from ..attachments import benzersiz_yol
from ..logger import hata_kaydet
from ..message_center import mesaj_soyle_ve_sonra_calistir
from ..message_parser import ad_ve_adresi_goster, yanit_basliklari_hazirla
from ..text_utils import (
    duz_metni_ekran_okuyucu_icin_temizle,
    guvenli_dosya_adi,
    http_baglantilarini_bul,
    konu_gosterimini_duzenle,
)
from ..ui_helpers import guvenli_call_after, guvenli_modal_goster, gorunum_denetime_uygula
from .compose_window import YeniPostaPenceresi


class MesajOkumaPenceresi(wx.Dialog):
    def __init__(self, parent, mesaj_verisi, ebeveyn_pencere):
        super().__init__(parent, title="E-posta")
        self.mesaj_verisi = mesaj_verisi
        self.ebeveyn = ebeveyn_pencere
        self._kapatildi = False
        self.Bind(wx.EVT_WINDOW_DESTROY, self._pencere_yok_ediliyor)
        self.Bind(wx.EVT_CHAR_HOOK, self.tus_yakalandi)

        duzen = wx.BoxSizer(wx.VERTICAL)
        ek_sayisi = len(mesaj_verisi.get("ekler", []))
        ek_notu = f"\nBu e-postada {ek_sayisi} ek dosya var.\n" if ek_sayisi else ""
        if mesaj_verisi.get("ekler_eksik"):
            ek_notu += "Bazı ekler çevrimdışı önbellekte bulunmuyor.\n"
        kime_satiri = f"Kime: {mesaj_verisi.get('kime', '')}\n" if mesaj_verisi.get("kime") else ""
        bilgi_satiri = f"Bilgi: {mesaj_verisi.get('bilgi', '')}\n" if mesaj_verisi.get("bilgi") else ""
        kimden_gosterimi = ad_ve_adresi_goster(
            mesaj_verisi.get("kimden_tam", ""),
            mesaj_verisi.get("kimden_adres", ""),
            "Bilinmiyor",
        )
        ust_bilgi = (
            f"Kimden: {kimden_gosterimi}\n"
            f"{kime_satiri}"
            f"{bilgi_satiri}"
            f"Tarih: {mesaj_verisi.get('tarih', '')}\n"
            f"Konu: {konu_gosterimini_duzenle(mesaj_verisi.get('konu', ''))}\n"
            f"{ek_notu}{'-' * 50}\n\n"
        )
        mesaj_icerigi = duz_metni_ekran_okuyucu_icin_temizle(
            mesaj_verisi.get('icerik', '')
        )
        icerik = ust_bilgi + mesaj_icerigi
        self.icerik_baslangic_indeksi = len(ust_bilgi)
        self.txt_icerik = wx.TextCtrl(self, value=icerik, style=wx.TE_MULTILINE | wx.TE_READONLY | wx.TE_RICH2)
        denetim_icerigi = self.txt_icerik.GetValue()
        self.baglanti_konumlari = http_baglantilarini_bul(denetim_icerigi)
        self.konusma_ileti_konumlari = (
            [
                eslesme.start()
                for eslesme in re.finditer(
                    r"(?m)^\d+\. ileti\r?\nKimden:", denetim_icerigi
                )
            ]
            if mesaj_verisi.get("konusma_mi") else []
        )
        if self.konusma_ileti_konumlari:
            self.icerik_baslangic_indeksi = self.konusma_ileti_konumlari[0]
        self.txt_icerik.SetName("E-posta içeriği")
        duzen.Add(self.txt_icerik, 1, wx.ALL | wx.EXPAND, 10)
        gorunum_denetime_uygula(self.txt_icerik)

        btn_duzen = wx.BoxSizer(wx.HORIZONTAL)
        if ek_sayisi:
            ek_btn = wx.Button(self, label=f"&Ekleri Kaydet ({ek_sayisi})")
            ek_btn.Bind(wx.EVT_BUTTON, self.ekleri_kaydet)
            btn_duzen.Add(ek_btn, 0, wx.ALL, 5)

        yanitla_btn = wx.Button(self, label="&Yanıtla")
        yanitla_btn.Bind(wx.EVT_BUTTON, self.mesaji_yanitla)
        btn_duzen.Add(yanitla_btn, 0, wx.ALL, 5)

        ilet_btn = wx.Button(self, label="İ&let")
        ilet_btn.Bind(wx.EVT_BUTTON, self.mesaji_ilet)
        btn_duzen.Add(ilet_btn, 0, wx.ALL, 5)

        arsiv_btn = wx.Button(self, label="A&rşivle")
        arsiv_btn.Bind(wx.EVT_BUTTON, self.mesaji_arsivle_ve_kapat)
        btn_duzen.Add(arsiv_btn, 0, wx.ALL, 5)

        sil_btn = wx.Button(self, label="&Sil")
        sil_btn.Bind(wx.EVT_BUTTON, self.mesaji_sil_ve_kapat)
        btn_duzen.Add(sil_btn, 0, wx.ALL, 5)

        kapat_btn = wx.Button(self, label="&Kapat")
        kapat_btn.Bind(wx.EVT_BUTTON, lambda event: self.EndModal(wx.ID_OK))
        btn_duzen.Add(kapat_btn, 0, wx.ALL, 5)

        duzen.Add(btn_duzen, 0, wx.CENTER | wx.BOTTOM, 10)
        self.SetSizer(duzen)
        self.SetSize((860, 660))
        self.CenterOnParent()
        wx.CallAfter(self.icerik_baslangicina_odaklan)

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

    def _pencere_yok_ediliyor(self, event):
        if event.GetEventObject() is self:
            self._kapatildi = True
        event.Skip()

    def tus_yakalandi(self, event):
        tus = event.GetKeyCode()
        if tus == wx.WXK_ESCAPE:
            self.EndModal(wx.ID_OK)
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
            ui.message("Bu e-postada bağlantı bulunmuyor.")
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
                f"Bağlantı {hedef_indeks + 1} bölü {len(self.baglanti_konumlari)}. {adres}"
            )
        except Exception as e:
            hata_kaydet("E-postadaki bağlantılar arasında gezinilemedi.", e)
            ui.message("Bağlantıya gidilemedi.")

    def _uzerindeki_baglanti(self):
        indeks = self._uzerindeki_baglanti_indeksi()
        if indeks is None:
            ui.message("İmlecin bulunduğu yerde bağlantı yok.")
            return ""
        return self.baglanti_konumlari[indeks][2]

    def uzerindeki_baglantiyi_kopyala(self):
        adres = self._uzerindeki_baglanti()
        if not adres:
            return
        try:
            if not wx.TheClipboard.Open():
                raise RuntimeError("Pano açılamadı.")
            try:
                veri = wx.TextDataObject(adres)
                if not wx.TheClipboard.SetData(veri):
                    raise RuntimeError("Bağlantı panoya yazılamadı.")
                try:
                    wx.TheClipboard.Flush()
                except Exception:
                    pass
            finally:
                wx.TheClipboard.Close()
            ui.message("Bağlantı panoya kopyalandı.")
        except Exception as e:
            hata_kaydet("Bağlantı panoya kopyalanamadı.", e)
            ui.message("Bağlantı panoya kopyalanamadı.")

    def uzerindeki_baglantiyi_ac(self):
        adres = self._uzerindeki_baglanti()
        if not adres:
            return
        try:
            parcalar = urlsplit(adres)
            if parcalar.scheme.lower() not in ("http", "https") or not parcalar.netloc:
                raise ValueError("Geçersiz HTTP bağlantısı.")
            mesaj_soyle_ve_sonra_calistir(
                "Bağlantı varsayılan tarayıcıda açılıyor.",
                lambda: self._baglantiyi_varsayilan_tarayıcıda_ac(adres),
                ad="E-posta bağlantısını açma",
            )
        except Exception as e:
            hata_kaydet("Bağlantı varsayılan tarayıcıda açılamadı.", e)
            ui.message("Bağlantı açılamadı.")

    def _baglantiyi_varsayilan_tarayıcıda_ac(self, adres):
        try:
            try:
                os.startfile(adres)
            except Exception:
                if not webbrowser.open(adres, new=2):
                    raise RuntimeError("Varsayılan tarayıcı açılamadı.")
        except Exception as e:
            hata_kaydet("Bağlantı varsayılan tarayıcıda açılamadı.", e)
            ui.message("Bağlantı açılamadı.")

    def konusmada_gezin(self, ileri=True):
        """N ve P ile konuşmadaki sonraki veya önceki ileti başlığına gider."""
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
            hata_kaydet("Konuşmadaki iletiler arasında gezinilemedi.", e)

    def ekleri_kaydet(self, event):
        konu = guvenli_dosya_adi(self.mesaj_verisi.get("konu", "Konusuz"), "Konusuz")
        indirilenler = os.path.join(os.path.expanduser("~"), "Downloads")
        varsayilan_klasor = indirilenler if os.path.isdir(indirilenler) else os.path.expanduser("~")
        dlg = wx.DirDialog(
            self,
            "Eklerin kaydedileceği klasörü seçin:",
            defaultPath=varsayilan_klasor,
            style=wx.DD_DEFAULT_STYLE | wx.DD_DIR_MUST_EXIST,
        )
        try:
            if dlg.ShowModal() != wx.ID_OK:
                return
            hedef_klasor = os.path.join(dlg.GetPath(), f"E-posta_Ekleri_{konu}")
            os.makedirs(hedef_klasor, exist_ok=True)
            kaydedilen = 0
            for dosya_adi, veri in self.mesaj_verisi.get("ekler", []):
                if not veri:
                    continue
                temiz_ad = guvenli_dosya_adi(dosya_adi, "ek_dosya")
                hedef_yol = benzersiz_yol(hedef_klasor, temiz_ad)
                with open(hedef_yol, "wb") as dosya:
                    dosya.write(veri)
                kaydedilen += 1
            if kaydedilen:
                ui.message(f"{kaydedilen} ek dosya kaydedildi. Klasör: {hedef_klasor}")
            else:
                ui.message("Kaydedilecek ek dosya bulunamadı.")
        except Exception as e:
            hata_kaydet("Ek dosyalar kaydedilemedi.", e)
            ui.message("Ekler kaydedilemedi. Lütfen dosya izinlerini kontrol edin.")
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
        icerik = f"\n\n\n--- Orijinal E-posta ---\n{asil_icerik}"
        pencere = YeniPostaPenceresi(
            self,
            varsayilan_kime=kime,
            varsayilan_konu=konu,
            varsayilan_icerik=icerik,
            yanit_basliklari=yanit_basliklari_hazirla(self.mesaj_verisi),
            taslak_kaydet_callback=lambda: self.ebeveyn.taslak_kaydedildi(),
            taslak_klasor_adaylari=self.ebeveyn.taslak_klasor_adaylari(),
        )
        guvenli_modal_goster(pencere, self.txt_icerik, self)

    def mesaji_ilet(self, event):
        konu = self.mesaj_verisi.get("konu", "")
        if not konu.lower().startswith("fwd:"):
            konu = "Fwd: " + konu
        icerik = f"\n\n\n--- İletilen E-posta ---\n{self.mesaj_verisi.get('icerik', '')}"
        pencere = YeniPostaPenceresi(
            self,
            varsayilan_kime="",
            varsayilan_konu=konu,
            varsayilan_icerik=icerik,
            taslak_kaydet_callback=lambda: self.ebeveyn.taslak_kaydedildi(),
            taslak_klasor_adaylari=self.ebeveyn.taslak_klasor_adaylari(),
            hazir_ekler=self.mesaj_verisi.get("ekler", []),
        )
        guvenli_modal_goster(pencere, self.txt_icerik, self)

    def mesaji_arsivle_ve_kapat(self, event):
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
            self.EndModal(wx.ID_OK)
