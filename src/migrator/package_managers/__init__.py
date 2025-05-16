"""
Package managers module for migrator.

This module provides implementations for various package managers.
"""

from .base import Package, PackageManager
from .factory import PackageManagerFactory
from .apt import AptPackageManager
from .snap import SnapPackageManager
from .flatpak import FlatpakPackageManager
from .appimage import AppImageManager
from .dnf import DnfPackageManager
from .pacman import PacmanPackageManager

__all__ = [
    'Package',
    'PackageManager',
    'PackageManagerFactory',
    'AptPackageManager',
    'SnapPackageManager',
    'FlatpakPackageManager',
    'AppImageManager',
    'DnfPackageManager',
    'PacmanPackageManager',
]
