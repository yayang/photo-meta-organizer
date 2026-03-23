"""Shared image I/O helpers."""


def register_heif_support() -> None:
    """Registers the Pillow HEIF opener when the dependency is available."""
    try:
        from pillow_heif import register_heif_opener
    except ImportError:
        return

    register_heif_opener()
