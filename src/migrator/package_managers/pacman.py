#!/usr/bin/env python3
"""
Pacman package manager implementation for Arch-based systems
"""

import subprocess
import re
import os
import logging
from typing import List, Optional, Dict, Any
from datetime import datetime

from .base import PackageManager, Package

logger = logging.getLogger(__name__)

class PacmanPackageManager(PackageManager):
    """Package manager for Pacman (Arch Linux, Manjaro, etc.)"""
    
    def __init__(self):
        super().__init__('pacman')
        
        # Check if we have sudo privileges
        self.has_sudo = self._check_sudo()
    
    def _check_sudo(self) -> bool:
        """Check if we have sudo privileges"""
        try:
            # Use pacman instead of sudo to avoid asking for password
            subprocess.run(['pacman', '-V'], 
                           stdout=subprocess.PIPE, 
                           stderr=subprocess.PIPE, 
                           check=True)
            return True
        except (subprocess.SubprocessError, FileNotFoundError):
            return False
    
    def list_installed_packages(self) -> List[Package]:
        """List all packages installed via Pacman"""
        packages = []
        
        try:
            # Get list of installed packages with their versions
            cmd = ['pacman', '-Q']
            result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, check=True)
            
            # Parse pacman -Q output
            for line in result.stdout.splitlines():
                parts = line.split(maxsplit=1)
                if len(parts) >= 2:
                    name = parts[0]
                    version = parts[1]
                    
                    # Get more detailed info
                    pkg_info = self.get_package_info(name)
                    if pkg_info:
                        packages.append(pkg_info)
                    else:
                        # Basic info only
                        packages.append(Package(
                            name=name,
                            version=version,
                            source='pacman'
                        ))
            
            return packages
        
        except subprocess.SubprocessError as e:
            logger.error(f"Error listing installed packages: {e}")
            return []
    
    def is_user_installed(self, package_name: str) -> bool:
        """Check if a package was explicitly installed by the user"""
        try:
            # In Pacman, explicitly installed packages can be found with -Qe
            cmd = ['pacman', '-Qe', package_name]
            result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, check=False)
            return result.returncode == 0
        except subprocess.SubprocessError:
            return False
    
    def is_package_available(self, package_name: str) -> bool:
        """Check if a package is available in the Pacman repositories"""
        try:
            cmd = ['pacman', '-Si', package_name]
            result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, check=False)
            return result.returncode == 0
        except subprocess.SubprocessError:
            return False
    
    def get_package_info(self, package_name: str) -> Optional[Package]:
        """Get detailed information about a package"""
        try:
            # Check if installed first
            installed_version = self.get_installed_version(package_name)
            if not installed_version:
                return None
            
            # Get package details
            cmd = ['pacman', '-Qi', package_name]
            result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, check=True)
            
            # Parse pacman -Qi output
            package_info = {}
            current_key = None
            current_value = ""
            
            for line in result.stdout.splitlines():
                if not line.strip():
                    continue
                
                if ":" in line and not line.startswith(" "):
                    # New field
                    if current_key:
                        package_info[current_key] = current_value.strip()
                    
                    key, value = line.split(":", 1)
                    current_key = key.strip()
                    current_value = value.strip()
                elif line.startswith(" ") and current_key:
                    # Continuation of previous field
                    current_value += " " + line.strip()
            
            # Add the last field
            if current_key:
                package_info[current_key] = current_value.strip()
            
            # Extract install date
            install_date = None
            if "Install Date" in package_info:
                try:
                    # Format is typically: "Thu 26 Jan 2023 08:34:21"
                    date_str = package_info["Install Date"]
                    install_date = datetime.strptime(date_str, "%a %d %b %Y %H:%M:%S")
                except (ValueError, KeyError) as e:
                    logger.warning(f"Could not parse install date: {e}")
            
            # Get manual installation status
            manually_installed = self.is_user_installed(package_name)
            
            return Package(
                name=package_name,
                version=package_info.get("Version", ""),
                description=package_info.get("Description", ""),
                source='pacman',
                install_date=install_date,
                manually_installed=manually_installed
            )
            
        except subprocess.SubprocessError as e:
            logger.error(f"Error getting package info for {package_name}: {e}")
            return None
    
    def get_installed_version(self, package_name: str) -> Optional[str]:
        """Get the installed version of a package"""
        try:
            cmd = ['pacman', '-Q', package_name]
            result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, check=False)
            
            if result.returncode != 0:
                return None
            
            # Parse output
            line = result.stdout.strip()
            parts = line.split()
            if len(parts) >= 2:
                return parts[1]
            
            return None
            
        except subprocess.SubprocessError:
            return None
    
    def get_latest_version(self, package_name: str) -> Optional[str]:
        """Get the latest available version of a package"""
        try:
            cmd = ['pacman', '-Si', package_name]
            result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, check=False)
            
            if result.returncode != 0:
                return None
            
            # Parse output
            for line in result.stdout.splitlines():
                if line.startswith("Version"):
                    return line.split(":", 1)[1].strip()
            
            return None
            
        except subprocess.SubprocessError:
            return None
    
    def is_version_available(self, package_name: str, version: str) -> bool:
        """Check if a specific version of a package is available
        
        Note: Pacman typically only keeps the latest version in the repositories,
        so this will usually return True only if the version matches the latest.
        """
        latest = self.get_latest_version(package_name)
        return latest == version
    
    def install_package(self, package_name: str, version: Optional[str] = None) -> bool:
        """Install a package using Pacman
        
        Args:
            package_name: The name of the package to install
            version: The version to install (if not provided, install latest)
            
        Note: Pacman doesn't support direct version specification on the command line.
        If a specific version is needed, you need to either:
        1. Install an AUR package with specific version
        2. Downgrade using pacman cache
        3. Use a specific repository that has that version
        
        Here we just attempt to install the package with the assumption that the
        repositories have the desired version.
        """
        if not self.has_sudo:
            logger.error("Sudo privileges required to install packages")
            return False
        
        try:
            # Check if version is available
            if version:
                latest = self.get_latest_version(package_name)
                if latest != version:
                    logger.warning(f"Requested version {version} for {package_name} is not available. Latest is {latest}.")
                    return False
            
            # For Pacman, we use -S to install
            cmd = ['pacman', '-S', '--noconfirm', package_name]
            
            result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, check=True)
            return result.returncode == 0
            
        except subprocess.SubprocessError as e:
            logger.error(f"Error installing package {package_name}: {e}")
            return False 