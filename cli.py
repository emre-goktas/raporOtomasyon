#!/usr/bin/env python3
"""
cli.py — İş kurma ve belge çıkarımı.

    python cli.py kur   --girdi <klasör> [--cases cases]
    python cli.py cikar --case cases/90001_ALI_VELI [--girdi <belge klasörü>]

`kur`   : görev emri PDF'i + DenetimListesi*.xlsx -> cases/<no>_<ad>/case.json
`cikar` : klasördeki belgeleri içeriğinden tanır, alanlarını çıkarır,
          case.json'daki `belgeler` listesine yazar ve künyeyle çapraz doğrular.
""" 
import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from core import belge as belge_mod
from core import manifest as manifest_mod
from core import capraz
from core import case as case_mod
from core import denetim_listesi, gorev_emri
from core.cikarim import sema
from core.rapor.render import render
from core.xlsx import read_rows


def _bul(girdi: Path, kaliplar: list[str], ad: str) -> Path:
    for kalip in kaliplar:
        adaylar = sorted(girdi.glob(kalip))
        if adaylar:
            return adaylar[0]
    sys.exit(f"HATA: {ad} bulunamadı ({girdi} içinde {kaliplar})")


def kur(girdi: Path, cases_dir: Path) -> int:
    xlsx = _bul(girdi, ["DenetimListesi*.xlsx", "*.xlsx"], "denetim listesi")
    pdf = _bul(girdi, ["gorevEmri*.pdf", "document.pdf", "*.pdf"], "görev emri")

    print(f"denetim listesi : {xlsx.name}")
    print(f"görev emri      : {pdf.name}\n")

    ge = gorev_emri.oku(pdf)
    for u in ge.get("uyarilar", []):
        print(f"  ⚠ {u}")
    print(f"  görevlendirme : {ge.get('grup_baskanligi')} — "
          f"{ge.get('tarih')} / {ge.get('sayi')}")
    print(f"  müfettiş      : {ge.get('mufettis')}")
    print(f"  son tarih     : {ge.get('son_tarih')}\n")

    isler = denetim_listesi.oku(xlsx, read_rows(xlsx))

    # Çapraz kontrol: görev emri kaç denetim diyor, listede kaç satır var
    beklenen = ge.get("denetim_adedi")
    if beklenen is not None and beklenen != len(isler):
        print(f"  ⚠ görev emri {beklenen} denetim diyor, listede {len(isler)} satır var\n")

    cases_dir.mkdir(parents=True, exist_ok=True)
    for i in isler:
        i["gorev_emri"] = ge
        i["domain"] = case_mod.domain_bul(i.get("denetim_alani"))
        if i["domain"] is None:
            i["uyarilar"].append(f"denetim alanı eşlenemedi: {i.get('denetim_alani')!r}")

        # Görev emri müfettişi ile liste müfettişi tutuyor mu?
        if ge.get("mufettis") and i.get("mufettis"):
            if case_mod.sadelestir(ge["mufettis"]).lower() != case_mod.sadelestir(i["mufettis"]).lower():
                i["uyarilar"].append(
                    f"müfettiş uyuşmuyor: görev emri {ge['mufettis']!r}, liste {i['mufettis']!r}")

        yol = case_mod.kaydet(i, cases_dir)
        sig = ", ".join(s["ad_soyad"] for s in i["sigortalilar"]) or "—"
        isaret = "⚠" if i["uyarilar"] else "✓"
        print(f"  {isaret} {yol.parent.name}")
        print(f"      alan     : {i['denetim_alani']}  → domain={i['domain']}")
        print(f"      sigortalı: {sig}")
        print(f"      işveren  : {'tescilli' if i['isveren']['tescilli'] else 'TESCİLSİZ'}"
              f" — {i['isveren']['unvan'] or '—'}")
        for u in i["uyarilar"]:
            print(f"      ⚠ {u}")

    print(f"\n{len(isler)} iş klasörü hazır: {cases_dir}")
    return 0


def cikar(case_yolu: Path, girdi: Path | None) -> int:
    case_json = case_yolu / "case.json" if case_yolu.is_dir() else case_yolu
    if not case_json.exists():
        sys.exit(f"HATA: {case_json} yok — önce 'kur' çalıştır")

    kayit = case_mod.yukle(case_json)
    domain = kayit.get("domain")
    if not domain:
        sys.exit(f"HATA: {case_json} içinde domain yok, çıkarım hangi kurallarla "
                 f"yapılacağı belirsiz")

    domain_dizini = Path(__file__).parent / "domains" / domain
    tanimlar = sema.yukle_domain(domain_dizini)
    if not tanimlar:
        sys.exit(f"HATA: {domain_dizini}/cikarim/ altında belge tanımı yok")

    girdi = girdi or (case_json.parent / "belgeler")
    if not girdi.is_dir():
        sys.exit(f"HATA: belge klasörü yok: {girdi}")

    print(f"case   : {case_json.parent.name}")
    print(f"domain : {domain}  ({len(tanimlar)} belge tanımı)")
    print(f"girdi  : {girdi}\n")

    belgeler = belge_mod.topla(girdi, tanimlar)
    if not belgeler:
        print("  (klasörde PDF yok)")

    taninan = 0
    for b in belgeler:
        isaret = "✓" if b["tur"] and not b["uyarilar"] else ("·" if not b["tur"] else "⚠")
        ozet = (f"{len(b['alanlar'])} alan" if b["alanlar"]
                else f"{len(b['satirlar'])} satır" if b["satirlar"] else "—")
        print(f"  {isaret} {b['kaynak']['dosya_adi']}")
        print(f"      tür: {b['tur'] or 'TANINMADI'}  ({b['kaynak']['sayfa_sayisi']} sayfa, {ozet})")
        for u in b["uyarilar"]:
            print(f"      ⚠ {u}")
        taninan += bool(b["tur"])

    # JETEK manifest'i — ek numaraları. Yoksa sorun değil: belgeler yine
    # çıkarılır, yalnızca rapordaki atıflar '‹Ek:?›' kalır.
    manifest_uyarilar: list[str] = []
    ekler: list[dict] = []
    manifest_yolu = manifest_mod.bul(girdi, case_json.parent)
    if manifest_yolu:
        ekler, manifest_uyarilar = manifest_mod.oku(manifest_yolu)
        u2, bilgiler = manifest_mod.bagla(belgeler, ekler)
        manifest_uyarilar += u2
        eslesen = sum(1 for b in belgeler if b.get("ek_no") is not None)
        print(f"\n  manifest: {manifest_yolu.name} — {len(ekler)} ek, "
              f"{eslesen}/{len(belgeler)} belge eşleşti")
        for u in manifest_uyarilar:
            print(f"      ⚠ {u}")
        for b in bilgiler:
            print(f"      · {b}")
    else:
        print(f"\n  manifest: yok — ek numaraları boş kalacak "
              f"(JETEK ZIP'indeki {manifest_mod.DOSYA_ADI} bu klasöre konursa dolar)")

    capraz_uyarilar = capraz.dogrula(kayit, belgeler)
    print(f"\n  çapraz doğrulama: "
          f"{'uyumsuzluk yok' if not capraz_uyarilar else str(len(capraz_uyarilar)) + ' uyumsuzluk'}")
    for u in capraz_uyarilar:
        print(f"      ⚠ {u}")

    kayit["belgeler"] = belgeler
    # Tek gerçek kaynak case.json — 'rapor' komutu manifest dosyasını tekrar
    # aramak zorunda kalmasın. Tanıyamadığımız belgelerin (ifade, bilirkişi)
    # atıf anahtarları da yalnızca burada yaşıyor. Manifest ortadan kalktıysa
    # liste de gider: elde olmayan bir manifest'ten kalma ek numarası, hiç
    # numara olmamasından tehlikelidir — rapor yanlış eke atıf yapar ve bunu
    # hiçbir şey fark etmez.
    if manifest_yolu:
        kayit["ekler"] = ekler
    elif kayit.pop("ekler", None):
        print("      ⚠ önceki çalıştırmadan kalan ek listesi silindi")
    # Katman kendi şüphesini yazar; her çalıştırmada baştan üretilir ki
    # düzeltilen bir uyarı listede asılı kalmasın.
    kayit["uyarilar"] = [u for u in kayit.get("uyarilar", [])
                         if not u.startswith(("çapraz:", "manifest:"))]
    kayit["uyarilar"] += capraz_uyarilar + [u for u in manifest_uyarilar if u.startswith("manifest:")]
    case_json.write_text(json.dumps(kayit, ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"\n{taninan}/{len(belgeler)} belge tanındı -> {case_json}")
    return 0


def rapor(case_yolu: Path, bolum: str | None) -> int:
    import yaml

    case_json = case_yolu / "case.json" if case_yolu.is_dir() else case_yolu
    if not case_json.exists():
        sys.exit(f"HATA: {case_json} yok — önce 'kur' ve 'cikar' çalıştır")
    kayit = case_mod.yukle(case_json)
    if not kayit.get("belgeler"):
        sys.exit("HATA: case.json'da belge yok — önce 'cikar' çalıştır")

    dizin = Path(__file__).parent / "domains" / kayit["domain"] / "rapor"
    dosyalar = sorted(d for d in dizin.glob("*.yaml") if not d.name.startswith("_"))
    if bolum:
        dosyalar = [d for d in dosyalar if d.name.startswith(bolum)]
    if not dosyalar:
        sys.exit(f"HATA: {dizin} altında bölüm tanımı yok")

    ekler = manifest_mod.ek_haritasi(kayit["belgeler"], kayit.get("ekler"))
    toplam_uyari = 0
    for d in dosyalar:
        tanim = yaml.safe_load(d.read_text(encoding="utf-8"))
        s = render(tanim, kayit, kayit["belgeler"], ekler=ekler)
        print(f"\n{'=' * 78}\n{tanim['bolum']}. {tanim['baslik']}\n{'=' * 78}\n")
        print(s.metin)
        if s.doldurulacaklar:
            print(f"\n  ── DOLDURULACAK ({len(s.doldurulacaklar)}) ──")
            for g in s.doldurulacaklar:
                print(f"     · [{g['blok']}] {g.get('soru', g['ad'])}")
        if s.atlanan_bloklar:
            print(f"\n  basılmayan blok: {', '.join(s.atlanan_bloklar)}")
        for u in s.uyarilar:
            print(f"  ⚠ {u}")
        toplam_uyari += len(s.uyarilar)

    print(f"\n{len(dosyalar)} bölüm basıldı, {toplam_uyari} uyarı")
    return 0


def main():
    ap = argparse.ArgumentParser(description="Sigorta rapor otomasyonu")
    alt = ap.add_subparsers(dest="komut", required=True)
    k = alt.add_parser("kur", help="görev emri + denetim listesinden iş klasörlerini kur")
    k.add_argument("--girdi", type=Path, required=True)
    k.add_argument("--cases", type=Path, default=Path(__file__).parent / "cases")

    c = alt.add_parser("cikar", help="belgeleri tanı, alanlarını çıkar, case.json'a yaz")
    c.add_argument("--case", type=Path, required=True, help="cases/<no>_<ad> klasörü")
    c.add_argument("--girdi", type=Path, default=None,
                   help="belge klasörü (varsayılan: <case>/belgeler)")

    r = alt.add_parser("rapor", help="case.json'dan rapor bölümlerini bas")
    r.add_argument("--case", type=Path, required=True)
    r.add_argument("--bolum", default=None, help="yalnız bu bölüm (ör. 4.1)")

    a = ap.parse_args()
    if a.komut == "rapor":
        sys.exit(rapor(a.case, a.bolum))
    if a.komut == "kur":
        sys.exit(kur(a.girdi, a.cases))
    if a.komut == "cikar":
        sys.exit(cikar(a.case, a.girdi))


if __name__ == "__main__":
    main()
