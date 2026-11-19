# -*- coding: utf-8 -*-


class MailHatasi(Exception):
    """Kullanıcıya sade biçimde bildirilebilecek posta işlemi hatası."""

    def __init__(self, mesaj, belirsiz_kayit=False):
        super().__init__(mesaj)
        self.belirsiz_kayit = bool(belirsiz_kayit)
