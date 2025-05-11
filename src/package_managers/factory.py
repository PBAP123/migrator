#!/usr/bin/env python3
"""
Package manager factory implementation
"""

import logging
from typing import List

from .base import PackageManager
from .apt import AptPackageManager
from .snap import SnapPackageManager
from .flatpak import FlatpakPackageManager
from .appimage import AppImageManager

# Import other package managers as they are implemented
# from .dnf import DnfPackageManager
# from .pacman import PacmanPackageManager
# etc.

logger = logging.getLogger(__name__)

class PackageManagerFactory:
    """Factory for creating appropriate package managers"""
    
    @staticmethod
    def create_for_system() -> List[PackageManager]:
        """Create all available package managers for the current system"""
        package_managers = []
        
        # Try to create each package manager and add if available
        package_manager_classes = [
            AptPackageManager,
            SnapPackageManager,
            FlatpakPackageManager,
            AppImageManager,
            # Add others as they are implemented
            # DnfPackageManager,
            # PacmanPackageManager,
            # etc.
        ]
        
        for cls in package_manager_classes:
            try:
                manager = cls()
                if manager.available:
                    logger.info(f"Package manager available: {manager.name}")
                    package_managers.append(manager)
                else:
                    logger.debug(f"Package manager not available: {manager.name}")
            except Exception as e:
                logger.error(f"Error creating package manager {cls.__name__}: {e}")
        
        return package_managers 