"""
Bridge module: connects new clean architecture to existing business logic.

This module provides access to the existing business logic classes in
App/Models/Classes/ until they are fully migrated to the service/repository
pattern. This ensures zero business logic changes during the refactor.

Usage in API endpoints:
    from app.services.bridge import get_legacy_module
    Classes = get_legacy_module("Classes")
"""

import importlib
import sys
from pathlib import Path

# Ensure the old App directory is on the Python path
_app_dir = str(Path(__file__).resolve().parent.parent.parent / "App")
if _app_dir not in sys.path:
    sys.path.insert(0, _app_dir)


def get_legacy_classes():
    """Import and return the legacy Models.Classes module."""
    return importlib.import_module("Models.Classes")


def get_legacy_db():
    """Import and return the legacy Models.db module."""
    return importlib.import_module("Models.db")


def get_legacy_schemas():
    """Import and return the legacy Models.db.schemas module."""
    return importlib.import_module("Models.db.schemas")


def get_legacy_utils():
    """Import and return the legacy Models.utils module."""
    return importlib.import_module("Models.utils")
