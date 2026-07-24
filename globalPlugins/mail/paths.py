# -*- coding: utf-8 -*-

import os

import globalVars

EKLENTI_KOK_DIZINI = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
AYARLAR_KLASORU = os.path.join(globalVars.appArgs.configPath, "engelsiz-mail")
AYARLAR_DOSYASI = os.path.join(AYARLAR_KLASORU, "ayarlar.json")
VERITABANI_DOSYASI = os.path.join(AYARLAR_KLASORU, "engelsiz_mail.db")
EKLER_KLASORU = os.path.join(AYARLAR_KLASORU, "attachments")
