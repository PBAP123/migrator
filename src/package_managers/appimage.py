#!/usr/bin/env python3
"""
AppImage detector for finding AppImage applications
"""

import os
import glob
import subprocess
import logging
import shutil
from typing import List, Optional, Dict, Any
from datetime import datetime
import hashlib

from .base import PackageManager, Package

logger = logging.getLogger(__name__)

class AppImageManager(PackageManager):
    """Package manager for AppImage applications"""
    
    def __init__(self):
        # AppImage is not a package manager command, but we'll
        # check for appimaged if it exists
        super().__init__('appimaged')
        
        # AppImage is always considered "available" regardless of appimaged
        # since we detect them by filesystem scanning
        self.available = True
        
        # Define common locations where AppImages are stored
        self.common_locations = [
            os.path.expanduser("~/Applications"),
            os.path.expanduser("~/.local/bin"),
            os.path.expanduser("~/bin"),
            os.path.expanduser("~/Downloads"),
            os.path.expanduser("~/Desktop"),
            "/opt",
            "/usr/local/bin"
        ]
    
    def list_installed_packages(self) -> List[Package]:
        """List all AppImage applications found in common locations"""
        packages = []
        
        # Search for .AppImage files in common locations
        for location in self.common_locations:
            if not os.path.exists(location):
                continue
                
            # Search both directly in the directory and one level down
            # This covers both ~/Applications/app.AppImage and ~/Applications/AppName/app.AppImage
            patterns = [
                os.path.join(location, "*.AppImage"),
                os.path.join(location, "*", "*.AppImage")
            ]
            
            for pattern in patterns:
                for appimage_path in glob.glob(pattern):
                    if os.path.isfile(appimage_path) and os.access(appimage_path, os.X_OK):
                        # Extract app info from the AppImage file
                        name = self._get_appimage_name(appimage_path)
                        version = self._extract_version_from_filename(appimage_path)
                        
                        # Try to get more detailed info
                        install_date = datetime.fromtimestamp(os.path.getmtime(appimage_path))
                        
                        packages.append(Package(
                            name=name,
                            version=version,
                            description=f"AppImage found at {appimage_path}",
                            source='appimage',
                            install_date=install_date,
                            manually_installed=True  # AppImages are manually installed
                        ))
        
        return packages
    
    def _get_appimage_name(self, appimage_path: str) -> str:
        """Extract a reasonable name from an AppImage file path"""
        # Extract the filename without path
        filename = os.path.basename(appimage_path)
        
        # Remove .AppImage extension
        name = filename.replace(".AppImage", "")
        
        # Try to clean up version numbers
        # Common patterns like AppName-1.2.3, AppName_1.2.3, etc.
        parts = name.split('-')
        if len(parts) > 1 and any(c.isdigit() for c in parts[-1]):
            name = '-'.join(parts[:-1])
        else:
            parts = name.split('_')
            if len(parts) > 1 and any(c.isdigit() for c in parts[-1]):
                name = '_'.join(parts[:-1])
        
        return name
    
    def _extract_version_from_filename(self, appimage_path: str) -> str:
        """Try to extract version information from the AppImage filename"""
        filename = os.path.basename(appimage_path)
        name = filename.replace(".AppImage", "")
        
        # Common patterns for version extraction
        # AppName-1.2.3.AppImage
        # AppName_1.2.3.AppImage
        # AppName-v1.2.3.AppImage
        
        version = ""
        
        # Try to find version with dash separator
        parts = name.split('-')
        if len(parts) > 1 and any(c.isdigit() for c in parts[-1]):
            version = parts[-1]
            # Remove 'v' prefix if present
            if version.startswith('v') and len(version) > 1 and version[1].isdigit():
                version = version[1:]
        
        # Try with underscore separator if dash didn't work
        if not version:
            parts = name.split('_')
            if len(parts) > 1 and any(c.isdigit() for c in parts[-1]):
                version = parts[-1]
                # Remove 'v' prefix if present
                if version.startswith('v') and len(version) > 1 and version[1].isdigit():
                    version = version[1:]
        
        return version
    
    def get_appimage_path(self, package_name: str) -> Optional[str]:
        """Find the path to an AppImage by name"""
        # Search for matching AppImage in common locations
        for package in self.list_installed_packages():
            if package.name == package_name:
                # Extract path from description
                if "found at " in package.description:
                    return package.description.split("found at ", 1)[1]
        
        return None
    
    def is_package_available(self, package_name: str) -> bool:
        """Check if an AppImage is available (installed)"""
        return self.get_appimage_path(package_name) is not None
    
    def get_package_info(self, package_name: str) -> Optional[Package]:
        """Get detailed information about an AppImage"""
        # Since AppImages are standalone, we just return the basic info
        # from the list_installed_packages search
        for package in self.list_installed_packages():
            if package.name == package_name:
                return package
        
        return None
    
    def get_installed_version(self, package_name: str) -> Optional[str]:
        """Get the installed version of an AppImage"""
        package = self.get_package_info(package_name)
        if package:
            return package.version
        return None
    
    def get_latest_version(self, package_name: str) -> Optional[str]:
        """Get the latest available version of an AppImage
        
        Note: This isn't generally possible without knowing the AppImage's source.
        We just return the installed version.
        """
        return self.get_installed_version(package_name)
    
    def install_package(self, package_name: str, version: Optional[str] = None) -> bool:
        """Install an AppImage
        
        Note: This isn't directly supported as AppImages are usually manually downloaded.
        """
        logger.error("Direct installation of AppImages is not supported. Please download manually.")
        return False
    
    def is_user_installed(self, package_name: str) -> bool:
        """Check if an AppImage was explicitly installed by the user
        
        All AppImages are considered manually installed.
        """
        return self.get_appimage_path(package_name) is not None 