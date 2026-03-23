import unittest
import os
import shutil
import json
import subprocess
from datetime import datetime
from pathlib import Path
import time

PROJECT_ROOT = Path(__file__).resolve().parents[2]
CLI_MODULE = "photo_meta_organizer.cli"

TEST_ROOT = Path("/tmp/pmo_e2e_test")
SRC_DIR = TEST_ROOT / "src"
DST_DIR = TEST_ROOT / "dst"
CONFIG_FILE = TEST_ROOT / "config.yaml"
PARAMS_FILE = TEST_ROOT / "params.json"


class TestPhotoMetaOrganizerE2E(unittest.TestCase):
    def setUp(self):
        # Clean start
        if TEST_ROOT.exists():
            shutil.rmtree(TEST_ROOT)
        TEST_ROOT.mkdir(parents=True)
        SRC_DIR.mkdir()
        DST_DIR.mkdir()

        # Env setup
        self.env = os.environ.copy()
        self.env["PYTHONPATH"] = str(PROJECT_ROOT / "src")

    def tearDown(self):
        if TEST_ROOT.exists():
            shutil.rmtree(TEST_ROOT)

    def create_dummy_file(self, path: Path, size_mb: float = 0.001):
        with open(path, "wb") as f:
            f.write(b"\0" * int(size_mb * 1024 * 1024))

    def run_cli(self, args):
        cmd = ["uv", "run", "python", "-m", CLI_MODULE] + args
        result = subprocess.run(
            cmd, env=self.env, capture_output=True, text=True, cwd=PROJECT_ROOT
        )
        return result

    def test_clean_junk(self):
        # Create small file
        junk_file = SRC_DIR / "small.jpg"
        self.create_dummy_file(junk_file, size_mb=0.1)

        # Create params
        params = {
            "task": "clean-junk",
            "input_dirs": [str(SRC_DIR)],
            "threshold": 0.5,
            "dry_run": False,
        }
        with open(PARAMS_FILE, "w") as f:
            json.dump(params, f)

        # Run
        res = self.run_cli(["run-task", str(PARAMS_FILE)])
        self.assertEqual(res.returncode, 0, f"CLI Failed: {res.stderr}")

        # Verify
        # Check if small.jpg is gone from source root
        self.assertFalse((SRC_DIR / "small.jpg").exists(), "small.jpg should be moved")

        junk_dir = SRC_DIR / "junk"
        self.assertTrue(junk_dir.exists())
        self.assertTrue((junk_dir / "small.jpg").exists())

    def test_organize_fallback(self):
        # Create photo
        photo = SRC_DIR / "test.jpg"
        self.create_dummy_file(photo, size_mb=1.0)

        # Set mtime to 2023-01-01
        date_time = time.mktime((2023, 1, 1, 12, 0, 0, 0, 0, 0))
        os.utime(photo, (date_time, date_time))

        # Create params
        params = {
            "task": "organize",
            "input_dirs": [str(SRC_DIR)],
            "output_dir": str(DST_DIR),
            "dry_run": False,
        }
        with open(PARAMS_FILE, "w") as f:
            json.dump(params, f)

        # Run
        res = self.run_cli(["run-task", str(PARAMS_FILE)])
        self.assertEqual(res.returncode, 0, f"CLI Failed: {res.stderr}")

        # Verify
        # Should be in a zero-padded month folder like DST/.../2023/2023-01/test.jpg
        moved_files = list(DST_DIR.rglob("test.jpg"))
        self.assertEqual(len(moved_files), 1, "File should be in destination")
        self.assertIn("2023-01", str(moved_files[0]))

    def test_rename(self):
        # Create photo
        photo = SRC_DIR / "rename_me.jpg"
        self.create_dummy_file(photo, size_mb=1.0)

        # Set mtime
        date_time = time.mktime((2023, 5, 20, 10, 0, 0, 0, 0, 0))
        os.utime(photo, (date_time, date_time))

        # Create params
        params = {"task": "rename", "input_dirs": [str(SRC_DIR)], "dry_run": False}
        with open(PARAMS_FILE, "w") as f:
            json.dump(params, f)

        # Run
        res = self.run_cli(["run-task", str(PARAMS_FILE)])
        self.assertEqual(res.returncode, 0, f"CLI Failed: {res.stderr}")

        # Verify
        renamed = list(SRC_DIR.glob("*.jpg"))
        self.assertEqual(len(renamed), 1)
        # Expected: 20230520_100000_sys_rename_me.jpg (or similar)
        self.assertIn("20230520", renamed[0].name)
        self.assertNotEqual(renamed[0].name, "rename_me.jpg")

    def test_fix_video_metadata(self):
        target_dir = SRC_DIR / "2020" / "5"
        target_dir.mkdir(parents=True)
        videos = [target_dir / "clip.mp4", target_dir / "clip.mov"]

        for video in videos:
            create_video = subprocess.run(
                [
                    "ffmpeg",
                    "-hide_banner",
                    "-loglevel",
                    "error",
                    "-f",
                    "lavfi",
                    "-i",
                    "color=c=black:s=16x16:d=1",
                    "-pix_fmt",
                    "yuv420p",
                    str(video),
                    "-y",
                ],
                capture_output=True,
                text=True,
            )
            self.assertEqual(create_video.returncode, 0, create_video.stderr)

        params = {
            "task": "fix",
            "input_dirs": [str(SRC_DIR)],
            "dry_run": False,
        }
        with open(PARAMS_FILE, "w") as f:
            json.dump(params, f)

        res = self.run_cli(["run-task", str(PARAMS_FILE)])
        self.assertEqual(res.returncode, 0, f"CLI Failed: {res.stderr}")

        for video in videos:
            probe = subprocess.run(
                [
                    "ffprobe",
                    "-v",
                    "error",
                    "-show_entries",
                    "format_tags=creation_time",
                    "-of",
                    "default=noprint_wrappers=1:nokey=1",
                    str(video),
                ],
                capture_output=True,
                text=True,
            )
            self.assertEqual(probe.returncode, 0, probe.stderr)
            self.assertEqual(probe.stdout.strip(), "2020-05-15T12:00:00")

            mtime = datetime.fromtimestamp(video.stat().st_mtime)
            self.assertEqual(
                mtime.strftime("%Y-%m-%d %H:%M:%S"), "2020-05-15 12:00:00"
            )


if __name__ == "__main__":
    unittest.main()
