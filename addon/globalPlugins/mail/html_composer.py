# -*- coding: utf-8 -*-
"""Engelsiz Mail - E-posta yazma için HTML biçimlendirme ve dönüştürme motoru."""

import html
import re
from urllib.parse import urlsplit

# Desteklenen temel biçimlendirme etiketleri
GECERLI_ETIKETLER = {"b", "strong", "i", "em", "u"}

RE_BAGLANTI_ETIKETI = re.compile(
    r'<a\b[^>]*\bhref\s*=\s*["\'](?P<url>[^"\']*)["\'][^>]*>(?P<metin>.*?)</a>',
    re.IGNORECASE | re.DOTALL,
)

RE_BILINEN_HTML_ETIKETLERI = re.compile(
    r'</?(?:b|strong|i|em|u|p|br|div|span|h[1-6]|ul|ol|li|blockquote|pre|hr|a\b[^>]*)>',
    re.IGNORECASE,
)

RE_MADDE_ISARETI = re.compile(r'^[•\*\-]\s+(.*)$')
RE_NUMARALI_MADDE = re.compile(r'^\d+[\.\)]\s+(.*)$')


RE_ZENGIN_ETIKET = re.compile(r"<\s*(?:a|b|strong|i|em|u|img|table|h[1-6])\b", re.IGNORECASE)
RE_ZENGIN_HIZALAMA = re.compile(r"text-align\s*:\s*(?:center|right)", re.IGNORECASE)
RE_STIL_VE_BASLIK_BLOGU = re.compile(r"<\s*(style|head)\b[^>]*>.*?<\s*/\s*\1\s*>", re.IGNORECASE | re.DOTALL)


def html_zengin_bicim_iceriyor_mu(html_metni):
    """Taslak HTML'inde düzenleyicinin geri yükleyemediği biçim (bağlantı, resim, başlık...) var mı?

    Eklenti düzenleyicisi düz metin gösterir; bağlantı, kalın/italik/altı çizili,
    başlık, tablo, resim ve ortalama/sağa hizalama yeniden açıldığında yüklenmez.
    Liste ve paragraflar düz metinden yeniden üretilebildiği için sayılmaz.
    """
    metin = RE_STIL_VE_BASLIK_BLOGU.sub(" ", str(html_metni or ""))
    return bool(RE_ZENGIN_ETIKET.search(metin) or RE_ZENGIN_HIZALAMA.search(metin))


def metin_degisimini_bul(eski, yeni, imlec=None):
    """Eski ve yeni metin arasındaki tek düzenlemeyi (konum, silinen, eklenen) olarak döndürür.

    ``imlec`` yeni metindeki imleç konumudur; tekrarlı harflerde (``aaa`` -> ``aaaa``)
    eklemenin gerçekte nerede yapıldığını belirlemek için kullanılır.
    """
    eski = str(eski or "")
    yeni = str(yeni or "")
    if eski == yeni:
        return None
    sinir = min(len(eski), len(yeni))
    konum = 0
    while konum < sinir and eski[konum] == yeni[konum]:
        konum += 1
    kuyruk = 0
    kuyruk_sinir = min(len(eski), len(yeni)) - konum
    while kuyruk < kuyruk_sinir and eski[len(eski) - 1 - kuyruk] == yeni[len(yeni) - 1 - kuyruk]:
        kuyruk += 1
    silinen = len(eski) - konum - kuyruk
    eklenen = len(yeni) - konum - kuyruk
    if silinen == 0 and eklenen > 0 and imlec is not None:
        aday = int(imlec) - eklenen
        if 0 <= aday <= len(eski) and yeni[:aday] + yeni[aday + eklenen:] == eski:
            konum = aday
    return konum, silinen, eklenen


def aralik_sozlugunu_kaydir(sozluk, konum, silinen, eklenen, satir_araligi=False):
    """(başlangıç, bitiş) anahtarlı sözlüğü, metindeki bir düzenlemeye göre günceller.

    ``satir_araligi`` doğruysa (hizalama ve başlık) satırın başında veya sonunda
    yapılan ekleme aralığı uzatır. Bağlantılarda ise başa eklenen metin bağlantıyı
    sağa iter, sona eklenen metin bağlantıya katılmaz.
    """
    delta = eklenen - silinen
    son = konum + silinen
    sonuc = {}
    for (bas, bit), deger in dict(sozluk or {}).items():
        if satir_araligi and silinen == 0 and bas <= konum <= bit:
            yeni_bas, yeni_bit = bas, bit + eklenen
        elif bit <= konum:
            yeni_bas, yeni_bit = bas, bit
        elif bas >= son:
            yeni_bas, yeni_bit = bas + delta, bit + delta
        else:
            yeni_bas = bas if bas < konum else konum + eklenen
            yeni_bit = bit + delta if bit > son else konum + eklenen
        if yeni_bit > yeni_bas:
            sonuc[(yeni_bas, yeni_bit)] = deger
    return sonuc


def url_guvenli_yap(url):
    """Verilen web adresini doğrular, gerekirse https:// ön eki ekler ve temizler."""
    temiz_url = str(url or "").strip()
    if not temiz_url:
        return ""
    # mailto:, http://, https://, ftp:// gibi şemaları kontrol et
    alt_url = temiz_url.lower()
    if not (
        alt_url.startswith("http://")
        or alt_url.startswith("https://")
        or alt_url.startswith("mailto:")
        or alt_url.startswith("ftp://")
    ):
        temiz_url = "https://" + temiz_url
    return temiz_url


def metni_etiketle(metin, etiket="b"):
    """Seçili metni HTML etiketiyle sarar. Zaten o etiketle sarılıysa etiketi kaldırır (aç/kapa)."""
    etiket = str(etiket or "b").strip().lower()
    metin = str(metin or "")

    acma = f"<{etiket}>"
    kapatma = f"</{etiket}>"

    # Eğer metin zaten bu etiketle başlıyor ve bitiyorsa, etiketi kaldır (toggle)
    metin_alt = metin.lower()
    if metin_alt.startswith(acma) and metin_alt.endswith(kapatma):
        return metin[len(acma):-len(kapatma)]

    return f"{acma}{metin}{kapatma}"


def baglanti_olustur(gorunen_metin, url):
    """Görünen metin ve adresten güvenli bir <a href="..."> köprüsü üretir."""
    guvenli_url = url_guvenli_yap(url)
    metin = str(gorunen_metin or "").strip()
    if not metin:
        metin = guvenli_url or str(url or "").strip()

    if not guvenli_url:
        return html.escape(metin)

    # Güvenlik için HTML kaçışları
    kacisli_url = guvenli_url.replace('"', '&quot;')
    return f'<a href="{kacisli_url}">{metin}</a>'


def metin_bicimlendirme_iceriyor_mu(metin):
    """Metnin b, i, u, a veya diğer HTML biçimlendirme etiketleri taşıyıp taşımadığını denetler."""
    if not metin:
        return False
    return bool(RE_BILINEN_HTML_ETIKETLERI.search(metin))


def _ham_metin_ve_etiketleri_ayristir(metin):
    """Geçerli HTML etiketlerini koruyup aradaki serbest metinlerdeki < ve > işaretlerini güvenle kaçırır."""
    if not metin:
        return ""

    parcalar = []
    son_indeks = 0
    for eslesme in RE_BILINEN_HTML_ETIKETLERI.finditer(metin):
        baslangic, bitis = eslesme.span()
        # Etiketten önceki düz metin parçası
        if baslangic > son_indeks:
            duz_parca = metin[son_indeks:baslangic]
            parcalar.append(html.escape(duz_parca, quote=False))
        # Orijinal etiket
        parcalar.append(eslesme.group(0))
        son_indeks = bitis

    if son_indeks < len(metin):
        kalan = metin[son_indeks:]
        parcalar.append(html.escape(kalan, quote=False))

    return "".join(parcalar)


def eposta_metnini_htmle_donustur(metin, imza=""):
    """Kullanıcının yazdığı metni ve imzayı zengin, erişilebilir bir HTML e-postaya dönüştürür."""
    icerik = str(metin or "")
    guvenli_govde = _ham_metin_ve_etiketleri_ayristir(icerik)

    # Paragrafları böl
    paragraflar = guvenli_govde.split("\n\n")
    html_parcalar = []
    for p in paragraflar:
        p_temiz = p.strip()
        if not p_temiz:
            continue
        p_satirlar = p_temiz.replace("\n", "<br>\n")
        html_parcalar.append(f"<p>{p_satirlar}</p>")

    ana_icerik_html = "\n".join(html_parcalar) if html_parcalar else "<p></p>"

    # İmza ekleme
    imza_html = ""
    temiz_imza = str(imza or "").strip()
    if temiz_imza:
        imza_guvenli = html.escape(temiz_imza).replace("\n", "<br>\n")
        imza_html = f'''
<div class="imza" style="margin-top: 24px; padding-top: 12px; border-top: 1px solid #ccc; color: #555;">
{imza_guvenli}
</div>'''

    return f'''<!DOCTYPE html>
<html lang="tr">
<head>
<meta charset="utf-8">
<style>
body {{
    font-family: Arial, Helvetica, sans-serif;
    font-size: 11pt;
    line-height: 1.6;
    color: #222;
    background-color: #fff;
    margin: 16px;
}}
p {{
    margin: 0 0 12px 0;
}}
a {{
    color: #0066cc;
    text-decoration: underline;
}}
</style>
</head>
<body>
{ana_icerik_html}
{imza_html}
</body>
</html>'''


def eposta_metnini_duz_metne_donustur(metin, imza=""):
    """HTML biçimlendirmeleri taşıyan metni temiz, ekran okuyucu dostu bir düz metne dönüştürür."""
    icerik = str(metin or "")
    if not icerik:
        return str(imza or "").strip()

    # 1. Bağlantıları dönüştür: <a href="url">metin</a> -> metin (url) veya url
    def baglanti_donusturucu(eslesme):
        url = eslesme.group("url").strip()
        link_metni = re.sub(r'<[^>]+>', '', eslesme.group("metin")).strip()
        if not link_metni or link_metni == url:
            return url
        return f"{link_metni} ({url})"

    temiz = RE_BAGLANTI_ETIKETI.sub(baglanti_donusturucu, icerik)

    # 2. Satır sonu ve paragraf etiketlerini yeni satıra çevir
    temiz = re.sub(r'</p\s*>', '\n\n', temiz, flags=re.IGNORECASE)
    temiz = re.sub(r'<br\s*/?>', '\n', temiz, flags=re.IGNORECASE)

    # 3. Kalan tüm HTML etiketlerini (b, i, u vb.) kaldır
    temiz = re.sub(r'<[^>]+>', '', temiz)

    # 4. HTML karakter kodlarını çöz (&amp; -> &, &quot; -> " vb.)
    temiz = html.unescape(temiz)

    # 5. Boşlukları ve fazla boş satırları toparla
    satirlar = [satir.rstrip() for satir in temiz.split("\n")]
    sonuc = "\n".join(satirlar)
    sonuc = re.sub(r'\n{3,}', '\n\n', sonuc).strip()

    # 6. İmza ekle
    temiz_imza = str(imza or "").strip()
    if temiz_imza:
        if sonuc:
            sonuc = f"{sonuc}\n\n-- \n{temiz_imza}"
        else:
            sonuc = temiz_imza

    return sonuc


RE_TABLO_BLOGU = re.compile(
    r'\[Tablo Başlangıcı(?P<basliksiz>,\s*başlıksız)?\](?:\r?\n)?(?P<icerik>.*?)\[Tablo Bitişi\]',
    re.DOTALL | re.IGNORECASE,
)


def _tablo_html_olustur(eslesme):
    icerik = eslesme.group("icerik").strip()
    if not icerik:
        return ""
    satirlar = [s.strip() for s in icerik.split("\n") if s.strip()]
    if not satirlar:
        return ""

    html_satirlar = ['<table style="border-collapse: collapse; width: 100%; margin: 16px 0; border: 1px solid #ccc; font-size: 10.5pt;">']
    basliksiz = bool(eslesme.group("basliksiz"))
    if basliksiz:
        html_satirlar.append("  <tbody>")
    ilk_satir = not basliksiz
    for satir in satirlar:
        ham_hucreler = satir.split("|")
        if len(ham_hucreler) >= 2 and ham_hucreler[0] == "":
            ham_hucreler.pop(0)
        if ham_hucreler and ham_hucreler[-1] == "":
            ham_hucreler.pop()

        hucreler = [h.strip() for h in ham_hucreler]
        if not hucreler:
            continue

        if ilk_satir:
            th_listesi = [f'<th style="border: 1px solid #ccc; padding: 8px 12px; background-color: #f2f2f2; text-align: left; font-weight: bold;">{h}</th>' for h in hucreler]
            html_satirlar.append("  <thead>\n    <tr>\n      " + "\n      ".join(th_listesi) + "\n    </tr>\n  </thead>\n  <tbody>")
            ilk_satir = False
        else:
            td_listesi = [f'<td style="border: 1px solid #ccc; padding: 8px 12px; text-align: left;">{h}</td>' for h in hucreler]
            html_satirlar.append("    <tr>\n      " + "\n      ".join(td_listesi) + "\n    </tr>")

    if not ilk_satir:
        html_satirlar.append("  </tbody>")
    html_satirlar.append("</table>")
    return "\n".join(html_satirlar)


def tablo_bloklarini_htmle_donustur(metin):
    """Metin içindeki [Tablo Başlangıcı] ... [Tablo Bitişi] bloklarını şık HTML tablolara dönüştürür."""
    if not metin or "[Tablo Başlangıcı" not in metin:
        return metin
    return RE_TABLO_BLOGU.sub(_tablo_html_olustur, metin)


def zengin_metinden_htmle_donustur(txt_icerik, imza="", baglantilar=None, ekli_resimler=None, hizalamalar=None, basliklar=None):
    """wx.TextCtrl üzerindeki karakter ve paragraf biçimlerini tarayarak zengin HTML gövdesi üretir."""
    baglantilar = dict(baglantilar or {})
    ekli_resimler = dict(ekli_resimler or {})
    hizalamalar = dict(hizalamalar or {})
    basliklar = dict(basliklar or {})
    tam_metin = str(txt_icerik.GetValue() if hasattr(txt_icerik, "GetValue") else (txt_icerik or ""))
    uzunluk = len(tam_metin)
    if uzunluk == 0:
        return eposta_metnini_htmle_donustur("", imza=imza)

    try:
        import wx
    except Exception:
        wx = None

    def _hizalama_al(indeks):
        for (bas, bit), h in hizalamalar.items():
            if bas <= indeks <= bit or (bas <= indeks and indeks < bit):
                return h
        if wx and hasattr(txt_icerik, "GetStyle"):
            attr = wx.TextAttr()
            try:
                if txt_icerik.GetStyle(indeks, attr):
                    a = attr.GetAlignment()
                    if a == wx.TEXT_ALIGNMENT_CENTRE:
                        return "center"
                    if a == wx.TEXT_ALIGNMENT_RIGHT:
                        return "right"
            except Exception:
                pass
        return "left"

    def _baslik_al(indeks):
        for (bas, bit), sev in basliklar.items():
            if bas <= indeks <= bit or (bas <= indeks and indeks < bit):
                return sev
        return 0

    satir_hizalamalari = []
    su_anki_pos = 0
    for satir in tam_metin.split("\n"):
        satir_hizalamalari.append(_hizalama_al(su_anki_pos))
        su_anki_pos += len(satir) + 1

    parcalar = []
    mevcut_stil = None
    mevcut_metin = []

    for i in range(uzunluk):
        char = tam_metin[i]
        bold = False
        italic = False
        underline = False
        url = ""

        if wx and hasattr(txt_icerik, "GetStyle"):
            attr = wx.TextAttr()
            try:
                if txt_icerik.GetStyle(i, attr):
                    bold = (attr.GetFontWeight() == wx.FONTWEIGHT_BOLD)
                    italic = (attr.GetFontStyle() == wx.FONTSTYLE_ITALIC)
                    underline = bool(attr.GetFontUnderlined())
                    url = str(attr.GetURL() or "").strip()
            except Exception:
                pass

        for (bas, bit), b_url in baglantilar.items():
            if bas <= i < bit:
                url = b_url
                break

        stil_anahtari = (bold, italic, underline, url)
        if stil_anahtari == mevcut_stil:
            mevcut_metin.append(char)
        else:
            if mevcut_metin:
                parcalar.append(("".join(mevcut_metin), mevcut_stil))
            mevcut_stil = stil_anahtari
            mevcut_metin = [char]

    if mevcut_metin:
        parcalar.append(("".join(mevcut_metin), mevcut_stil))

    def _parca_html(metin_parcasi, bold, italic, underline):
        kacisli = html.escape(metin_parcasi)
        if bold:
            kacisli = f"<b>{kacisli}</b>"
        if italic:
            kacisli = f"<i>{kacisli}</i>"
        if underline:
            kacisli = f"<u>{kacisli}</u>"
        return kacisli

    # Aynı adrese bağlı ardışık parçalar (kalın/italik/altı çizili farkları olsa bile)
    # tek bir <a> içinde birleştirilir. Aksi hâlde RICH2'nin bir stil aralığının ilk
    # karakterini farklı bildirmesi, "Aykurt" gibi bir kelimeyi "A" + "ykurt" diye iki
    # ayrı bağlantıya bölerdi ve ekran okuyucu bunları iki satır okurdu.
    html_govde = []
    sira = 0
    while sira < len(parcalar):
        metin_parcasi, stil = parcalar[sira]
        bold, italic, underline, url = stil if stil else (False, False, False, "")
        if not url:
            html_govde.append(_parca_html(metin_parcasi, bold, italic, underline))
            sira += 1
            continue
        ic_parcalar = []
        while sira < len(parcalar):
            sonraki_metin, sonraki_stil = parcalar[sira]
            s_bold, s_italic, _s_alti, s_url = sonraki_stil if sonraki_stil else (False, False, False, "")
            if s_url != url:
                break
            # Bağlantı zaten altı çizili görünür; ayrıca <u> eklenmez.
            ic_parcalar.append(_parca_html(sonraki_metin, s_bold, s_italic, False))
            sira += 1
        html_govde.append(f'<a href="{html.escape(url, quote=True)}">{"".join(ic_parcalar)}</a>')

    birlestirilmis = "".join(html_govde)

    # Ekli resimleri (satır içi görseller) yer tutucuların yerine yerleştir
    for cid, resim_bilgisi in ekli_resimler.items():
        etiket = resim_bilgisi.get("etiket", "")
        alt_metin = html.escape(resim_bilgisi.get("alt", "Resim"), quote=True)
        img_html = f'<span class="posta-resmi" style="display: block; margin: 12px 0;"><img src="cid:{cid}" alt="{alt_metin}" style="max-width: 100%; height: auto; border: 1px solid #ddd; border-radius: 4px;"></span>'
        if etiket and etiket in birlestirilmis:
            birlestirilmis = birlestirilmis.replace(etiket, img_html)

    # Tablo bloklarını dönüştür
    birlestirilmis = tablo_bloklarini_htmle_donustur(birlestirilmis)

    p_listesi = []
    arama_konumu = 0
    ham_paragraflar = birlestirilmis.split("\n\n")
    for p in ham_paragraflar:
        p_temiz = p.strip()
        if not p_temiz:
            continue

        if p_temiz.startswith("<table") or p_temiz.startswith('<span class="posta-resmi"'):
            p_listesi.append(p_temiz)
            continue

        p_satirlar = p_temiz.split("\n")
        satir_stilleri = []
        satir_basliklari = []
        for s in p_satirlar:
            saf_s = re.sub(r'<[^>]+>', '', s).strip()
            if saf_s:
                konum = tam_metin.find(saf_s, arama_konumu)
                if konum != -1:
                    h = _hizalama_al(konum)
                    b = _baslik_al(konum)
                    arama_konumu = konum + len(saf_s)
                else:
                    h = "left"
                    b = 0
            else:
                h = "left"
                b = 0
            satir_stilleri.append(h)
            satir_basliklari.append(b)

        islenmis_bloklar = []
        aktif_liste_turu = None
        aktif_liste_ogeleri = []
        aktif_paragraf_satirlari = []
        aktif_paragraf_hizasi = None

        def aktif_listeyi_bosalt():
            nonlocal aktif_liste_turu, aktif_liste_ogeleri
            if aktif_liste_turu and aktif_liste_ogeleri:
                li_metinleri = "\n".join(f"  <li>{o}</li>" for o in aktif_liste_ogeleri)
                islenmis_bloklar.append(f"<{aktif_liste_turu}>\n{li_metinleri}\n</{aktif_liste_turu}>")
                aktif_liste_turu = None
                aktif_liste_ogeleri = []

        def aktif_paragrafi_bosalt():
            nonlocal aktif_paragraf_satirlari, aktif_paragraf_hizasi
            if aktif_paragraf_satirlari:
                stil = f' style="text-align: {aktif_paragraf_hizasi};"' if aktif_paragraf_hizasi in ("center", "right") else ""
                p_metin = "<br>\n".join(aktif_paragraf_satirlari)
                islenmis_bloklar.append(f"<p{stil}>{p_metin}</p>")
                aktif_paragraf_satirlari = []
                aktif_paragraf_hizasi = None

        for j, s in enumerate(p_satirlar):
            h = satir_stilleri[j]
            b = satir_basliklari[j]

            if b > 0:
                aktif_listeyi_bosalt()
                aktif_paragrafi_bosalt()
                stil_parcalari = []
                if h in ("center", "right"):
                    stil_parcalari.append(f"text-align: {h};")
                stil_attr = f' style="{" ".join(stil_parcalari)}"' if stil_parcalari else ""
                islenmis_bloklar.append(f"<h{b}{stil_attr}>{s}</h{b}>")
                continue

            madde_eslesme = RE_MADDE_ISARETI.match(s)
            numara_eslesme = RE_NUMARALI_MADDE.match(s)

            if madde_eslesme:
                aktif_paragrafi_bosalt()
                if aktif_liste_turu != "ul":
                    aktif_listeyi_bosalt()
                    aktif_liste_turu = "ul"
                aktif_liste_ogeleri.append(madde_eslesme.group(1))
            elif numara_eslesme:
                aktif_paragrafi_bosalt()
                if aktif_liste_turu != "ol":
                    aktif_listeyi_bosalt()
                    aktif_liste_turu = "ol"
                aktif_liste_ogeleri.append(numara_eslesme.group(1))
            else:
                aktif_listeyi_bosalt()
                if aktif_paragraf_hizasi != h and aktif_paragraf_satirlari:
                    aktif_paragrafi_bosalt()
                aktif_paragraf_hizasi = h
                aktif_paragraf_satirlari.append(s)

        aktif_listeyi_bosalt()
        aktif_paragrafi_bosalt()

        p_listesi.extend(islenmis_bloklar)

    ana_icerik_html = "\n".join(p_listesi) if p_listesi else "<p></p>"

    imza_html = ""
    temiz_imza = str(imza or "").strip()
    if temiz_imza:
        imza_guvenli = html.escape(temiz_imza).replace("\n", "<br>\n")
        imza_html = f'''
<div class="imza" style="margin-top: 24px; padding-top: 12px; border-top: 1px solid #ccc; color: #555;">
{imza_guvenli}
</div>'''

    return f'''<!DOCTYPE html>
<html lang="tr">
<head>
<meta charset="utf-8">
<style>
body {{
    font-family: Arial, Helvetica, sans-serif;
    font-size: 11pt;
    line-height: 1.6;
    color: #222;
    background-color: #fff;
    margin: 16px;
}}
h1, h2, h3, h4, h5, h6 {{
    margin: 14px 0 6px 0;
    line-height: 1.35;
    color: #111;
}}
h1 {{ font-size: 1.5em; }}
h2 {{ font-size: 1.3em; }}
h3 {{ font-size: 1.15em; }}
h4 {{ font-size: 1.05em; }}
h5 {{ font-size: 0.95em; }}
h6 {{ font-size: 0.85em; font-style: italic; }}
ul, ol {{
    margin: 8px 0 12px 24px;
    padding-left: 10px;
}}
li {{
    margin-bottom: 4px;
    line-height: 1.5;
}}
p {{
    margin: 0 0 12px 0;
}}
a {{
    color: #0066cc;
    text-decoration: underline;
}}
</style>
</head>
<body>
{ana_icerik_html}
{imza_html}
</body>
</html>'''


def zengin_metinden_duz_metne_donustur(txt_icerik, imza="", baglantilar=None):
    """wx.TextCtrl üzerindeki düz metni ve link adreslerini alarak temiz düz metin üretir."""
    baglantilar = dict(baglantilar or {})
    tam_metin = str(txt_icerik.GetValue() if hasattr(txt_icerik, "GetValue") else (txt_icerik or ""))
    if not baglantilar:
        sonuc = tam_metin.strip()
    else:
        parcalar = []
        son_indeks = 0
        sirali_araliklar = sorted(baglantilar.keys(), key=lambda k: k[0])
        for bas, bit in sirali_araliklar:
            if bas > son_indeks:
                parcalar.append(tam_metin[son_indeks:bas])
            link_metni = tam_metin[bas:bit]
            link_url = baglantilar[(bas, bit)]
            if link_metni.strip() == link_url.strip():
                parcalar.append(link_url)
            else:
                parcalar.append(f"{link_metni} ({link_url})")
            son_indeks = bit
        if son_indeks < len(tam_metin):
            parcalar.append(tam_metin[son_indeks:])
        sonuc = "".join(parcalar).strip()

    temiz_imza = str(imza or "").strip()
    if temiz_imza:
        if sonuc:
            sonuc = f"{sonuc}\n\n-- \n{temiz_imza}"
        else:
            sonuc = temiz_imza
    return sonuc

