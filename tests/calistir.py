#!/usr/bin/env python3
"""Tüm testler: python tests/calistir.py"""
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import test_capraz, test_cikarim, test_metin, test_onarim, test_satir  # noqa: E402

gecen = kalan = 0
for modul in (test_onarim, test_metin, test_capraz, test_cikarim, test_satir):
    s = modul.calistir()
    gecen += s.gecen
    kalan += s.kalan

print(f"\n{'='*54}\nSONUÇ: {gecen} geçti, {kalan} kaldı  "
      f"-> {'TÜMÜ GEÇTİ' if kalan == 0 else 'BAŞARISIZ'}")
sys.exit(0 if kalan == 0 else 1)
