#!/usr/bin/env python3
"""
Flatpak package manager implementation
"""

import subprocess
import json
import os
import logging
import shutil
from typing import List, Optional, Dict, Any
from datetime import datetime

from .base import PackageManager, Package

logger = logging.getLogger(__name__)

class FlatpakPackageManager(PackageManager):
    """Package manager for Flatpak packages"""
    
    def __init__(self):
        super().__init__('flatpak')
    
    def list_installed_packages(self, test_mode=False) -> List[Package]:
        """List all installed flatpak packages
        
        Args:
            test_mode: If True, only process a small number of packages for testing
        """
        if not shutil.which('flatpak'):
            logger.warning("Flatpak command not found in PATH")
            print("Flatpak command not found - skipping flatpak package scan")
            return []
        
        packages = []
        
        try:
            # First check if any flatpaks are installed
            print("Checking for installed Flatpak packages...")
            check_cmd = ['flatpak', 'list', '--app', '--columns=application']
            check_result = subprocess.run(check_cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, check=False)
            
            if check_result.returncode != 0:
                logger.warning(f"Error checking flatpak: {check_result.stderr.strip()}")
                print(f"Error accessing flatpak: {check_result.stderr.strip()}")
                return []
                
            # If the output has less than 2 lines (just header or empty), no flatpaks are installed
            if len(check_result.stdout.strip().splitlines()) < 2:
                logger.info("No Flatpak packages installed")
                print("No Flatpak packages installed")
                return []
                
            # Get list of installed flatpaks
            print("Getting list of installed Flatpak packages...")
            list_cmd = ['flatpak', 'list', '--app', '--columns=application,version,installation,branch', '--show-details']
            result = subprocess.run(list_cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, check=True)
            
            # Parse output
            flatpaks = []
            for line in result.stdout.strip().splitlines()[1:]:  # Skip header
                parts = line.split()
                if len(parts) >= 2:
                    flatpaks.append({
                        'application': parts[0],
                        'version': parts[1] if len(parts) > 1 else ''
                    })
            
            # Limit in test mode
            if test_mode and flatpaks:
                flatpaks = flatpaks[:5]  # Only process 5 flatpaks in test mode
                logger.info("Running in TEST MODE - only processing 5 Flatpak packages")
                
            total_pkgs = len(flatpaks)
            logger.info(f"Found {total_pkgs} Flatpak packages to process")
            print(f"Processing {total_pkgs} Flatpak packages...")
            
            # Process each flatpak
            for i, flatpak in enumerate(flatpaks):
                app_id = flatpak.get('application', '')
                version = flatpak.get('version', '')
                
                progress_pct = ((i + 1) / total_pkgs) * 100
                print(f"\rProcessing Flatpak packages: {i+1}/{total_pkgs} ({progress_pct:.1f}%)      ", end="", flush=True)
                
                # Basic info only for faster processing
                packages.append(Package(
                    name=app_id,
                    version=version,
                    source='flatpak',
                    manually_installed=True  # All flatpaks are manually installed
                ))
            
            if total_pkgs > 0:
                print(f"\rCompleted processing {total_pkgs} Flatpak packages             ")
            
            return packages
            
        except subprocess.SubprocessError as e:
            logger.error(f"Error listing installed flatpak packages: {e}")
            print(f"Failed to list Flatpak packages: {str(e)}")
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