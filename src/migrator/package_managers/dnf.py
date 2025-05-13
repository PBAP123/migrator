#!/usr/bin/env python3
"""
DNF package manager implementation for RHEL-based systems (Fedora, CentOS, etc.)
"""

import subprocess
import re
import os
import logging
from typing import List, Optional, Dict, Any
from datetime import datetime

from .base import PackageManager, Package

logger = logging.getLogger(__name__)

class DnfPackageManager(PackageManager):
    """Package manager for DNF (Fedora, RHEL, CentOS, etc.)"""
    
    def __init__(self):
        super().__init__('dnf')
        self.rpm_path = '/usr/bin/rpm'
        self.dnf_path = '/usr/bin/dnf'
        
        # Check if we have sudo privileges
        self.has_sudo = self._check_sudo()
    
    def _check_sudo(self) -> bool:
        """Check if we have sudo privileges"""
        try:
            # Use dnf instead of sudo to avoid asking for password
            subprocess.run(['dnf', '--version'], 
                           stdout=subprocess.PIPE, 
                           stderr=subprocess.PIPE, 
                           check=True)
            return True
        except (subprocess.SubprocessError, FileNotFoundError):
            return False
    
    def list_installed_packages(self) -> List[Package]:
        """List all packages installed via DNF/RPM"""
        packages = []
        
        try:
            # Get list of installed packages with their versions
            cmd = [self.rpm_path, '-qa', '--queryformat', '%{NAME} %{VERSION}-%{RELEASE} %{SUMMARY}\\n']
            result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, check=True)
            
            # Parse rpm output
            for line in result.stdout.splitlines():
                parts = line.split(maxsplit=2)
                if len(parts) >= 2:
                    name = parts[0]
                    version = parts[1]
                    description = parts[2] if len(parts) > 2 else ""
                    
                    # Check if it was manually installed
                    manually_installed = self.is_user_installed(name)
                    
                    # Get install date
                    install_date = self._get_install_date(name)
                    
                    packages.append(Package(
                        name=name,
                        version=version,
                        description=description,
                        source='dnf',
                        install_date=install_date,
                        manually_installed=manually_installed
                    ))
            
            return packages
        
        except subprocess.SubprocessError as e:
            logger.error(f"Error listing installed packages: {e}")
            return []
    
    def _get_install_date(self, package_name: str) -> Optional[datetime]:
        """Get the installation date of a package"""
        try:
            cmd = [self.rpm_path, '-q', '--queryformat', '%{INSTALLTIME}', package_name]
            result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, check=True)
            
            # Parse timestamp
            timestamp = result.stdout.strip()
            if timestamp and timestamp.isdigit():
                return datetime.fromtimestamp(int(timestamp))
            
            return None
        except subprocess.SubprocessError:
            return None
    
    def is_user_installed(self, package_name: str) -> bool:
        """Check if a package was explicitly installed by the user"""
        try:
            # In DNF, packages explicitly installed usually appear in the "install" transaction
            cmd = ['dnf', 'history', 'userinstalled']
            result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, check=False)
            
            if result.returncode != 0:
                return False
                
            return package_name in result.stdout
        except subprocess.SubprocessError:
            return False
    
    def is_package_available(self, package_name: str) -> bool:
        """Check if a package is available in the DNF repositories"""
        try:
            cmd = [self.dnf_path, 'info', package_name]
            result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, check=False)
            return result.returncode == 0 and "Available Packages" in result.stdout
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
            cmd = [self.rpm_path, '-qi', package_name]
            result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, check=True)
            
            # Parse rpm -qi output
            package_info = {}
            for line in result.stdout.splitlines():
                if not line.strip():
                    continue
                    
                if ': ' in line:
                    key, value = line.split(': ', 1)
                    package_info[key.strip()] = value.strip()
            
            # Get install date
            install_date = self._get_install_date(package_name)
            
            # Get manual installation status
            manually_installed = self.is_user_installed(package_name)
            
            return Package(
                name=package_name,
                version=package_info.get('Version', ''),
                description=package_info.get('Summary', ''),
                source='dnf',
                install_date=install_date,
                manually_installed=manually_installed
            )
            
        except subprocess.SubprocessError as e:
            logger.error(f"Error getting package info for {package_name}: {e}")
            return None
    
    def get_installed_version(self, package_name: str) -> Optional[str]:
        """Get the installed version of a package"""
        try:
            cmd = [self.rpm_path, '-q', '--queryformat', '%{VERSION}-%{RELEASE}', package_name]
            result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, check=False)
            
            if result.returncode != 0 or not result.stdout.strip():
                return None
            
            return result.stdout.strip()
            
        except subprocess.SubprocessError:
            return None
    
    def get_latest_version(self, package_name: str) -> Optional[str]:
        """Get the latest available version of a package"""
        try:
            # Use DNF info to get the available version
            cmd = [self.dnf_path, 'info', package_name]
            result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, check=False)
            
            if result.returncode != 0:
                return None
            
            # Parse the output for the available version
            available_section = False
            for line in result.stdout.splitlines():
                if "Available Packages" in line:
                    available_section = True
                elif available_section and line.startswith("Version"):
                    return line.split(":", 1)[1].strip()
            
            return None
            
        except subprocess.SubprocessError:
            return None
    
    def is_version_available(self, package_name: str, version: str) -> bool:
        """Check if a specific version of a package is available"""
        try:
            # DNF supports listing all available versions with the --showduplicates flag
            cmd = [self.dnf_path, 'list', '--showduplicates', package_name]
            result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, check=False)
            
            if result.returncode != 0:
                return False
            
            # Parse output to find all available versions
            available_versions = []
            available_section = False
            
            for line in result.stdout.splitlines():
                if "Available Packages" in line:
                    available_section = True
                    continue
                
                if available_section and package_name in line:
                    parts = line.split()
                    if len(parts) >= 2:
                        # Extract the version from the second column
                        ver = parts[1].strip()
                        available_versions.append(ver)
            
            # Check if our version is in the list
            # Note: DNF versions may include .el8, .fc35, etc. at the end
            for available in available_versions:
                if available.startswith(version) or version.startswith(available):
                    return True
            
            return False
            
        except subprocess.SubprocessError:
            return False
    
    def install_package(self, package_name: str, version: Optional[str] = None) -> bool:
        """Install a package using DNF"""
        if not self.has_sudo:
            logger.error("Sudo privileges required to install packages")
            return False
        
        try:
            cmd = [self.dnf_path, 'install', '-y']
            
            if version:
                # For DNF, we use package-version format
                cmd.append(f"{package_name}-{version}")
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
        logger.info(f"Planning installation for {total} DNF packages")
        
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
                commands.append(f"dnf install -y {name}-{version}")
            elif version:
                # Specific version requested but not available
                latest = self.get_latest_version(name)
                if latest:
                    # A different version is available
                    pkg_copy = pkg.copy()
                    pkg_copy['available_version'] = latest
                    upgradable_packages.append(pkg_copy)
                    commands.append(f"dnf install -y {name}  # Requested: {version}, Available: {latest}")
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
                    commands.append(f"dnf install -y {name}  # Will install version {latest}")
                else:
                    # Package exists in repo but no installable version found
                    pkg['reason'] = 'Package exists but no installable version found'
                    unavailable_packages.append(pkg)
            
            # Report progress periodically
            if (i+1) % 10 == 0 or (i+1) == total:
                logger.info(f"Planning progress: {i+1}/{total} packages processed")
                
        return available_packages, unavailable_packages, upgradable_packages, commands 