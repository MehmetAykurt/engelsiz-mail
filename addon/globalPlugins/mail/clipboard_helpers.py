# -*- coding: utf-8 -*-
"""Engelsiz Mail - Pano (clipboard) okuma yardımcıları."""

import io
import os

try:
    import addonHandler
    addonHandler.initTranslation()
except (ImportError, AttributeError):
    _ = lambda metin: metin

try:
    import wx
except ImportError:
    wx = None

from .logger import hata_kaydet

RESIM_UZANTILARI = {".png", ".jpg", ".jpeg", ".gif", ".bmp", ".webp"}
# Gönderilecek eklerin toplam sınırıyla aynıdır (attachments.AZAMI_TOPLAM_EK_BOYUTU).
AZAMI_RESIM_BOYUTU = 10 * 1024 * 1024


class ResimCokBuyukHatasi(Exception):
    """Panodaki resim, e-postaya eklenebilecek en büyük boyutu aşıyor."""


def panodan_resim_al():
    """Panoda resim (bitmap veya resim dosyası) varsa (bayt_verisi, uzanti, aday_ad) döndürür; yoksa None."""
    if not wx:
        return None

    try:
        if not wx.TheClipboard.Open():
            return None
    except Exception:
        return None

    try:
        # 1. Pano üzerinde doğrudan bitmap var mı? (Ekran alıntısı, web'den resmi kopyala, Paint vb.)
        bmp_obj = wx.BitmapDataObject()
        if wx.TheClipboard.GetData(bmp_obj):
            bitmap = bmp_obj.GetBitmap()
            if bitmap.IsOk() and bitmap.GetWidth() > 0 and bitmap.GetHeight() > 0:
                img = bitmap.ConvertToImage()
                stream = io.BytesIO()
                img.SaveFile(stream, wx.BITMAP_TYPE_PNG)
                baytlar = stream.getvalue()
                if len(baytlar) > AZAMI_RESIM_BOYUTU:
                    raise ResimCokBuyukHatasi()
                if baytlar:
                    return baytlar, "png", _("Resim")

        # 2. Pano üzerinde kopyalanmış dosya listesi var mı? (Dosya Gezgini'nde kopyalanan resimler)
        file_obj = wx.FileDataObject()
        if wx.TheClipboard.GetData(file_obj):
            dosyalar = file_obj.GetFilenames()
            for dosya_yolu in dosyalar:
                uzanti = os.path.splitext(dosya_yolu)[1].lower()
                if uzanti in RESIM_UZANTILARI and os.path.isfile(dosya_yolu):
                    # Boyut, dosya belleğe okunmadan önce denetlenir.
                    try:
                        cok_buyuk = os.path.getsize(dosya_yolu) > AZAMI_RESIM_BOYUTU
                    except OSError:
                        cok_buyuk = False
                    if cok_buyuk:
                        raise ResimCokBuyukHatasi()
                    try:
                        with open(dosya_yolu, "rb") as f:
                            baytlar = f.read()
                        if baytlar:
                            aday_ad = os.path.splitext(os.path.basename(dosya_yolu))[0]
                            temiz_uzanti = uzanti.lstrip(".")
                            if temiz_uzanti == "jpg":
                                temiz_uzanti = "jpeg"
                            return baytlar, temiz_uzanti, aday_ad
                    except Exception as e:
                        hata_kaydet(f"Kopyalanan resim dosyası okunamadı: {dosya_yolu}", e)

        return None
    except ResimCokBuyukHatasi:
        raise
    except Exception as e:
        hata_kaydet("Panodan resim okunamadı.", e)
        return None
    finally:
        try:
            wx.TheClipboard.Close()
        except Exception:
            pass


def tsv_metnini_tabloya_donustur(metin):
    """Sekmelerle ayrılmış Excel/web metnini [Tablo Başlangıcı] ... [Tablo Bitişi] şablonuna çevirir."""
    if not metin or "\t" not in metin:
        return ""
    satirlar = [s.strip() for s in str(metin).replace("\r\n", "\n").replace("\r", "\n").split("\n")]
    satirlar = [s for s in satirlar if s]
    if len(satirlar) < 1:
        return ""
    if not any("\t" in s for s in satirlar):
        return ""

    sonuc = ["[Tablo Başlangıcı]"]
    for satir in satirlar:
        hucreler = [h.strip() for h in satir.split("\t")]
        sonuc.append("| " + " | ".join(hucreler) + " |")
    sonuc.append("[Tablo Bitişi]")
    return "\n".join(sonuc)


def panodan_tablo_al():
    """Panoda sekmeli tablo verisi varsa tablo metnini döndürür; yoksa boş dize."""
    if not wx:
        return ""
    try:
        if not wx.TheClipboard.Open():
            return ""
    except Exception:
        return ""
    try:
        text_obj = wx.TextDataObject()
        if wx.TheClipboard.GetData(text_obj):
            ham_metin = text_obj.GetText()
            return tsv_metnini_tabloya_donustur(ham_metin)
        return ""
    except Exception as e:
        hata_kaydet("Panodan tablo metni okunamadı.", e)
        return ""
    finally:
        try:
            wx.TheClipboard.Close()
        except Exception:
            pass

