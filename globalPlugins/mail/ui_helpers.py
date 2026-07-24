# -*- coding: utf-8 -*-
"""Engelsiz Mail arayüz yardımcıları."""

import threading
import time
from dataclasses import dataclass

import wx

from .config import (
    GORUNUM_YAZI_TIPI_ALANI,
    GORUNUM_YAZI_BOYUTU_ALANI,
    GORUNUM_YAZI_STILI_ALANI,
    GORUNUM_METIN_RENGI_ALANI,
    GORUNUM_ARKA_PLAN_RENGI_ALANI,
    GORUNUM_SISTEM_RENKLERI_ALANI,
    GORUNUM_YAZI_STILI_SECENEKLERI,
    GORUNUM_METIN_RENKLERI,
    GORUNUM_ARKA_PLAN_RENKLERI,
    gorunum_ayarlari_yukle,
)
from .logger import hata_kaydet


_ARKA_PLAN_THREAD_KILIDI = threading.RLock()
_ARKA_PLAN_THREADLERI = set()


@dataclass(frozen=True)
class ArkaPlanGorevJetonu:
    """Bir pencereye ait arka plan görevinin kimliği ve değişmez girdileri."""

    sahip: object
    anahtar: str
    nesil: int
    baglam: object = None


def arka_plan_gorev_jetonu_olustur(pencere, anahtar, baglam=None):
    """Aynı anahtardaki eski görevi geçersiz kılan yeni bir görev jetonu üretir."""
    anahtar = str(anahtar or "varsayilan")
    kilit = getattr(pencere, "_arka_plan_gorev_kilidi", None)
    if kilit is None:
        kilit = threading.RLock()
        setattr(pencere, "_arka_plan_gorev_kilidi", kilit)
    with kilit:
        nesiller = getattr(pencere, "_arka_plan_gorev_nesilleri", None)
        if not isinstance(nesiller, dict):
            nesiller = {}
            setattr(pencere, "_arka_plan_gorev_nesilleri", nesiller)
        nesil = int(nesiller.get(anahtar, 0)) + 1
        nesiller[anahtar] = nesil
    return ArkaPlanGorevJetonu(pencere, anahtar, nesil, baglam)


def arka_plan_gorevi_gecerli_mi(jeton):
    """Görev hâlâ en yeniyse ve sahibi kapanmadıysa True döndürür."""
    if not isinstance(jeton, ArkaPlanGorevJetonu):
        return False
    pencere = jeton.sahip
    if not pencere_kullanilabilir_mi(pencere):
        return False
    baglam = jeton.baglam
    if isinstance(baglam, dict) and "kategori" in baglam:
        mevcut_kategori = str(getattr(pencere, "secili_kategori", "") or "")
        if mevcut_kategori != str(baglam.get("kategori", "") or ""):
            return False
    kilit = getattr(pencere, "_arka_plan_gorev_kilidi", None)
    nesiller = getattr(pencere, "_arka_plan_gorev_nesilleri", {})
    if kilit is None:
        return int(nesiller.get(jeton.anahtar, 0)) == jeton.nesil
    with kilit:
        return int(nesiller.get(jeton.anahtar, 0)) == jeton.nesil


def arka_plan_gorevlerini_gecersiz_kil(pencere):
    """Pencere kapanırken bekleyen bütün görev geri dönüşlerini geçersiz kılar."""
    kilit = getattr(pencere, "_arka_plan_gorev_kilidi", None)
    if kilit is None:
        return
    with kilit:
        nesiller = getattr(pencere, "_arka_plan_gorev_nesilleri", {})
        for anahtar in list(nesiller):
            nesiller[anahtar] = int(nesiller[anahtar]) + 1


def gorev_icin_guvenli_call_after(jeton, islev, *args, **kwargs):
    """Yalnızca jeton güncelse arayüz geri dönüşünü çalıştırır."""
    def calistir():
        if not arka_plan_gorevi_gecerli_mi(jeton):
            return
        try:
            islev(*args, **kwargs)
        except Exception as e:
            hata_kaydet("Arka plan görevi arayüz güncellemesi yapılamadı.", e)

    wx.CallAfter(calistir)


def gorev_veya_pencere_icin_call_after(pencere, jeton, islev, *args, **kwargs):
    """Jetonlu yeni çağrılarla eski doğrudan çağrıları güvenli biçimde destekler."""
    if isinstance(jeton, ArkaPlanGorevJetonu):
        gorev_icin_guvenli_call_after(jeton, islev, *args, **kwargs)
    else:
        guvenli_call_after(pencere, islev, *args, **kwargs)


def pencere_kullanilabilir_mi(pencere):
    """Kapanmış veya yok edilmekte olan wx pencerelerine geri dönüşü engeller."""
    try:
        if pencere is None:
            return False
        if getattr(pencere, "_kapatildi", False):
            return False
        if hasattr(pencere, "IsBeingDeleted") and pencere.IsBeingDeleted():
            return False
        return True
    except Exception:
        return False


def guvenli_call_after(pencere, islev, *args, **kwargs):
    """Arka plan işlemlerinden arayüze güvenli dönüş yapar."""
    def calistir():
        if not pencere_kullanilabilir_mi(pencere):
            return
        try:
            islev(*args, **kwargs)
        except Exception as e:
            hata_kaydet("Arayüz güncellemesi yapılamadı.", e)

    wx.CallAfter(calistir)


def guvenli_modal_goster(pencere, odak_denetcimi=None, ebeveyn=None):
    """Modal pencereyi gösterir; kapatılırken odağı pencere yok edilmeden hedef denetime döndürür."""
    sonuc = wx.ID_CANCEL
    try:
        sonuc = pencere.ShowModal()
        if odak_denetcimi is not None:
            try:
                hedef_pencere = ebeveyn if ebeveyn is not None else odak_denetcimi
                if pencere_kullanilabilir_mi(hedef_pencere):
                    try:
                        hedef_pencere.Raise()
                    except Exception:
                        pass
                    try:
                        odak_denetcimi.SetFocus()
                    except Exception as e:
                        hata_kaydet("Modal pencere sonrası odak denetime verilemedi.", e)
            except Exception as e:
                hata_kaydet("Modal pencere sonrası odak dönüşü yapılamadı.", e)
        return sonuc
    finally:
        try:
            pencere.Destroy()
        except Exception as e:
            hata_kaydet("Modal pencere yok edilemedi.", e)


def odagi_listeye_guvenli_dondur(pencere, denetim):
    """Dialog kapanışlarından sonra odağı ana listeye güvenli biçimde döndürür."""
    def odaklan():
        try:
            if pencere_kullanilabilir_mi(pencere):
                try:
                    pencere.Raise()
                except Exception:
                    pass
            if pencere_kullanilabilir_mi(denetim):
                denetim.SetFocus()
        except Exception as e:
            hata_kaydet("Odağın listeye dönmesi sağlanamadı.", e)

    try:
        wx.CallAfter(odaklan)
    except Exception as e:
        hata_kaydet("Odak dönüşü planlanamadı.", e)


def arka_planda_calistir(hedef, *args):
    def calistir():
        try:
            hedef(*args)
        except Exception as e:
            hata_kaydet("Arka plan görevi beklenmeyen bir hatayla sonlandı.", e)
        finally:
            with _ARKA_PLAN_THREAD_KILIDI:
                _ARKA_PLAN_THREADLERI.discard(threading.current_thread())

    thread = threading.Thread(target=calistir, daemon=True)
    with _ARKA_PLAN_THREAD_KILIDI:
        _ARKA_PLAN_THREADLERI.add(thread)
    try:
        thread.start()
    except Exception:
        with _ARKA_PLAN_THREAD_KILIDI:
            _ARKA_PLAN_THREADLERI.discard(thread)
        raise
    return thread


def arka_plan_gorevlerinin_bitmesini_bekle(zaman_asimi=0.5):
    """NVDA kapanırken çalışan görevler için toplam süreyle sınırlı bekleme yapar."""
    son = time.monotonic() + max(0.0, float(zaman_asimi or 0.0))
    mevcut = threading.current_thread()
    with _ARKA_PLAN_THREAD_KILIDI:
        threadler = [thread for thread in _ARKA_PLAN_THREADLERI if thread is not mevcut]
    for thread in threadler:
        kalan = son - time.monotonic()
        if kalan <= 0:
            break
        try:
            thread.join(kalan)
        except RuntimeError:
            continue


def gorunum_fontu_olustur(mevcut_font=None):
    """Görünüm ayarlarına göre wx.Font üretir. Ayar yoksa mevcut font korunur."""
    try:
        ayarlar = gorunum_ayarlari_yukle()
        yazi_tipi = ayarlar.get(GORUNUM_YAZI_TIPI_ALANI, "")
        yazi_boyutu = ayarlar.get(GORUNUM_YAZI_BOYUTU_ALANI, 0)
        yazi_stili = ayarlar.get(GORUNUM_YAZI_STILI_ALANI, "")

        temel_font = mevcut_font
        if temel_font is None or not temel_font.IsOk():
            temel_font = wx.SystemSettings.GetFont(wx.SYS_DEFAULT_GUI_FONT)

        nokta = yazi_boyutu or temel_font.GetPointSize()
        if not nokta or nokta <= 0:
            nokta = 10

        yuz = yazi_tipi or temel_font.GetFaceName()
        stil = temel_font.GetStyle()
        agirlik = temel_font.GetWeight()
        if yazi_stili in GORUNUM_YAZI_STILI_SECENEKLERI:
            stil, agirlik = GORUNUM_YAZI_STILI_SECENEKLERI[yazi_stili]

        font = wx.Font(
            int(nokta),
            wx.FONTFAMILY_DEFAULT,
            stil,
            agirlik,
            temel_font.GetUnderlined(),
            yuz,
        )
        if font.IsOk():
            return font
    except Exception as e:
        hata_kaydet("Görünüm fontu oluşturulamadı.", e)
    return mevcut_font


def gorunum_rengi_olustur(renk_adi, renkler, varsayilan_sistem_rengi):
    """Hazır renk adını wx.Colour nesnesine çevirir; boşsa sistem rengini döndürür."""
    try:
        if renk_adi in renkler:
            return wx.Colour(*renkler[renk_adi])
        return wx.SystemSettings.GetColour(varsayilan_sistem_rengi)
    except Exception as e:
        hata_kaydet("Görünüm rengi oluşturulamadı.", e)
        return wx.NullColour


def gorunum_renkleri_al():
    """Metin ve arka plan renklerini döndürür."""
    ayarlar = gorunum_ayarlari_yukle()
    if ayarlar.get(GORUNUM_SISTEM_RENKLERI_ALANI, False):
        return (
            wx.SystemSettings.GetColour(wx.SYS_COLOUR_WINDOWTEXT),
            wx.SystemSettings.GetColour(wx.SYS_COLOUR_WINDOW),
        )
    metin_rengi = gorunum_rengi_olustur(
        ayarlar.get(GORUNUM_METIN_RENGI_ALANI, ""),
        GORUNUM_METIN_RENKLERI,
        wx.SYS_COLOUR_WINDOWTEXT,
    )
    arka_plan_rengi = gorunum_rengi_olustur(
        ayarlar.get(GORUNUM_ARKA_PLAN_RENGI_ALANI, ""),
        GORUNUM_ARKA_PLAN_RENKLERI,
        wx.SYS_COLOUR_WINDOW,
    )
    return metin_rengi, arka_plan_rengi


def gorunum_denetime_uygula(denetim):
    """Tek bir wx denetimine kullanıcı görünüm ayarını uygular."""
    try:
        if denetim is None:
            return
        font = gorunum_fontu_olustur(denetim.GetFont())
        if font and font.IsOk():
            denetim.SetFont(font)

        metin_rengi, arka_plan_rengi = gorunum_renkleri_al()
        if metin_rengi and metin_rengi.IsOk():
            try:
                if hasattr(denetim, "SetTextColour"):
                    denetim.SetTextColour(metin_rengi)
                else:
                    denetim.SetForegroundColour(metin_rengi)
            except Exception:
                try:
                    denetim.SetForegroundColour(metin_rengi)
                except Exception:
                    pass
        if arka_plan_rengi and arka_plan_rengi.IsOk():
            try:
                denetim.SetBackgroundColour(arka_plan_rengi)
            except Exception:
                pass
        try:
            denetim.Refresh()
        except Exception:
            pass
    except Exception as e:
        hata_kaydet("Görünüm ayarı denetime uygulanamadı.", e)


def gorunum_denetimlerine_uygula(*denetimler):
    """Birden fazla denetime görünüm ayarını güvenli biçimde uygular."""
    for denetim in denetimler:
        gorunum_denetime_uygula(denetim)
