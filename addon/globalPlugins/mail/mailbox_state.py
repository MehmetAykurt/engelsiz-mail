# -*- coding: utf-8 -*-
"""Sunucu posta durumunu değiştiren ve uzlaştıran işlemler için ortak kilit."""

import threading


# Başlık senkronizasyonu ile silme işlemi aynı anda eski sunucu görüntüsünü
# SQLite'a yazmamalıdır. Kilit ağ işlemini ve onun yerel uzlaştırmasını kapsar.
POSTA_DURUM_KILIDI = threading.Lock()
