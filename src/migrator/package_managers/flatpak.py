#!/usr/bin/env python3
"""
Flatpak package manager implementation
"""

import subprocess
import json
import os
import logging
import shutil
from typing import List, Optional, Dict, Any, Tuple
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
                
            # Get list of installed flatpaks with application ID, name and version
            print("Getting list of installed Flatpak packages...")
            list_cmd = ['flatpak', 'list', '--app', '--columns=application,name,version']
            result = subprocess.run(list_cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, check=True)
            
            # Parse output to extract application IDs, display names, and versions
            flatpaks = []
            lines = result.stdout.strip().splitlines()
            if len(lines) <= 1:  # If we only have the header or empty output
                return []
                
            for line_idx in range(1, len(lines)):  # Skip header
                line = lines[line_idx]
                # Parse the line - app_id, display_name, version
                parts = self._parse_flatpak_list_line(line)
                
                if len(parts) >= 3:
                    app_id = parts[0]  # First part is always the app ID
                    display_name = parts[1]  # Second part is display name
                    version = parts[2]  # Third part is version
                    
                    logger.debug(f"Parsed Flatpak: ID={app_id}, Name={display_name}, Version={version}")
                    
                    flatpaks.append({
                        'app_id': app_id,
                        'display_name': display_name,
                        'version': version
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
                app_id = flatpak.get('app_id', '')
                display_name = flatpak.get('display_name', '')
                version = flatpak.get('version', '')
                
                progress_pct = ((i + 1) / total_pkgs) * 100
                print(f"\rProcessing Flatpak packages: {i+1}/{total_pkgs} ({progress_pct:.1f}%)      ", end="", flush=True)
                
                # IMPORTANT: Store the APPLICATION ID as the name
                # This is the key to fixing the lookup issues
                packages.append(Package(
                    name=app_id,  # This is the APPLICATION ID, not the display name
                    version=version,
                    description=f"Display name: {display_name}",
                    source='flatpak',
                    manually_installed=True  # All flatpaks are manually installed
                ))
            
            if total_pkgs > 0:
                print(f"\rCompleted processing {total_pkgs} Flatpak packages             ")
            
            logger.info(f"Completed processing {total_pkgs} Flatpak packages")
            return packages
            
        except subprocess.SubprocessError as e:
            logger.error(f"Error listing installed flatpak packages: {e}")
            print(f"Failed to list Flatpak packages: {str(e)}")
            return []
    
    def _parse_flatpak_list_line(self, line: str) -> List[str]:
        """Parse a line from flatpak list output to handle multiword app names correctly.
        
        Example line: 'com.github.KRTirtho.Spotube  Spotube  v4.0.2'
        Should return: ['com.github.KRTirtho.Spotube', 'Spotube', 'v4.0.2']
        
        For lines with multiword names like:
        'org.onlyoffice.desktopeditors  ONLYOFFICE Desktop Editors  8.3.3'
        Should return: ['org.onlyoffice.desktopeditors', 'ONLYOFFICE Desktop Editors', '8.3.3']
        """
        parts = line.strip().split()
        if len(parts) < 3:
            # Not enough parts
            return parts
            
        # First part is always the application ID
        app_id = parts[0]
        
        # Last part is always the version
        version = parts[-1]
        
        # Everything in between is the display name
        display_name = ' '.join(parts[1:-1])
        
        return [app_id, display_name, version]
    
    def is_package_available(self, package_name: str) -> bool:
        """Check if a flatpak package is available in the configured remotes"""
        if not self.available:
            return False
        
        try:
            # Log what we're searching for
            logger.info(f"Checking flatpak availability for: {package_name}")
            
            # Check if package_name is an application ID (contains dots)
            is_app_id = '.' in package_name
            
            # First try a direct search with exact matching
            cmd = ['flatpak', 'search', '--columns=application', package_name]
            result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, check=False)
            
            if result.returncode == 0:
                # This command returns a header line followed by application IDs
                lines = result.stdout.strip().split('\n')
                if len(lines) > 1:  # There's at least one result
                    # If we're searching with an app ID, check for exact match
                    if is_app_id:
                        for line in lines[1:]:  # Skip header
                            if line.strip() == package_name:
                                return True
                    else:
                        # For a display name search, check if there's a matching application
                        # Just having results is enough since we're searching by display name
                        return len(lines) > 1
            
            # If we're here and the package_name is an app ID that wasn't found,
            # try one more search with just the app name part
            if is_app_id and '.' in package_name:
                # Get the app name part from the app ID (e.g., "Spotube" from "com.github.KRTirtho.Spotube")
                name_parts = package_name.split('.')
                if len(name_parts) > 1:
                    app_name = name_parts[-1]
                    cmd = ['flatpak', 'search', '--columns=application,name', app_name]
                    result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, check=False)
                    
                    if result.returncode == 0:
                        lines = result.stdout.strip().split('\n')
                        if len(lines) > 1:  # There's at least one result
                            for line in lines[1:]:  # Skip header
                                parts = line.split('\t')
                                if len(parts) >= 1 and parts[0].strip() == package_name:
                                    return True
            
            # If we're here and the package_name is a display name that wasn't found,
            # try to find the app ID by searching for the display name
            if not is_app_id:
                # Try a more complex search with both columns
                cmd = ['flatpak', 'search', '--columns=application,name', package_name]
                result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, check=False)
                
                if result.returncode == 0:
                    lines = result.stdout.strip().split('\n')
                    if len(lines) > 1:  # There's at least one result
                        for line in lines[1:]:  # Skip header
                            parts = line.split('\t')
                            if len(parts) >= 2:
                                app_id = parts[0].strip()
                                name = parts[1].strip()
                                # Check if the display name is part of the name field
                                if package_name.lower() in name.lower():
                                    logger.info(f"Found matching app ID {app_id} for display name {package_name}")
                                    return True
            
            # If we got here, the package is not available
            logger.info(f"Package {package_name} not found in any flatpak remote")
            return False
        except Exception as e:
            logger.error(f"Error checking flatpak package availability: {e}")
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
            display_name = ''
            install_date = None
            
            for line in info_lines:
                line = line.strip()
                
                if line.startswith('Version:'):
                    version = line.split('Version:', 1)[1].strip()
                
                elif line.startswith('Description:'):
                    description = line.split('Description:', 1)[1].strip()
                
                elif line.startswith('Name:'):
                    display_name = line.split('Name:', 1)[1].strip()
                
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
            
            # Update description to include display name if available
            if display_name:
                description = f"Display name: {display_name}" + (f", {description}" if description else "")
            
            # All flatpak packages are considered manually installed
            return Package(
                name=package_name,  # Use application ID as the name
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
        
    def get_app_id_for_display_name(self, display_name: str) -> Optional[str]:
        """
        Try to find the application ID for a display name
        
        Args:
            display_name: The display name of the application
            
        Returns:
            The application ID if found, None otherwise
        """
        # Don't try empty display names
        if not display_name:
            return None
            
        # First try exact matching with direct search
        cmd = ['flatpak', 'search', '--columns=application,name', display_name]
        result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, check=False)
        
        if result.returncode == 0:
            lines = result.stdout.strip().split('\n')
            if len(lines) > 1:  # We have at least header + one result
                # Extract app IDs and display names
                app_ids = []
                for line in lines[1:]:  # Skip header
                    parts = line.split('\t')
                    if len(parts) >= 2:
                        app_id = parts[0].strip()
                        name = parts[1].strip()
                        
                        # Check for exact match (case insensitive)
                        if display_name.lower() == name.lower():
                            logger.info(f"Found exact match: {app_id} for {display_name}")
                            return app_id
                        
                        # Save all potential matches
                        app_ids.append((app_id, name))
                
                # If no exact match but we have app IDs, use the first one as a good candidate
                if app_ids and len(app_ids) == 1:
                    app_id, name = app_ids[0]
                    logger.info(f"Using best match: {app_id} for {display_name}")
                    return app_id
                
                # For multiple candidates, check for closest match
                for app_id, name in app_ids:
                    # Check if the display name is contained in the app name (case insensitive)
                    if display_name.lower() in name.lower():
                        logger.info(f"Found partial match: {app_id} for {display_name}")
                        return app_id
        
        # If we're still here, try direct lookup for common apps
        common_apps = {
            "spotify": "com.spotify.Client",
            "flatseal": "com.github.tchx84.Flatseal",
            "heroic": "com.heroicgameslauncher.hgl",
            "spotube": "com.github.KRTirtho.Spotube"
        }
        
        # Check if the display name matches a common app (case insensitive)
        for common_name, common_id in common_apps.items():
            if display_name.lower() == common_name.lower():
                # Verify this app ID exists
                cmd = ['flatpak', 'info', common_id]
                result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, check=False)
                if result.returncode == 0:
                    logger.info(f"Found common app: {common_id} for {display_name}")
                    return common_id
        
        # If we're still here, try some common application prefixes
        common_prefixes = [
            "com.github.",
            "org.gnome.",
            "com.",
            "org.",
            "io.",
        ]
        
        # Try known Flatpak app naming patterns
        for prefix in common_prefixes:
            app_id_candidate = f"{prefix}{display_name}"
            cmd = ['flatpak', 'info', app_id_candidate]
            result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, check=False)
            if result.returncode == 0:
                logger.info(f"Found app ID using pattern matching: {app_id_candidate}")
                return app_id_candidate
        
        # If we got here, we couldn't find a matching app ID
        logger.info(f"Could not find app ID for display name: {display_name}")
        return None

    def plan_installation(self, packages: List[Dict[str, Any]]) -> Dict[str, List]:
        """
        Generate an installation plan for Flatpak packages
        
        Args:
            packages: List of packages to install
            
        Returns:
            Dict with available, unavailable, upgradable packages and installation commands
        """
        if not self.available:
            return {
                "available": [],
                "unavailable": packages,
                "upgradable": [],
                "installation_commands": []
            }
        
        available = []
        unavailable = []
        upgradable = []
        commands = []
        app_id_map = {}  # Map display names to app IDs
        
        # Calculate total for progress reporting
        total = len(packages)
        logger.info(f"Planning installation for {total} Flatpak packages")
        
        # Process packages
        for i, pkg in enumerate(packages):
            name = pkg.get('name', '')
            version = pkg.get('version', '')
            
            # Skip if name is missing
            if not name:
                unavailable.append(pkg)
                continue
                
            # Check if this is already an app ID
            is_app_id = '.' in name
            if is_app_id:
                if self.is_package_available(name):
                    available.append(pkg)
                    # Add to install command
                    cmd = f"flatpak install -y {name}  # Will install latest version"
                    if cmd not in commands:
                        commands.append(cmd)
                else:
                    unavailable.append(pkg)
            else:
                # This is a display name - try to find the corresponding app ID
                app_id = self.get_app_id_for_display_name(name)
                
                if app_id:
                    # We found a matching app ID
                    app_id_map[name] = app_id
                    
                    # Create a new package entry with the app ID
                    new_pkg = pkg.copy()
                    new_pkg['name'] = app_id
                    new_pkg['original_name'] = name
                    available.append(new_pkg)
                    
                    # Add to install command
                    cmd = f"flatpak install -y {app_id}  # {name}, Will install latest version"
                    if cmd not in commands:
                        commands.append(cmd)
                else:
                    # No matching app ID found
                    unavailable.append(pkg)
            
            # Report progress periodically
            if (i+1) % 5 == 0 or (i+1) == total:
                logger.info(f"Planning progress: {i+1}/{total} Flatpak packages processed")
        
        # Add a note about flatpak version handling
        if commands:
            commands.insert(0, "# Note: Flatpak always installs the latest version available")
            commands.insert(1, "# Specific versions requested in the backup will be ignored")
        
        return {
            "available": available,
            "unavailable": unavailable,
            "upgradable": upgradable,
            "installation_commands": commands
        } 