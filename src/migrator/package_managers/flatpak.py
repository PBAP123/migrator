#!/usr/bin/env python3
"""
Flatpak package manager implementation
"""

import subprocess
import json
import os
import logging
from typing import List, Optional, Dict, Any
from datetime import datetime

from .base import PackageManager, Package

logger = logging.getLogger(__name__)

class FlatpakPackageManager(PackageManager):
    """Package manager for Flatpak packages"""
    
    def __init__(self):
        super().__init__('flatpak')
    
    def list_installed_packages(self) -> List[Package]:
        """List all installed flatpak packages"""
        if not self.available:
            logger.warning("Flatpak package manager not available")
            return []
        
        packages = []
        
        try:
            # Get list of installed flatpaks in JSON format
            cmd = ['flatpak', 'list', '--app', '--columns=application,version,installation,branch', '--show-details', '--json']
            result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, check=True)
            
            # Parse JSON output
            flatpaks_data = json.loads(result.stdout)
            
            for flatpak in flatpaks_data:
                app_id = flatpak.get('application', '')
                version = flatpak.get('version', '')
                
                # Get more detailed info
                pkg_info = self.get_package_info(app_id)
                if pkg_info:
                    packages.append(pkg_info)
                else:
                    # Basic info only
                    packages.append(Package(
                        name=app_id,
                        version=version,
                        source='flatpak'
                    ))
            
            return packages
            
        except (subprocess.SubprocessError, json.JSONDecodeError) as e:
            logger.error(f"Error listing installed flatpak packages: {e}")
            return []
    
    def is_package_available(self, package_name: str) -> bool:
        """Check if a flatpak package is available in the configured remotes"""
        if not self.available:
            return False
        
        try:
            cmd = ['flatpak', 'search', '--columns=application', package_name]
            result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, check=False)
            
            if result.returncode != 0:
                return False
                
            # Check if the exact package ID is in the results
            for line in result.stdout.splitlines():
                if line.strip() == package_name:
                    return True
                    
            return False
            
        except subprocess.SubprocessError:
            return False
    
    def get_package_info(self, package_name: str) -> Optional[Package]:
        """Get detailed information about a flatpak package"""
        if not self.available:
            return None
        
        try:
            # Check if package is installed
            cmd = ['flatpak', 'info', package_name]
            result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, check=False)
            
            if result.returncode != 0:
                return None
                
            # Parse flatpak info output
            info_lines = result.stdout.splitlines()
            
            # Initialize with defaults
            version = ''
            description = ''
            install_date = None
            
            for line in info_lines:
                line = line.strip()
                
                if line.startswith('Version:'):
                    version = line.split('Version:', 1)[1].strip()
                
                elif line.startswith('Description:'):
                    description = line.split('Description:', 1)[1].strip()
                
                # Flatpak doesn't provide install date in the info command
            
            # Get install date from filesystem (approximate)
            try:
                # Flatpak apps are typically stored in /var/lib/flatpak/app/[appid]
                # or ~/.local/share/flatpak/app/[appid]
                user_path = os.path.expanduser(f"~/.local/share/flatpak/app/{package_name}")
                system_path = f"/var/lib/flatpak/app/{package_name}"
                
                if os.path.exists(user_path):
                    install_date = datetime.fromtimestamp(os.path.getmtime(user_path))
                elif os.path.exists(system_path):
                    install_date = datetime.fromtimestamp(os.path.getmtime(system_path))
            except Exception as e:
                logger.warning(f"Could not determine flatpak install date: {e}")
            
            # All flatpak packages are considered manually installed
            return Package(
                name=package_name,
                version=version,
                description=description,
                source='flatpak',
                install_date=install_date,
                manually_installed=True  # Flatpaks are typically installed manually
            )
            
        except subprocess.SubprocessError as e:
            logger.error(f"Error getting flatpak package info for {package_name}: {e}")
            return None
    
    def get_installed_version(self, package_name: str) -> Optional[str]:
        """Get the installed version of a flatpak package"""
        if not self.available:
            return None
        
        try:
            cmd = ['flatpak', 'info', package_name]
            result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, check=False)
            
            if result.returncode != 0:
                return None
            
            # Parse output
            for line in result.stdout.splitlines():
                if line.strip().startswith('Version:'):
                    return line.split('Version:', 1)[1].strip()
            
            return None
            
        except subprocess.SubprocessError:
            return None
    
    def get_latest_version(self, package_name: str) -> Optional[str]:
        """Get the latest available version of a flatpak package"""
        if not self.available:
            return None
        
        try:
            # Try to get the latest remote version using remote-info
            # First, find what remote the app is in
            remotes = []
            search_cmd = ['flatpak', 'search', '--columns=application,origin', package_name]
            search_result = subprocess.run(
                search_cmd, 
                stdout=subprocess.PIPE, 
                stderr=subprocess.PIPE, 
                text=True, 
                check=False
            )
            
            if search_result.returncode == 0:
                # Parse output to find the remote
                for line in search_result.stdout.splitlines():
                    parts = line.strip().split()
                    if len(parts) >= 2 and parts[0] == package_name:
                        remotes.append(parts[1])
            
            # Try each remote to find version info
            for remote in remotes:
                info_cmd = ['flatpak', 'remote-info', remote, package_name]
                info_result = subprocess.run(
                    info_cmd,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    text=True,
                    check=False
                )
                
                if info_result.returncode == 0:
                    # Parse the output for Version
                    for line in info_result.stdout.splitlines():
                        if line.strip().startswith("Version:"):
                            return line.split("Version:", 1)[1].strip()
            
            # Fall back to the installed version if we couldn't find remote info
            return self.get_installed_version(package_name)
            
        except subprocess.SubprocessError as e:
            logger.error(f"Error getting latest Flatpak version for {package_name}: {e}")
            return None
    
    def is_version_available(self, package_name: str, version: str) -> bool:
        """Check if a specific version of a flatpak package is available
        
        Note: Flatpak doesn't provide an easy way to check specific versions availability.
        We can only approximate this for installed packages, which doesn't really help
        for restore purposes.
        
        Flatpak packages should generally be installed at the latest version.
        """
        # For Flatpak, we'll just assume specific versions aren't available
        # and always use the latest version instead
        return False
    
    def install_package(self, package_name: str, version: Optional[str] = None) -> bool:
        """Install a flatpak package
        
        Args:
            package_name: The name of the package to install
            version: Ignored for Flatpak - we always install the latest version
                    
        Note: For Flatpak, we always install the latest version available in the remote.
        """
        if not self.available:
            logger.error("Flatpak package manager not available")
            return False
        
        try:
            cmd = ['flatpak', 'install', '-y']
            
            # Determine if we need to specify a remote
            if '/' not in package_name:
                # Try to find a remote that has this package
                search_cmd = ['flatpak', 'search', '--columns=application,origin', package_name]
                search_result = subprocess.run(
                    search_cmd, 
                    stdout=subprocess.PIPE, 
                    stderr=subprocess.PIPE, 
                    text=True, 
                    check=False
                )
                
                if search_result.returncode == 0:
                    # Parse output to find the remote
                    for line in search_result.stdout.splitlines():
                        parts = line.strip().split()
                        if len(parts) >= 2 and parts[0] == package_name:
                            remote = parts[1]
                            package_name = f"{remote}/{package_name}"
                            break
            
            cmd.append(package_name)
            
            # For Flatpak, we always install the latest version
            # Ignore any specific version parameter
            
            result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, check=True)
            return result.returncode == 0
            
        except subprocess.SubprocessError as e:
            logger.error(f"Error installing flatpak package {package_name}: {e}")
            return False
    
    def is_user_installed(self, package_name: str) -> bool:
        """Check if a flatpak package was explicitly installed by the user"""
        # All flatpak packages are considered user-installed
        return self.get_installed_version(package_name) is not None 