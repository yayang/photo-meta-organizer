import os
import re
import shutil
import subprocess
from dataclasses import dataclass
from datetime import datetime
from functools import partial
from pathlib import Path
from typing import Callable, Dict, Any, Optional, Tuple

import piexif
from PIL import Image

from photo_meta_organizer.services.image_io import register_heif_support


register_heif_support()


@dataclass(frozen=True)
class FixTimestamp:
    """Normalized timestamp payload used by all fix writers."""

    exif_value: str
    iso_value: str
    datetime_value: datetime
    unix_ts: float


MetadataWriter = Callable[[Path, FixTimestamp], None]


def parse_date_from_path(file_path: Path) -> Tuple[Optional[int], Optional[int]]:
    """Parses year and month from the file path structure.

    Strategies:
    1. Parent name contains "YYYY-MM" or "YYYY MM" (e.g. "2023-5", "2023 05")
    2. Parent name is pure year "YYYY" (e.g. "2023") -> Defaults to January
    3. Parent is "MM" and Grandparent is "YYYY" (e.g. "2000/2")

    Args:
        file_path: Path to the file.

    Returns:
        Tuple[Optional[int], Optional[int]]: A tuple of (year, month) if found, else (None, None).
    """
    parent = file_path.parent.name
    grandparent = file_path.parent.parent.name

    # Strategy 1: Strong pattern "2023-5" / "2023 05"
    match = re.search(r"(\d{4})[-.\s]+(\d{1,2})", parent)
    if match:
        return int(match.group(1)), int(match.group(2))

    # Strategy 2: Pure year folder "2023" -> Jan
    if parent.isdigit() and len(parent) == 4:
        return int(parent), 1

    # Strategy 3: Year/Month structure "2000/2"
    if parent.isdigit() and len(parent) <= 2:
        if grandparent.isdigit() and len(grandparent) == 4:
            return int(grandparent), int(parent)

    return None, None


def build_fix_timestamp(year: int, month: int) -> FixTimestamp:
    """Builds the canonical timestamp payload for fix operations.

    Sets the date to the 15th of the specified month at 12:00:00.

    Args:
        year: The year to set.
        month: The month to set.

    Returns:
        FixTimestamp: Normalized values for metadata and filesystem writes.
    """
    dt_obj = datetime(year, month, 15, 12, 0, 0)
    return FixTimestamp(
        exif_value=dt_obj.strftime("%Y:%m:%d %H:%M:%S"),
        iso_value=dt_obj.strftime("%Y-%m-%dT%H:%M:%S"),
        datetime_value=dt_obj,
        unix_ts=dt_obj.timestamp(),
    )


def write_jpeg_metadata(file_path: Path, payload: FixTimestamp) -> None:
    """Writes EXIF metadata into JPEG files."""
    try:
        exif_dict = piexif.load(str(file_path))
    except Exception:
        exif_dict = {"0th": {}, "Exif": {}, "GPS": {}, "1st": {}, "thumbnail": None}

    exif_dict["Exif"][piexif.ExifIFD.DateTimeOriginal] = payload.exif_value
    exif_dict["Exif"][piexif.ExifIFD.DateTimeDigitized] = payload.exif_value
    exif_dict["0th"][piexif.ImageIFD.DateTime] = payload.exif_value
    exif_dict.pop("thumbnail", None)

    exif_bytes = piexif.dump(exif_dict)
    piexif.insert(exif_bytes, str(file_path))


def write_reencoded_image_metadata(
    file_path: Path,
    payload: FixTimestamp,
    format_name: str,
    preserve_xmp: bool = False,
) -> None:
    """Writes EXIF metadata by re-saving the image to a temporary file."""
    temp_path = file_path.with_name(f"{file_path.stem}.tmp{file_path.suffix}")

    try:
        with Image.open(file_path) as img:
            exif_data = img.getexif()
            exif_data[36867] = payload.exif_value
            exif_data[36868] = payload.exif_value
            exif_data[306] = payload.exif_value

            save_kwargs = {"format": format_name, "exif": exif_data.tobytes()}
            if preserve_xmp and "xmp" in img.info:
                save_kwargs["xmp"] = img.info["xmp"]

            img.save(temp_path, **save_kwargs)

        temp_path.replace(file_path)

    finally:
        if temp_path.exists():
            temp_path.unlink()


def write_video_metadata(file_path: Path, payload: FixTimestamp) -> None:
    """Writes creation time metadata into MP4/MOV containers."""
    ffmpeg_path = shutil.which("ffmpeg")
    if not ffmpeg_path:
        raise RuntimeError("ffmpeg not found")

    temp_path = file_path.with_name(f"{file_path.stem}.tmp{file_path.suffix}")

    try:
        subprocess.run(
            [
                ffmpeg_path,
                "-hide_banner",
                "-loglevel",
                "error",
                "-i",
                str(file_path),
                "-map",
                "0",
                "-c",
                "copy",
                "-metadata",
                f"creation_time={payload.iso_value}",
                "-movflags",
                "use_metadata_tags",
                str(temp_path),
                "-y",
            ],
            check=True,
            capture_output=True,
            text=True,
        )

        temp_path.replace(file_path)

    finally:
        if temp_path.exists():
            temp_path.unlink()


FIX_WRITERS = {
    ".jpg": ("EXIF Write", "exif_value", write_jpeg_metadata),
    ".jpeg": ("EXIF Write", "exif_value", write_jpeg_metadata),
    ".png": (
        "PNG EXIF Write",
        "exif_value",
        partial(write_reencoded_image_metadata, format_name="PNG"),
    ),
    ".heic": (
        "HEIC EXIF Write",
        "exif_value",
        partial(
            write_reencoded_image_metadata,
            format_name="HEIF",
            preserve_xmp=True,
        ),
    ),
    ".mp4": ("Video creation_time", "iso_value", write_video_metadata),
    ".mov": ("Video creation_time", "iso_value", write_video_metadata),
}


def apply_metadata_fix(
    file_path: Path,
    payload: FixTimestamp,
    dry_run: bool,
    metadata_label: str,
    metadata_value: str,
    writer: MetadataWriter,
) -> bool:
    """Applies a metadata writer and synchronizes filesystem timestamps.

    Args:
        file_path: Path to the target file.
        payload: Normalized timestamp payload.
        dry_run: If True, only simulate operations.
        metadata_label: User-facing metadata label for logs.
        metadata_value: User-facing metadata value for logs.
        writer: Format-specific metadata writer.

    Returns:
        bool: True if successful, False otherwise.
    """
    if dry_run:
        print(f"[Dry Run] {file_path.name}")
        print(f"      -> {metadata_label}: {metadata_value}")
        print(f"      -> System ModTime: {payload.datetime_value}")
        return True

    try:
        writer(file_path, payload)
        os.utime(str(file_path), (payload.unix_ts, payload.unix_ts))
        print(f"✅ [Success] {file_path.name} -> {metadata_value}")
        return True

    except subprocess.CalledProcessError as e:
        error_msg = e.stderr.strip() or e.stdout.strip() or str(e)
        print(f"❌ [Failed] {file_path.name}: {error_msg}")
        return False
    except Exception as e:
        print(f"❌ [Failed] {file_path.name}: {e}")
        return False


def process_fix_file(file_path: Path, dry_run: bool) -> bool:
    """Processes a single file if it matches a supported fix strategy."""
    suffix = file_path.suffix.lower()
    writer_config = FIX_WRITERS.get(suffix)
    if not writer_config:
        return False

    year, month = parse_date_from_path(file_path)
    if not year or not month:
        return False

    if not (1900 < year < 2030 and 1 <= month <= 12):
        return False

    metadata_label, value_attr, writer = writer_config
    payload = build_fix_timestamp(year, month)
    return apply_metadata_fix(
        file_path=file_path,
        payload=payload,
        dry_run=dry_run,
        metadata_label=metadata_label,
        metadata_value=getattr(payload, value_attr),
        writer=writer,
    )


def run_fix(config: Dict[str, Any], dry_run: Optional[bool] = None) -> Dict[str, Any]:
    """Runs the metadata fix process.

    Args:
        config: Configuration dictionary.
        dry_run: If True, only simulate operations. Defaults to config setting.

    Returns:
        Dict[str, Any]: Statistics including "success" and "failed".
    """
    target_root = Path(config["directories"]["fix_dir"])
    dry_run = dry_run if dry_run is not None else config["settings"]["dry_run"]

    print(
        f"🔧 Fix Mission Start (Exif + System Time) | Mode: {'[DRY RUN]' if dry_run else '[LIVE]'}"
    )
    print(f"📂 Target: {target_root}")

    if not target_root.exists():
        print(f"❌ Directory not found: {target_root}")
        return {"success": 0, "failed": 0}

    count = 0

    for file_path in target_root.rglob("*"):
        if not file_path.is_file():
            continue

        if process_fix_file(file_path, dry_run):
            count += 1

    print("-" * 40)
    print(f"🏁 Done. Processed: {count} files")

    return {"success": count, "failed": 0}
