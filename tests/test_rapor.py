"""Rapor render: Türkçe ek uyumu, koşul değerlendirme, blok seçimi.

Ek uyumu testleri gerçek raporlardaki hatayı hedefliyor: örnek raporda
`Can ÖRNEK'ya ait` yazılmış, doğrusu `ÖRNEK'e`. Kural deterministik, bu
hata kategorisi tamamen kapanmalı.
"""
import re

from yardim import KOK, Sonuc
from core.ek import cekimle
from core.rapor.kosul import degerlendir
from core.rapor.render import render, tarih_tr, veri_kur

CEKIM = [
    ("ALİ VELİ", "yonelme", "ALİ VELİ'ye"), ("ALİ VELİ", "ilgi", "ALİ VELİ'nin"),
    ("ALİ VELİ", "belirtme", "ALİ VELİ'yi"),
    ("CAN ÖRNEK", "yonelme", "CAN ÖRNEK'e"),        # raporda 'ÖRNEK'ya' yazılmıştı
    ("MEHMET KAYA", "yonelme", "MEHMET KAYA'ya"),   # sesliyle biter → tampon y
    ("MURAT", "ilgi", "MURAT'ın"),                  # kalın-düz
    ("METİN GÜRBÜZ", "yonelme", "METİN GÜRBÜZ'e"),  # ince-yuvarlak son sesli
    ("HASAN KURT", "bulunma", "HASAN KURT'ta"),     # sert ünsüz → -ta
    ("AHMET", "ayrilma", "AHMET'ten"),
    ("GAZİANTEP", "bulunma", "GAZİANTEP'te"),
    ("ÖRNEK LTD.ŞTİ.", "ilgi", "ÖRNEK LTD.ŞTİ.'nin"),   # kısaltma: son ses 'i'
    ("DENEME A.Ş.", "ilgi", "DENEME A.Ş.'nin"),         # "a şe" → 'e'
]

_CASE = {
    "domain": "is_kazasi", "denetim_no": "90001", "mufettis": "ÖRNEK MÜFETTİŞ",
    "isveren": {"tescilli": True, "unvan": "ÖRNEK LTD.ŞTİ.", "sicil_no": "2 0000 01"},
    "sigortalilar": [{"ad_soyad": "ALİ VELİ", "tc": "10000000078"}],
    "diger_isveren": None,
}
_BELGELER = [
    {"tur": "isyeri_tescil", "ek_no": 7, "alanlar": {
        "unvan": "ÖRNEK LTD.ŞTİ.", "sicil_no": "2 0000 01 01 1000000 027 09-51",
        "is_kolu_kodu": "494102-Kara yolu", "tehlike_sinifi": "Tehlikeli",
        "kanun_kapsamina_alinis": "2020-01-25"}},
    {"tur": "ise_giris_bildirgesi", "ek_no": 4, "alanlar": {
        "tc": "10000000078", "ad": "ALİ", "soyad": "VELİ",
        "ise_baslama_tarihi": "2023-03-27"}},
    {"tur": "isten_ayrilis_bildirgesi", "ek_no": 5, "alanlar": {
        "ayrilis_tarihi": "2024-03-02"}},
]
_TANIM = {
    "bolum": "4.1", "baslik": "Test",
    "bloklar": [
        {"ad": "mevzuat", "kosul": "her zaman", "metin": "Sabit mevzuat cümlesi."},
        {"ad": "tescilli", "kosul": "işyeri tescilli",
         "metin": "{{isyeri_unvan}} unvanlı işyeri {{kanun_kapsamina_alinis}}\ntarihinde kapsama alınmıştır. {{ek:isyeri_tescil}}"},
        {"ad": "tescilsiz", "kosul": "işyeri tescilsiz", "metin": "Tescil bulunmadığı…"},
        {"ad": "alt-isv", "kosul": "alt işveren var", "metin": "Alt işveren…"},
        {"ad": "kapanis", "kosul": "işyeri tescilli",
         "metin": "{{sigortali|belirtme}} çalıştıran {{isyeri_unvan|ilgi}} işveren olduğu."},
    ],
}


def calistir():
    s = Sonuc("rapor — ek uyumu · koşul · render")

    for sozcuk, cekim, beklenen in CEKIM:
        s.kontrol(f"{sozcuk} + {cekim}", cekimle(sozcuk, cekim), beklenen)
    s.dogru("bilinmeyen çekim gürültülü hata verir",
            _hata_veriyor(lambda: cekimle("ALİ", "olmayan_cekim")))

    baglam = {"case": _CASE, "belgeler": _BELGELER, "alanlar": {}}
    s.kontrol("koşul: her zaman", degerlendir("her zaman", baglam)[0], True)
    s.kontrol("koşul: işyeri tescilli", degerlendir("işyeri tescilli", baglam)[0], True)
    s.kontrol("koşul: işyeri tescilsiz", degerlendir("işyeri tescilsiz", baglam)[0], False)
    s.kontrol("koşul: alt işveren var", degerlendir("alt işveren var", baglam)[0], False)
    s.kontrol("koşul: işyeri tescil var", degerlendir("işyeri tescil var", baglam)[0], True)
    s.kontrol("koşul: iş kazası bildirim formu yok",
              degerlendir("iş kazası bildirim formu yok", baglam)[0], True)
    # Belirlenemeyen koşul sessizce False dönmemeli
    sonuc, uyari = degerlendir("tanık var", baglam)
    s.kontrol("bilinmeyen koşul False değil None döner", sonuc, None)
    s.dogru("… ve uyarı üretir", bool(uyari))

    s.kontrol("tarih TR biçimine çevrilir", tarih_tr("2023-03-27"), "27/03/2023")
    v = veri_kur(_CASE, _BELGELER)
    s.kontrol("ad ve soyad birleşti", v["sigortali"], "ALİ VELİ")
    s.kontrol("çalışma dönemi türetildi", v["calisma_donemi"],
              "27/03/2023-02/03/2024 tarihleri arasında")
    s.kontrol("takma ad çalışıyor", v["iş_yeri_unvan"], v["isyeri_unvan"])

    r = render(_TANIM, _CASE, _BELGELER)
    s.kontrol("koşulu tutmayan bloklar basılmadı", len(r.atlanan_bloklar), 2)
    s.dogru("ek numarası çözüldü", "(Ek:7)" in r.metin)
    s.dogru("ek çekimi uygulandı", "ALİ VELİ'yi" in r.metin and "LTD.ŞTİ.'nin" in r.metin)
    s.dogru("YAML satır kırılması metne geçmedi", "\n" not in r.metin.split("\n\n")[1])
    s.kontrol("uyarısız render", r.uyarilar, [])

    # Boş alan sessizce silinmemeli
    eksik = render({"bolum": "x", "baslik": "x", "bloklar": [
        {"ad": "t", "kosul": "her zaman", "metin": "{{olmayan_alan}} bir cümle."}]},
        _CASE, _BELGELER)
    s.dogru("bilinmeyen alan metinde işaretlenir", "‹olmayan_alan?›" in eksik.metin)
    s.dogru("… ve uyarı üretir", any("olmayan_alan" in u for u in eksik.uyarilar))
    return s


def _hata_veriyor(f):
    try:
        f(); return False
    except ValueError:
        return True
