"""
render.py — Bölüm YAML'ını case.json ile doldurup metne çevirir.

Akış: blokları sırayla gez → koşulu değerlendir → tutuyorsa yer tutucuları
doldur. Koşul tutmuyorsa blok hiç basılmaz; belirlenemiyorsa da basılmaz ama
uyarı üretilir.

Bilinmeyen ya da boş yer tutucu **sessizce silinmez** — `‹alan?›` olarak
metinde görünür ve uyarı listesine düşer. Rapor yazarken bir alanın boş
kaldığını fark etmemek, yanlış değer basmak kadar tehlikeli.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field

from core.ek import cekimle
from core.metin import anahtarla
from core.rapor.kosul import degerlendir

_TUTUCU = re.compile(r"\{\{\s*([^}|]+?)\s*(?:\|\s*([^}]+?)\s*)?\}\}")


@dataclass
class Sonuc:
    metin: str
    uyarilar: list[str] = field(default_factory=list)
    doldurulacaklar: list[dict] = field(default_factory=list)
    atlanan_bloklar: list[str] = field(default_factory=list)


def tarih_tr(iso: str | None) -> str | None:
    """2023-03-27 -> 27/03/2023 (rapor biçimi)"""
    if not iso or not re.fullmatch(r"\d{4}-\d{2}-\d{2}", str(iso)):
        return iso
    y, a, g = str(iso).split("-")
    return f"{g}/{a}/{y}"


def veri_kur(case: dict, belgeler: list[dict]) -> dict:
    """case.json + belgeler[] -> yer tutucu sözlüğü.

    YAML'da hangi adı yazdıysa çalışsın diye cömert takma adlar var; Emre
    `isyeri_unvan` de yazabilir `iş_yeri_unvan` da.
    """
    a = {b["tur"]: (b.get("alanlar") or {}) for b in belgeler if b.get("tur")}
    t, ig, ia = a.get("isyeri_tescil", {}), a.get("ise_giris_bildirgesi", {}), \
                a.get("isten_ayrilis_bildirgesi", {})
    dg, uk = a.get("denetim_gerekcesi", {}), a.get("unite_karari", {})
    sig = (case.get("sigortalilar") or [{}])[0]

    ad_soyad = " ".join(x for x in (ig.get("ad"), ig.get("soyad")) if x) \
               or sig.get("ad_soyad") or uk.get("kazali_ad_soyad")

    v = {
        # işyeri
        "isyeri_unvan": t.get("unvan") or (case.get("isveren") or {}).get("unvan"),
        "isyeri_sicil_no": t.get("sicil_no") or (case.get("isveren") or {}).get("sicil_no"),
        "is_kolu_kodu": t.get("is_kolu_kodu"), "tehlike_sinifi": t.get("tehlike_sinifi"),
        "isin_mahiyeti": t.get("isin_mahiyeti"), "mahiyet_kodu": t.get("mahiyet_kodu"),
        "kanun_kapsamina_alinis": tarih_tr(t.get("kanun_kapsamina_alinis")),
        "vergi_no": t.get("vergi_no"), "ticaret_sicil_no": t.get("ticaret_sicil_no"),
        "isyeri_adres": " ".join(x for x in (t.get("mahalle"), t.get("cadde"),
                                 t.get("dis_kapi"), t.get("ilce"), t.get("il")) if x) or None,
        # sigortalı
        "sigortali": ad_soyad, "sigortali_tc": ig.get("tc") or sig.get("tc") or uk.get("tc"),
        "baba_adi": ig.get("baba_adi"), "ana_adi": ig.get("ana_adi"),
        "dogum_tarihi": tarih_tr(ig.get("dogum_tarihi")), "meslek": ig.get("meslek"),
        "ise_baslama_tarihi": tarih_tr(ig.get("ise_baslama_tarihi")),
        "ayrilis_tarihi": tarih_tr(ia.get("ayrilis_tarihi")),
        # olay
        "kaza_tarihi": tarih_tr(dg.get("kaza_tarihi") or uk.get("kaza_tarihi")),
        "kaza_saati": uk.get("kaza_saati"), "olum_tarihi": tarih_tr(dg.get("olum_tarihi")),
        "olus_sekli": uk.get("olus_sekli"),
        # yazışma künyeleri
        "dg_sayi": dg.get("sayi"), "dg_tarih": tarih_tr(dg.get("tarih")),
        "dg_mudurluk": dg.get("mudurluk"),
        "uk_karar_no": uk.get("karar_no"), "uk_karar_tarihi": tarih_tr(uk.get("karar_tarihi")),
        "mufettis": case.get("mufettis"), "denetim_no": case.get("denetim_no"),
    }
    # türetilmiş: "…-… tarihleri arasında" / "… tarihinde"
    g, c = v["ise_baslama_tarihi"], v["ayrilis_tarihi"]
    v["calisma_donemi"] = (f"{g}-{c} tarihleri arasında" if g and c and g != c
                           else (f"{g} tarihinde" if g else None))
    # takma adlar — YAML'da hangi yazımı kullandıysa tutsun
    for takma, asil in [("iş_yeri_unvan", "isyeri_unvan"), ("işyeri_unvan", "isyeri_unvan"),
                        ("sigortalı_ad_soyad", "sigortali"), ("sigortali_ad_soyad", "sigortali"),
                        ("sigortalı_tc_no", "sigortali_tc"), ("sigortali_tc_no", "sigortali_tc"),
                        ("sigortalı_ig_tarih", "ise_baslama_tarihi"),
                        ("sigortalı_ia_tarih", "ayrilis_tarihi"),
                        ("iş_kolu_kodu", "is_kolu_kodu")]:
        v.setdefault(takma, v.get(asil))
    return v


def _doldur(metin: str, veri: dict, ekler: dict, uyarilar: list[str], nerede: str) -> str:
    def degistir(m):
        alan, cekim = m.group(1).strip(), (m.group(2) or "").strip()
        if alan.startswith("ek:"):
            no = ekler.get(alan[3:])
            if no is None:
                uyarilar.append(f"{nerede}: '{alan}' — bu belgenin ek numarası bilinmiyor")
                return "‹Ek:?›"
            return f"(Ek:{no})"
        if alan not in veri:
            uyarilar.append(f"{nerede}: '{alan}' diye bir alan yok — yazımı kontrol et")
            return f"‹{alan}?›"
        d = veri[alan]
        if d in (None, ""):
            uyarilar.append(f"{nerede}: '{alan}' boş")
            return f"‹{alan}?›"
        if cekim:
            try:
                return cekimle(str(d), cekim)
            except ValueError as e:
                uyarilar.append(f"{nerede}: {e}")
                return str(d)
        return str(d)
    return _TUTUCU.sub(degistir, metin)


def render(tanim: dict, case: dict, belgeler: list[dict], *, ekler: dict | None = None) -> Sonuc:
    veri = veri_kur(case, belgeler)
    ekler = ekler or {b["tur"]: b.get("ek_no") for b in belgeler if b.get("tur")}
    s = Sonuc(metin="")
    parcalar: list[str] = []

    for blok in tanim.get("bloklar", []):
        ad = blok.get("ad", "?")
        tut, uyari = degerlendir(blok.get("kosul", "her zaman"),
                                 {"case": case, "belgeler": belgeler,
                                  "alanlar": {b["tur"]: b.get("alanlar") or {}
                                              for b in belgeler if b.get("tur")}})
        if uyari:
            s.uyarilar.append(uyari)
        if tut is not True:
            s.atlanan_bloklar.append(f"{ad} ({blok.get('kosul')} → {tut})")
            continue

        for g in blok.get("girdi", []) or []:
            s.doldurulacaklar.append({"blok": ad, **g})
            veri.setdefault(g["ad"], f"[[DOLDURULACAK — {g.get('soru', g['ad'])}]]")

        metin = (blok.get("metin") or "").strip()
        if not metin:
            s.uyarilar.append(f"blok {ad!r}: 'metin' yok ya da boş")
            continue
        dolu = _doldur(metin, veri, ekler, s.uyarilar, f"blok {ad!r}")
        # YAML'daki satır kırılmaları yazım kolaylığı içindi, metnin parçası değil:
        # paragraf içi tek satır sonları boşluğa iner, çift satır sonu paragrafı böler.
        parcalar.extend(re.sub(r"\s*\n\s*", " ", par).strip()
                        for par in re.split(r"\n\s*\n", dolu) if par.strip())

    s.metin = "\n\n".join(parcalar)
    return s
