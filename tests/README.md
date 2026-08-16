# Engelsiz Mail Test Altyapısı

Bu klasör, NVDA ve gerçek Gmail hesabı olmadan üretim modüllerini güvenli biçimde sınamak için ortak araçlar içerir.

## Ortak araçlar

- `support/module_loader.py`: Üretim modüllerini yalıtılmış `mail` paketi altında yükler ve `sys.modules` durumunu test sonunda geri getirir.
- `support/fakes.py`: SMTP, IMAP, wxPython ve temel NVDA modüllerinin denetlenebilir taklitlerini sağlar.
- `support/environment.py`: Geçici ayar dizini, ek önbelleği ve gerçek SQLite göçlerini kullanan geçici veritabanı sağlar.

## Test çalıştırma

Proje kökünde:

```text
python -m unittest discover -s tests -p "test_*.py" -v
```

veya `pytest` kuruluysa:

```text
python -m pytest -q
```

Testler gerçek ağa bağlanmamalı, kullanıcının NVDA ayar klasörüne yazmamalı ve test sonunda geçici dosya bırakmamalıdır.

## Üçüncü aşama geriye dönük testleri

`test_reported_regressions.py`, derin inceleme raporunda doğrulanan davranışları
geriye dönük testlerle korur. Orta ve düşük düzey düzeltmeler tamamlandığından
bu dosyada beklenen başarısızlık bırakılmamıştır; aynı davranışlardan biri
yeniden ortaya çıkarsa test takımı doğrudan başarısız olur.

Ayar yedeğinde uygulama şifresinin taşınması kullanıcının bilinçli tercihi
olduğundan hata testi değildir; mevcut sözleşmeyi koruyan normal bir testtir.

## Dördüncü aşama

`test_stage4_medium_fixes.py` orta düzey düzeltmelerin davranışını doğrular:

- Bir alıcı alanındaki geçersiz adreslerin sessizce atılmaması,
- Eşitleme atlandığında canlı IMAP listesinin kullanılması,
- Başlangıç ve bekleyen silme yöneticilerinin etkin IMAP bağlantısını kapatması,
- Ayar yedeği başarısızlığında geçici ZIP bırakılmaması,
- Paketlenmiş `imaplib.py` değişikliğinin ve gerçek SHA-256 özetinin belgelenmesi.

## Beşinci aşama

`test_stage5_low_fixes.py` ve güncellenen `test_reported_regressions.py`
aşağıdaki düşük düzey düzeltmeleri doğrular:

- Alıcıların yalnızca başarılı gönderimden sonra adres geçmişine eklenmesi,
- Geçersiz ek kayıtlarının anlaşılır `MailHatasi` üretmesi,
- Günlükleyicinin verilen hata türünü, metnini ve iz bilgisini koruması,
- Kaynak ZIP paketlerinin `__pycache__`, `.pytest_cache`, `.pyc` ve `.pyo`
  kalıntıları olmadan yeniden üretilebilir biçimde oluşturulması,
- SMTPUTF8 kapsamındaki Unicode yerel bölümler ve IDNA alan adlarının
  doğrulanması ve ileti başlığında korunması.

Temiz kaynak arşivi oluşturmak için proje kökünde şu komut kullanılabilir:

```text
python tools/build_source_archive.py . hedef.zip --kok-adi engelsiz_mail
```

## Altıncı aşama

Temel işlev testleri aşağıdaki dosyalarda genişletilmiştir:

- `test_core_smtp_and_drafts.py`: SMTP ileti oluşturma, SSL/STARTTLS geçişi,
  gönderim belirsizliği ve taslakların IMAP klasörüne kaydedilmesi.
- `test_core_message_processing.py`: MIME çözümleme, Türkçe karakterler,
  HTML/düz metin seçimi, ön izleme ve ek dosyası güvenliği.
- `test_core_storage_contacts_folders.py`: Atomik JSON kaydı, rehber,
  Modified UTF-7 klasör adları, konuşma gruplama ve ek önbelleği.
- `test_core_store_search_listing.py`: SQLite başlık/gövde kaydı,
  listeleme, konuşmalar, okundu durumu ve arama.
- `test_core_online_listing_and_actions.py`: Çevrim içi IMAP listeleme,
  yanıt, iletme ve EML/TXT dışa kaydetme akışları.

Bu aşama testleri gerçek Gmail hesabına bağlanmaz ve gerçek NVDA ayarlarına
veya kullanıcı dosyalarına yazmaz.

## Yedinci aşama

Silme, kalıcı silme ve veri bütünlüğü testleri aşağıdaki dosyalarda
genişletilmiştir:

- `test_deletion_queue_and_processing.py`: Tekli ve toplu silme kuyruğu,
  yerel gizleme, Çöp Kutusu'na taşıma, kalıcı silme, ek dosyası temizliği,
  iptal, kilit ve istek belirteci yarış durumları.
- `test_imap_deletion_safety.py`: Seçili UID ile `UID EXPUNGE`, Gmail ileti
  kimliği, UIDVALIDITY, etiket desteği ve boyut sınırı güvenlik denetimleri.
- `test_database_migrations_integrity.py`: Şema sürümleri 0-9'dan 10'a
  göç, işlem geri alma, dış anahtar bütünlüğü, bozuk veritabanı yedeği ve
  dosya değiştirme algılama.
- `test_database_maintenance.py`: Yetim önbellek temizliği, bekleyen silme
  koruması, yerel Gmail iletisi temizliği, bakım, sıkıştırma ve güvenli
  veritabanı sıfırlama.

Bu aşamada dosya hazırlık önbelleği, aynı dosya kimliği yeniden kullanılsa
bile boş veya değiştirilmiş bir SQLite dosyasını algılayacak biçimde
güçlendirilmiştir. Ayrıca geçerli ve geçersiz UID değerlerinin aynı silme
isteğinde bulunması, kısmi silme yerine işlemin tamamını güvenli biçimde
durdurur.

## Sekizinci aşama

Türkçe karakter, bildirim, erişilebilirlik ve yaşam döngüsü testleri şu
alanlarda genişletilmiştir:

- `test_stage8_turkish_and_accessibility.py`: Windows-1254/UTF-8 çözümleme,
  bozuk Türkçe metin onarımı, Türkçe dosya adları, konu önekleri, dört farklı
  I/i biçimi ve aksansız arama, erişilebilir denetim adları, ana liste modları,
  temel klavye kısayolları ve Enter/Escape/Delete/Boşluk davranışları.
- `test_stage8_notifications.py`: İlk bildirim gecikmesi, kapalı bildirim
  ayarı, bekleyen konuşma zamanlayıcısının iptali, eski IDLE dinleyicilerinin
  sonuçlarının yok sayılması, açık pencere callback'i, Türkçe bildirim metni,
  ilk UID tabanı, okunmuş/okunmamış yeni iletiler ve UIDVALIDITY değişimi.
- `test_stage8_plugin_lifecycle.py`: Üç arka plan yöneticisinin kurulması,
  NVDA kapanışında yöneticilerin, menünün ve açık pencerenin temizlenmesi,
  tek bir yöneticinin hata vermesi durumunda diğer temizleme adımlarının
  sürmesi, açık pencerenin ikinci kez oluşturulmaması ve pencere kapanınca
  bildirim callback'inin kaldırılması.

Türkçe arama, SQLite FTS5'in eksik bıraktığı `I/İ/ı/i` ve aksan eşleşmelerini
Türkçe uyumlu katlanmış SQL aramasıyla tamamlar. Böylece örneğin `IŞIK`,
`CAGRI`, `GULSUM`, `SULE` ve `FISILTI` sorguları Türkçe içerikleri bulabilir.

## Dokuzuncu aşama

`test_final_package_quality.py` son dağıtımın yapısal ve hukuki bütünlüğünü
korur:

- GPL 2.0 `LICENSE` dosyasının bulunması,
- manifest, Python sürüm sabiti ve HTML belgelerinin aynı sürümü bildirmesi,
- belgelerdeki yerel dosya bağlantılarının geçerli olması,
- CPython ve SQLite ikili dosyalarının belgelenmiş SHA-256 özetleri,
- paketlenmiş SQLite bileşenlerinin Windows x64 mimarisi,
- üretim kodunda geliştirme kalıntılarının bulunmaması,
- kökünde `manifest.ini` bulunan, test ve önbellek taşımayan, yeniden
  üretilebilir `.nvda-addon` paketinin oluşturulması.

Kurulabilir eklenti paketini oluşturmak için proje kökünde:

```text
python tools/build_addon_package.py . EngelsizMail-1.8.2.nvda-addon
```

## Onuncu aşama

`test_stage10_live_fixes.py`, gerçek NVDA ve Gmail canlı testinde belirlenen
iki kullanıcı deneyimi sorununu korur:

- Gönderim başarı mesajı tamamlanmadan gönderim sonrası yenileme callback'inin
  ve yazma penceresi kapanışının başlamaması.
- Bekleyen tekli veya çoklu silmelerin klasör toplamlarına yalnız gösterim
  sırasında uygulanması; sunucudan alınan ham sayı önbelleğinin değiştirilmemesi
  ve ilave IMAP bağlantısı oluşturulmaması.

## On birinci çalışma / dördüncü aşama

`test_stage11_translation_infrastructure.py`, kaynak Türkçe kalırken NVDA'nın
gettext tabanlı çeviri altyapısına güvenli geçişi korur:

- `_()` kullanılan üretim modüllerinde `addonHandler.initTranslation()`
  çağrısının bulunması,
- Gmail sistem klasörlerinin iç Türkçe anahtarlarının değişmemesi ve yalnız
  görünüm katmanında çevrilmesi,
- yazı stili ve renk ayarlarında kalıcı Türkçe anahtarların korunması,
- çevrilmiş `[Okunmadı]` etiketinin eski Türkçe önbellek biçimleriyle birlikte
  güvenle temizlenmesi,
- `locale` çalışma zamanı dosyalarının `.nvda-addon` paketine alınması; `.po`
  ve `.pot` geliştirme dosyalarının dağıtım paketine alınmaması,
- ortak kullanıcı arayüzü çağrılarında çıplak, çeviriye açılmamış sabit metin
  kalmaması.

Çeviri şablonunu yeniden üretmek için:

```text
python tools/extract_translations.py . locale/nvda.pot
```

Bu aşamada İngilizce çeviri eklenmez; `locale/nvda.pot` yalnız sonraki aşamada
hazırlanacak İngilizce dil dosyasının kaynak şablonudur.

## On birinci çalışma / beşinci aşama

`test_stage11_english_translation.py`, Türkçe kaynak metinlerden üretilen İngilizce
kataloğun çalışma zamanı sözleşmelerini korur:

- İngilizce katalogda kaynak şablondaki bütün kullanıcı metinlerinin bulunması,
- boş çeviri ve yer tutucu kaybı olmaması,
- `.mo` dosyasının gerçek `gettext` ile doğru İngilizce sonuç üretmesi,
- İngilizce manifest ile Yardım/Yenilikler belgelerinin bulunması,
- NVDA dili İngilizce olduğunda `doc/en`, Türkçe olduğunda `doc/tr` seçilmesi,
- kurulabilir pakete yalnız çalışma zamanı dil dosyalarının alınması.

## On birinci çalışma / altıncı aşama

`test_stage11_language_quality.py`, İngilizce kullanıcı dilinin editoryal ve
klavye erişilebilirliği kalitesini korur:

- İngilizce çevirilerde yanlışlıkla Türkçe özel harf kalmaması,
- ana menü ve iletişim pencerelerinde erişim harflerinin çakışmaması,
- İngilizce Yardım Kılavuzu kısayollarının gerçek İngilizce arayüzle eşleşmesi,
- bilinen bozuk İngilizce cümle kalıplarının geri gelmemesi,
- `.mo` kataloğunda düzeltilmiş erişim harflerinin bulunması,
- temel noktalama kusurlarının otomatik yakalanması.

## On birinci çalışma / yedinci aşama

`test_stage11_localization_integrity.py`, final öncesi yerelleştirme zincirini
uçtan uca doğrular:

- `locale/nvda.pot` dosyasının güncel Python kaynaklarından bayt düzeyinde
  yeniden üretilebilmesi,
- `nvda.mo` dosyasının İngilizce `.po` dosyasından bayt düzeyinde yeniden
  üretilebilmesi,
- İngilizce katalog metadata, fuzzy/obsolete kayıt ve şablon kalıntısı
  denetimleri,
- `.po` içindeki bütün çevirilerin çalışma zamanı `.mo` kataloğuyla birebir
  eşleşmesi,
- Python brace-format yer tutucularının ve katalog bayraklarının korunması,
- derleme aracının fuzzy veya yer tutucusu bozuk çeviriyi reddetmesi,
- IMAP `\\Seen` bayrağı ve Windows Gezgini `/select,` anahtarı gibi iç teknik
  değerlerin hiçbir dil kataloğuna alınmaması,
- wxPython kurucuları ve menü çağrılarını da kapsayan genişletilmiş çıplak
  kullanıcı metni taraması,
- İngilizce yerel manifestin yalnız `summary` ve `description` alanlarını
  değiştirmesi,
- `en`, `en_US`, `en-GB` gibi İngilizce varyantları ile Türkçe geri dönüşün
  doğru seçilmesi,
- Türkçe ve İngilizce HTML belgelerinde dil ve bölüm bağlantılarının tutarlı
  kalması,
- kaynakla aynı kalan İngilizce karşılıkların yalnız bilinçli izin listesindeki
  özel ad ve evrensel terimler olması.

Bu aşamada çeviri derleyicisi de dağıtıma uygun olmayan fuzzy, obsolete veya
yer tutucusu bozulmuş `.po` kayıtlarını reddedecek biçimde sıkılaştırılmıştır.
