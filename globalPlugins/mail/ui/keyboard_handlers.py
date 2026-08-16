# -*- coding: utf-8 -*-
# Engelsiz Mail - klavye ve liste olayları yardımcıları


# NVDA eklenti çevirilerini bu modül için etkinleştir.
try:
    import addonHandler
    addonHandler.initTranslation()
except (ImportError, AttributeError):
    # NVDA dışındaki otomatik testlerde Türkçe kaynak metni aynen kullan.
    _ = lambda metin: metin

import ui
import wx

from .folder_view import LISTE_MODU_EPOSTA, LISTE_MODU_KLASOR
from ..config import escape_kapat_ayari_yukle


def ana_pencere_tus_yakalandi(pencere, event):
    """Ana penceredeki Enter/Escape tuş davranışlarını güvenli biçimde yönetir."""
    tus = event.GetKeyCode()
    try:
        odak = wx.Window.FindFocus()
    except Exception:
        odak = None

    if odak is not pencere.liste:
        event.Skip()
        return

    if tus == wx.WXK_ESCAPE:
        if getattr(pencere, "liste_modu", LISTE_MODU_KLASOR) == LISTE_MODU_EPOSTA:
            pencere.klasor_gorunumunu_goster(pencere.secili_kategori, odak_ver=True)
            return
        if escape_kapat_ayari_yukle():
            pencere.pencereyi_kapat()
            return

    if tus in (wx.WXK_RETURN, wx.WXK_NUMPAD_ENTER) and getattr(pencere, "liste_modu", LISTE_MODU_KLASOR) == LISTE_MODU_KLASOR:
        pencere.secili_klasoru_ac()
        return
    event.Skip()


def liste_ogesi_odaklandi(pencere, event):
    if getattr(pencere, "liste_modu", LISTE_MODU_KLASOR) == LISTE_MODU_KLASOR:
        pencere.klasor_secimini_odaktan_guncelle()
    event.Skip()


def liste_ogesi_aktiflestirildi(pencere, event):
    if getattr(pencere, "liste_modu", LISTE_MODU_KLASOR) == LISTE_MODU_KLASOR:
        pencere.secili_klasoru_ac()
        return
    pencere.mesaj_oku(event)


def tusa_basildi(pencere, event):
    tus = event.GetKeyCode()
    if getattr(pencere, "liste_modu", LISTE_MODU_KLASOR) == LISTE_MODU_KLASOR:
        if tus in (wx.WXK_RETURN, wx.WXK_NUMPAD_ENTER):
            pencere.secili_klasoru_ac()
            return
        if tus == wx.WXK_SPACE:
            pencere.klasor_secimini_odaktan_guncelle()
            return
        event.Skip()
        return
    if tus == wx.WXK_DELETE:
        if event.ShiftDown():
            pencere.posta_kalici_sil()
        else:
            pencere.posta_sil()
        return
    if tus != wx.WXK_SPACE:
        event.Skip()
        return
    indeks = pencere.liste.GetFocusedItem()
    if indeks == -1 or indeks >= len(pencere.mailler):
        ui.message(_("İşaretlenecek e-posta yok."))
        return
    mail_id = pencere.mailler[indeks]["id"]
    if mail_id in pencere.isaretliler:
        pencere.isaretliler.remove(mail_id)
        pencere.liste.SetItem(indeks, 0, pencere.mesaj_liste_gosterimi(pencere.mailler[indeks]))
        ui.message(_("İşaret kaldırıldı."))
    else:
        pencere.isaretliler.add(mail_id)
        pencere.liste.SetItem(indeks, 0, _("[İşaretli] ") + pencere.mesaj_liste_gosterimi(pencere.mailler[indeks]))
        ui.message(_("E-posta işaretlendi."))
