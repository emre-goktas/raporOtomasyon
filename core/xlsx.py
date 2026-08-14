"""
xlsx.py — Bağımlılıksız .xlsx okuyucu.

openpyxl'e bağlanmamak için stdlib (zipfile + ElementTree) ile okuyor.
Denetim listesi tek sayfalı ve basit; ihtiyaç büyürse openpyxl'e geçilebilir,
çağıran taraf sadece satır listesi görüyor.

Hücre değeri ham haliyle döner (string ya da float). Excel'in sessiz
bozmalarının onarımı burada DEĞİL, alan bazında denetim_listesi.py'da yapılır —
çünkü hangi kolonun tarih, hangisinin uzun sayı olduğunu ancak orası bilir.
"""
import zipfile
import xml.etree.ElementTree as ET

_NS = "{http://schemas.openxmlformats.org/spreadsheetml/2006/main}"


def _col_index(ref: str) -> int:
    """'C7' -> 2 (0 tabanlı sütun indeksi)."""
    letters = "".join(ch for ch in ref if ch.isalpha())
    n = 0
    for ch in letters:
        n = n * 26 + (ord(ch.upper()) - 64)
    return n - 1


def read_rows(path, sheet_index: int = 0) -> list[list]:
    """Sayfadaki satırları [[hücre, ...], ...] olarak döndürür.

    Boş hücreler None gelir ve satır içindeki konumları korunur (seyrek
    XML'de eksik <c> elemanları doldurulur), böylece kolon indeksleri kayamaz.
    """
    with zipfile.ZipFile(path) as z:
        shared: list[str] = []
        if "xl/sharedStrings.xml" in z.namelist():
            root = ET.fromstring(z.read("xl/sharedStrings.xml"))
            shared = ["".join(t.text or "" for t in si.iter(f"{_NS}t")) for si in root]

        sheets = sorted(n for n in z.namelist() if n.startswith("xl/worksheets/sheet"))
        root = ET.fromstring(z.read(sheets[sheet_index]))

        rows = []
        for row_el in root.iter(f"{_NS}row"):
            cells: list = []
            for c in row_el.iter(f"{_NS}c"):
                idx = _col_index(c.get("r", "A1"))
                while len(cells) < idx:
                    cells.append(None)

                ctype = c.get("t")
                if ctype == "inlineStr":
                    is_el = c.find(f"{_NS}is")
                    val = "".join(t.text or "" for t in is_el.iter(f"{_NS}t")) if is_el is not None else None
                else:
                    v = c.find(f"{_NS}v")
                    if v is None or v.text is None:
                        val = None
                    elif ctype == "s":
                        val = shared[int(v.text)]
                    else:
                        try:
                            val = float(v.text)
                        except ValueError:
                            val = v.text
                cells.append(val)
            rows.append(cells)
        return rows
