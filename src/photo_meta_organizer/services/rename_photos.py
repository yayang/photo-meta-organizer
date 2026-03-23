import os
import re
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, Optional, Tuple, Set, List
from PIL import Image
from photo_meta_organizer.services.image_io import register_heif_support

register_heif_support()

RENAMED_PREFIX_PATTERN = re.compile(
    r"^(?P<prefix>\d{8}_\d{6}_(?:sys_)?)?(?P<original>.+)$"
)


def get_date_strategy(
    file_path: Path, image_extensions: Set[str]
) -> Tuple[Optional[datetime], str]:
    """Determines the best date strategy for the file.

    Strategies:
    1. EXIF DateTimeOriginal (for images).
    2. EXIF DateTime (fallback for images).
    3. File modification time (for videos or images without EXIF).

    Args:
        file_path: Path to the file.
        image_extensions: Set of extensions considered as images.

    Returns:
        Tuple[Optional[datetime], str]: A tuple containing the datetime object
        (or None if not found) and a source tag string ("" for EXIF, "sys_" for system time).
    """
    suffix = file_path.suffix.lower()

    # --- Strategy A: Try reading EXIF for images ---
    if suffix in image_extensions:
        try:
            with Image.open(file_path) as img:
                exif_data = img.getexif()
                if exif_data:
                    # 36867=DateTimeOriginal, 306=DateTime
                    date_str = exif_data.get(36867) or exif_data.get(306)
                    if date_str:
                        # Format is typically YYYY:MM:DD HH:MM:SS
                        return (
                            datetime.strptime(date_str, "%Y:%m:%d %H:%M:%S"),
                            "",
                        )  # Empty string indicates official EXIF
        except Exception:
            pass  # Fallback to next strategy

    # --- Strategy B: System modification time (Video or failed EXIF) ---
    # Note: Returns "sys_" tag to indicate it's a guess
    try:
        mtime = os.path.getmtime(file_path)
        return datetime.fromtimestamp(mtime), "sys_"
    except Exception:
        return None, ""


def get_unique_path(path: Path) -> Path:
    """Generates a unique path by appending a counter if the file exists.

    Format: filename_1.ext, filename_2.ext, etc.

    Args:
        path: The original destination path.

    Returns:
        Path: A path that does not currently exist.
    """
    if not path.exists():
        return path

    stem = path.stem
    suffix = path.suffix
    parent = path.parent
    counter = 1

    while True:
        new_name = f"{stem}_{counter}{suffix}"
        new_path = parent / new_name
        if not new_path.exists():
            return new_path
        counter += 1


def get_original_filename(file_name: str) -> str:
    """Returns the original filename without a generated time prefix."""
    match = RENAMED_PREFIX_PATTERN.match(file_name)
    if not match:
        return file_name

    prefix = match.group("prefix")
    original = match.group("original")
    return original if prefix else file_name


def prepare_rename_context(
    config: Dict[str, Any], dry_run: Optional[bool]
) -> Tuple[Path, Set[str], Set[str], bool]:
    """Builds the runtime context for rename."""
    from photo_meta_organizer.config import get_extensions

    target_dir = Path(config["directories"]["target_dir"])
    resolved_dry_run = (
        dry_run if dry_run is not None else config["settings"]["dry_run"]
    )
    extensions = get_extensions(config)
    return target_dir, extensions["image"], extensions["all"], resolved_dry_run


def collect_rename_candidates(target_dir: Path, valid_extensions: Set[str]) -> List[Path]:
    """Collects candidate files for rename."""
    candidates = []

    for file_path in target_dir.rglob("*"):
        if not file_path.is_file():
            continue
        if file_path.name.startswith(".") or file_path.name == ".DS_Store":
            continue
        if file_path.suffix.lower() not in valid_extensions:
            continue
        candidates.append(file_path)

    return candidates


def run_rename_candidates(
    candidates: List[Path], image_extensions: Set[str], dry_run: bool
) -> Dict[str, int]:
    """Runs rename processing for collected candidate files."""
    count_success = 0
    count_skip = 0

    for file_path in candidates:
        try:
            renamed, skipped = process_rename_file(
                file_path=file_path,
                image_extensions=image_extensions,
                dry_run=dry_run,
            )
            if skipped:
                count_skip += 1
                continue
            if not renamed:
                continue
            count_success += 1
        except Exception as e:
            print(f"❌ [Error] {file_path.name}: {e}")
            count_skip += 1

    return {"success": count_success, "skipped": count_skip}


def process_rename_file(
    file_path: Path,
    image_extensions: Set[str],
    dry_run: bool,
) -> Tuple[bool, bool]:
    """Processes a single file for rename.

    Returns:
        Tuple[bool, bool]: (renamed, skipped)
    """
    date_obj, source_tag = get_date_strategy(file_path, image_extensions)
    if not date_obj:
        print(f"⚠️ [No Date] Cannot process: {file_path.name}")
        return False, True

    time_prefix = date_obj.strftime("%Y%m%d_%H%M%S")
    original_name = get_original_filename(file_path.name)
    new_filename = f"{time_prefix}_{source_tag}{original_name}"
    target_path = file_path.parent / new_filename

    if target_path.name == file_path.name:
        return False, False

    if target_path.exists():
        target_path = get_unique_path(target_path)

    if dry_run:
        print(f"📝 [Dry Run] {file_path.name}  --->  {target_path.name}")
    else:
        file_path.rename(target_path)
        print(f"✅ {file_path.name} -> {target_path.name}")

    return True, False


def rename_process(
    config: Dict[str, Any], dry_run: Optional[bool] = None, verbose: bool = False
) -> Dict[str, Any]:
    """Runs the batch rename process.

    Renames files to YYYYMMDD_HHMMSS_[sys_]OriginalName.ext.

    Args:
        config: Configuration dictionary.
        dry_run: If True, only simulate operations. Defaults to config setting.
        verbose: If True, print detailed logs.

    Returns:
        Dict[str, Any]: Statistics including "success" and "skipped".
    """
    target_dir, image_extensions, valid_extensions, dry_run = prepare_rename_context(
        config, dry_run
    )

    print(f"🚀 Rename Mission Start | Mode: {'[DRY RUN]' if dry_run else '[LIVE]'}")
    print(f"📂 Target: {target_dir}")
    print("-" * 40)

    if not target_dir.exists():
        print("❌ Target directory not found")
        return {"success": 0, "skipped": 0}

    candidates = collect_rename_candidates(target_dir, valid_extensions)
    result = run_rename_candidates(candidates, image_extensions, dry_run)

    print("-" * 40)
    print(
        f"🏁 Done. Planned rename: {result['success']}, Skipped/Error: {result['skipped']}"
    )
    if dry_run:
        print("💡 Tip: Set DRY_RUN = False in code or config to execute.")
    return result
