"""Command Line Interface entry point using Typer."""

import sys
from typing import Optional
import typer
from photo_meta_organizer.config import load_config

# Create Typer app
app = typer.Typer(
    help="Photo Meta Organizer - Organize by time, fix metadata, batch rename",
    add_completion=False,
)


@app.command()
def organize(
    config_path: Optional[str] = typer.Option(
        None, "--config", "-c", help="Path to configuration file"
    ),
    dry_run: bool = typer.Option(
        False, "--dry-run", help="Dry run mode: print operations without executing"
    ),
    verbose: bool = typer.Option(False, "--verbose", "-v", help="Show verbose logs"),
) -> None:
    """Organize photos into target directory based on metadata."""
    from photo_meta_organizer.services.organize_photos import (
        organize as service_organize,
    )

    try:
        config = load_config(config_path)
        result = service_organize(config=config, dry_run=dry_run, verbose=verbose)

        if result["success"] > 0:
            typer.echo(f"\n✅ Successfully processed {result['success']} files")
        if result.get("errors"):
            typer.echo(f"❌ Failed {len(result['errors'])} files")

    except FileNotFoundError as e:
        typer.echo(f"❌ Error: {e}", err=True)
        raise typer.Exit(code=1)
    except Exception as e:
        typer.echo(f"❌ Execution failed: {e}", err=True)
        if verbose:
            import traceback

            traceback.print_exc()
        raise typer.Exit(code=1)


@app.command()
def fix(
    source: Optional[str] = typer.Option(
        None, "--source", "-s", help="Directory to fix (overrides fix_dir in config)"
    ),
    config_path: Optional[str] = typer.Option(
        None, "--config", "-c", help="Path to configuration file"
    ),
    dry_run: bool = typer.Option(
        False, "--dry-run", help="Dry run mode: print operations without executing"
    ),
    verbose: bool = typer.Option(False, "--verbose", "-v", help="Show verbose logs"),
) -> None:
    """Fix photo metadata based on directory names."""
    from photo_meta_organizer.services.fix_metadata import run_fix

    try:
        config = load_config(config_path)
        # Override config if source is specified
        if source:
            config["directories"]["fix_dir"] = source

        result = run_fix(config=config, dry_run=dry_run)

        if result["success"] > 0:
            typer.echo(f"\n✅ Successfully fixed {result['success']} files")

    except FileNotFoundError as e:
        typer.echo(f"❌ Error: {e}", err=True)
        raise typer.Exit(code=1)
    except Exception as e:
        typer.echo(f"❌ Execution failed: {e}", err=True)
        if verbose:
            import traceback

            traceback.print_exc()
        raise typer.Exit(code=1)


@app.command()
def rename(
    target: Optional[str] = typer.Option(
        None,
        "--target",
        "-t",
        help="Directory to rename (overrides target_dir in config)",
    ),
    config_path: Optional[str] = typer.Option(
        None, "--config", "-c", help="Path to configuration file"
    ),
    dry_run: bool = typer.Option(
        False, "--dry-run", help="Dry run mode: print operations without executing"
    ),
    verbose: bool = typer.Option(False, "--verbose", "-v", help="Show verbose logs"),
) -> None:
    """Batch rename photos to YYYYMMDD_HHMMSS_OriginalName.ext format."""
    from photo_meta_organizer.services.rename_photos import rename_process

    try:
        config = load_config(config_path)
        # Override config if target is specified
        if target:
            config["directories"]["target_dir"] = target

        result = rename_process(config=config, dry_run=dry_run, verbose=verbose)

        if result["success"] > 0:
            typer.echo(f"\n✅ Scheduled to rename {result['success']} files")

    except FileNotFoundError as e:
        typer.echo(f"❌ Error: {e}", err=True)
        raise typer.Exit(code=1)
    except Exception as e:
        typer.echo(f"❌ Execution failed: {e}", err=True)
        if verbose:
            import traceback

            traceback.print_exc()
        raise typer.Exit(code=1)


@app.command()
def clean_junk(
    threshold: Optional[float] = typer.Option(
        None, "--threshold", help="Size threshold in MB (default: use config value)"
    ),
    config_path: Optional[str] = typer.Option(
        None, "--config", "-c", help="Path to configuration file"
    ),
    dry_run: bool = typer.Option(
        False, "--dry-run", help="Dry run mode: print operations without executing"
    ),
    verbose: bool = typer.Option(False, "--verbose", "-v", help="Show verbose logs"),
) -> None:
    """Clean small files by moving them to junk directory."""
    from photo_meta_organizer.services.junk_finder import clean_small_files_recursive

    try:
        config = load_config(config_path)
        # Override config if threshold is specified
        if threshold is not None:
            config["settings"]["size_threshold_mb"] = threshold

        result = clean_small_files_recursive(
            config=config, dry_run=dry_run, verbose=verbose
        )

        if result["found"] > 0:
            typer.echo(f"\n✅ Found {result['found']} small files")

    except FileNotFoundError as e:
        typer.echo(f"❌ Error: {e}", err=True)
        raise typer.Exit(code=1)
    except Exception as e:
        typer.echo(f"❌ Execution failed: {e}", err=True)
        if verbose:
            import traceback

            traceback.print_exc()
        raise typer.Exit(code=1)


@app.command()
def run_task(
    params_file: str = typer.Argument(..., help="Path to the JSON parameters file"),
    verbose: bool = typer.Option(False, "--verbose", "-v", help="Show verbose logs"),
) -> None:
    """Execute a task defined in a JSON file."""
    import json
    from pathlib import Path

    p_file = Path(params_file)
    if not p_file.exists():
        typer.echo(f"❌ Error: Parameters file not found: {p_file}", err=True)
        raise typer.Exit(code=1)

    try:
        with open(p_file, "r", encoding="utf-8") as f:
            params = json.load(f)
    except json.JSONDecodeError as e:
        typer.echo(f"❌ Error parsing JSON: {e}", err=True)
        raise typer.Exit(code=1)

    task_name = params.get("task")
    if not task_name:
        typer.echo("❌ Error: 'task' field missing in JSON", err=True)
        raise typer.Exit(code=1)

    # Load base config
    config = load_config()

    # Ensure structure exists
    config.setdefault("directories", {})
    config.setdefault("settings", {})

    # Common params
    # Default dry_run to True if not specified anywhere (Safety first)
    dry_run = params.get("dry_run", config.get("settings", {}).get("dry_run", True))
    input_dirs = params.get("input_dirs", [])
    output_dir = params.get("output_dir")

    # Map generic JSON params to specific config structure based on task
    if task_name == "organize":
        from photo_meta_organizer.services.organize_photos import (
            organize as service_organize,
        )

        if input_dirs:
            config["directories"]["source"] = input_dirs[0]
        if output_dir:
            config["directories"]["destination"] = output_dir

        # Ensure settings exist for service consumption
        config.setdefault("settings", {})["dry_run"] = dry_run

        result = service_organize(config=config, dry_run=dry_run, verbose=verbose)

    elif task_name == "fix":
        from photo_meta_organizer.services.fix_metadata import run_fix

        if input_dirs:
            config["directories"]["fix_dir"] = input_dirs[0]

        config.setdefault("settings", {})["dry_run"] = dry_run

        result = run_fix(config=config, dry_run=dry_run)

    elif task_name == "rename":
        from photo_meta_organizer.services.rename_photos import rename_process

        if input_dirs:
            config["directories"]["target_dir"] = input_dirs[0]

        config.setdefault("settings", {})["dry_run"] = dry_run

        result = rename_process(config=config, dry_run=dry_run, verbose=verbose)

    elif task_name == "clean-junk":
        from photo_meta_organizer.services.junk_finder import (
            clean_small_files_recursive,
        )

        if input_dirs:
            config["directories"]["root_dir"] = input_dirs[0]

        # Specific param for clean-junk: threshold
        # 1. Try params['threshold']
        # 2. Try params['size_threshold_mb']
        # 3. Try config['settings']['size_threshold_mb']
        # 4. Default to 0.01 MB
        threshold = params.get("threshold") or params.get("size_threshold_mb")
        if not threshold:
            threshold = config.get("settings", {}).get("size_threshold_mb", 0.01)

        config.setdefault("settings", {})["size_threshold_mb"] = float(threshold)
        config.setdefault("settings", {})["dry_run"] = dry_run

        result = clean_small_files_recursive(
            config=config, dry_run=dry_run, verbose=verbose
        )

    else:
        typer.echo(f"❌ Error: Unknown task '{task_name}'", err=True)
        raise typer.Exit(code=1)

    # Output results (Unified simple reporting)
    if isinstance(result, dict):
        if result.get("success", 0) > 0 or result.get("found", 0) > 0:
            typer.echo(f"\n✅ Task '{task_name}' completed successfully.")
        else:
            typer.echo(f"\n⚠️ Task '{task_name}' completed but processed 0 files.")


def main() -> None:
    """CLI Main Entry Point."""
    app()


if __name__ == "__main__":
    main()
