"""
etiketli.py — 'Etiket : Değer' düzenindeki belgeleri ayrıştırır.

İşyeri tescil çıktısı bu düzende: iki kolon, her kolonda etiket / ':' / değer
sabit x konumlarında. Hem etiket hem değer bir alt satıra taşabiliyor:

    İşyeri Ünvanı        : ÖRNEK LOJİSTİK NAKLİYAT TAŞIMACILIK SANAYİ
                           VE TİCARET LİMİ                       <- değer taşması
    Faaliyette Bulunduğu : LİMİTED ŞT.
    Sektör                                                       <- etiket taşması
    01 - Ortak AHMET ÖRNEK                                <- bölüm başlığı

Eski projedeki tescil parser'ı taşan satırı yeni bir anahtar sanıyor,
"VE TİCARET LİMİ Vergi No" gibi uydurma alanlar üretiyordu. Buradaki ayrım
konumsal ve belgenin kendisinden ölçülüyor:

  * kolon çapaları  — kelime başlangıç x'lerinin histogramındaki tepeler
  * değer taşması   — satır değer çapasında başlıyor
  * etiket taşması  — satır tümüyle ':' kolonunun solunda kalıyor VE bir
                      önceki alanın hemen altındaki satır
  * bölüm başlığı   — ikisine de uymuyor; `serbest` olarak ayrı tutulur,
                      ortak/yönetici bloklarını bölmek için işe yarar

Aynı etiket birden çok kez geçebilir (her ortak bloğunda 'Mernis No' var).
Bu yüzden sözlük değil **liste** dönüyoruz; düzleştirmek çağıranın kararı.
"""
from __future__ import annotations

from collections import Counter
from dataclasses import dataclass

from core.metin import anahtarla
from core.pdf import Belge, Satir

# Taşma satırı, ait olduğu alanın hemen altında olmalı (punto ~10, satır ~16)
_TASMA_DIKEY_ESIK = 22.0
# Değer taşmasının değer çapasına yatay yakınlığı
_CAPA_TOLERANS = 12.0


@dataclass
class Alan:
    etiket: str          # belgede yazdığı hâliyle
    anahtar: str         # eşleştirme için katlanmış hâli
    deger: str
    sayfa: int
    y: float


@dataclass
class Serbest:
    """Etiket:değer kalıbına uymayan satır — bölüm başlığı, sayfa numarası."""
    metin: str
    sayfa: int
    y: float
    x0: float


@dataclass
class _Kolon:
    etiket_x: float      # etiketlerin sol çapası
    nokta_x: float       # ':' kolonu
    deger_x: float       # değerlerin sol çapası
    sol_sinir: float
    sag_sinir: float


def _tepeler(x_degerleri: list[float], esik: int, tolerans: float = 4.0) -> list[tuple[float, int]]:
    """Yakın x değerlerini kümeler, en az `esik` kez geçenleri (merkez, adet) döndürür."""
    sayac = Counter(round(x) for x in x_degerleri)
    kumeler: list[list[int]] = []
    for x in sorted(sayac):
        if kumeler and x - kumeler[-1][-1] <= tolerans:
            kumeler[-1].append(x)
        else:
            kumeler.append([x])
    out = []
    for k in kumeler:
        adet = sum(sayac[x] for x in k)
        if adet >= esik:
            out.append((sum(sayac[x] * x for x in k) / adet, adet))
    return out


def _kolonlari_olc(belge: Belge) -> tuple[list[_Kolon], list[str]]:
    """Kolon çapalarını belgenin kendi yerleşiminden ölçer."""
    kelimeler = [k for s in belge.sayfalar for k in s.kelimeler]
    noktalar = [k.x0 for k in kelimeler if k.metin == ":"]
    if not noktalar:
        return [], ["etiketli: belgede ':' ayracı yok — bu belge etiket:değer düzeninde değil"]

    nokta_kolonlari = _tepeler(noktalar, esik=max(3, len(noktalar) // 10))
    if not nokta_kolonlari:
        return [], ["etiketli: ':' konumları dağınık, kolon çıkarılamadı"]

    # Çapa sayılmak için kolon başına düşen ':' sayısının dörtte biri kadar
    # tekrar gerekli — böylece rastgele hizalanmış birkaç kelime kolon olmuyor.
    esik = max(5, int(0.25 * (len(noktalar) / len(nokta_kolonlari))))
    guclu = [x for x, _ in _tepeler([k.x0 for k in kelimeler], esik=esik)]

    kolonlar: list[_Kolon] = []
    uyarilar: list[str] = []
    for i, (nx, _) in enumerate(nokta_kolonlari):
        onceki_deger_x = kolonlar[-1].deger_x if kolonlar else -1.0
        etiket_adaylari = [x for x in guclu if onceki_deger_x < x < nx]
        deger_adaylari = [x for x in guclu if x > nx]
        if not etiket_adaylari or not deger_adaylari:
            uyarilar.append(f"etiketli: x={nx:.0f} kolonu için etiket/değer çapası bulunamadı")
            continue
        kolonlar.append(_Kolon(
            etiket_x=min(etiket_adaylari),
            nokta_x=nx,
            deger_x=min(deger_adaylari),
            sol_sinir=min(etiket_adaylari) - _CAPA_TOLERANS,
            sag_sinir=float("inf"),
        ))
    for i in range(len(kolonlar) - 1):
        kolonlar[i].sag_sinir = kolonlar[i + 1].sol_sinir
    if kolonlar:
        kolonlar[0].sol_sinir = 0.0
    return kolonlar, uyarilar


def _dilim(satir: Satir, kol: _Kolon):
    return [k for k in satir.kelimeler if kol.sol_sinir <= k.x0 < kol.sag_sinir]


def _kolon_no(kolonlar: list[_Kolon], nokta) -> int:
    """Bir ':' kelimesini en yakın kolon çapasına eşler."""
    return min(range(len(kolonlar)), key=lambda i: abs(kolonlar[i].nokta_x - nokta.x0))


def ayristir(belge: Belge) -> tuple[list[Alan], list[Serbest], list[str]]:
    """Belgedeki 'Etiket : Değer' çiftlerini ve kalıp dışı satırları döndürür."""
    kolonlar, uyarilar = _kolonlari_olc(belge)
    if not kolonlar:
        return [], [], uyarilar

    alanlar: list[Alan] = []
    serbestler: list[Serbest] = []

    for sayfa in belge.sayfalar:
        son: dict[int, tuple[Alan, float] | None] = {i: None for i in range(len(kolonlar))}

        for satir in sayfa.satirlar():
            noktalar = [(k, _kolon_no(kolonlar, k)) for k in satir.kelimeler if k.metin == ":"]

            if noktalar:
                # Değerin sağ sınırı, satırdaki BİR SONRAKİ ':' kolonudur.
                # Sonraki kolonda ':' yoksa değer satır sonuna kadar uzar —
                # "İş Kolu Kodu"nun uzun açıklaması sayfanın tamamını kaplıyor
                # ve kolon sınırında kesilmemeli.
                for sira, (nokta, i) in enumerate(noktalar):
                    kol = kolonlar[i]
                    sag = (kolonlar[noktalar[sira + 1][1]].sol_sinir
                           if sira + 1 < len(noktalar) else float("inf"))
                    etiket = " ".join(k.metin for k in satir.kelimeler
                                      if kol.sol_sinir <= k.x0 and k.x1 <= nokta.x0)
                    deger = " ".join(k.metin for k in satir.kelimeler
                                     if nokta.x1 <= k.x0 < sag)
                    if not etiket:
                        serbestler.append(Serbest(satir.metin, sayfa.no, satir.y0,
                                                  satir.kelimeler[0].x0))
                        uyarilar.append(f"etiketli: s.{sayfa.no} y={satir.y0:.0f} — "
                                        f"':' var ama etiket yok ({deger[:40]!r})")
                        son[i] = None
                        continue
                    alan = Alan(etiket, anahtarla(etiket), deger, sayfa.no, satir.y0)
                    alanlar.append(alan)
                    son[i] = (alan, satir.y1)
                continue

            # ':' yok — taşma mı, kalıp dışı satır mı? Kolon kolon bakılır.
            for i, kol in enumerate(kolonlar):
                icerik = _dilim(satir, kol)
                if not icerik:
                    continue
                onceki = son[i]
                bitis = max(k.x1 for k in icerik)
                bitisik = onceki is not None and (satir.y0 - onceki[1]) < _TASMA_DIKEY_ESIK
                parca = " ".join(k.metin for k in icerik)

                if bitisik and abs(icerik[0].x0 - kol.deger_x) <= _CAPA_TOLERANS:
                    onceki[0].deger = (onceki[0].deger + " " + parca).strip()
                    son[i] = (onceki[0], satir.y1)
                elif bitisik and bitis <= kol.nokta_x:
                    onceki[0].etiket = (onceki[0].etiket + " " + parca).strip()
                    onceki[0].anahtar = anahtarla(onceki[0].etiket)
                    son[i] = (onceki[0], satir.y1)
                else:
                    serbestler.append(Serbest(parca, sayfa.no, satir.y0, icerik[0].x0))
                    son[i] = None   # bölüm değişti, taşma zinciri kopsun

    return alanlar, serbestler, uyarilar


def sozluk(alanlar: list[Alan]) -> tuple[dict[str, str], list[str]]:
    """Alan listesini anahtar->değer sözlüğüne indirger.

    Aynı anahtar tekrar ediyorsa ilki alınır ve uyarı üretilir — sessizce
    üzerine yazmak veri kaybıdır.
    """
    out: dict[str, str] = {}
    tekrar: Counter = Counter()
    for a in alanlar:
        if a.anahtar in out:
            tekrar[a.anahtar] += 1
            continue
        out[a.anahtar] = a.deger
    uyarilar = [f"etiketli: {a!r} belgede {n + 1} kez geçiyor, ilki alındı"
                for a, n in tekrar.items()]
    return out, uyarilar
