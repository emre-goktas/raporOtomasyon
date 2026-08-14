"""
satir.py — Satır içi 'Etiket: Değer' düzeni (kurum yazışmaları).

Denetim gerekçesi ve ünite kararı bu düzende: tek kolon, ':' etiketin hemen
ardında, yani sabit bir x kolonu yok. `etiketli.py` sabit kolonlu tescil
çıktısı için yazıldı ve buraya uymuyor; ayrım gerçek ve ölçüldü:

    tescil          ':' x konumları  ->  {123, 461}      iki net kolon
    ünite kararı    ':' x konumları  ->  80..332 arası dağınık

Burada geometri bilgi taşımıyor, **satırın kendisi taşıyor**: ilk ':' solu
etiket, sağı değer. Değer alt satıra taşarsa (kazanın oluş şekli iki satır
sürüyor) `coksatir: true` ile toplanır; bölüm başlıkları (A-İŞVEREN,
E-SONUÇ ve KANAAT) ve elektronik imza altbilgisi toplamayı durdurur.

'12:40' gibi değer içindeki ':' sorun değil — ayrım **ilk** ':' üzerinden.
"""
from __future__ import annotations

import re

from core.metin import anahtarla
from core.pdf import Belge

# Her kurum yazısının altında duran e-imza bloğu — veri değil
_ALTBILGI = ("bu belge, guvenli elektronik imza", "dogrulama kodu:", "adres:",
             "telefon:", "faks:", "e-posta:", "bilgi icin:")
# Değeri "kapalı" sayan bitişler: cümle bitmiş, alt satır devamı değildir
_KAPALI = re.compile(r"[.)\]]\s*$")


def _altbilgi_mi(satir: str) -> bool:
    a = anahtarla(satir)
    return any(a.startswith(x) for x in _ALTBILGI)


def _baslik_mi(satir: str) -> bool:
    """Bölüm başlığı mı? Ölçüt büyük harf oranı — 'C-KARAR (DAYANAĞI OLAN
    BELGELER)' başlık, 'b-Kaza sonrası ilk müracaat edilen sağlık' değil."""
    harfler = [c for c in satir if c.isalpha()]
    if len(harfler) < 4:
        return False
    return sum(c.isupper() for c in harfler) / len(harfler) >= 0.8


def _acik_mi(deger: str) -> bool:
    """Değer alt satırda devam ediyor olabilir mi?

    'İnşaatın ... dengesini' devam ediyor; 'B cetveli XIII Düz işçiler 1
    (Benzetilerek)' bitmiş, altındaki satır yeni bir etiketin ön parçasıdır.
    """
    d = deger.strip()
    return bool(d) and d != "---" and not _KAPALI.search(d)


def satirlari_topla(belge: Belge) -> list[tuple[int, float, float, float, str]]:
    """(sayfa, y0, y1, x0, metin) — altbilgi ve sayfa numarası atılmış."""
    out = []
    for sayfa in belge.sayfalar:
        for s in sayfa.satirlar():
            m = s.metin.strip()
            if m and not _altbilgi_mi(m) and not re.fullmatch(r"\d+\s*/\s*\d+", m):
                out.append((sayfa.no, s.y0, s.y1, min(k.x0 for k in s.kelimeler), m))
    return out


def ayristir(belge: Belge) -> tuple[dict[str, str], dict[str, str], list[str]]:
    """(anahtar -> değer, bölüm başlığı -> altındaki serbest metin, uyarılar).

    ':' içermeyen satır üç şeyden biri olabilir; ayrım şöyle yapılır:
      * büyük harf oranı yüksekse           -> bölüm başlığı
      * önceki değer 'açık' kaldıysa        -> o değerin devamı
      * aksi hâlde                          -> bir sonraki etiketin ön parçası
        (D-HASTANE bölümünde etiketler iki satıra bölünüyor)
    """
    alanlar: dict[str, str] = {}
    bloklar: dict[str, list[str]] = {}
    uyarilar: list[str] = []
    son: str | None = None            # en son doldurulan alan
    son_baslik: str | None = None
    tampon: list[tuple[int, float, float, float, str]] = []   # bekleyen satırlar

    satirlar = satirlari_topla(belge)
    # Bir etiketin ön parçası, etiket satırına **bitişik** olur. İmza bloğu
    # ("Ahmet PAR" / "Sosyal Güvenlik İl Müdür Yardımcısı") aşağıdaki "Ek:"
    # satırından uzakta durur; bitişiklik ölçüsü ikisini ayırır.
    yukseklik = [y1 - y0 for _, y0, y1, _, _ in satirlar]
    bitisik_esik = 1.8 * (sorted(yukseklik)[len(yukseklik) // 2] if yukseklik else 12.0)

    def _tamponu_bosalt(hedef_bitisik: bool):
        """Bekleyen satırları etikete değil, ait olduğu yere yazar."""
        nonlocal tampon
        if not tampon:
            return []
        if hedef_bitisik:
            alinan, tampon = [t[4] for t in tampon], []
            return alinan
        for t in tampon:
            if son_baslik is not None:
                bloklar[son_baslik].append(t[4])
            else:
                bloklar.setdefault("_ust", []).append(t[4])
        tampon = []
        return []

    for sayfa_no, y0, y1, x0, ham in satirlar:
        if _baslik_mi(ham):
            _tamponu_bosalt(False)
            son, son_baslik = None, ham
            bloklar.setdefault(ham, [])
            continue

        # Ayraç normalde ':'. Bir müdürlük "İşyeri Sicil Numarası ;" yazmış;
        # ';' yalnızca satırda hiç ':' yoksa denenir — aksi hâlde ünite
        # kararındaki "...durumu; yapıldı ise tarihleri :" etiketi bölünürdü.
        ayrac = ":" if ":" in ham else (";" if ";" in ham else None)
        if ayrac:
            etiket, _, deger = ham.partition(ayrac)   # değerdeki '12:40' bozmasın
            # Ön parça hem dikeyde bitişik hem de aynı sol hizada olmalı:
            # antet ortalanmış (x≈197), etiketler sola dayalı (x≈41).
            bitisik = (bool(tampon) and (y0 - tampon[-1][2]) <= bitisik_esik
                       and all(abs(t[3] - x0) <= 6.0 for t in tampon))
            onek = _tamponu_bosalt(bitisik)
            etiket = re.sub(r"\s+", " ", " ".join(onek + [etiket])).strip()
            if not etiket:
                uyarilar.append(f"satir: etiketsiz ':' satırı — {ham[:50]!r}")
                son = None
                continue
            anahtar = anahtarla(etiket)
            if anahtar in alanlar:
                uyarilar.append(f"satir: {etiket!r} birden çok kez geçiyor, ilki alındı")
                son = None
                continue
            alanlar[anahtar] = deger.strip()
            son = anahtar
            continue

        if son is not None and _acik_mi(alanlar[son]) and not tampon:
            alanlar[son] = f"{alanlar[son]} {ham}".strip()
        else:
            tampon.append((sayfa_no, y0, y1, x0, ham))   # sonraki etiketin ön parçası olabilir

    _tamponu_bosalt(False)

    return alanlar, {k: " ".join(v).strip() for k, v in bloklar.items() if v}, uyarilar


def ham_sozluk(alanlar: dict[str, str], bloklar: dict[str, str]) -> dict[str, str]:
    """Şema katmanına verilecek tek sözlük. Bölüm blokları '@' önekiyle
    görünür, böylece YAML `etiket: "@REHBERLİK VE TEFTİŞ BAŞKANLIĞINA"` diyerek
    başlık altındaki serbest metni de alan gibi kullanabilir."""
    out = dict(alanlar)
    for baslik, metin in bloklar.items():
        out[anahtarla("@" + baslik)] = metin
    return out
