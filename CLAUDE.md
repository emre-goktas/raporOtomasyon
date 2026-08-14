# SigortaOtomasyonu

SGK müfettiş rapor otomasyonu. Emre'nin kendi iş akışı için kişisel araç —
satılacak ürün değil, o yüzden "herkesin tarzına uyması" gibi bir kısıt yok,
yalnızca **onun** rapor tarzına uyması yeterli.

## Temel tez

> Rapor iş türü ne olursa olsun **süreç aynı**. Değişen şey kural ve yorum.

Bu cümle mimarinin tamamını belirliyor:

```
ÇEKİRDEK (core/) — bir kez yazılır, iş türünden bağımsız
   iş oluştur → belge topla → sınıflandır → çıkar → kural işlet → rapor render

DOMAIN PAKETİ (domains/<ad>/) — her iş türü için bir klasör, kod yok
   belgeler.yaml   hangi belgeler beklenir, hangisi zorunlu
   cikarim/*.yaml  belge türü başına: tanıma imzası + alan kuralları
   kurallar.yaml   eksik belge → İPC maddesi, tarih mantığı kontrolleri
   mevzuat/*.md    rapora giren sabit alıntı blokları
   rapor.docx      şablon
```

Yeni iş türü eklemek = yeni klasör açmak. Python yazılmaz.

**Hedef kapsam (uzun vade):**

| # | Alan | Domain |
|---|---|---|
| 1 | Sigorta işleri | `is_kazasi` ← **şu an burası**, `meslek_hastaligi`, `asgari_iscilik` |
| 2 | Sağlık işleri | hastane / eczane soruşturmaları |
| 3 | Personel soruşturması | |
| 4 | Teftiş | |
| 5 | Karma kapsamlı işler | birden çok domaini bağlar |

---

## Mevcut durum

**Bitti — Faz 1** (commit `4a1ae0e`) ve **Faz 2'nin 3a ayağı** (14.08.2026),
ikisi de gerçek veriyle doğrulandı. `tests/calistir.py` → 53 test geçiyor.

| Dosya | İş |
|---|---|
| `core/xlsx.py` | Bağımlılıksız `.xlsx` okuyucu (stdlib). `openpyxl` gerekmiyor. |
| `core/onarim.py` | Excel'in sessiz bozmalarını geri alır (aşağıya bak) |
| `core/denetim_listesi.py` | `DenetimListesi.xlsx` → iş kayıtları |
| `core/gorev_emri.py` | Görev emri PDF → künye |
| `core/case.py` | `case.json` yaz/oku, klasör adı, domain eşleme |
| `core/metin.py` | Tarih (ISO + takvim doğrulaması) · sayı (TR/ABD ayracı) · TC sağlaması · Türkçe harf katlama |
| `core/pdf.py` | pymupdf üzerine konumlu okuma: `Kelime` / `Satir` / `Sayfa`, metin katmanı kontrolü |
| `core/cikarim/sema.py` | YAML belge tanımı okur, alanları tiplendirir, eksik/boş ayrımı yapar |
| `core/cikarim/etiketli.py` | `Etiket : Değer` düzeni (tescil) — kolon çapaları histogramdan, taşma birleştirme |
| `core/cikarim/form.py` | Sabit devlet formları (ig/ia) — etiket çapalı uzamsal okuma |
| `core/cikarim/tablo.py` | Sabit kolonlu tablolar (hizmet dökümü) — kolon çapaları YAML'da, her sayfada başlıkla doğrulanır |
| `core/cikarim/satir.py` | Satır içi `Etiket: Değer` (denetim gerekçesi, ünite kararı) — kurum yazışması düzeni |
| `core/belge.py` | Belge türünü **içerikten** tanır, doğru motora yönlendirir |
| `core/capraz.py` | Aynı bilgiyi kaynaklar arasında karşılaştırır (kural 6) |
| `cli.py` | `kur` + `cikar` komutları |

**Faz 2 sonucu — Ali Veli dosyası (5 belge):**

| Belge | Motor | Çıktı | Uyarı |
|---|---|---|---|
| işe giriş bildirgesi | form | 13 alan | — |
| işten ayrılış bildirgesi | form | 14 alan | — |
| işyeri tescil | etiketli | 27 alan | 1 (ünvan 60 karakterde kırpılmış) |
| hizmet dökümü | tablo | 270 satır | — |
| `262506575.pdf` (13 s.) | — | — | metin katmanı yok → Faz 5 |

Çapraz doğrulama: TC, ad-soyad, işyeri sicil ve ünvan **dört kaynakta da uyuşuyor**.
Hizmet dökümünün `Asıl` kayıtlarının gün toplamı (8103) belgenin kendi
"Toplam 4a Uzun Vade PÖGS" satırıyla birebir aynı — çıkarımın bağımsız kanıtı.

**UDF kapsam dışı** (14.08.2026 kararı): yeni kurum sisteminde denetim
gerekçesi ve ünite kararı **metin katmanlı PDF** olarak geliyor. UDF okuyucusu
yazılmayacak.

**Bitmedi:** Faz 3–7.

**Bağımlılık:** `pymupdf` + `pyyaml`. Kendi venv'i var: `.venv/` (`requirements.txt`).

---

## Yol haritası

| Faz | İş | AI? |
|---|---|---|
| ~~1~~ | ~~Görev emri + denetim listesi → `case.json`~~ | ✗ |
| **2** | ~~3a belgeleri → alan çıkarımı~~ · UDF denetim gerekçesi **bekliyor** | ✗ |
| 3 | İçerik bazlı belge sınıflandırma — *temeli `core/belge.py` ile atıldı* | ✗ |
| 4 | Kural motoru: eksik belge → İPC, tarih mantığı, çapraz doğrulama | ✗ |
| 5 | Taranmış 3b/3c belgeleri → özet + alan çıkarımı | ✓ |
| 6 | Rapor render: docxtpl + Türkçe ek uyumu + `{{ek:...}}` çözümü | kısmen |
| 7 | JETEK manifest bağlantısı — `ek_no` geri beslemesi | ✗ |

Faz 1–4 AI'sız ve işin ~%70'i. **AI'ı erken çağırma.**

---

## `case.json` — tek gerçek kaynak

Rapor da, ek listesi de, kural motoru da, JETEK manifest'i de bu dosyadan
beslenir. İkinci bir "gerçek kaynak" dosyası **açılmayacak**.

```jsonc
{
  "schema_version": 1,
  "denetim_no": "90001",
  "domain": "is_kazasi",              // denetim_alani'ndan eşlenir
  "denetim_alani": "İş Kazası İncelemesi",
  "statu": "MUFETTİŞE İLETİLDİ",
  "il": "Ankara",
  "mufettis": "EMRE GÖKTAŞ",

  "gorev_emri":        { "tarih", "sayi", "sayi_tam", "grup_baskanligi",
                         "mufettis", "imzalayan", "denetim_adedi", "son_tarih" },
  "denetim_gerekcesi": { "tarih", "sayi", "mudurluk" },   // mudurluk → Faz 2, UDF'den

  "sigortalilar": [ { "sira": 1, "ad_soyad": "...", "tc": "..." } ],  // birden fazla olabilir
  "isveren":      { "tescilli": true, "unvan": "...", "sicil_no": "..." },
  "diger_isveren": null,

  "belgeler": [{   // `cikar` üretir; her belge bir girdi
    "tur": "isyeri_tescil",        // içerikten tanındı, dosya adından DEĞİL
    "motor": "etiketli",
    "kaynak": { "dosya", "dosya_adi", "sayfa_sayisi", "metin_katmani" },
    "alanlar": { },                // etiketli/form motorlarında tiplendirilmiş alanlar
    "satirlar": [ ],               // tablo motorunda satır listesi
    "uyarilar": [ ],
    "ek_no": null,                 // Faz 7 — JETEK manifest'inden
    "citation_key": "isyeri-tescil" // Faz 6 — rapordaki sabit atıf anahtarı
  }],
  "bulgular": [],   // Faz 4 — kural motoru çıktısı
  "uyarilar": [],   // her katman kendi şüphesini buraya yazar
  "kaynak":   { "denetim_listesi": "...", "satir": 5 }
}
```

`core/case.py:kaydet()` **yeniden çalıştırmaya dayanıklıdır**: `belgeler`,
`bulgular`, `notlar` korunur, yalnızca künye tazelenir.

---

## Çıkarım motorları — yeni belge türü nasıl eklenir

Üç motor var, üçü de genel; belge bilgisi YAML'da (kural 7). Yeni belge türü
eklemek `domains/<domain>/cikarim/<belge>.yaml` yazmaktır, **Python yazılmaz**.

| Motor | Ne için | Nasıl çalışır |
|---|---|---|
| `satir` | Satır içi `Etiket: Değer` (denetim gerekçesi, ünite kararı) | Geometri bilgi taşımıyor, satırın kendisi taşıyor: ilk `:` solu etiket, sağı değer. Taşan değer `_acik_mi` ile, iki satıra bölünen etiket bitişiklik + sol hiza ile, bölüm başlığı büyük harf oranıyla ayrılır |
| `etiketli` | `Etiket : Değer` düzeni (işyeri tescil) | `:` konumlarının histogramından kolon çapaları ölçülür; taşan satır x konumundan değer mi etiket mi olduğu anlaşılır; kalıba uymayan satır `serbest` olarak ayrı tutulur |
| `form` | Sabit devlet formu (ig, ia) | Çapa = **etiketin kendi kelimeleri**; değer `sag` (aynı satırda) ya da `alt` (bir alt satırda). Değerin bittiği yeri **yatay boşluk** söyler: kolon arası 25pt+, kelime arası 2–4pt |
| `tablo` | Sabit kolonlu tablo (hizmet dökümü) | Kolon çapaları YAML'da; **her sayfada başlık satırıyla doğrulanır**. `satir_capasi` dolu olan satır yeni kayıt açar, bitişik satırlar aynı kayda eklenir |

Her tanımda bir `tanima:` bloğu var — belge türü buradan **içerikle** anlaşılır:

```yaml
tanima:
  metin_icerir: ["SİGORTALI İŞE GİRİŞ BİLDİRGESİ"]   # düz metinde geçmeli
  gerekli_anahtarlar: ["İş Yeri Sicil No"]            # etiketli motorda
```

### Koordinat nerede kaldı, neden

Yalnızca **hücre ızgaralı** alanlarda (TC'nin haneleri, işyeri sicilinin
bölümleri) ve tablo kolonlarında açık `x` var — çünkü oralarda geometri
gerçekten yapının kendisi. Eski projenin battığı yer koordinat kullanması
değil, **kalibrasyon kaydığında sessiz kalmasıydı**. Bu yüzden her koordinatlı
alan bir doğrulamayla eşleşir:

```yaml
tc:
  x_araligi: [170, 440]
  dogrula: tc            # TC sağlaması tutmazsa gürültülü hata
```

Bu gerçekten işe yaradı: işten ayrılış bildirgesinde pencereyi ilk seferde
dar verdim, 11 hane yerine 8 hane okundu, `dogrula: tc` anında yakaladı.
Sessiz kalsaydı rapora eksik TC girecekti.

`deger_deseni` aynı işi belirsizlik için yapar: "Sicil Numarası" etiketi
bildirgede iki yerde geçiyor; doğru olanı **sırasından değil biçiminden**
(`\d{13}`) ayırıyoruz.

---

## Değişmez kurallar

Bunlar eski projenin (`02_RaporOtomasyonu`) tam olarak battığı yerlerden çıkarıldı.

**1. Sessiz başarısızlık yasak.** Eski pipeline altı parser çağırıyordu, dördü
hiçbir uyarı vermeden boş dönüyordu. Bir belge yoksa, bir alan boşsa, bir
dönüşüm şüpheliyse → `uyarilar`'a yazılır. Sessizce `None` dönmek en tehlikeli
davranış; **sessizce yanlış dönmek ondan da kötü.**

**2. Sabit kolon indeksi / sabit dosya adı deseni varsayma.** Excel kolonları
başlık satırından çözülür. Belge türü içerikten anlaşılır (Faz 3), dosya adından
değil — eski projede config `*_ic.pdf` bekliyordu, sistem `_ia` veriyordu, parser
sessizce hiç çalışmadı. Ayrıca **JETEK dosyaları yeniden adlandırıyor**, yani
dosya adına dayanan her şey zaten kırılgan.

**3. Yapılandırılmış belgede AI kullanma.** 3a belgeleri (işe giriş, tescil,
hizmet dökümü) formatlı ve temiz — deterministik çıkarım %100 kesin ve
denetlenebilir. Bu rapor idari para cezasına yol açıyor; kesinliğin bedava
olduğu yerde LLM'in %99'una razı olma. AI yalnızca **taranmış** 3b/3c
belgelerinde (ifade, bilirkişi, olay yeri) devreye girer.

**4. Ayrı OCR katmanı ekleme.** Vision modeli taranmış PDF'i doğrudan okuyor;
araya Tesseract koymak kaliteyi düşürür.

**5. Çıkarım ≠ değerlendirme.** Parser olguyu çıkarır (`ise_giris_tarihi`),
kural motoru değerlendirir (`bildirim_zamaninda: false, gecikme_gun: 7`),
writer ikisini basar. Karıştırma.

**6. Çapraz doğrulama.** Aynı bilgi birden çok belgede var: işyeri sicil no
hem Excel'de, hem tescil PDF'inde, hem denetim gerekçesi UDF'inde. Üçü
uyuşuyorsa güven yüksek; uyuşmuyorsa **işaretle, insana sor.** Excel verisi
güvenilmez — Emre birkaç kez TC/sicil düzelttirmiş.

**7. Domain bilgisi koda değil YAML'a.** Emre bu deseni bağımsız olarak iki kez
buldu (JETEK'te `templates.json`, eski projede `document_templates.yaml`).
Motor genel, belge bilgisi konfigürasyonda.

---

## Excel'in sessiz bozmaları (`core/onarim.py`)

Gerçek veride görülen, `onarim.py`'ın geri aldığı bozulmalar:

| Bozulma | Örnek | Not |
|---|---|---|
| Seri tarih numarası | `45366` → `2024-03-15` | 1900 artık yıl hatası: epok `1899-12-30` |
| Bilimsel gösterim | `9.2063506E7` → `92063506` | 15 basamak üstünde hassasiyet uyarısı |
| Baştaki sıfır kaybı | `01234` → `1234` | posta/stok/vergi kodlarında |
| Karışık ondalık ayracı | `20.002,50` yanında `666.75` | gerçek raporun hizmet dökümü tablosunda görüldü |

Şüpheli dönüşüm **tahmin edilmez**, uyarı üretilir.

---

## Gerçek veriden çıkan bulgular (Faz 2)

**1. Kurum sistemi işveren ünvanını tam 60 karakterde kırpıyor.**
Hem denetim listesinde hem tescil çıktısında, kelime ortasından:

```
ÖRNEK LOJİSTİK NAKLİYAT TAŞIMACILIK SANAYİ VE TİCARET LİMİTE   (60, "LİMİTED ŞİRKETİ" kesik)
DENEME GALVANİZ METAL YOL İNŞAAT TAAHHÜT SANAYİ VE TİCARET L    (60)
İKİNCİ DENEME SANAYİ VE TİCARET LTD.ŞTİ.                         (39, sağlam)
```

Bildirgedeki ünvan da kısa ama farklı uzunlukta (55). **Tam ünvan hiçbir 3a
belgesinde yok** — rapora tam yazılacaksa başka kaynak gerekiyor (ticaret
sicil / vergi levhası / işveren yazısı). `kirpma_esigi: 60` bu durumu her
seferinde uyarıyla işaretliyor; çapraz doğrulama kırpma farkını yanlış alarm
saymıyor (kısası uzunun başlangıcıysa aynı işveren).

**2. Hizmet dökümünde `İptal` kaydı eşleşen kaydı geçersiz kılar** — ikisi de
yıl toplamına girmez. Bu netleştirme **Faz 4'ün işi** (kural 5: çıkarım ≠
değerlendirme), çıkarım ham satırları olduğu gibi veriyor. Doğrulandı: 244
kayıtta `Asıl` gün toplamı 8103, belgenin kendi beyanıyla birebir aynı;
yıl bazında 26 TOPLAM satırının 25'i iptal çifti elenince tutuyor.

**3. İşyeri sicil numarasının kontrol hanesi kaynaklar arasında farklı
görünüyor** — tescilde `... 027 09-51 000 001`, bildirgede aynı satır
`27 | 9 | 9 | 0` (İL KOD | İLÇE | KONT NO | ALT İŞV). Çapraz doğrulama şimdilik
**iş kolu + 7 haneli işyeri sıra numarası** üzerinden yapılıyor; ikisi her
kaynakta tutuyor. Sicil biçiminin tam çözümü Emre'ye sorulacak.

**4. Aynı belgeyi her SGK müdürlüğü farklı etiketliyor.** Yedi denetim
gerekçesinde yedi ayrı yazım görüldü:

```
işveren ünvanı : "Adı - Soyadı Veya Ticaret Unvanı" · "... Unvan" (sondaki ı yok)
                 "İşverenin/Alt İşvereninAdı-Soyadı veya Ticaret Unv." · "Ticaret Unvanı"
                 "2-İşverenin Adı Soyadı, Unvanı"
kaza tarihi    : "Kaza Tarihi" · "Tespit Tarihi" · "Meslek hastalığı Tespit Tarihi"
                 "Kaza Tarihi / Meslek hastalığı Tespit Tarihi" · "5- Olay Tarihi"
ayraç          : bir müdürlük ':' yerine ';' yazmış
```

Bu yüzden şemada `anahtar_kelimeler:` var — tam metin yerine hepsinde geçen
kelimeyi ("unv", "tarih") arıyor. Varyantları tek tek saymak sürdürülemez.

**5. Denetim gerekçesindeki `Ek: ... (N Sayfa)` bedava bir eksik ek kontrolü.**
Altı örnekte beyan edilen sayfa adedi indirilen muhteviyat PDF'iyle **birebir
tuttu** (34/18/76/26/25/49). Ek eksikse burada yakalanır.

**6. Ünite kararındaki `Mevcut ( X ) / Mevcut değil ( )` kutucukları** komisyonun
elindeki belge listesi — Faz 4'ün "belge yoksa İPC" kuralının doğrudan girdisi.

**7. Henüz çıkarılmayanlar** (bilerek, kapsam dışı):
- Hizmet dökümünün 1. sayfasındaki üst yazı (TC, ad-soyad, doğum bilgileri,
  `Toplam 4a Uzun Vade PÖGS`) — aynı veriler bildirgeden zaten geliyor
- Tescildeki ortak / yönetici blokları — `etiketli` motoru blok başlıklarını
  `serbest` satır olarak zaten veriyor, bölmek kolay
- İşten ayrılış bildirgesindeki aylık PEK mini tablosu (17. alan)

---

## Domain bilgisi: iş kazası süreci

**1. Görev emri** Belgenet'e düşer. PDF, metin tabanlı, tek sayfa, rutin işlerde
içerik sabit. Büyük soruşturmalarda içeriği okumak gerekir.

**2. Denetim listesi** görev emrinin eki, `.xlsx`. Kolonlar: Denetim No,
Yazı Tarihi, Yazı Sayısı, Denetim Alanı, Statüsü, İlleri, Sigortalı Bilgisi,
Tescilli İşveren Bilgisi, Diğer İşveren Bilgisi, Havale Edilen Müfettiş.

- Sigortalı hücresi çok kişili olabilir: `1.AD SOYAD\nTC NO:...\n2.AD SOYAD\n...`
- Tescilli işveren hücresi: `1.ÜNVAN\nSİCİL NO:...`
- **Tescilli işveren boşsa işyeri tescilsizdir** — ayrı rapor akışı gerektirir
- Bu verilere körü körüne güvenme (kural 6)

**3. Belge toplama — üç kaynak, üç farklı kalite:**

| Kaynak | Ne | Format |
|---|---|---|
| **3a** | Kurum sisteminden sorgulanıp indirilenler: işe giriş/ayrılış bildirgesi, hizmet dökümü, işyeri tescil | %90+ formatlı, temiz metin. **OCR gerekmez.** Deterministik çıkarım. |
| **3b** | İş no bazlı toplu ek indirme — müdürlüğün topladığı evrak: denetim gerekçesi ve ekleri, ünite kararı, ifadeler, tutanaklar, olay yeri inceleme, 3a'nın taranmış kopyaları | Şansına ne çıkarsa. Çoğu tarama. |
| **3c** | Müfettişin yazdığı yazılara gelen cevaplar: nüfus md., il sağlık md., savcılık, işveren | Karışık — metin + tarama + bazen JPEG |

**4. Kural motoru (şu an Emre'nin kafasında):**
- Belge yoksa → idari para cezası (örn. iş kazası bildirim formu yoksa)
- Mevcut belgelerde kural ihlali: bildirge tarihi ≤ işe başlama tarihi?
  kaza bildirimi süresinde mi? işten ayrılış tarihi kaza tarihiyle tutarlı mı?

**5. Rapor yazımı** — bugün elle: Word'de Ctrl+H ile veri yapıştırma,
kesme işareti eklerini gözle düzeltme. Değerlendirme çoğunlukla belgelerin
özeti ("bilirkişi şöyle demiş, ifadelerde şöyle denmiş"), ardından 1–2 paragraf
kusur takdiri ve 5510 maddelerinin uygulanması.

### Belge kısaltmaları (kurum sistemi dosya adlarında)

`_ig` işe giriş · `_ia` işten ayrılış · `HizmetDokumu` hizmet dökümü ·
`tescilBilgi` işyeri tescil · `.udf` UYAP formatı (denetim gerekçesi, ünite kararı)

**UDF okuma:** zip arşivi → `content.xml` → `<content><![CDATA[ ... ]]></content>`
içinde düz metin, hizalama boşluklarla korunmuş. Etiket:değer formatında,
kolayca parse edilir. (Eski projedeki hardcode'a gerek yok.)

---

## Rapor anatomisi

`ornek_veri/ornek_rapor_kalp_krizi.docx`
gerçek örnektir. 10–12 sayfa, çoğu mevzuat alıntısı.

| Bölüm | Kaynak | Otomasyon |
|---|---|---|
| Tablo: **GENEL BİLGİLER** (6×2) | tescil + denetim gerekçesi | ✅ %100 |
| **2. İncelemenin Konusu** | excel + denetim gerekçesi + olay özeti | ✅ şablon + 1 cümle |
| **3. Değerlendirmeye Esas Belgeler** | **manifest / JETEK** | ✅ %100 |
| **4.1** İşyerinin tescil işlemleri | mevzuat + tescil | ✅ |
| **4.2** Sigortalılık nitelikleri | mevzuat + ig/ia + hizmet dökümü | ✅ |
| **4.3** Prime esas kazançlar | mevzuat + hizmet dökümü tablosu | ✅ + tablo |
| **4.4** İş kazası yönünden | mevzuat + ifadeler + sağlık raporu | ⚠️ AI özet + **insan yorumu** |
| **4.5** İşverenin sorumluluğu | mevzuat + OSGB belgeleri | ⚠️ AI + **kusur takdiri insan** |
| **4.6** Sigortalının sorumluluğu | mevzuat | ✅ çoğu vakada standart |
| **4.7** Üçüncü kişilerin sorumluluğu | mevzuat | ✅ çoğu vakada standart |
| **5. Sonuç ve Kanaat** (5.1–5.10) | 4.x'in ayna görüntüsü | ✅ kalıp + değişken |

**Bölüm 4'ün her alt başlığı aynı üçlü kalıpta:**
① mevzuat alıntısı (sabit) → ② olgu tespiti (`case.json`) → ③ değerlendirme (AI taslak / insan)

**Bölüm 5, bölüm 4'ün ayna görüntüsü** — her boyut için bir sonuç cümlesi.

**Alt başlıklar olaya göre eklenebilir** — şablon sabit değil, iskelet sabit.

### Ek atıf formatı — JETEK sözleşmesi

Bölüm 3 tamamen manifest'ten üretilir. Gerçek örnekten:

```
Rehberlik ve Teftiş Ankara Grup Başkanlığının 21/11/2024 tarihli ve
106535159 sayılı görevlendirmesi. (Ek:1)
Batman SGK İl Müdürlüğünün 16/10/2024 tarih ve 104009524 sayılı denetim
gerekçesi ve ekleri. (Ek:2,2/1-7)
Müfettişliğimizin 08/01/2025 tarihli ve 109662589 sayılı yazısı ve işveren
tarafından ibraz edilen kayıt ve belgeler. (Ek:3-4)
```

Desteklenmesi gereken biçimler: tek `(Ek:1)` · aralık `(Ek:3-4)` ·
**hiyerarşik alt numara** `(Ek:2,2/1-7)`.

Raporda numara değil **sabit anahtar** yazılır, render'da çözülür:

```
şablonda:  {{ek:denetim-gerekcesi}} sayılı belgede...
çıktıda:   Ek:2,2/1-7 sayılı belgede...
```

Araya belge girdiğinde hiçbir atıf elle düzeltilmez.

### Türkçe ek uyumu

Gerçek raporda **iki yerde hata var**: `Can ÖRNEK'ya ait` (yanlış, `ÖRNEK'e`
olmalı) — önceki rapordan kalan Ctrl+H artığı, gözle kontrolden kaçmış.

Ünlü uyumu + ünsüz benzeşmesi deterministik. ~40 satırlık fonksiyon bu hata
kategorisini tamamen kapatır:

```
{{sigortali|yonelme}}  →  ALİ VELİ'e
{{sigortali|ilgi}}     →  ALİ VELİ'in
{{isveren|ilgi}}       →  ...LTD.ŞTİ.'nin
```

---

## Nereden ne alınacak

### `01_PROJECTS/02_RaporOtomasyonu` (ve JETEK içindeki kopyası)

Eski deneme. %80'i bitmiş sonra durmuş; Mart 2026'dan beri çalışmamış.
`main.py` altı parser çağırıyor ama `writer.py` yalnızca birini okuyor —
beş JSON üretilip yerde kalıyor. **Kodu taşıma, bilgiyi taşı.**

| Dosya | Karar |
|---|---|
| `src/utils.py` | **TAŞI.** `tarih_bul`, `tarih_cikart_ve_temizle`, `sayi_bul` — tarih/sayı varyantları belgelenmiş, regex'ler modül seviyesinde derlenmiş. `core/metin.py` olarak gelsin, testleriyle. |
| `src/bildirge_parser.py` | **MOTORU AL.** YAML'dan koordinat okuyup `clip` + regex uygulayan genel motor doğru. `core/cikarim/koordinat.py` olarak genelleştir. |
| `templates/document_templates.yaml` | **REFERANS.** Koordinatlar **kalibrasyonu kaçırmış** — şu an iki alan `null`, biri formun başka yerinden metin getiriyor. Yeniden ölçülecek, ama alan adları ve yapı örnek. |
| `src/isyeri_tescil_parser.py` | **MANTIĞI AL.** Blok bazlı etiket:değer okuma → `core/cikarim/etiketli.py`. **Taşma hatası var**: ünvan bloğa sığmayınca taşan kısım yeni anahtar sanılıyor (`"VE TİCARET LİMİ Vergi No"` diye uydurma anahtar üretiyor, ünvan kesiliyor). Genel taşma birleştirme yaz. |
| `src/unite_karari_parser.py` | **REFERANS.** `_get_lines_from_udf` / `_get_lines_from_pdf` / 250 satırlık durum makinesi → `core/cikarim/serbest.py`'nin girdisi. UDF okuma artık çözülü (yukarı bak), o kısmı sadeleştir. |
| `src/denetim_gerekcesi_parser.py` | **REFERANS.** `is_signature_block` fikri işe yarar (imza bloğunu veriden ayırma). |
| `src/kaza_bildirim_parser.py` | **REFERANS.** Alan listesi için. |
| `src/writer.py` | **DESENİ AL.** `docxtpl` + context sözlüğü kullanımı doğru. Ama tek JSON yerine `case.json`'dan beslenecek. |
| `notes/` | **OKUNDU, bu dosyaya soğuruldu.** `Proje Planlaması.txt` iş kazası karar ağacını içeriyor — Faz 4 kural motoru yazılırken tekrar bak. |
| `src/config.py`, `src/logger.py` | Yeniden yaz, taşınacak değeri yok. |
| Dosya adı desenleri (`IG_PATTERN` vb.) | **TAŞIMA.** Kural 2. |

### `01_PROJECTS/06_JETEK`

**JETEK ayrı bir araç olarak kalır** — birleştirilmeyecek. Belgeleri gruplar,
isimlendirir, EK numarası verir, dizi pusulasını üretir. Bu otomasyonla
sözleşmesi **manifest**.

| Ne | Nerede | Not |
|---|---|---|
| Manifest veri şekli | `frontend/static/js/document-builder.js:98` `gatherOutputFilesData()` | `{file_id, filename, page_count, ek_no, mahiyet}` üretiyor ama **Word'e basıp atıyor**. Kalıcılaştırılması gerek. |
| OOXML tablo doldurma | aynı dosya `:494` `buildDocxFromExistingTemplate()` | Ek listesi üretimi. Desen olarak sağlam. |
| Sayfaya numara basma | aynı dosya `:145` `stampEkNumbers()` | Hiyerarşik alt numara (2/1-7) desteği eklenmeli |
| Bildirimsel şablon konfigürasyonu | `backend/data/templates.json` | Kural 7'nin örneği |
| İlk sayfadan AI sınıflandırma | `backend/services/ai_service.py` | Faz 3 sınıflandırma için desen |

**JETEK'e eklenmesi gerekenler** (bu proje için):
- `manifest.json` çıktısı — ZIP'in içine ve ayrı indirilebilir
- Her belgede `source.original_filename` — **yeniden adlandırma sonrası izlenebilirlik**
- Kümülatif `page_range` — `"Ek-7, s. 3-5"` atıfları için
- `citation_key` — sabit anahtar, numara kayınca atıflar bozulmasın
- Hiyerarşik alt numaralandırma — `Ek:2,2/1-7`

---

## Test verisi

`ornek_veri/` — gerçek ve güncel belgeler. **Gerçek kişisel veri içerir**
(TC, ad-soyad) → `.gitignore`'da, commit edilmez.

**Kök:** `document.pdf` (görev emri) · `DenetimListesi_22.7.2026.xlsx` (4 iş)

**`ornek_veri/ornek_dosya/`** — ana test dosyası. **Eksiksiz değil, bu kasıtlı olarak faydalı:**

| Belge | Durum |
|---|---|
| `262506574.udf` — denetim gerekçesi | ✅ UDF, temiz metin |
| `..._ig.pdf` — işe giriş bildirgesi | ✅ 1 sayfa, metin |
| `..._ia.pdf` — işten ayrılış bildirgesi | ✅ 1 sayfa, metin |
| `..._HizmetDokumuUV.pdf` | ✅ 10 sayfa, metin (raporun 2. tablosu buradan) |
| `tescilBilgi_....pdf` | ✅ 4 sayfa, metin |
| `262506575.pdf` | ❓ 13 sayfa, **metin katmanı yok — tarama.** Muhtemelen denetim gerekçesi ekleri. Faz 5 test malzemesi. |
| `takip_izleme.xlsx` | ❓ içeriği incelenmedi |
| **İş kazası bildirim formu** | ❌ **YOK** |
| **Ünite kararı** | ❌ **YOK** |

Eksik iki belge **kural motorunun (Faz 4) doğal test senaryosu**: eksik belge →
İPC yolu tam olarak burada denenecek. Uydurup tamamlama.

`ornek_dosya_tescilsiz/` klasöründe belge az. Ayrıca bu iş **tescilsiz işveren**
(denetim listesinde tescilli işveren hücresi boş) — ayrı akışın test verisi.

---

## Çalıştırma

```bash
python cli.py kur --girdi ornek_veri
```

Bağımlılık: `pymupdf` — `.venv/bin/python` kullan.
Test verisi `ornek_veri/` altında (14.08.2026'da eski projeden taşındı).

`git` T7 mount'unda sahiplik uyarısı veriyor; ya global `safe.directory` ekle
ya da komut bazında `git -c safe.directory=<repo>` geç.

## Dil

Kod, yorum, commit mesajı, değişken adları: **Türkçe**. Alan adları kurum
terminolojisiyle aynı (`denetim_no`, `sigortalilar`, `isveren`, `ek_no`) —
mevzuat metniyle rapor şablonu arasında çeviri katmanı olmasın.
