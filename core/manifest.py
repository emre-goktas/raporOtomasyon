"""JETEK manifest'i — `(Ek:7)` atıflarının tek kaynağı.

JETEK belgeleri gruplar, yeniden adlandırır ve her birine bir Ek numarası
verir; o numarayı bugüne kadar yalnızca insanın okuduğu Word pusulasına
basıyordu. `manifest.json` aynı bilgiyi makine okunur biçimde ZIP'in içine
yazar — bu modül onu okuyup `belgeler[]` ile eşler, böylece raporda
`{{ek:isyeri_tescil}}` yazan yer tutucu `(Ek:7)` olarak basılır.

**Eşleme dosya adına bakar ama dosya adına *güvenmez*.** Kural 2 dosya adı
desenlerini yasaklıyor; buradaki kullanım o yasağın kapsamına girmiyor, çünkü
desen tahmin edilmiyor: manifest'in kendisi hangi dosyanın hangi ek olduğunu
*açıkça yazıyor*, biz yalnızca o beyanı okuyoruz. Belge türü yine içerikten
tanınıyor (`core/belge.py`); manifest sadece numarayı söylüyor.

İki eşleme yolu var, çünkü belgeler bize iki farklı hâlde gelebiliyor:

  1. JETEK ZIP'inden çıkmış hâli — dosya adı `07_Isyeri_Tescil.pdf`,
     manifest'teki `dosya` ile birebir aynı.
  2. Kurumdan indirilmiş ham hâli — dosya adı `tescilBilgi_92063506.pdf`.
     JETEK bunu `kaynak.dosya_adi` olarak sakladığı için ham klasör de
     eşleşiyor; belgeleri JETEK'ten geçirmeden önce de ek numarası biliniyor.

Manifest'in beyan ettiği sayfa adedi ayrıca bedava bir doğrulamadır (kural 6):
tutmuyorsa ya yanlış dosya eşleşti ya da elimizdeki kopya eksik.
"""
from __future__ import annotations

import json
from pathlib import Path

DOSYA_ADI = "manifest.json"
SURUM = 1


def bul(*dizinler: Path) -> Path | None:
    """Verilen dizinlerde manifest dosyasını arar, ilk bulduğunu döndürür."""
    for d in dizinler:
        if d is None:
            continue
        aday = d / DOSYA_ADI
        if aday.is_file():
            return aday
    return None


def oku(yol: Path) -> tuple[list[dict], list[str]]:
    """manifest.json → (ekler, uyarılar). Bozuk dosya sessizce boş dönmez."""
    uyarilar: list[str] = []
    try:
        veri = json.loads(yol.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as e:
        return [], [f"manifest okunamadı ({yol.name}): {e}"]

    if not isinstance(veri, dict):
        return [], [f"manifest beklenen biçimde değil: {yol}"]

    surum = veri.get("surum")
    if surum != SURUM:
        # Okumayı denemeye devam ediyoruz — alanlar tanıdıksa çalışır — ama
        # sessizce değil: sürüm farkı ileride biçim değiştiğinin tek işareti.
        uyarilar.append(f"manifest sürümü {surum!r}, beklenen {SURUM} — biçim değişmiş olabilir")

    ekler = veri.get("ekler")
    if not isinstance(ekler, list) or not ekler:
        uyarilar.append(f"manifest'te ek listesi yok: {yol}")
        return [], uyarilar

    return ekler, uyarilar


def _adlar(ek: dict) -> set[str]:
    """Bir ek girdisinin eşleşebileceği dosya adları."""
    adlar = {ek.get("dosya")}
    kaynak = ek.get("kaynak") or {}
    adlar.add(kaynak.get("dosya_adi"))
    return {a for a in adlar if a}


def bagla(belgeler: list[dict], ekler: list[dict]) -> tuple[list[str], list[str]]:
    """`belgeler[].ek_no` alanlarını manifest'ten doldurur.

    Belgeleri yerinde değiştirir, `(uyarilar, bilgiler)` döndürür.

    İkisinin ayrı olması kasıtlı. Elimizdeki bir belgenin manifest'te
    karşılığı yoksa **uyarı**: o belgeye rapordan atıf yapılamayacak.
    Manifest'teki bir ekin klasörde karşılığı yoksa **bilgi**: manifest ZIP'in
    tamamını anlatır, biz ise yalnızca çıkarım yaptığımız PDF'leri
    topluyoruz — görev emri başka yerden okunuyor, denetim gerekçesi UDF,
    ifade tutanağı taranmış. Bunları uyarı saymak her çalıştırmada üç dört
    yanlış alarm üretir; birkaç kez yanlış alarm veren uyarı okunmaz olur ve
    o listedeki *gerçek* uyarıyı da beraberinde götürür.
    """
    uyarilar: list[str] = []
    bilgiler: list[str] = []
    ad_ek: dict[str, dict] = {}
    for ek in ekler:
        for ad in _adlar(ek):
            ad_ek.setdefault(ad, ek)

    eslesen_ek: set[int] = set()
    for b in belgeler:
        ad = (b.get("kaynak") or {}).get("dosya_adi")
        ek = ad_ek.get(ad)
        if ek is None:
            b["ek_no"] = None
            uyarilar.append(f"manifest: {ad!r} ek listesinde yok — ek numarası atanmadı")
            continue

        b["ek_no"] = ek.get("ek_no")
        eslesen_ek.add(id(ek))

        beyan = ek.get("sayfa_adedi")
        okunan = (b.get("kaynak") or {}).get("sayfa_sayisi")
        if beyan and okunan and beyan != okunan:
            uyarilar.append(
                f"manifest: Ek:{ek.get('ek_no')} ({ad}) {beyan} sayfa beyan ediyor, "
                f"elimizdeki kopya {okunan} sayfa")

    for ek in ekler:
        if id(ek) not in eslesen_ek:
            bilgiler.append(
                f"Ek:{ek.get('ek_no')} {ek.get('mahiyet')} — bu klasörde yok, "
                f"atıfı yine de çözülür ({ek.get('citation_key')})")

    return uyarilar, bilgiler


def ek_haritasi(belgeler: list[dict], ekler: list[dict] | None) -> dict[str, int]:
    """Rapor render'ının `{{ek:...}}` çözümlemesi için anahtar → ek_no.

    İki anahtar kümesi birleşir: tanınan belgelerin `tur`'ü (`isyeri_tescil`)
    ve manifest'in `citation_key`'i (`ifade-tutanagi`). İkincisi olmadan
    yalnızca içerikten tanıyabildiğimiz belgelere atıf yapılabilirdi —
    oysa raporun atıf yaptığı belgelerin çoğu (ifade, bilirkişi raporu,
    olay yeri tutanağı) hiçbir zaman deterministik olarak tanınmayacak.
    """
    harita: dict[str, int] = {}
    for ek in ekler or []:
        anahtar, no = ek.get("citation_key"), ek.get("ek_no")
        if anahtar and no is not None:
            harita[anahtar] = no
    for b in belgeler:
        if b.get("tur") and b.get("ek_no") is not None:
            harita[b["tur"]] = b["ek_no"]
        if b.get("citation_key") and b.get("ek_no") is not None:
            harita.setdefault(b["citation_key"], b["ek_no"])
    return harita
