# -*- coding: utf-8 -*-
"""wx nesnelerinin ömrüyle ilgili beklenen hataları ayırt eden küçük yardımcı."""


def silinmis_wx_nesnesi_hatasi_mi(hata):
    """Pencere kapandıktan sonra geç gelen bir çağrının ürettiği hatayı tanır.

    Konuşma tamamlanınca çalışan işlemler (odak verme gibi) pencere bu arada
    kapanmışsa ``wrapped C/C++ object ... has been deleted`` hatası verir. Bu durum
    zararsızdır ve hata günlüğünü kirletmemelidir.
    """
    return isinstance(hata, RuntimeError) and "has been deleted" in str(hata)
