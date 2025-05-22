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
        # Check if flatpak is available
        self.available = shutil.which('flatpak') is not None
        
        # Initialize cached remotes list
        self._cached_remotes = None
        
        # Prefetch remotes to know if we have a properly configured Flatpak
        if self.available:
            try:
                logger.info("Checking Flatpak configuration during initialization")
                remotes = self._get_configured_remotes()
                if remotes:
                    logger.info(f"Flatpak initialized with {len(remotes)} remotes: {', '.join(remotes)}")
                else:
                    logger.warning("Flatpak is installed but no remotes are configured")
                    print("Warning: Flatpak is installed but no remotes were detected. Some features may not work correctly.")
            except Exception as e:
                logger.error(f"Error checking Flatpak configuration: {e}")
                self.available = False
    
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
            # Try a direct approach first - just use the basic flatpak list command
            # This should work in all cases and is the most reliable
            print("Checking for installed Flatpak packages...")
            cmd = ['flatpak', 'list']
            logger.info(f"Trying direct command: {' '.join(cmd)}")
            result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, check=False)
            
            if result.returncode == 0:
                lines = result.stdout.strip().splitlines()
                # Skip the header line if present
                if lines and "Name" in lines[0] and "Application ID" in lines[0]:
                    lines = lines[1:]
                    
                total_pkgs = len(lines)
                logger.info(f"Found {total_pkgs} Flatpak entries with direct command")
                
                if total_pkgs > 0:
                    print(f"Processing {total_pkgs} Flatpak packages...")
                    flatpaks_found = []
                    
                    # Process each line
                    for i, line in enumerate(lines):
                        parts = line.split()
                        if len(parts) >= 2:
                            # The Application ID is usually the second column in wide format
                            # Find the part that looks like an app ID (contains dots)
                            app_id = None
                            for part in parts:
                                if "." in part and "/" not in part:  # App IDs have dots but not slashes
                                    app_id = part
                                    break
                            
                            if app_id:
                                # Determine if this is a runtime or an actual application
                                is_runtime = (
                                    app_id.startswith("org.freedesktop.Platform") or
                                    app_id.startswith("org.kde.Platform") or
                                    app_id.startswith("org.gnome.Platform") or
                                    ".Platform." in app_id or
                                    ".Sdk." in app_id or
                                    app_id.endswith(".Gtk3theme")
                                )
                                
                                # For actual applications (not runtimes), mark them as manually installed
                                manually_installed = not is_runtime
                                
                                # Get version and other metadata
                                version = "unknown"
                                display_name = app_id
                                installation = "system"
                                
                                # Try to extract version from the line
                                for j, part in enumerate(parts):
                                    if j > parts.index(app_id) and "." in part and part != app_id:
                                        version = part
                                        break
                                
                                # Extract display name from the beginning of the line for full output
                                if "Name" in lines[0] and line.strip().startswith(app_id):
                                    # This is a simple format, just use the app ID as the name
                                    display_name = app_id
                                else:
                                    # In the full format, the name comes before the app ID
                                    name_parts = []
                                    for part in parts:
                                        if part == app_id:
                                            break
                                        name_parts.append(part)
                                    
                                    if name_parts:
                                        display_name = " ".join(name_parts)
                                
                                # Only include the app if it's not already in our list
                                if not any(pkg.get('app_id') == app_id for pkg in flatpaks_found):
                                    flatpaks_found.append({
                                        'app_id': app_id,
                                        'display_name': display_name,
                                        'version': version,
                                        'installation': installation,
                                        'is_runtime': is_runtime
                                    })
                    
                    # Count applications and runtimes
                    apps = [pkg for pkg in flatpaks_found if not pkg.get('is_runtime', False)]
                    runtimes = [pkg for pkg in flatpaks_found if pkg.get('is_runtime', False)]
                    
                    logger.info(f"Found {len(apps)} applications and {len(runtimes)} runtimes out of {len(flatpaks_found)} total Flatpak entries")
                    print(f"Found {len(apps)} Flatpak applications and {len(runtimes)} runtimes")
                    
                    # Limit in test mode
                    if test_mode:
                        if apps:
                            apps = apps[:3]
                        if runtimes:
                            runtimes = runtimes[:2]
                        logger.info("Running in TEST MODE - limiting packages processed")
                    
                    # Process applications first
                    for i, flatpak in enumerate(apps):
                        app_id = flatpak.get('app_id', '')
                        display_name = flatpak.get('display_name', '')
                        version = flatpak.get('version', '')
                        installation = flatpak.get('installation', 'unknown')
                        
                        logger.info(f"Adding Flatpak application: {app_id} ({display_name}), version {version}")
                        
                        # Store as package with application metadata in description
                        packages.append(Package(
                            name=app_id,  # Use the application ID as the name
                            version=version,
                            description=f"[FLATPAK_APP] Display name: {display_name}, Installation: {installation}",
                            source='flatpak',
                            manually_installed=True  # Applications are manually installed
                        ))
                    
                    # Then process runtimes
                    for i, flatpak in enumerate(runtimes):
                        app_id = flatpak.get('app_id', '')
                        display_name = flatpak.get('display_name', '')
                        version = flatpak.get('version', '')
                        installation = flatpak.get('installation', 'unknown')
                        
                        logger.info(f"Adding Flatpak runtime: {app_id}, version {version}")
                        
                        # Store as package with runtime metadata in description
                        packages.append(Package(
                            name=app_id,
                            version=version,
                            description=f"[FLATPAK_RUNTIME] Installation: {installation}",
                            source='flatpak',
                            manually_installed=False  # Runtimes are automatically installed
                        ))
                    
                    logger.info(f"Completed processing {len(packages)} total Flatpak packages")
                    return packages
            
            # If the direct approach didn't find anything, try the more detailed approaches
            # (Keeping the rest of the fallback logic for compatibility)
            logger.info("Direct approach didn't find applications, trying more detailed methods...")
            
            # Use a more reliable and direct approach to check for installed flatpaks
            # Try each of these commands in order until one works
            commands = [
                ['flatpak', 'list', '--app', '--columns=application'],
                ['flatpak', 'list', '--columns=application'],
                ['flatpak', 'list'],
            ]
            
            found_installed = False
            installed_count = 0
            
            for cmd in commands:
                try:
                    logger.info(f"Trying command: {' '.join(cmd)}")
                    check_result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, check=False)
                    
                    if check_result.returncode == 0:
                        output_lines = check_result.stdout.strip().splitlines()
                        installed_count = len(output_lines) - 1 if len(output_lines) > 0 else 0
                        
                        logger.info(f"Command returned {installed_count} lines (excluding header)")
                        
                        # Consider it found if we have more than just a header line
                        if installed_count > 0:
                            found_installed = True
                            logger.info(f"Found {installed_count} installed Flatpak entries")
                            break
                except Exception as e:
                    logger.warning(f"Error running command {' '.join(cmd)}: {e}")
            
            if not found_installed:
                logger.info("No Flatpak packages installed")
                print("No Flatpak packages installed")
                return []
            
            # Use a more comprehensive approach to get installed flatpaks with all info
            installations = ['--user', '--system']
            flatpaks_found = []
            
            for installation in installations:
                logger.info(f"Checking {installation} Flatpak installation")
                list_cmd = ['flatpak', 'list', '--columns=application,name,version']  # Include all, not just apps
                try:
                    result = subprocess.run(list_cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, check=False)
                    
                    if result.returncode == 0:
                        lines = result.stdout.strip().splitlines()
                        if len(lines) > 0:  # We have at least header, possibly results
                            line_count = len(lines) - 1 if len(lines) > 0 else 0
                            logger.info(f"Found {line_count} lines (excluding header) in {installation} installation")
                            
                            # Process each line after the header (if any)
                            for line_idx in range(1, len(lines)):
                                line = lines[line_idx]
                                parts = self._parse_flatpak_list_line(line)
                                
                                if len(parts) >= 3:
                                    app_id = parts[0]  # First part is always the app ID
                                    display_name = parts[1]  # Second part is display name
                                    version = parts[2]  # Third part is version
                                    
                                    # Determine if this is a runtime
                                    is_runtime = (
                                        app_id.startswith("org.freedesktop.Platform") or
                                        app_id.startswith("org.kde.Platform") or
                                        app_id.startswith("org.gnome.Platform") or
                                        ".Platform." in app_id or
                                        ".Sdk." in app_id or
                                        app_id.endswith(".Gtk3theme")
                                    )
                                    
                                    # Only add if we haven't seen this app_id yet
                                    if not any(pkg.get('app_id') == app_id for pkg in flatpaks_found):
                                        flatpaks_found.append({
                                            'app_id': app_id,
                                            'display_name': display_name,
                                            'version': version,
                                            'installation': installation,
                                            'is_runtime': is_runtime
                                        })
                                        logger.debug(f"Added {app_id} from {installation} installation")
                    else:
                        logger.warning(f"Error listing {installation} Flatpak packages: {result.stderr.strip()}")
                except Exception as e:
                    logger.warning(f"Exception listing {installation} Flatpak packages: {e}")
            
            # If we didn't find any packages with the specific installation approaches, 
            # fall back to the generic list command
            if not flatpaks_found:
                logger.info("Trying fallback generic flatpak list command")
                list_cmd = ['flatpak', 'list', '--columns=application,name,version']
                try:
                    result = subprocess.run(list_cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, check=False)
                    
                    # Parse output to extract application IDs, display names, and versions
                    if result.returncode == 0:
                        lines = result.stdout.strip().splitlines()
                        if len(lines) > 0:  # We have at least a header
                            for line_idx in range(1, len(lines)):  # Skip header
                                line = lines[line_idx]
                                parts = self._parse_flatpak_list_line(line)
                                
                                if len(parts) >= 3:
                                    app_id = parts[0]  
                                    display_name = parts[1]
                                    version = parts[2]
                                    
                                    # Determine if this is a runtime
                                    is_runtime = (
                                        app_id.startswith("org.freedesktop.Platform") or
                                        app_id.startswith("org.kde.Platform") or
                                        app_id.startswith("org.gnome.Platform") or
                                        ".Platform." in app_id or
                                        ".Sdk." in app_id or
                                        app_id.endswith(".Gtk3theme")
                                    )
                                    
                                    flatpaks_found.append({
                                        'app_id': app_id,
                                        'display_name': display_name,
                                        'version': version,
                                        'installation': 'unknown',
                                        'is_runtime': is_runtime
                                    })
                except Exception as e:
                    logger.warning(f"Error with fallback list command: {e}")
                    
                # If we still haven't found anything, try with reduced columns
                if not flatpaks_found:
                    logger.info("Trying minimal fallback flatpak list command")
                    list_cmd = ['flatpak', 'list']
                    try:
                        result = subprocess.run(list_cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, check=False)
                        
                        if result.returncode == 0:
                            lines = result.stdout.strip().splitlines()
                            if len(lines) > 0:
                                # Skip header line if present
                                if "Name" in lines[0] and "Application ID" in lines[0]:
                                    lines = lines[1:]
                                    
                                for line in lines:
                                    # Simple parsing for basic output format
                                    parts = line.strip().split()
                                    # Find part that looks like an app ID
                                    for part in parts:
                                        if "." in part and not part.startswith("/"):
                                            app_id = part
                                            # Determine if it's a runtime
                                            is_runtime = (
                                                app_id.startswith("org.freedesktop.Platform") or
                                                app_id.startswith("org.kde.Platform") or
                                                app_id.startswith("org.gnome.Platform") or
                                                ".Platform." in app_id or
                                                ".Sdk." in app_id or
                                                app_id.endswith(".Gtk3theme")
                                            )
                                            
                                            flatpaks_found.append({
                                                'app_id': app_id,
                                                'display_name': app_id,  # Use app ID as fallback display name
                                                'version': 'unknown',
                                                'installation': 'unknown',
                                                'is_runtime': is_runtime
                                            })
                                            break
                    except Exception as e:
                        logger.warning(f"Error with minimal fallback list command: {e}")
            
            # Limit in test mode
            if test_mode and flatpaks_found:
                flatpaks_found = flatpaks_found[:5]
                logger.info("Running in TEST MODE - only processing 5 Flatpak packages")
            
            # Split into apps and runtimes
            apps = [pkg for pkg in flatpaks_found if not pkg.get('is_runtime', False)]
            runtimes = [pkg for pkg in flatpaks_found if pkg.get('is_runtime', False)]
            
            logger.info(f"Found {len(apps)} applications and {len(runtimes)} runtimes out of {len(flatpaks_found)} total Flatpak entries")
            print(f"Processing {len(flatpaks_found)} Flatpak entries ({len(apps)} apps, {len(runtimes)} runtimes)...")
            
            # Process each flatpak
            for i, flatpak in enumerate(flatpaks_found):
                app_id = flatpak.get('app_id', '')
                display_name = flatpak.get('display_name', '')
                version = flatpak.get('version', '')
                installation = flatpak.get('installation', 'unknown')
                is_runtime = flatpak.get('is_runtime', False)
                
                progress_pct = ((i + 1) / len(flatpaks_found)) * 100
                print(f"\rProcessing Flatpak packages: {i+1}/{len(flatpaks_found)} ({progress_pct:.1f}%)      ", end="", flush=True)
                
                # IMPORTANT: Store the APPLICATION ID as the name
                packages.append(Package(
                    name=app_id,  # This is the APPLICATION ID, not the display name
                    version=version,
                    description=f"[{'FLATPAK_RUNTIME' if is_runtime else 'FLATPAK_APP'}] {'Installation: ' + installation if is_runtime else 'Display name: ' + display_name + ', Installation: ' + installation}",
                    source='flatpak',
                    manually_installed=not is_runtime  # Apps are manually installed, runtimes aren't
                ))
            
            if flatpaks_found:
                print(f"\rCompleted processing {len(flatpaks_found)} Flatpak packages ({len(apps)} apps, {len(runtimes)} runtimes)   ")
            
            logger.info(f"Completed processing {len(flatpaks_found)} Flatpak packages")
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
        
        Also handles tab-delimited format:
        'com.valvesoftware.Steam\tSteam\t1.0.0.78'
        """
        # First check if this is tab-delimited
        if '\t' in line:
            parts = line.strip().split('\t')
            # Make sure we have at least 3 parts
            if len(parts) >= 3:
                return [parts[0], parts[1], parts[2]]
            elif len(parts) == 2:
                # If only 2 parts, assume app_id and version
                return [parts[0], "", parts[1]]
            else:
                # Just return what we have
                return parts
        
        # Handle space-delimited format
        parts = line.strip().split()
        if len(parts) < 3:
            # Not enough parts
            logger.warning(f"Couldn't parse Flatpak line properly: {line}")
            return parts
        
        # First part is always the application ID
        app_id = parts[0]
        
        # Last part is always the version
        version = parts[-1]
        
        # Everything in between is the display name
        display_name = ' '.join(parts[1:-1])
        
        logger.debug(f"Parsed Flatpak line: ID={app_id}, Name={display_name}, Version={version}")
        return [app_id, display_name, version]
    
    def is_package_available(self, package_name: str) -> bool:
        """Check if a flatpak package is available in the configured remotes"""
        if not self.available:
            return False
        
        try:
            # Log what we're searching for
            logger.info(f"Checking flatpak availability for: {package_name}")
            
            # Get list of configured remotes (using cached version)
            logger.info("Getting list of configured Flatpak remotes")
            remotes = self._get_configured_remotes()
            
            if not remotes:
                logger.warning("No Flatpak remotes found, using global search")
            
            # Check if package_name is an application ID (contains dots)
            is_app_id = '.' in package_name
            logger.info(f"Search term appears to be an {'app ID' if is_app_id else 'display name'}")
            
            # For efficiency, try the first remote (likely flathub) first
            if remotes:
                primary_remote = remotes[0]  # First remote is typically flathub after our optimization
                try:
                    logger.info(f"Trying direct remote-info for {package_name} in primary remote {primary_remote}")
                    info_cmd = ['flatpak', 'remote-info', primary_remote, package_name]
                    info_result = subprocess.run(
                        info_cmd, 
                        stdout=subprocess.PIPE, 
                        stderr=subprocess.PIPE, 
                        text=True, 
                        check=False
                    )
                    
                    if info_result.returncode == 0:
                        logger.info(f"Found {package_name} directly in primary remote {primary_remote}")
                        return True
                except Exception as e:
                    logger.warning(f"Error checking remote-info for {package_name} in {primary_remote}: {e}")
            
            # If app ID and not found in primary remote, check other remotes directly
            if is_app_id:
                # For app IDs, try other remotes directly as it's faster than search
                for remote in remotes[1:]:  # Skip the primary remote we already checked
                    try:
                        logger.info(f"Trying direct remote-info for {package_name} in remote {remote}")
                        info_cmd = ['flatpak', 'remote-info', remote, package_name]
                        info_result = subprocess.run(
                            info_cmd, 
                            stdout=subprocess.PIPE, 
                            stderr=subprocess.PIPE, 
                            text=True, 
                            check=False
                        )
                        
                        if info_result.returncode == 0:
                            logger.info(f"Found {package_name} directly in remote {remote}")
                            return True
                    except Exception as e:
                        logger.warning(f"Error checking remote-info for {package_name} in {remote}: {e}")
                
                # For app IDs, try a global search as last resort
                try:
                    logger.info(f"Trying global search for app ID: {package_name}")
                    cmd = ['flatpak', 'search', '--columns=application', package_name]
                    result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, check=False)
                    
                    if result.returncode == 0:
                        lines = result.stdout.strip().splitlines()
                        for line in lines[1:]:  # Skip header
                            if package_name in line:
                                logger.info(f"Found {package_name} in global search results")
                                return True
                except Exception as e:
                    logger.warning(f"Error during global search for {package_name}: {e}")
                
                # If we got here and it's an app ID, it's likely not available
                logger.info(f"App ID {package_name} not found after direct checks")
                return False
            
            # For display names, we'll need to do more extensive searching
            # Try a direct global search first for efficiency
            try:
                logger.info(f"Searching globally for display name: {package_name}")
                cmd = ['flatpak', 'search', '--columns=application,name', package_name]
                result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, check=False)
                
                if result.returncode == 0:
                    lines = result.stdout.strip().splitlines()
                    logger.debug(f"Global search results for {package_name}: {len(lines)-1 if len(lines) > 0 else 0} results")
                    
                    if len(lines) > 1:  # There's at least one result beyond the header
                        logger.info(f"Found potential matches for display name: {package_name}")
                        return True
            except Exception as e:
                logger.warning(f"Error during global search for {package_name}: {e}")
            
            # As a last resort for common packages, try to check if it's installed
            # This helps with packages that might be from a remote we can't detect
            try:
                cmd = ['flatpak', 'info', package_name]
                result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, check=False)
                if result.returncode == 0:
                    logger.info(f"Package {package_name} is already installed, considering it available")
                    return True
            except Exception as e:
                logger.debug(f"Error checking if {package_name} is installed: {e}")
            
            # If we've reached here, the package is likely not available
            logger.info(f"Package {package_name} not found in any flatpak remote after searches")
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
            
        logger.info(f"Searching for app ID for display name: {display_name}")
        
        # Get list of configured remotes first
        remotes = self._get_configured_remotes()
        
        # First try searching for installed apps with this display name
        # This is the most reliable way if the app is already installed
        try:
            logger.info(f"Checking if {display_name} is already installed")
            list_cmd = ['flatpak', 'list', '--app', '--columns=application,name']
            result = subprocess.run(list_cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, check=False)
            
            if result.returncode == 0:
                # Parse each line to check for a match
                for line in result.stdout.strip().splitlines()[1:]:  # Skip header
                    parts = line.split('\t') if '\t' in line else line.split()
                    if len(parts) >= 2:
                        app_id = parts[0].strip()
                        name = ' '.join(parts[1:]).strip()
                        
                        # Check for a match
                        if display_name.lower() == name.lower() or display_name.lower() in name.lower():
                            logger.info(f"Found installed app matching {display_name}: {app_id}")
                            return app_id
        except Exception as e:
            logger.warning(f"Error checking installed apps for {display_name}: {e}")
        
        # Then try a direct global search
        try:
            cmd = ['flatpak', 'search', '--columns=application,name', display_name]
            result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, check=False)
            
            if result.returncode == 0:
                lines = result.stdout.strip().splitlines()
                logger.debug(f"Search returned {len(lines)-1 if len(lines) > 0 else 0} results for {display_name}")
                
                if len(lines) > 1:  # There's at least one result beyond the header
                    # Extract app IDs and display names
                    app_ids = []
                    for line in lines[1:]:  # Skip header
                        parts = line.split('\t') if '\t' in line else line.split()
                        if len(parts) >= 2:
                            app_id = parts[0].strip()
                            name = parts[1].strip() if len(parts) > 1 else ""
                            
                            # Check for exact match (case insensitive)
                            if name and display_name.lower() == name.lower():
                                logger.info(f"Found exact display name match: {app_id} for {display_name}")
                                return app_id
                            
                            # Save for potential fuzzy matching
                            if name:
                                app_ids.append((app_id, name))
                
                    # If we have exactly one result, use it even if not exact match
                    if len(app_ids) == 1:
                        app_id, name = app_ids[0]
                        logger.info(f"Using closest match: {app_id} for {display_name}")
                        return app_id
                    
                    # For multiple candidates, look for the one containing the display name
                    for app_id, name in app_ids:
                        if display_name.lower() in name.lower() or name.lower() in display_name.lower():
                            logger.info(f"Found fuzzy match: {app_id} for {display_name} (matched with {name})")
                            return app_id
        except Exception as e:
            logger.warning(f"Error searching globally for {display_name}: {e}")
        
        # Try each remote specifically
        for remote in remotes:
            try:
                logger.info(f"Searching in remote {remote} for {display_name}")
                cmd = ['flatpak', 'search', '--origin', remote, display_name]
                result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, check=False)
                
                if result.returncode == 0:
                    lines = result.stdout.strip().splitlines()
                    if len(lines) > 1:  # At least one result
                        # Parse first result for app ID
                        parts = lines[1].split('\t') if '\t' in lines[1] else lines[1].split()
                        if len(parts) >= 1:
                            app_id = parts[0].strip()
                            logger.info(f"Found app ID in remote {remote}: {app_id} for {display_name}")
                            return app_id
            except Exception as e:
                logger.warning(f"Error searching in remote {remote} for {display_name}: {e}")
        
        # Search in common apps as fallback
        common_apps = {
            "spotify": "com.spotify.Client",
            "flatseal": "com.github.tchx84.Flatseal",
            "heroic": "com.heroicgameslauncher.hgl",
            "heroic games launcher": "com.heroicgameslauncher.hgl",
            "spotube": "com.github.KRTirtho.Spotube",
            "discord": "com.discordapp.Discord",
            "firefox": "org.mozilla.firefox",
            "steam": "com.valvesoftware.Steam",
            "vlc": "org.videolan.VLC",
            "vscode": "com.visualstudio.code",
            "visual studio code": "com.visualstudio.code",
            "code": "com.visualstudio.code",
            "obs": "com.obsproject.Studio",
            "obs studio": "com.obsproject.Studio",
            "gimp": "org.gimp.GIMP",
            "libreoffice": "org.libreoffice.LibreOffice"
        }
        
        # Check common apps with more flexible matching
        display_name_lower = display_name.lower()
        for common_name, common_id in common_apps.items():
            if (common_name.lower() == display_name_lower or 
                common_name.lower() in display_name_lower or 
                display_name_lower in common_name.lower()):
                
                # Verify this app ID exists
                found = False
                
                # First try direct info - this works for installed apps
                try:
                    cmd = ['flatpak', 'info', common_id]
                    result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, check=False)
                    if result.returncode == 0:
                        logger.info(f"Found common app {common_id} for {display_name} (installed)")
                        return common_id
                except Exception:
                    pass
                    
                # Then check each remote 
                for remote in remotes:
                    try:
                        cmd = ['flatpak', 'remote-info', remote, common_id]
                        result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, check=False)
                        if result.returncode == 0:
                            logger.info(f"Found common app {common_id} for {display_name} in remote {remote}")
                            return common_id
                    except Exception:
                        pass
                    
        # Try more aggressive pattern matching with known prefixes
        # Convert display name to a flatpak-friendly format (lowercase, no spaces)
        friendly_name = display_name.lower().replace(' ', '')
        
        common_prefixes = [
            "com.github.",
            "org.gnome.",
            "com.",
            "org.",
            "io.",
            "net.",
            "dev."
        ]
        
        # Try each remote with each prefix
        for remote in remotes:
            for prefix in common_prefixes:
                app_id_candidate = f"{prefix}{friendly_name}"
                try:
                    cmd = ['flatpak', 'remote-info', remote, app_id_candidate]
                    result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, check=False)
                    if result.returncode == 0:
                        logger.info(f"Found app ID using pattern matching: {app_id_candidate} in remote {remote}")
                        return app_id_candidate
                except Exception:
                    pass
        
        # If we got here, we couldn't find a matching app ID
        logger.warning(f"Could not find app ID for display name: {display_name}")
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
            logger.warning("Flatpak not available, skipping plan generation")
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
        
        # Split packages into applications and runtimes
        apps = []
        runtimes = []
        
        for pkg in packages:
            # Check if this is a runtime based on description tag or name pattern
            name = pkg.get('name', '')
            description = pkg.get('description', '')
            
            is_runtime = (
                '[FLATPAK_RUNTIME]' in description or
                (name and (
                    name.startswith("org.freedesktop.Platform") or
                    name.startswith("org.kde.Platform") or
                    name.startswith("org.gnome.Platform") or
                    ".Platform." in name or
                    ".Sdk." in name or
                    name.endswith(".Gtk3theme")
                ))
            )
            
            if is_runtime:
                runtimes.append(pkg)
            else:
                apps.append(pkg)
        
        # Calculate totals for reporting
        total_apps = len(apps)
        total_runtimes = len(runtimes)
        logger.info(f"Planning installation for {total_apps} Flatpak applications and {total_runtimes} runtimes")
        
        # Get list of configured remotes once at the beginning
        configured_remotes = self._get_configured_remotes()
        
        # Add a note about the available remotes to the commands
        if configured_remotes:
            commands.append(f"# FLATPAK: Found {len(configured_remotes)} remotes: {', '.join(configured_remotes)}")
        else:
            commands.append("# FLATPAK: Warning - No remotes configured. You need to add remotes before installing packages.")
            commands.append("# FLATPAK: Run: flatpak remote-add --if-not-exists flathub https://flathub.org/repo/flathub.flatpakrepo")
        
        # Optimize: Primarily use Flathub for checking app availability
        primary_remote = 'flathub' if 'flathub' in configured_remotes else (configured_remotes[0] if configured_remotes else None)
        
        if primary_remote:
            logger.info(f"Using {primary_remote} as primary remote for package availability checks")
            commands.append(f"# FLATPAK: Using {primary_remote} as primary source for packages")
        
        # Process applications first
        if apps:
            commands.append(f"# FLATPAK: Processing {total_apps} applications")
            
            # Create a cache for app ID lookups to avoid redundant searches
            app_id_cache = {}
            
            # Process each application package
            for i, pkg in enumerate(apps):
                name = pkg.get('name', '')
                version = pkg.get('version', '')
                
                # Skip if name is missing
                if not name:
                    logger.warning(f"Skipping package with no name: {pkg}")
                    unavailable.append(pkg)
                    continue
                
                # Log progress
                logger.info(f"Processing application {i+1}/{total_apps}: {name}")
                
                # Check if this is already an app ID
                is_app_id = '.' in name
                
                if is_app_id:
                    # Optimize: Check the primary remote first if it exists
                    if primary_remote:
                        found = False
                        try:
                            logger.info(f"Checking if {name} is available in primary remote: {primary_remote}")
                            info_cmd = ['flatpak', 'remote-info', primary_remote, name]
                            info_result = subprocess.run(
                                info_cmd, 
                                stdout=subprocess.PIPE, 
                                stderr=subprocess.PIPE, 
                                text=True, 
                                check=False
                            )
                            
                            if info_result.returncode == 0:
                                logger.info(f"Found {name} directly in primary remote {primary_remote}")
                                found = True
                                available.append(pkg)
                                cmd = f"flatpak install -y {primary_remote}/{name}  # FLATPAK: Application from {primary_remote}, will install latest version"
                                if cmd not in commands:
                                    commands.append(cmd)
                        except Exception as e:
                            logger.warning(f"Error checking {name} in primary remote {primary_remote}: {e}")
                        
                        # If not found in primary remote, check others
                        if not found:
                            # Fall back to the full availability check
                            if self.is_package_available(name):
                                logger.info(f"Found app ID {name} in remotes after extended search")
                                available.append(pkg)
                                
                                # Get remote info if possible
                                remote_info = "unknown remote"
                                for remote in configured_remotes:
                                    cmd = ['flatpak', 'remote-info', remote, name]
                                    result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, check=False)
                                    if result.returncode == 0:
                                        remote_info = remote
                                        break
                                
                                # Add to install command
                                cmd = f"flatpak install -y {name}  # FLATPAK: Application from {remote_info}, will install latest version"
                                if cmd not in commands:
                                    commands.append(cmd)
                            else:
                                logger.warning(f"App ID {name} not found in any remote")
                                unavailable.append(pkg)
                                commands.append(f"# FLATPAK: Warning - Application {name} not found in any remote")
                    else:
                        # No primary remote, use the full availability check
                        if self.is_package_available(name):
                            logger.info(f"Found app ID {name} in remotes")
                            available.append(pkg)
                            
                            # Get remote info if possible
                            remote_info = "unknown remote"
                            for remote in configured_remotes:
                                cmd = ['flatpak', 'remote-info', remote, name]
                                result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, check=False)
                                if result.returncode == 0:
                                    remote_info = remote
                                    break
                            
                            # Add to install command
                            cmd = f"flatpak install -y {name}  # FLATPAK: Application from {remote_info}, will install latest version"
                            if cmd not in commands:
                                commands.append(cmd)
                        else:
                            logger.warning(f"App ID {name} not found in any remote")
                            unavailable.append(pkg)
                            commands.append(f"# FLATPAK: Warning - Application {name} not found in any remote")
                else:
                    # This is a display name - try to find the corresponding app ID
                    # First check if we already have this in our cache
                    if name in app_id_cache:
                        app_id = app_id_cache[name]
                        logger.info(f"Using cached app ID {app_id} for display name {name}")
                    else:
                        logger.info(f"Searching for app ID for display name: {name}")
                        app_id = self.get_app_id_for_display_name(name)
                        # Cache the result for future lookups
                        app_id_cache[name] = app_id
                    
                    if app_id:
                        # We found a matching app ID
                        logger.info(f"Found app ID {app_id} for display name {name}")
                        app_id_map[name] = app_id
                        
                        # Create a new package entry with the app ID
                        new_pkg = pkg.copy()
                        new_pkg['name'] = app_id
                        new_pkg['original_name'] = name
                        available.append(new_pkg)
                        
                        # Optimize: Check primary remote first
                        remote_info = "unknown remote"
                        if primary_remote:
                            cmd = ['flatpak', 'remote-info', primary_remote, app_id]
                            result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, check=False)
                            if result.returncode == 0:
                                remote_info = primary_remote
                        
                        # If not found in primary, check other remotes
                        if remote_info == "unknown remote":
                            for remote in configured_remotes:
                                if remote == primary_remote:
                                    continue  # Skip primary as we already checked it
                                cmd = ['flatpak', 'remote-info', remote, app_id]
                                result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, check=False)
                                if result.returncode == 0:
                                    remote_info = remote
                                    break
                        
                        # Add to install command
                        install_remote = f"{remote_info}/" if remote_info != "unknown remote" else ""
                        cmd = f"flatpak install -y {install_remote}{app_id}  # FLATPAK: Application {name}, from {remote_info}, will install latest version"
                        if cmd not in commands:
                            commands.append(cmd)
                    else:
                        # No matching app ID found
                        logger.warning(f"Could not find app ID for display name: {name}")
                        unavailable.append(pkg)
                        commands.append(f"# FLATPAK: Warning - Could not find app ID for application {name}")
                
                # Report progress periodically
                if (i+1) % 5 == 0 or (i+1) == total_apps:
                    logger.info(f"Planning progress: {i+1}/{total_apps} Flatpak applications processed")

        # Now process runtimes - these are typically installed automatically
        # but we'll plan them anyway for completeness
        if runtimes:
            commands.append(f"\n# FLATPAK: Processing {total_runtimes} runtimes")
            commands.append("# FLATPAK: Note - Runtimes are typically installed automatically when applications are installed")
            
            available_runtimes = []
            unavailable_runtimes = []
            
            for i, pkg in enumerate(runtimes):
                name = pkg.get('name', '')
                version = pkg.get('version', '')
                
                # Skip if name is missing
                if not name:
                    logger.warning(f"Skipping runtime with no name: {pkg}")
                    unavailable_runtimes.append(pkg)
                    continue
                
                # Check if this runtime is available
                found = False
                for remote in configured_remotes:
                    try:
                        cmd = ['flatpak', 'remote-info', remote, name]
                        result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, check=False)
                        if result.returncode == 0:
                            found = True
                            available_runtimes.append(pkg)
                            
                            # Add to commands but comment it out by default
                            cmd = f"# flatpak install -y {remote}/{name}  # FLATPAK: Runtime, typically installed automatically"
                            if cmd not in commands:
                                commands.append(cmd)
                            break
                    except Exception:
                        pass
                
                if not found:
                    unavailable_runtimes.append(pkg)
                    # Note: We don't add unavailable runtimes to commands since they're not critical
            
            # Add available runtimes to the overall available list, 
            # but don't add unavailable ones to the unavailable list
            # since runtimes are optional and automatically installed
            available.extend(available_runtimes)
            
            # Just log the unavailable runtimes
            if unavailable_runtimes:
                commands.append(f"# FLATPAK: {len(unavailable_runtimes)} runtimes not available in current remotes (typically not an issue)")
                
            logger.info(f"Found {len(available_runtimes)} available runtimes and {len(unavailable_runtimes)} unavailable")
        
        # Add a note about flatpak version handling
        if available:
            notes = [
                "# FLATPAK: Note - Flatpak always installs the latest version available",
                "# FLATPAK: Note - Specific versions requested in the backup will be ignored",
                f"# FLATPAK: Successfully mapped {len(available)}/{len(packages)} packages"
            ]
            
            for note in notes:
                if note not in commands:
                    commands.insert(0, note)
        
        return {
            "available": available,
            "unavailable": unavailable,
            "upgradable": upgradable,
            "installation_commands": commands
        }

    def _get_configured_remotes(self) -> List[str]:
        """Get a list of configured Flatpak remotes
        
        Returns:
            List of remote names
        """
        # Use cached remotes if available
        if self._cached_remotes is not None:
            logger.debug(f"Using cached remotes: {', '.join(self._cached_remotes)}")
            return self._cached_remotes
            
        remotes = []
        
        # Try different methods to detect remotes more reliably
        methods = [
            # Standard method - should work for most cases
            ('standard', ['flatpak', 'remotes', '--columns=name']),
            
            # Specifically list system remotes (will include Fedora remote)
            ('system', ['flatpak', 'remotes', '--system', '--columns=name']),
            
            # Specifically list user remotes
            ('user', ['flatpak', 'remotes', '--user', '--columns=name']),
            
            # More verbose output
            ('verbose', ['flatpak', 'remotes', '-d', '--columns=name']),
            
            # Try the list-remote command directly
            ('list-remote', ['flatpak', 'remote-list']),
            
            # Full output with all columns to catch any obscure remotes
            ('full', ['flatpak', 'remotes']),
        ]
        
        # Try each method until we find remotes
        for method_name, cmd in methods:
            try:
                logger.info(f"Trying to list Flatpak remotes using method: {method_name}")
                result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, check=False)
                
                if result.returncode == 0:
                    output = result.stdout.strip()
                    logger.debug(f"Raw output from {method_name}: {output}")
                    
                    # Skip header line and get remote names
                    lines = output.splitlines()
                    if len(lines) > 0:  # We have at least a header, possibly remotes
                        # For simple methods, assume first line is header, rest are remotes
                        if method_name in ('standard', 'system', 'user', 'verbose'):
                            new_remotes = []
                            for line in lines[1:]:
                                parts = line.strip().split()
                                if parts:
                                    remote_name = parts[0].strip()
                                    if remote_name and remote_name not in new_remotes:
                                        new_remotes.append(remote_name)
                        else:
                            # For other methods, try to parse each line
                            new_remotes = []
                            for line in lines:
                                parts = line.strip().split()
                                if parts:
                                    remote_name = parts[0].strip()
                                    # Some standard checks to avoid header lines and other non-remote entries
                                    if remote_name and remote_name not in ('Name', 'Remote', '--') and remote_name not in new_remotes:
                                        new_remotes.append(remote_name)
                                        
                        logger.info(f"Found {len(new_remotes)} remotes via {method_name}: {', '.join(new_remotes)}")
                        
                        # Add any new remotes to our list
                        for remote in new_remotes:
                            if remote and remote not in remotes:
                                remotes.append(remote)
                else:
                    logger.warning(f"Error listing Flatpak remotes via {method_name}: {result.stderr.strip()}")
            except Exception as e:
                logger.error(f"Exception getting Flatpak remotes via {method_name}: {e}")
                
        # Check specifically for known remotes, including fedora
        known_remotes = ['flathub', 'fedora', 'fedora-testing', 'gnome-nightly']
        for known_remote in known_remotes:
            if known_remote not in remotes:
                try:
                    # Try to verify if this remote exists
                    test_cmd = ['flatpak', 'remote-info', known_remote, '--system']
                    test_result = subprocess.run(test_cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, check=False)
                    
                    if test_result.returncode == 0:
                        logger.info(f"Verified known remote {known_remote} exists but wasn't in detected list")
                        remotes.append(known_remote)
                except Exception:
                    pass
        
        # If we still don't have the Fedora remote but we're on a Fedora system,
        # we can add it with high confidence
        if 'fedora' not in remotes:
            try:
                # Check if we're on Fedora
                if os.path.exists('/etc/fedora-release'):
                    logger.info("On Fedora system, adding fedora remote if not already detected")
                    # Add the fedora remote to our list, it's most likely there
                    remotes.append('fedora')
            except Exception:
                pass
        
        # Check for repositories in the filesystem
        if not remotes:
            # Check filesystem for flatpak remote configurations
            logger.info("Checking filesystem for flatpak remote configuration files")
            config_paths = [
                '/var/lib/flatpak/repo/config',  # System-wide flatpak config
                os.path.expanduser('~/.local/share/flatpak/repo/config'),  # User flatpak config
                '/etc/flatpak/remotes.d/',  # System remote configs 
                os.path.expanduser('~/.local/share/flatpak/remotes/'),  # User remote configs
                '/var/lib/flatpak/repo/', # Direct repo check
            ]
            
            for path in config_paths:
                try:
                    if os.path.exists(path):
                        logger.info(f"Found flatpak config at: {path}")
                        # If this is a directory, check for .flatpakrepo files
                        if os.path.isdir(path):
                            for file in os.listdir(path):
                                if file.endswith('.flatpakrepo'):
                                    remote_name = file.split('.')[0]
                                    logger.info(f"Found remote config for: {remote_name}")
                                    if remote_name and remote_name not in remotes:
                                        remotes.append(remote_name)
                                        
                                # Fedora repos might be in directories
                                if 'fedora' in file.lower() and 'fedora' not in remotes:
                                    remotes.append('fedora')
                except Exception as e:
                    logger.warning(f"Error checking config path {path}: {e}")
        
        # If we still haven't found flathub but we know it's commonly used
        if not remotes:
            logger.warning("No remotes found through detection methods - adding common defaults")
            remotes = ['flathub']  # Start with flathub
            
            # If on Fedora, add the fedora remote
            if os.path.exists('/etc/fedora-release'):
                remotes.append('fedora')
        
        # Always order flathub first as it's the most common
        if 'flathub' in remotes and remotes[0] != 'flathub':
            remotes.remove('flathub')
            remotes.insert(0, 'flathub')
            
        if remotes:
            logger.info(f"Final list of {len(remotes)} Flatpak remotes: {', '.join(remotes)}")
        else:
            logger.warning("No Flatpak remotes detected after trying multiple methods")
        
        # Cache the results
        self._cached_remotes = remotes
        
        return remotes 