import unittest

from photo_meta_organizer.services.rename_photos import get_original_filename


class TestRenamePhotos(unittest.TestCase):
    def test_get_original_filename_removes_existing_prefix(self):
        file_name = "19990626_120000_c2692b91b18379935ac1539d436a33c6.HEIC"
        self.assertEqual(
            get_original_filename(file_name),
            "c2692b91b18379935ac1539d436a33c6.HEIC",
        )

    def test_get_original_filename_removes_existing_sys_prefix(self):
        file_name = "20230520_100000_sys_rename_me.jpg"
        self.assertEqual(get_original_filename(file_name), "rename_me.jpg")

    def test_get_original_filename_keeps_plain_name(self):
        file_name = "rename_me.jpg"
        self.assertEqual(get_original_filename(file_name), file_name)


if __name__ == "__main__":
    unittest.main()
