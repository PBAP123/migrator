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
    
    def list_installed_packages(self, test_mode=False) -> List[Package]:
        """List all AppImage applications found in common locations
        
        Args:
            test_mode: If True, only process a small number of packages for testing
        """
        packages = []
        
        print("Scanning for AppImage applications...")
        logger.info("Scanning for AppImage applications in common locations")
        
        # Create a list to hold all found AppImage paths
        appimage_paths = []
        
        # Count all checked locations for progress reporting
        total_locations = sum(1 for location in self.common_locations if os.path.exists(location))
        
        if total_locations == 0:
            print("No AppImage locations found - skipping AppImage scan")
            return []
            
        # Search for .AppImage files in common locations
        for i, location in enumerate(self.common_locations):
            if not os.path.exists(location):
                continue
            
            print(f"\rScanning location {i+1}/{total_locations}: {location}", end="", flush=True)
            
            # Search both directly in the directory and one level down
            # This covers both ~/Applications/app.AppImage and ~/Applications/AppName/app.AppImage
            patterns = [
                os.path.join(location, "*.AppImage"),
                os.path.join(location, "*", "*.AppImage")
            ]
            
            for pattern in patterns:
                for appimage_path in glob.glob(pattern):
                    if os.path.isfile(appimage_path) and os.access(appimage_path, os.X_OK):
                        appimage_paths.append(appimage_path)
        
        # Limit in test mode
        if test_mode and appimage_paths:
            appimage_paths = appimage_paths[:5]  # Only process 5 AppImages in test mode
            logger.info("Running in TEST MODE - only processing 5 AppImage files")
        
        total_appimages = len(appimage_paths)
        logger.info(f"Found {total_appimages} AppImage files to process")
        print(f"\rProcessing {total_appimages} AppImage files...                                 ")
        
        # Process each AppImage
        for i, appimage_path in enumerate(appimage_paths):
            progress_pct = ((i + 1) / total_appimages) * 100 if total_appimages > 0 else 100
            print(f"\rProcessing AppImage files: {i+1}/{total_appimages} ({progress_pct:.1f}%)      ", end="", flush=True)
            
            # Extract app info from the AppImage file
            name = self._get_appimage_name(appimage_path)
            version = self._extract_version_from_filename(appimage_path)
            
            # Get modified time for install date
            install_date = datetime.fromtimestamp(os.path.getmtime(appimage_path))
            
            packages.append(Package(
                name=name,
                version=version,
                description=f"AppImage found at {appimage_path}",
                source='appimage',
                install_date=install_date,
                manually_installed=True  # AppImages are manually installed
            ))
        
        if total_appimages > 0:
            print(f"\rCompleted processing {total_appimages} AppImage files                         ")
        else:
            print("No AppImage files found")
        
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
    
    def is_version_available(self, package_name: str, version: str) -> bool:
        """Check if a specific version of an AppImage is available
        
        Note: For AppImages, we can only check if the exact version is installed.
        We can't check for availability of other versions without knowing the source.
        """
        package = self.get_package_info(package_name)
        if package and package.version == version:
            return True
        return False
    
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
        
    def plan_installation(self, packages: List[Dict[str, Any]]) -> tuple:
        """Plan package installation without executing it
        
        Args:
            packages: List of package dictionaries from backup
            
        Returns:
            Tuple of (available_packages, unavailable_packages, upgradable_packages, commands)
        """
        available_packages = []
        unavailable_packages = []
        upgradable_packages = []
        commands = []
        
        # Add note about AppImage manual installation
        commands.append("# NOTE: AppImages must be manually downloaded and installed.")
        commands.append("# The following AppImages were found in your backup:")
        
        # Calculate total for progress reporting
        total = len(packages)
        logger.info(f"Planning installation for {total} AppImage packages")
        
        # Get currently installed AppImages for comparison
        installed_appimages = self.list_installed_packages()
        installed_names = {pkg.name: pkg for pkg in installed_appimages}
        
        for i, pkg in enumerate(packages):
            name = pkg.get('name', '')
            version = pkg.get('version', '')
            
            # Skip if name is missing
            if not name:
                continue
                
            # Create a note for manual installation
            commands.append(f"# AppImage: {name} (version: {version})")
            
            if name in installed_names:
                # AppImage is already installed
                current_version = installed_names[name].version
                
                if version and current_version and version != current_version:
                    # Different version is installed
                    pkg_copy = pkg.copy()
                    pkg_copy['available_version'] = current_version
                    upgradable_packages.append(pkg_copy)
                    commands.append(f"# Already installed but different version: {current_version}")
                    commands.append(f"# Path: {self.get_appimage_path(name)}")
                else:
                    # Same version is installed
                    available_packages.append(pkg)
                    commands.append(f"# Already installed at: {self.get_appimage_path(name)}")
            else:
                # AppImage is not installed
                pkg_copy = pkg.copy()
                pkg_copy['reason'] = 'AppImage must be manually downloaded'
                unavailable_packages.append(pkg_copy)
                
                # Add suggestions for common AppImages if we can recognize them
                if "libreoffice" in name.lower():
                    commands.append("# LibreOffice AppImage can be downloaded from: https://www.libreoffice.org/download/appimage/")
                elif "gimp" in name.lower():
                    commands.append("# GIMP AppImage can be downloaded from: https://www.gimp.org/downloads/")
                elif "krita" in name.lower():
                    commands.append("# Krita AppImage can be downloaded from: https://krita.org/en/download/")
                elif "kdenlive" in name.lower():
                    commands.append("# Kdenlive AppImage can be downloaded from: https://kdenlive.org/en/download/")
                elif "glimpse" in name.lower():
                    commands.append("# Glimpse AppImage can be downloaded from: https://glimpse-editor.github.io/downloads/")
                else:
                    commands.append("# Search for this AppImage on AppImageHub: https://appimage.github.io/apps/")
                
                # Add general installation instructions
                commands.append("# After downloading, make executable: chmod +x path/to/downloaded.AppImage")
                commands.append("# And move to appropriate location: mv path/to/downloaded.AppImage ~/Applications/")
            
            # Report progress periodically
            if (i+1) % 5 == 0 or (i+1) == total:
                logger.info(f"Planning progress: {i+1}/{total} AppImage packages processed")
                
        return available_packages, unavailable_packages, upgradable_packages, commands 