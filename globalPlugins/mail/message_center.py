# -*- coding: utf-8 -*-
"""Engelsiz Mail mesaj merkezi.

Bu modül, NVDA'nın kısa mesajları yutmasını önlemek için konuşma tamamlandıktan
sonra işlem çalıştırma yardımcısını içerir.
"""

import wx
import speech
from speech.commands import CallbackCommand

from .logger import hata_kaydet


VARSAYILAN_MESAJ_ONCESI_BEKLEME_MS = 150
VARSAYILAN_CALLBACK_BEKLEME_MS = 150
VARSAYILAN_GUVENCE_BEKLEME_MS = 8000


def _bekleme_degerini_duzenle(bekleme_ms):
    try:
        bekleme_ms = int(bekleme_ms)
    except Exception:
        bekleme_ms = VARSAYILAN_CALLBACK_BEKLEME_MS
    if bekleme_ms < 0:
        return 0
    return bekleme_ms


def _callback_guvenli_calistir(callback):
    try:
        callback()
    except Exception as hata:
        hata_kaydet("Mesaj sonrası işlem çalıştırılamadı.", hata)


def _callback_sonrasi_calistir(callback, bekleme_ms):
    bekleme_ms = _bekleme_degerini_duzenle(bekleme_ms)

    def zamanlayiciyi_baslat():
        wx.CallLater(bekleme_ms, lambda: _callback_guvenli_calistir(callback))

    wx.CallAfter(zamanlayiciyi_baslat)


def mesaj_soyle_ve_sonra_calistir(
    mesaj,
    callback,
    ad="Engelsiz Mail işlem",
    mesaj_oncesi_bekleme_ms=VARSAYILAN_MESAJ_ONCESI_BEKLEME_MS,
    bekleme_ms=VARSAYILAN_CALLBACK_BEKLEME_MS,
    guvence_bekleme_ms=VARSAYILAN_GUVENCE_BEKLEME_MS,
):
    """Mesaj konuşması bittikten sonra callback çalıştırır.

    Bu yardımcı, mesajdan hemen sonra pencere/klasör/dosya/tarayıcı açma gibi
    odak değiştiren işlemler yapılacaksa kullanılır. İşlem, NVDA konuşması
    başlamadan önce 150 ms, tamamlandıktan sonra da varsayılan olarak 150 ms
    rahatlama payından sonra
    başlatılır.
    """
    durum = {"calistirildi": False, "zamanlayici": None}

    def yalniz_bir_kez_calistir():
        if durum["calistirildi"]:
            return
        durum["calistirildi"] = True
        zamanlayici = durum.get("zamanlayici")
        if zamanlayici:
            try:
                zamanlayici.Stop()
            except Exception:
                pass
        _callback_guvenli_calistir(callback)

    def guvenceyi_baslat():
        if durum["calistirildi"]:
            return
        guvence_ms = _bekleme_degerini_duzenle(guvence_bekleme_ms)
        durum["zamanlayici"] = wx.CallLater(guvence_ms, yalniz_bir_kez_calistir)

    def konusmayi_baslat():
        try:
            speech.speak(
                [
                    mesaj,
                    CallbackCommand(
                        name=ad,
                        callback=lambda: _callback_sonrasi_calistir(
                            yalniz_bir_kez_calistir,
                            bekleme_ms,
                        ),
                    ),
                ],
                priority=speech.Spri.NOW,
            )
        except Exception as hata:
            hata_kaydet("Mesaj konuşması başlatılamadı; işlem güvence zamanlayıcısına bırakıldı.", hata)

    def konusma_zamanlayicisini_baslat():
        wx.CallLater(
            _bekleme_degerini_duzenle(mesaj_oncesi_bekleme_ms),
            konusmayi_baslat,
        )

    wx.CallAfter(guvenceyi_baslat)
    wx.CallAfter(konusma_zamanlayicisini_baslat)
