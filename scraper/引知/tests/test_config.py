import tempfile
import unittest
from pathlib import Path

from caoliao_archiver.config import (
    DEFAULT_ENTRY_URL,
    canonicalize_url,
    load_config,
    normalize_entry_to_qrcode,
    qrcode_route_from_url,
)


class ConfigTests(unittest.TestCase):
    def test_normalize_h5_entry_to_qrcode_url(self):
        self.assertEqual(
            normalize_entry_to_qrcode(DEFAULT_ENTRY_URL),
            "https://h.qr61.cn/odBU6p/qYtCDec",
        )

    def test_normalize_plain_qrcode_url_without_scheme(self):
        self.assertEqual(
            normalize_entry_to_qrcode("h.qr61.cn/odBU6p/qYtCDec"),
            "https://h.qr61.cn/odBU6p/qYtCDec",
        )

    def test_qrcode_route_from_url(self):
        self.assertEqual(
            qrcode_route_from_url("https://h.qr61.cn/odBU6p/qYtCDec"),
            "h.qr61.cn/odBU6p/qYtCDec",
        )

    def test_canonicalize_url_trims_trailing_slash(self):
        self.assertEqual(
            canonicalize_url("HTTPS://H.QR61.CN/odBU6p/qYtCDec/"),
            "https://h.qr61.cn/odBU6p/qYtCDec",
        )

    def test_load_config_accepts_new_limits(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "config.json"
            path.write_text(
                """
                {
                  "entry_url": "https://h.qr61.cn/odBU6p/qYtCDec",
                  "max_assets": 12,
                  "max_external_pages": 3
                }
                """,
                encoding="utf-8",
            )
            cfg = load_config(path)
            self.assertEqual(cfg.max_assets, 12)
            self.assertEqual(cfg.max_external_pages, 3)


if __name__ == "__main__":
    unittest.main()
