# User Manual

## Overview
Photo Meta Organizer is a CLI tool designed to help you organize your photo collection.

## Workflow (Recommended)
The tool is designed to be used with JSON parameter files for reproducibility.

1.  **Copy an example**:
    ```bash
    cp params/examples/organize.json params/my_organize.json
    ```
2.  **Edit parameters**:
    Modify `params/my_organize.json` to set your `input_dirs` and `output_dir`.
3.  **Run**:
    ```bash
    make run config=params/my_organize.json
    ```

## Features

### 1. Organize (`organize`)
Scans source directories and moves photos into a structured destination (e.g., `2023/05`).
- **Use case**: Importing photos from an SD card or phone backup.

### 2. Fix Metadata (`fix`)
Infers date/time from folder names (e.g., `1990/05`) and writes it to photo EXIF/PNG/HEIC dates or MP4/MOV `creation_time`.
- **Use case**: Scanned old photos, PNG/HEIC photos, or MP4/MOV videos that lack usable capture time metadata.

### 3. Rename (`rename`)
Renames photos to `YYYYMMDD_HHMMSS_OriginalName.ext`.
- **Use case**: Standardizing filenames across your collection.

### 4. Clean Junk (`clean-junk`)
Moves small files (below a threshold) to a `junk/` folder.
- **Use case**: Removing corrupted thumbnails or tiny system files.

## CLI Usage (Advanced)
For ad-hoc usage without JSON files, see the built-in help:
```bash
make run args="--help"
```
