import unittest
from datetime import datetime
from pathlib import Path
from unittest.mock import patch

from photo_meta_organizer.services.organize_photos import get_date_taken


class FakeImage:
    def __init__(self, exif_data):
        self._exif_data = exif_data

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def getexif(self):
        return self._exif_data


class TestOrganizePhotos(unittest.TestCase):
    def test_get_date_taken_reads_datetime_original(self):
        file_path = Path("sample.heic")

        with patch(
            "photo_meta_organizer.services.organize_photos.Image.open",
            return_value=FakeImage({36867: "2023:05:20 10:00:00"}),
        ):
            date_taken = get_date_taken(file_path, {".heic"})

        self.assertEqual(date_taken, datetime(2023, 5, 20, 10, 0, 0))

    def test_get_date_taken_reads_datetime_fallback(self):
        file_path = Path("sample.heic")

        with patch(
            "photo_meta_organizer.services.organize_photos.Image.open",
            return_value=FakeImage({306: "2023:05:20 10:00:00"}),
        ):
            date_taken = get_date_taken(file_path, {".heic"})

        self.assertEqual(date_taken, datetime(2023, 5, 20, 10, 0, 0))


if __name__ == "__main__":
    unittest.main()
