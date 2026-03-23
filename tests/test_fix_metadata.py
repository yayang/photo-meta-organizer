import tempfile
import unittest
from pathlib import Path
import sys
import types
from functools import partial
from unittest.mock import patch

sys.modules.setdefault("piexif", types.SimpleNamespace())

from photo_meta_organizer.services.fix_metadata import (
    apply_metadata_fix,
    build_fix_timestamp,
    write_reencoded_image_metadata,
)


class FakeExif(dict):
    def tobytes(self):
        return b"fake-exif"


class FakeImage:
    def __init__(self):
        self.exif_data = FakeExif()
        self.info = {"xmp": b"fake-xmp"}
        self.saved_kwargs = None

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def getexif(self):
        return self.exif_data

    def save(self, file_path, **kwargs):
        self.saved_kwargs = kwargs
        Path(file_path).write_bytes(b"fake-heic")


class TestFixMetadata(unittest.TestCase):
    def test_apply_heic_metadata_fix(self):
        fake_image = FakeImage()

        with tempfile.TemporaryDirectory() as temp_dir:
            file_path = Path(temp_dir) / "sample.heic"
            file_path.write_bytes(b"original")

            with patch(
                "photo_meta_organizer.services.fix_metadata.Image.open",
                return_value=fake_image,
            ), patch(
                "photo_meta_organizer.services.fix_metadata.os.utime"
            ) as mock_utime:
                payload = build_fix_timestamp(2021, 2)
                success = apply_metadata_fix(
                    file_path=file_path,
                    payload=payload,
                    dry_run=False,
                    metadata_label="HEIC EXIF Write",
                    metadata_value=payload.exif_value,
                    writer=partial(
                        write_reencoded_image_metadata,
                        format_name="HEIF",
                        preserve_xmp=True,
                    ),
                )

        self.assertTrue(success)
        self.assertEqual(fake_image.exif_data[36867], "2021:02:15 12:00:00")
        self.assertEqual(fake_image.exif_data[36868], "2021:02:15 12:00:00")
        self.assertEqual(fake_image.exif_data[306], "2021:02:15 12:00:00")
        self.assertEqual(fake_image.saved_kwargs["format"], "HEIF")
        self.assertEqual(fake_image.saved_kwargs["exif"], b"fake-exif")
        self.assertEqual(fake_image.saved_kwargs["xmp"], b"fake-xmp")
        mock_utime.assert_called_once()

    def test_apply_png_metadata_fix(self):
        fake_image = FakeImage()

        with tempfile.TemporaryDirectory() as temp_dir:
            file_path = Path(temp_dir) / "sample.png"
            file_path.write_bytes(b"original")

            with patch(
                "photo_meta_organizer.services.fix_metadata.Image.open",
                return_value=fake_image,
            ), patch(
                "photo_meta_organizer.services.fix_metadata.os.utime"
            ) as mock_utime:
                payload = build_fix_timestamp(2021, 2)
                success = apply_metadata_fix(
                    file_path=file_path,
                    payload=payload,
                    dry_run=False,
                    metadata_label="PNG EXIF Write",
                    metadata_value=payload.exif_value,
                    writer=partial(
                        write_reencoded_image_metadata,
                        format_name="PNG",
                    ),
                )

        self.assertTrue(success)
        self.assertEqual(fake_image.exif_data[36867], "2021:02:15 12:00:00")
        self.assertEqual(fake_image.exif_data[36868], "2021:02:15 12:00:00")
        self.assertEqual(fake_image.exif_data[306], "2021:02:15 12:00:00")
        self.assertEqual(fake_image.saved_kwargs["format"], "PNG")
        self.assertEqual(fake_image.saved_kwargs["exif"], b"fake-exif")
        mock_utime.assert_called_once()


if __name__ == "__main__":
    unittest.main()
