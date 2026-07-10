"""Tests for planespotters aircraft photo helpers."""

import sys
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from utilities import aircraft_photo  # noqa: E402


class TestAircraftPhoto(unittest.TestCase):
    def test_normalize_hex(self):
        self.assertEqual(aircraft_photo.normalize_icao_hex("A068D1"), "a068d1")
        self.assertEqual(aircraft_photo.normalize_icao_hex("0x3C66B3"), "3c66b3")
        self.assertEqual(aircraft_photo.normalize_icao_hex(""), "")
        self.assertEqual(aircraft_photo.normalize_icao_hex("abc"), "")

    def test_pick_image_url(self):
        photo = {
            "thumbnail_large": {"src": "https://t.plnspttrs.net/x_280.jpg"},
            "photographer": "Test",
        }
        self.assertTrue(aircraft_photo._pick_image_url(photo).endswith("_280.jpg"))

    def test_lookup_caches_miss(self):
        with mock.patch.object(aircraft_photo, "_load_meta", return_value={
            "3c66b3": {"miss": True, "ts": 9e12},
        }):
            with mock.patch("utilities.aircraft_photo.requests.get") as get:
                result = aircraft_photo.lookup_aircraft_photo("3C66B3")
                self.assertIsNone(result)
                get.assert_not_called()

    def test_credit_line(self):
        self.assertEqual(
            aircraft_photo.photo_credit_line({"photographer": "Jane Doe"}),
            "© Jane Doe",
        )


if __name__ == "__main__":
    unittest.main()
