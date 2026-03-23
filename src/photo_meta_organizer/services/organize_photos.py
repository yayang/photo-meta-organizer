import os
import shutil
import re
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, Optional, Set, Tuple, List
from PIL import Image

from photo_meta_organizer.services.image_io import register_heif_support


register_heif_support()


def extract_location_info(folder_name: str) -> str:
    """Extracts Chinese characters from the folder name to determine location.

    Args:
        folder_name: The name of the folder to scan.

    Returns:
        str: A string containing merged Chinese characters found, or empty string.
    """
    matches = re.findall(r"[\u4e00-\u9fa5]+", folder_name)
    return "".join(matches) if matches else ""


def get_date_taken(path: Path, image_extensions: Set[str]) -> datetime:
    """Gets the creation date of the file.

    Tries to read EXIF data for images. Falls back to file modification time.

    Args:
        path: Path to the file.
        image_extensions: Set of extensions considered as images.

    Returns:
        datetime: The datetime object representing when the file was taken/created.
    """
    is_image = path.suffix.lower() in image_extensions
    if is_image:
        try:
            with Image.open(path) as img:
                exif_data = img.getexif()
                if exif_data:
                    date_str = exif_data.get(36867) or exif_data.get(306)
                    if date_str:
                        return datetime.strptime(date_str, "%Y:%m:%d %H:%M:%S")
        except Exception:
            pass
    return datetime.fromtimestamp(os.path.getmtime(path))


def get_unique_path(path: Path) -> Path:
    """Generates a unique path by appending a counter if the file exists.

    Args:
        path: The original destination path.

    Returns:
        Path: A path that does not currently exist.
    """
    if not path.exists():
        return path
    counter = 1
    while True:
        new_path = path.parent / f"{path.stem}_{counter}{path.suffix}"
        if not new_path.exists():
            return new_path
        counter += 1


def prepare_organize_context(
    config: Dict[str, Any], dry_run: Optional[bool]
) -> Tuple[Path, Path, Set[str], Set[str], bool]:
    """Builds the runtime context for organize."""
    from photo_meta_organizer.config import get_extensions

    source_dir = Path(config["directories"]["source"])
    target_dir = Path(config["directories"]["destination"])
    resolved_dry_run = (
        dry_run if dry_run is not None else config["settings"]["dry_run"]
    )
    extensions = get_extensions(config)
    return (
        source_dir,
        target_dir,
        extensions["image"],
        extensions["all"],
        resolved_dry_run,
    )


def print_organize_header(source_dir: Path, dry_run: bool) -> None:
    """Prints the standard organize task header."""
    print(f"🚀 Mission Start | Mode: {'[DRY RUN]' if dry_run else '[LIVE]'}")
    print(f"📂 Source: {source_dir}")
    print("-" * 40)


def build_missing_source_result() -> Dict[str, Any]:
    """Builds the standard result for a missing source directory."""
    print("❌ Source directory does not exist")
    return {
        "success": 0,
        "skipped": 0,
        "errors": ["Source directory does not exist"],
    }


def collect_organize_candidates(
    source_dir: Path, valid_extensions: Set[str], verbose: bool
) -> Tuple[List[Path], int]:
    """Collects candidate files and returns initial skip count."""
    candidates = []
    skipped = 0

    for file_path in source_dir.rglob("*"):
        if not file_path.is_file():
            continue

        if file_path.name.startswith(".") or file_path.name == ".DS_Store":
            if verbose:
                print(f"🗑️ [Skip] System file: {file_path.name}")
            skipped += 1
            continue

        if file_path.suffix.lower() not in valid_extensions:
            print(
                f"⚠️ [Skip] Unsupported format: {file_path.name} ({file_path.parent.name})"
            )
            skipped += 1
            continue

        candidates.append(file_path)

    return candidates, skipped


def run_organize_candidates(
    candidates: List[Path],
    target_dir: Path,
    image_extensions: Set[str],
    dry_run: bool,
    verbose: bool,
    initial_skip: int,
) -> Dict[str, Any]:
    """Runs organize processing for collected candidate files."""
    count_success = 0
    count_skip = initial_skip
    errors = []
    files_processed_ok = 0

    for file_path in candidates:
        try:
            files_processed_ok += 1
            result = process_organize_file(
                file_path=file_path,
                target_dir=target_dir,
                image_extensions=image_extensions,
                dry_run=dry_run,
                verbose=verbose,
                files_processed_ok=files_processed_ok,
            )
            if result == "in_place":
                count_skip += 1
                continue
            count_success += 1
        except Exception as e:
            error_msg = f"{file_path.name}: {e}"
            print(f"❌ [Error] {error_msg}")
            errors.append(error_msg)
            count_skip += 1

    return {"success": count_success, "skipped": count_skip, "errors": errors}


def process_organize_file(
    file_path: Path,
    target_dir: Path,
    image_extensions: Set[str],
    dry_run: bool,
    verbose: bool,
    files_processed_ok: int,
) -> Optional[str]:
    """Processes a single file for organize and returns an optional error."""
    should_print = (files_processed_ok == 1) or (files_processed_ok % 20 == 0)

    date_obj = get_date_taken(file_path, image_extensions)
    year_str = str(date_obj.year)
    month_str = f"{date_obj.month:02d}"

    loc = extract_location_info(file_path.parent.name) or extract_location_info(
        file_path.parent.parent.name
    )
    suffix = f" {loc}" if loc else ""

    decade = "1979-" if date_obj.year <= 1979 else f"{(date_obj.year // 10) * 10}+"
    target_folder = target_dir / decade / year_str / f"{year_str}-{month_str}{suffix}"
    target_path = target_folder / file_path.name

    if dry_run:
        final_path = target_path
        note = ""
        if final_path.exists():
            final_path = get_unique_path(final_path)
            note = " [Rename Required]"

        if should_print or verbose:
            print(
                f"[Dry Run] ({files_processed_ok}) .../{final_path.parent.name}/{final_path.name}{note}"
            )
        return None

    target_folder.mkdir(parents=True, exist_ok=True)

    if target_path.exists() and file_path.resolve() == target_path.resolve():
        if verbose:
            print(f"⏩ [Skip] In Place: {file_path.name}")
        return "in_place"

    if target_path.exists():
        target_path = get_unique_path(target_path)

    shutil.move(str(file_path), str(target_path))

    if should_print or verbose:
        print(f"✅ [Success] ({files_processed_ok}) {file_path.name}")

    return None


def organize(
    config: Dict[str, Any], dry_run: Optional[bool] = None, verbose: bool = False
) -> Dict[str, Any]:
    """Organizes photos based on metadata into a structured directory tree.

    Structure: Destination / Decade / Year / Year-Month [Location] / Filename

    Args:
        config: Configuration dictionary containing directory paths and settings.
        dry_run: If True, only simulate operations. Defaults to config setting.
        verbose: If True, print detailed logs.

    Returns:
        Dict[str, Any]: Statistics including "success", "skipped", and "errors".
    """
    source_dir, target_dir, image_extensions, valid_extensions, dry_run = (
        prepare_organize_context(config, dry_run)
    )
    print_organize_header(source_dir, dry_run)

    if not source_dir.exists():
        return build_missing_source_result()

    candidates, initial_skip = collect_organize_candidates(
        source_dir, valid_extensions, verbose
    )
    result = run_organize_candidates(
        candidates=candidates,
        target_dir=target_dir,
        image_extensions=image_extensions,
        dry_run=dry_run,
        verbose=verbose,
        initial_skip=initial_skip,
    )

    print("-" * 40)
    print(f"🏁 Done. Success: {result['success']}, Skipped/Error: {result['skipped']}")
    return result
