"""
case.py — İş (case) nesnesinin diske yazılması ve okunması.

case.json tek gerçek kaynaktır: künye, belgeler, bulgular ve uyarılar hep
burada durur. Rapor da, ek listesi de, JETEK manifest'i de bu dosyadan üretilir.

Yeniden çalıştırma güvenli: dosya varsa toplanmış belgeler ve bulgular korunur,
yalnızca künye alanları tazelenir.
"""
import json
import re
from datetime import datetime, timezone
from pathlib import Path

from core.metin import anahtarla, sadelestir  # noqa: F401  (sadelestir dışarıya da açık)

# Denetim listesindeki "Denetim Alanı" -> domains/ altındaki paket adı
_ALAN_DOMAIN = {
    "is kazasi": "is_kazasi",
    "meslek hastaligi": "meslek_hastaligi",
    "asgari iscilik": "asgari_iscilik",
}


def domain_bul(denetim_alani: str | None) -> str | None:
    """'İş Kazası İncelemesi' -> 'is_kazasi'. Tanınmazsa None."""
    if not denetim_alani:
        return None
    d = anahtarla(denetim_alani)
    for anahtar, domain in _ALAN_DOMAIN.items():
        if d.startswith(anahtar):
            return domain
    return None


def klasor_adi(is_kaydi: dict) -> str:
    """'90001_ALI_VELI' — denetim no + ilk sigortalı."""
    no = is_kaydi.get("denetim_no") or "000000"
    sigortalilar = is_kaydi.get("sigortalilar") or []
    ad = sigortalilar[0]["ad_soyad"] if sigortalilar else "ISIMSIZ"
    ad = re.sub(r"[^A-Za-z0-9]+", "_", sadelestir(ad)).strip("_").upper()
    return f"{no}_{ad}"[:80]


def kaydet(is_kaydi: dict, cases_dir: Path) -> Path:
    """İşi cases/<klasor>/case.json olarak yazar, belgeler/ klasörünü açar."""
    klasor = cases_dir / klasor_adi(is_kaydi)
    (klasor / "belgeler").mkdir(parents=True, exist_ok=True)
    yol = klasor / "case.json"

    if yol.exists():
        mevcut = json.loads(yol.read_text(encoding="utf-8"))
        # Toplanmış iş kaybolmasın: bu alanlar yeniden üretilmez
        for korunan in ("belgeler", "bulgular", "notlar"):
            if mevcut.get(korunan):
                is_kaydi[korunan] = mevcut[korunan]
        is_kaydi["olusturuldu"] = mevcut.get("olusturuldu", is_kaydi.get("olusturuldu"))

    is_kaydi.setdefault("olusturuldu", datetime.now(timezone.utc).astimezone().isoformat())
    is_kaydi["guncellendi"] = datetime.now(timezone.utc).astimezone().isoformat()

    yol.write_text(json.dumps(is_kaydi, ensure_ascii=False, indent=2), encoding="utf-8")
    return yol


def yukle(case_json: Path) -> dict:
    return json.loads(Path(case_json).read_text(encoding="utf-8"))
