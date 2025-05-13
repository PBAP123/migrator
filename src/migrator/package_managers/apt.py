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
    
    def list_installed_packages(self, test_mode=False) -> List[Package]:
        """List all packages installed via APT
        
        Args:
            test_mode: If True, only process a small number of packages for testing
        """
        packages = []
        
        try:
            # First get a quick count of installed packages for feedback
            count_cmd = [self.dpkg_path, '--list']
            count_result = subprocess.run(count_cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, check=True)
            
            # In test mode, limit to a small number of packages
            pkg_lines = [line for line in count_result.stdout.splitlines() if line.startswith('ii')]
            if test_mode:
                pkg_lines = pkg_lines[:10]  # Only process 10 packages in test mode
                logger.info("Running in TEST MODE - only processing 10 packages")
                
            total_pkgs = len(pkg_lines)
            
            logger.info(f"Found {total_pkgs} APT packages to process")
            print(f"Processing {total_pkgs} APT packages, this may take a while...")
            
            # Get list of installed packages with their versions
            cmd = [self.dpkg_path, '--list']
            result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, check=True)
            
            # Parse dpkg output
            counter = 0
            progress_interval = max(1, total_pkgs // 20)  # Show progress at 5% intervals
            
            for line in result.stdout.splitlines():
                # Skip header lines
                if not line.startswith('ii'):
                    continue
                
                # In test mode, only process a limited number of packages
                if test_mode and counter >= 10:
                    break
                    
                parts = line.split()
                if len(parts) >= 3:
                    name = parts[1]
                    version = parts[2]
                    
                    counter += 1
                    if counter % progress_interval == 0 or counter == total_pkgs:
                        progress_pct = (counter / total_pkgs) * 100
                        print(f"\rProcessing APT packages: {counter}/{total_pkgs} ({progress_pct:.1f}%)      ", end="", flush=True)
                    
                    # Get basic package info without using apt-mark for every package
                    # This makes the process much faster
                    packages.append(Package(
                        name=name,
                        version=version,
                        source='apt',
                        manually_installed=False  # Will be updated later
                    ))
            
            print("\rAPT package list collected. Getting installation details...      ")
            
            # Now get manually installed status in a single call
            manual_pkgs = set()
            try:
                manual_cmd = ['apt-mark', 'showmanual']
                manual_result = subprocess.run(manual_cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, check=True)
                manual_pkgs = set(manual_result.stdout.strip().split('\n'))
            except subprocess.SubprocessError as e:
                logger.error(f"Error getting manually installed packages: {e}")
            
            # Update manually installed status
            for pkg in packages:
                if pkg.name in manual_pkgs:
                    pkg.manually_installed = True
            
            print(f"Completed processing {len(packages)} APT packages")
            return packages
        
        except subprocess.SubprocessError as e:
            logger.error(f"Error listing installed packages: {e}")
            print("Failed to list APT packages. See log for details.")
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
    
    def is_version_available(self, package_name: str, version: str) -> bool:
        """Check if a specific version of a package is available"""
        try:
            cmd = [self.apt_cache_path, 'policy', package_name]
            result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, check=True)
            
            # Extract all versions from output
            version_pattern = r'[ \t]\d+[ \t]+http'
            lines = result.stdout.splitlines()
            version_section = False
            available_versions = []
            
            for line in lines:
                if line.strip().startswith('Version table:'):
                    version_section = True
                    continue
                    
                if version_section and re.search(version_pattern, line):
                    # This line contains a version
                    version_line = line.strip().split()[0]
                    if version_line:
                        available_versions.append(version_line)
            
            return version in available_versions
            
        except subprocess.SubprocessError:
            return False
    
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
        
        # Calculate total for progress reporting
        total = len(packages)
        logger.info(f"Planning installation for {total} apt packages")
        
        # Group packages for more efficient batch checking later
        for i, pkg in enumerate(packages):
            name = pkg.get('name', '')
            version = pkg.get('version', '')
            
            # Skip if name is missing
            if not name:
                continue
                
            # Check if package is available in the repositories
            if not self.is_package_available(name):
                pkg['reason'] = 'Package not available in current repositories'
                unavailable_packages.append(pkg)
                continue
                
            # Check if specific version is requested and available
            if version and self.is_version_available(name, version):
                # Exact version is available
                available_packages.append(pkg)
                commands.append(f"apt install -y {name}={version}")
            elif version:
                # Specific version requested but not available
                latest = self.get_latest_version(name)
                if latest:
                    # A different version is available
                    pkg_copy = pkg.copy()
                    pkg_copy['available_version'] = latest
                    upgradable_packages.append(pkg_copy)
                    commands.append(f"apt install -y {name}  # Requested: {version}, Available: {latest}")
                else:
                    # No version available
                    pkg['reason'] = f'Requested version {version} not available and no alternative found'
                    unavailable_packages.append(pkg)
            else:
                # No specific version requested
                latest = self.get_latest_version(name)
                if latest:
                    # Latest version is available
                    pkg_copy = pkg.copy()
                    pkg_copy['available_version'] = latest
                    available_packages.append(pkg_copy)
                    commands.append(f"apt install -y {name}  # Will install version {latest}")
                else:
                    # Package exists in repo but no installable version found
                    pkg['reason'] = 'Package exists but no installable version found'
                    unavailable_packages.append(pkg)
            
            # Report progress periodically
            if (i+1) % 10 == 0 or (i+1) == total:
                logger.info(f"Planning progress: {i+1}/{total} packages processed")
                
        return available_packages, unavailable_packages, upgradable_packages, commands 