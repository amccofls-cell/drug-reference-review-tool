import unittest
from datetime import date

from drug_reference.core import extract_barcode_key, extract_mdscd_key, select_effective_price


class CoreTests(unittest.TestCase):
    def test_product_code_matching_rule(self):
        self.assertEqual(extract_barcode_key("8801234567890"), "12345678")
        self.assertEqual(extract_mdscd_key("123456789"), "12345678")

    def test_price_selection_by_reference_date(self):
        rows = [
            {"mdsCd": "123456789", "adtStaDd": "20240101", "sellEptDd": "20241231", "mxCprc": "100"},
            {"mdsCd": "123456789", "adtStaDd": "20250101", "sellEptDd": "", "mxCprc": "120"},
            {"mdsCd": "123456789", "adtStaDd": "20260101", "sellEptDd": "", "mxCprc": "140"},
        ]
        selected = select_effective_price(rows, date(2025, 6, 1))
        self.assertIsNotNone(selected)
        self.assertEqual(selected["mxCprc"], "120")

    def test_deleted_price_is_ignored(self):
        rows = [
            {"adtStaDd": "20250101", "sellEptDd": "", "mxCprc": "999", "payTpNm": "삭제"},
            {"adtStaDd": "20240101", "sellEptDd": "", "mxCprc": "100", "payTpNm": "급여"},
        ]
        self.assertEqual(select_effective_price(rows, date(2025, 6, 1))["mxCprc"], "100")


if __name__ == "__main__":
    unittest.main()
