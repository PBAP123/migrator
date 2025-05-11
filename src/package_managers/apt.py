#!/usr/bin/env python3
"""
APT package manager implementation for Debian-based systems
"""

import subprocess
import re
import os
import logging
from typing import List, Optional, Dict, Any
from datetime import datetime

from .base import PackageManager, Package

logger = logging.getLogger(__name__)

class AptPackageManager(PackageManager):
    """Package manager for APT (Debian, Ubuntu, etc.)"""
    
    def __init__(self):
        super().__init__('apt')
        self.dpkg_path = '/usr/bin/dpkg'
        self.apt_cache_path = '/usr/bin/apt-cache'
        self.apt_path = '/usr/bin/apt'
        
        # Check if we have sudo privileges
        self.has_sudo = self._check_sudo()
    
    def _check_sudo(self) -> bool:
        """Check if we have sudo privileges"""
        try:
            # Use apt instead of sudo to avoid asking for password
            subprocess.run(['apt', '--version'], 
                           stdout=subprocess.PIPE, 
                           stderr=subprocess.PIPE, 
                           check=True)
            return True
        except (subprocess.SubprocessError, FileNotFoundError):
            return False
    
    def list_installed_packages(self) -> List[Package]:
        """List all packages installed via APT"""
        packages = []
        
        try:
            # Get list of installed packages with their versions
            cmd = [self.dpkg_path, '--list']
            result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, check=True)
            
            # Parse dpkg output
            for line in result.stdout.splitlines():
                # Skip header lines
                if not line.startswith('ii'):
                    continue
                
                parts = line.split()
                if len(parts) >= 3:
                    name = parts[1]
                    version = parts[2]
                    
                    # Get description and other details
                    pkg_info = self.get_package_info(name)
                    if pkg_info:
                        packages.append(pkg_info)
                    else:
                        # Basic info only
                        packages.append(Package(
                            name=name,
                            version=version,
                            source='apt'
                        ))
            
            return packages
        
        except subprocess.SubprocessError as e:
            logger.error(f"Error listing installed packages: {e}")
            return []
    
    def get_manually_installed_packages(self) -> List[Package]:
        """Get list of packages that were explicitly installed by the user"""
        try:
            # Use apt-mark showmanual to get manually installed packages
            cmd = ['apt-mark', 'showmanual']
            result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, check=True)
            
            manual_pkgs = set(result.stdout.strip().split('\n'))
            
            # Get full package info
            packages = []
            for pkg_name in manual_pkgs:
                pkg_info = self.get_package_info(pkg_name)
                if pkg_info:
                    pkg_info.manually_installed = True
                    packages.append(pkg_info)
            
            return packages
            
        except subprocess.SubprocessError as e:
            logger.error(f"Error getting manually installed packages: {e}")
            return []
    
    def is_user_installed(self, package_name: str) -> bool:
        """Check if a package was explicitly installed by the user"""
        try:
            cmd = ['apt-mark', 'showmanual']
            result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, check=True)
            manual_pkgs = set(result.stdout.strip().split('\n'))
            return package_name in manual_pkgs
        except subprocess.SubprocessError:
            return False
    
    def is_package_available(self, package_name: str) -> bool:
        """Check if a package is available in the APT repositories"""
        try:
            cmd = [self.apt_cache_path, 'show', package_name]
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
            cmd = [self.dpkg_path, '-s', package_name]
            result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, check=True)
            
            # Parse dpkg -s output
            pkg_info = {}
            for line in result.stdout.splitlines():
                if ': ' in line:
                    key, value = line.split(': ', 1)
                    pkg_info[key] = value
            
            # Get install date (not directly available from dpkg)
            # We can check file modification time of /var/lib/dpkg/info/package.list
            install_date = None
            info_file = f"/var/lib/dpkg/info/{package_name}.list"
            if os.path.exists(info_file):
                install_date = datetime.fromtimestamp(os.path.getmtime(info_file))
            
            # Get manual installation status
            manually_installed = self.is_user_installed(package_name)
            
            return Package(
                name=package_name,
                version=pkg_info.get('Version', installed_version),
                description=pkg_info.get('Description', '').split('\n')[0],  # First line only
                source='apt',
                install_date=install_date,
                manually_installed=manually_installed
            )
            
        except subprocess.SubprocessError as e:
            logger.error(f"Error getting package info for {package_name}: {e}")
            return None
    
    def get_installed_version(self, package_name: str) -> Optional[str]:
        """Get the installed version of a package"""
        try:
            cmd = [self.dpkg_path, '-s', package_name]
            result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, check=False)
            
            if result.returncode != 0:
                return None
            
            # Extract version from output
            for line in result.stdout.splitlines():
                if line.startswith('Version: '):
                    return line.split('Version: ', 1)[1].strip()
            
            return None
            
        except subprocess.SubprocessError:
            return None
    
    def get_latest_version(self, package_name: str) -> Optional[str]:
        """Get the latest available version of a package"""
        try:
            cmd = [self.apt_cache_path, 'policy', package_name]
            result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, check=True)
            
            # Extract candidate version from output
            candidate_pattern = r'Candidate: (.+)'
            match = re.search(candidate_pattern, result.stdout)
            if match:
                return match.group(1).strip()
            
            return None
            
        except subprocess.SubprocessError:
            return None
    
    def install_package(self, package_name: str, version: Optional[str] = None) -> bool:
        """Install a package using APT"""
        if not self.has_sudo:
            logger.error("Sudo privileges required to install packages")
            return False
        
        try:
            cmd = [self.apt_path, 'install', '-y']
            if version:
                cmd.append(f"{package_name}={version}")
            else:
                cmd.append(package_name)
            
            result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, check=True)
            return result.returncode == 0
            
        except subprocess.SubprocessError as e:
            logger.error(f"Error installing package {package_name}: {e}")
            return False 