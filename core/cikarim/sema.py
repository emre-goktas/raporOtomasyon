"""
sema.py — Belge tanımlarını (YAML) okur ve ham alanları tiplendirir.

Motor genel, belge bilgisi konfigürasyonda (kural 7). Bir belge türü eklemek
`domains/<ad>/cikarim/<belge>.yaml` yazmaktır; Python'a dokunulmaz.

    belge_turu: isyeri_tescil
    motor: etiketli
    tanima:
      gerekli_anahtarlar: ["İş Yeri Sicil No", "İşyeri Ünvanı"]
    alanlar:
      sicil_no: { etiket: "İş Yeri Sicil No", tip: metin, zorunlu: true }
      unvan:    { etiket: "İşyeri Ünvanı", tip: metin, kirpma_esigi: 60 }
      tescil_tarihi: { etiket: "Kan.Kap. Alınış Tar", tip: tarih }

Alan bulunamazsa değeri None kalır **ve uyarı üretilir**; zorunlu alan
eksikse uyarı ayrıca 'zorunlu' diye işaretlenir. Sessizce boş geçmek yok.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from decimal import Decimal
from pathlib import Path

from core.metin import anahtarla, ondalik, rakamlar, tarih_bul, tc_gecerli

# Kurum sistemi metin alanlarını sabit uzunlukta kırpıyor: işveren ünvanı
# hem denetim listesinde hem tescil çıktısında tam 60 karakterde kesiliyor
# ("...SANAYİ VE TİCARET LİMİ"). Tam uzunluk = kırpılmış olma şüphesi.
def _kirpma_uyarisi(ad: str, deger: str, esik: int | None) -> str | None:
    if esik and len(deger) == esik:
        return (f"{ad}: değer tam {esik} karakter — kurum sistemi kırpmış olabilir, "
                f"tam metni başka belgeden doğrula ({deger[-18:]!r})")
    return None


def _t_metin(ham: str, ad: str):
    return re.sub(r"\s+", " ", ham).strip() or None, None


def _t_rakam(ham: str, ad: str):
    """Yalnız rakam: '2 0000 01' -> '2000001'. Biçimi korumak için tip: metin kullan."""
    r = rakamlar(ham)
    if not r:
        return None, f"{ad}: rakam bulunamadı ({ham!r})"
    return r, None


def _t_tamsayi(ham: str, ad: str):
    r = rakamlar(ham)
    if not r:
        return None, f"{ad}: sayı bulunamadı ({ham!r})"
    return int(r), None


def _t_tarih(ham: str, ad: str):
    iso, uyari = tarih_bul(ham)
    if iso is None and uyari is None:
        return None, f"{ad}: tarih bulunamadı ({ham!r})"
    return iso, (f"{ad}: {uyari}" if uyari else None)


def _t_ondalik(ham: str, ad: str):
    d, uyari = ondalik(ham, alan=ad)
    return (str(d) if isinstance(d, Decimal) else None), uyari


def _t_eposta(ham: str, ad: str):
    """Satır kırılmasıyla araya giren boşluğu kapatır: 'ad@g mail.com'."""
    s = re.sub(r"\s+", "", ham)
    if not s:
        return None, None
    if "@" not in s:
        return s, f"{ad}: '@' yok, e-posta gibi durmuyor ({ham!r})"
    return s, None


def _t_tc(ham: str, ad: str):
    r = rakamlar(ham)
    if not r:
        return None, f"{ad}: TC bulunamadı ({ham!r})"
    if not tc_gecerli(r):
        return r, f"{ad}: TC sağlama tutmuyor ({r}) — kaynağı doğrula"
    return r, None


def _t_mevcut(ham: str, ad: str):
    """'Mevcut ( X ) Mevcut değil ( )' -> True/False. Ünite kararındaki
    belge var/yok kutucukları; Faz 4'ün eksik belge kuralını besler."""
    m = re.search(r"mevcut\s*\(\s*(x?)\s*\).*?de[gğ]il\s*\(\s*(x?)\s*\)",
                  ham, re.IGNORECASE | re.DOTALL)
    if not m:
        return None, f"{ad}: 'Mevcut ( ) Mevcut değil ( )' kalıbı bulunamadı ({ham[:50]!r})"
    var, yok = bool(m.group(1)), bool(m.group(2))
    if var == yok:
        return None, (f"{ad}: kutucukların ikisi de {'işaretli' if var else 'boş'} "
                      f"({ham[:50]!r})")
    return var, None


_TIPLER = {
    "metin": _t_metin, "rakam": _t_rakam, "tamsayi": _t_tamsayi,
    "tarih": _t_tarih, "ondalik": _t_ondalik, "eposta": _t_eposta, "tc": _t_tc,
    "mevcut": _t_mevcut,
}


@dataclass
class AlanTanimi:
    ad: str
    etiket: str | None = None
    etiketler: list[str] = field(default_factory=list)
    tip: str = "metin"
    zorunlu: bool = False
    kirpma_esigi: int | None = None
    # Ham değerin içinden parça almak için regex; ilk yakalama grubu kullanılır.
    # "Of – 20.03.1971" tek alanda iki bilgi taşıyor, ikisi ayrı alana gitsin.
    desen: str | None = None
    # Etiketi tam metinle değil kelimeyle yakala. Her SGK müdürlüğü aynı alanı
    # başka türlü yazıyor ("Kaza Tarihi" / "Tespit Tarihi" / "5- Olay Tarihi");
    # hepsinde geçen kelimeyi vermek, varyantları tek tek saymaktan sağlam.
    anahtar_kelimeler: list[str] = field(default_factory=list)
    # Alan belgede meşru olarak bulunmayabilir (ölüm tarihi yalnız ölümlü
    # olaylarda var). Desen tutmazsa uyarı üretilmez, alan None kalır.
    kosullu: bool = False
    # Motora özel anahtarlar (form motorunda capa/yon/bosluk_esigi gibi).
    # Şema bunları yorumlamaz, ilgili motora olduğu gibi geçer.
    ek: dict = field(default_factory=dict)

    @property
    def adaylar(self) -> list[str]:
        return [e for e in ([self.etiket] if self.etiket else []) + self.etiketler if e]


@dataclass
class BelgeTanimi:
    belge_turu: str
    motor: str
    alanlar: list[AlanTanimi]
    tanima: dict
    yol: Path | None = None


def yukle(yaml_yolu) -> BelgeTanimi:
    import yaml as _yaml

    yol = Path(yaml_yolu)
    ham = _yaml.safe_load(yol.read_text(encoding="utf-8")) or {}
    eksik = [a for a in ("belge_turu", "motor") if a not in ham]
    # Tablo motorunda alan listesi isteğe bağlı: çıktı satır listesidir,
    # kolonlar 'tablo.kolonlar' altında tanımlanır.
    if ham.get("motor") != "tablo" and "alanlar" not in ham:
        eksik.append("alanlar")
    if eksik:
        raise ValueError(f"{yol}: zorunlu anahtar eksik: {eksik}")
    if ham.get("motor") == "tablo" and not ham.get("tablo"):
        raise ValueError(f"{yol}: motor 'tablo' ama 'tablo:' bloğu yok")

    alanlar = []
    for ad, tanim in (ham.get("alanlar") or {}).items():
        tanim = tanim or {}
        tip = tanim.get("tip", "metin")
        if tip not in _TIPLER:
            raise ValueError(f"{yol}: {ad} alanında bilinmeyen tip {tip!r} "
                             f"(geçerli: {sorted(_TIPLER)})")
        bilinen = {"etiket", "etiketler", "tip", "zorunlu", "kirpma_esigi", "desen", "anahtar_kelimeler", "kosullu"}
        alanlar.append(AlanTanimi(
            ad=ad, etiket=tanim.get("etiket"), etiketler=tanim.get("etiketler") or [],
            tip=tip, zorunlu=bool(tanim.get("zorunlu")),
            kirpma_esigi=tanim.get("kirpma_esigi"), desen=tanim.get("desen"),
            anahtar_kelimeler=tanim.get("anahtar_kelimeler") or [],
            kosullu=bool(tanim.get("kosullu")),
            ek={k: v for k, v in tanim.items() if k not in bilinen},
        ))
    return BelgeTanimi(ham["belge_turu"], ham["motor"], alanlar,
                       ham.get("tanima") or {}, yol)


def yukle_domain(domain_dizini) -> dict[str, BelgeTanimi]:
    """domains/<ad>/cikarim/*.yaml -> {belge_turu: BelgeTanimi}"""
    dizin = Path(domain_dizini) / "cikarim"
    if not dizin.is_dir():
        return {}
    out = {}
    for y in sorted(dizin.glob("*.yaml")):
        t = yukle(y)
        if t.belge_turu in out:
            raise ValueError(f"{y}: '{t.belge_turu}' belge türü zaten "
                             f"{out[t.belge_turu].yol} içinde tanımlı")
        out[t.belge_turu] = t
    return out


def uygula(tanim: BelgeTanimi, ham: dict[str, str]) -> tuple[dict, list[str]]:
    """Ham {anahtar: değer} sözlüğünü tanıma göre tiplendirir."""
    sonuc: dict = {}
    uyarilar: list[str] = []

    for a in tanim.alanlar:
        if a.kosullu and a.zorunlu:
            uyarilar.append(f"{tanim.belge_turu}: {a.ad} hem 'kosullu' hem 'zorunlu' "
                            f"olamaz — zorunluluk yok sayıldı")
        bulunan = None
        adaylar = a.adaylar or [a.ad]
        for aday in adaylar:
            if (v := ham.get(anahtarla(aday))) is not None and str(v).strip():
                bulunan = str(v)
                break

        # Tam eşleşme yoksa benzersiz alt dize: kurum yazılarında etiket iki
        # satıra bölünebiliyor ve önündeki parça anahtara karışıyor
        # ("(Uzuv kaybı varsa...) e-Kaza geçirdiği işyerinde ... raporları").
        if bulunan is None and a.anahtar_kelimeler:
            kelimeler = [anahtarla(x) for x in a.anahtar_kelimeler]
            esler = [(ad, v) for ad, v in ham.items()
                     if str(v).strip() and all(k in ad for k in kelimeler)]
            if len(esler) == 1:
                bulunan = str(esler[0][1])
            elif len(esler) > 1:
                uyarilar.append(f"{tanim.belge_turu}: {a.ad} — {a.anahtar_kelimeler} "
                                f"{len(esler)} etikete uyuyor, atlandı "
                                f"({[e[0][:30] for e in esler[:3]]})")

        if bulunan is None:
            for aday in adaylar:
                k = anahtarla(aday)
                esler = [(ad, v) for ad, v in ham.items() if k in ad and str(v).strip()]
                if len(esler) == 1:
                    bulunan = str(esler[0][1])
                    break
                if len(esler) > 1:
                    uyarilar.append(f"{tanim.belge_turu}: {a.ad} — {aday!r} "
                                    f"{len(esler)} etikete uyuyor, atlandı "
                                    f"({[e[0][:28] for e in esler[:3]]})")
                    break

        if bulunan is None:
            sonuc[a.ad] = None
            etiket = " / ".join(a.adaylar) or a.ad
            # "etiket belgede yok" ile "etiket var ama değeri boş" ayrı şeyler:
            # ilki biçim değişikliğine işaret eder (her zaman uyarı), ikincisi
            # çoğu zaman gerçekten boş bir alandır (yalnız zorunluysa uyarı).
            varmis = any(anahtarla(x) in ham for x in (a.adaylar or [a.ad]))
            if not varmis:
                uyarilar.append(
                    f"{tanim.belge_turu}: {a.ad} — '{etiket}' etiketi belgede hiç yok"
                    + (" [ZORUNLU]" if a.zorunlu else ""))
            elif a.zorunlu:
                uyarilar.append(f"{tanim.belge_turu}: {a.ad} — '{etiket}' var ama "
                                f"değeri boş [ZORUNLU]")
            continue

        if a.desen:
            m = re.search(a.desen, bulunan)
            if not m:
                sonuc[a.ad] = None
                if not a.kosullu:
                    uyarilar.append(f"{tanim.belge_turu}: {a.ad} — değer {a.desen!r} "
                                    f"desenine uymadı ({bulunan[:60]!r})")
                continue
            bulunan = m.group(1) if m.groups() else m.group(0)

        deger, uyari = _TIPLER[a.tip](bulunan, f"{tanim.belge_turu}.{a.ad}")
        sonuc[a.ad] = deger
        if uyari:
            uyarilar.append(uyari)
        if k := _kirpma_uyarisi(f"{tanim.belge_turu}.{a.ad}", bulunan, a.kirpma_esigi):
            uyarilar.append(k)

    return sonuc, uyarilar
