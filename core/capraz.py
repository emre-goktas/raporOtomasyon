"""
capraz.py — Aynı bilgiyi birden çok kaynakta karşılaştırır (kural 6).

İşyeri sicil no hem denetim listesinde, hem tescil PDF'inde, hem bildirgede
var. Üçü uyuşuyorsa güven yüksek; uyuşmuyorsa **işaretlenir, insana sorulur** —
otomatik bir tanesi seçilmez. Excel verisi güvenilmez, Emre birkaç kez TC ve
sicil düzelttirmiş.

Karşılaştırmalar biçim farkına takılmayacak şekilde normalize edilir:
sicil numarası kurumun üç ayrı yazımıyla geliyor

    denetim listesi : 2 0000 01 01 1000000 027 09-51
    tescil          : 2 0000 01 01 1000000 027 09-51 000 001
    bildirge        : 2 0000 1 1 1000000 27 9 9 0        (baştaki sıfırlar yok)

ortak ve kimliklendirici kısım 7 haneli işyeri sıra numarasıdır; kıyas onun
ve iş kolu kodunun üzerinden yapılır.
"""
from __future__ import annotations

import re

from core.metin import anahtarla, rakamlar


def _sicil_cekirdegi(s: str | None) -> tuple[str, str] | None:
    """Sicil dizesinden (iş kolu, işyeri sıra no) çekirdeğini çıkarır."""
    if not s:
        return None
    parcalar = re.findall(r"\d+", s)
    if len(parcalar) < 3:
        return None
    is_kolu = next((p for p in parcalar if len(p) == 4), None)
    sira = max(parcalar, key=len)
    if not is_kolu or len(sira) < 6:
        return None
    return is_kolu, sira.lstrip("0")


def _unvan_uyumu(a: str, b: str) -> bool:
    """Kurum sistemi ünvanı farklı uzunluklarda kırpıyor; kısası uzunun
    başlangıcıysa uyumlu sayılır."""
    ka, kb = anahtarla(a), anahtarla(b)
    kisa, uzun = (ka, kb) if len(ka) <= len(kb) else (kb, ka)
    return uzun.startswith(kisa)


def _ekle(uyarilar: list[str], konu: str, degerler: dict[str, str]) -> None:
    farkli = {k: v for k, v in degerler.items() if v}
    if len({*farkli.values()}) > 1:
        detay = "  |  ".join(f"{k}={v!r}" for k, v in farkli.items())
        uyarilar.append(f"çapraz: {konu} kaynaklar arasında UYUŞMUYOR — {detay}")


def dogrula(case: dict, belgeler: list[dict]) -> list[str]:
    """case.json künyesi ile belgelerden çıkan alanları karşılaştırır."""
    uyarilar: list[str] = []
    tur = {}
    for b in belgeler:
        if b.get("tur"):
            tur.setdefault(b["tur"], b)

    ig = tur.get("ise_giris_bildirgesi", {}).get("alanlar", {})
    ia = tur.get("isten_ayrilis_bildirgesi", {}).get("alanlar", {})
    tescil = tur.get("isyeri_tescil", {}).get("alanlar", {})
    hizmet = tur.get("hizmet_dokumu", {}).get("satirlar", [])

    # --- sigortalı kimliği ---
    sigortalilar = case.get("sigortalilar") or []
    liste_tc = rakamlar(sigortalilar[0].get("tc")) if sigortalilar else ""
    _ekle(uyarilar, "sigortalı TC", {
        "denetim listesi": liste_tc,
        "işe giriş bildirgesi": rakamlar(ig.get("tc")),
        "işten ayrılış bildirgesi": rakamlar(ia.get("tc")),
    })

    if sigortalilar and (ig.get("ad") or ia.get("ad")):
        liste_ad = anahtarla(sigortalilar[0].get("ad_soyad") or "")
        for etiket, kaynak in (("işe giriş", ig), ("işten ayrılış", ia)):
            if kaynak.get("ad") and kaynak.get("soyad"):
                belge_ad = anahtarla(f"{kaynak['ad']} {kaynak['soyad']}")
                if liste_ad and belge_ad != liste_ad:
                    uyarilar.append(f"çapraz: sigortalı adı UYUŞMUYOR — "
                                    f"denetim listesi={sigortalilar[0]['ad_soyad']!r}  |  "
                                    f"{etiket} bildirgesi="
                                    f"{kaynak['ad']} {kaynak['soyad']!r}")

    # --- işyeri kimliği ---
    isveren = case.get("isveren") or {}
    cekirdekler = {
        "denetim listesi": _sicil_cekirdegi(isveren.get("sicil_no")),
        "tescil": _sicil_cekirdegi(tescil.get("sicil_no")),
        "işe giriş bildirgesi": _sicil_cekirdegi(ig.get("isyeri_sicil_hucreler")),
        "işten ayrılış bildirgesi": _sicil_cekirdegi(ia.get("isyeri_sicil_hucreler")),
    }
    _ekle(uyarilar, "işyeri sicil no (iş kolu + sıra no)",
          {k: "-".join(v) for k, v in cekirdekler.items() if v})

    unvanlar = {
        "denetim listesi": isveren.get("unvan"),
        "tescil": tescil.get("unvan"),
        "işe giriş bildirgesi": ig.get("isveren_unvan"),
        "işten ayrılış bildirgesi": ia.get("isveren_unvan"),
    }
    unvanlar = {k: v for k, v in unvanlar.items() if v}
    if len(unvanlar) > 1:
        temel_ad, temel = max(unvanlar.items(), key=lambda p: len(p[1]))
        for ad, v in unvanlar.items():
            if ad != temel_ad and not _unvan_uyumu(temel, v):
                uyarilar.append(f"çapraz: işveren ünvanı UYUŞMUYOR — "
                                f"{temel_ad}={temel!r}  |  {ad}={v!r}")

    # --- tarih tutarlılığı ---
    if (giris := ig.get("ise_baslama_tarihi")) and (cikis := ia.get("ayrilis_tarihi")):
        if cikis < giris:
            uyarilar.append(f"çapraz: işten ayrılış tarihi ({cikis}) işe giriş "
                            f"tarihinden ({giris}) önce")

    if hizmet and (isyeri := _sicil_cekirdegi(tescil.get("sicil_no") or
                                              isveren.get("sicil_no"))):
        ilgili = [s for s in hizmet if s.get("isyeri_no")
                  and s["isyeri_no"].lstrip("0") == isyeri[1]]
        if not ilgili:
            uyarilar.append(f"çapraz: hizmet dökümünde {isyeri[1]} numaralı işyerine "
                            f"ait hiç kayıt yok — sigortalı bu işyerinde görünmüyor")
        else:
            donemler = sorted(s["donem"] for s in ilgili if s.get("donem"))
            if giris := ig.get("ise_baslama_tarihi"):
                beklenen = f"{giris[:4]}/{giris[5:7]}"
                if donemler and donemler[0] > beklenen:
                    uyarilar.append(
                        f"çapraz: işe giriş bildirgesi {giris} diyor ama hizmet "
                        f"dökümünde bu işyerinin ilk dönemi {donemler[0]} — "
                        f"aradaki dönemler bildirilmemiş olabilir")

    return uyarilar
