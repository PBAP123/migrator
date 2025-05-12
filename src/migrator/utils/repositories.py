#!/usr/bin/env python3
"""
Repository manager module for Migrator

Handles backup and restoration of custom software repositories across different
Linux distributions with support for conflict detection and resolution.
"""

import os
import logging
import subprocess
import re
import shutil
from typing import List, Dict, Any, Optional, Tuple, Set
from pathlib import Path
import json

from ..utils.distro import get_distro_info, DistroInfo

logger = logging.getLogger(__name__)

class Repository:
    """Representation of a software repository"""
    
    def __init__(self, repo_id: str, name: str, enabled: bool, url: str, distro_type: str, repo_type: str):
        """Initialize a repository
        
        Args:
            repo_id: Unique identifier for the repository
            name: Human-readable name of the repository
            enabled: Whether the repository is enabled
            url: URL or source line of the repository
            distro_type: Type of distribution (debian, fedora, arch, etc.)
            repo_type: Type of repository (apt, dnf, pacman, flatpak, etc.)
        """
        self.repo_id = repo_id
        self.name = name
        self.enabled = enabled
        self.url = url
        self.distro_type = distro_type
        self.repo_type = repo_type
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert repository to dictionary for serialization"""
        return {
            "repo_id": self.repo_id,
            "name": self.name,
            "enabled": self.enabled,
            "url": self.url,
            "distro_type": self.distro_type,
            "repo_type": self.repo_type
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'Repository':
        """Create repository from dictionary"""
        return cls(
            repo_id=data.get("repo_id", ""),
            name=data.get("name", ""),
            enabled=data.get("enabled", True),
            url=data.get("url", ""),
            distro_type=data.get("distro_type", ""),
            repo_type=data.get("repo_type", "")
        )
    
    def is_compatible_with(self, distro_info: DistroInfo) -> bool:
        """Check if repository is compatible with given distribution
        
        Args:
            distro_info: Distribution information to check compatibility against
            
        Returns:
            Whether the repository is compatible with the distribution
        """
        # Repository from same distro type is always compatible
        if self.distro_type.lower() == distro_info.id.lower():
            return True
            
        # Check for compatible distro families
        # Debian-based: debian, ubuntu, mint, pop, elementary, etc.
        if self.distro_type.lower() in ['debian', 'ubuntu'] and distro_info.id.lower() in ['debian', 'ubuntu', 'linuxmint', 'pop', 'elementary']:
            return True
            
        # RPM-based: fedora, rhel, centos, rocky, alma, etc.
        if self.distro_type.lower() in ['fedora', 'rhel', 'centos'] and distro_info.id.lower() in ['fedora', 'rhel', 'centos', 'rocky', 'almalinux', 'oracle']:
            return True
            
        # Arch-based: arch, manjaro, endeavouros, etc.
        if self.distro_type.lower() in ['arch', 'manjaro'] and distro_info.id.lower() in ['arch', 'manjaro', 'endeavouros', 'garuda']:
            return True
            
        # Universal repositories like Flatpak remotes are compatible across distros
        if self.repo_type.lower() in ['flatpak', 'snap']:
            return True
            
        # By default, repositories are not compatible across different distro types
        return False
    
    def get_compatibility_issue(self, distro_info: DistroInfo) -> Optional[str]:
        """Get compatibility issue description if repository is not compatible
        
        Args:
            distro_info: Distribution information to check compatibility against
            
        Returns:
            Description of compatibility issue, or None if compatible
        """
        if self.is_compatible_with(distro_info):
            return None
            
        # Special cases for specific repository types
        if self.repo_type.lower() == 'apt' and distro_info.id.lower() not in ['debian', 'ubuntu', 'linuxmint', 'pop', 'elementary']:
            return f"APT repository from {self.distro_type} cannot be used with {distro_info.name}"
            
        if self.repo_type.lower() == 'ppa' and distro_info.id.lower() != 'ubuntu':
            return f"Ubuntu PPA cannot be used with {distro_info.name}"
            
        if self.repo_type.lower() == 'dnf' and distro_info.id.lower() not in ['fedora', 'rhel', 'centos', 'rocky', 'almalinux', 'oracle']:
            return f"DNF repository from {self.distro_type} cannot be used with {distro_info.name}"
            
        if self.repo_type.lower() == 'pacman' and distro_info.id.lower() not in ['arch', 'manjaro', 'endeavouros', 'garuda']:
            return f"Pacman repository from {self.distro_type} cannot be used with {distro_info.name}"
            
        # Default message
        return f"Repository from {self.distro_type} is not compatible with {distro_info.name}"


class RepositoryManager:
    """Manager for software repositories across different distributions"""
    
    def __init__(self):
        """Initialize the repository manager"""
        self.distro_info = get_distro_info()
        self.repositories: List[Repository] = []
        
        # Define repository source locations by distro family
        self.repo_locations = {
            "debian": [
                # APT sources
                "/etc/apt/sources.list",
                "/etc/apt/sources.list.d/*.list"
            ],
            "ubuntu": [
                # APT sources and PPAs
                "/etc/apt/sources.list",
                "/etc/apt/sources.list.d/*.list"
            ],
            "fedora": [
                # DNF/YUM repos
                "/etc/yum.repos.d/*.repo"
            ],
            "rhel": [
                # DNF/YUM repos
                "/etc/yum.repos.d/*.repo"
            ],
            "centos": [
                # DNF/YUM repos
                "/etc/yum.repos.d/*.repo"
            ],
            "rocky": [
                # DNF/YUM repos
                "/etc/yum.repos.d/*.repo"
            ],
            "almalinux": [
                # DNF/YUM repos
                "/etc/yum.repos.d/*.repo"
            ],
            "arch": [
                # Pacman config
                "/etc/pacman.conf",
                "/etc/pacman.d/mirrorlist"
            ],
            "manjaro": [
                # Pacman config
                "/etc/pacman.conf",
                "/etc/pacman.d/mirrorlist"
            ],
            # Common across all distributions
            "common": [
                # Flatpak
                "~/.local/share/flatpak/repo",
                "/var/lib/flatpak/repo",
                # Snap
                "/etc/snap"
            ]
        }
        
    def scan_repositories(self) -> List[Repository]:
        """Scan the system for custom repositories
        
        Returns:
            List of found repositories
        """
        distro_id = self.distro_info.id.lower()
        
        # Reset repositories list
        self.repositories = []
        
        # Map the distro to a distro family for repository scanning
        distro_family = distro_id
        if distro_id in ['linuxmint', 'pop', 'elementary']:
            distro_family = 'ubuntu'
        elif distro_id in ['endeavouros', 'garuda']:
            distro_family = 'arch'
        elif distro_id in ['rocky', 'almalinux', 'oracle']:
            distro_family = 'rhel'
        
        # Get repository locations for this distro
        locations = self.repo_locations.get(distro_family, [])
        if not locations:
            logger.warning(f"No known repository locations for {distro_id}")
            
        # Add common repository locations
        locations.extend(self.repo_locations.get("common", []))
        
        # Process by distro family
        if distro_family in ['debian', 'ubuntu']:
            self._scan_apt_repositories(locations)
            self._scan_flatpak_remotes()
            self._scan_snap_channels()
        elif distro_family in ['fedora', 'rhel', 'centos']:
            self._scan_dnf_repositories(locations)
            self._scan_flatpak_remotes()
            self._scan_snap_channels()
        elif distro_family in ['arch', 'manjaro']:
            self._scan_pacman_repositories(locations)
            self._scan_flatpak_remotes()
            self._scan_snap_channels()
        else:
            # For unsupported distros, just try common repositories
            self._scan_flatpak_remotes()
            self._scan_snap_channels()
        
        return self.repositories
    
    def _scan_apt_repositories(self, locations: List[str]) -> None:
        """Scan APT repositories
        
        Args:
            locations: List of file paths to scan
        """
        repo_files = []
        
        # Expand glob patterns in locations
        for location in locations:
            expanded_path = os.path.expanduser(location)
            if '*' in expanded_path:
                import glob
                repo_files.extend(glob.glob(expanded_path))
            elif os.path.exists(expanded_path):
                repo_files.append(expanded_path)
        
        # Process each repo file
        for repo_file in repo_files:
            try:
                with open(repo_file, 'r') as f:
                    content = f.read()
                
                # Extract repository entries
                lines = content.splitlines()
                for i, line in enumerate(lines):
                    line = line.strip()
                    
                    # Skip comments and empty lines
                    if not line or line.startswith('#'):
                        continue
                    
                    # Check for deb or deb-src entries
                    if line.startswith('deb ') or line.startswith('deb-src '):
                        # Extract parts
                        parts = line.split()
                        if len(parts) < 3:
                            continue
                        
                        repo_type = parts[0]  # deb or deb-src
                        url = parts[1]
                        components = ' '.join(parts[2:])
                        
                        # Generate a unique ID
                        repo_id = f"apt:{url.replace('/', '_')}:{components}"
                        
                        # Skip standard Ubuntu/Debian repos
                        if url in [
                            'http://archive.ubuntu.com/ubuntu',
                            'http://security.ubuntu.com/ubuntu',
                            'http://deb.debian.org/debian',
                            'http://security.debian.org/debian-security'
                        ]:
                            continue
                        
                        # Check for PPA
                        is_ppa = "ppa.launchpad.net" in url or "/ppa/" in url
                        actual_repo_type = "ppa" if is_ppa else "apt"
                        
                        # Create name from URL
                        name = url
                        if is_ppa:
                            # Extract PPA name from URL
                            ppa_match = re.search(r'ppa:([^/]+/[^/]+)', url)
                            if ppa_match:
                                name = ppa_match.group(1)
                            else:
                                ppa_parts = url.split('/')
                                if len(ppa_parts) >= 2:
                                    name = f"PPA: {ppa_parts[-2]}/{ppa_parts[-1]}"
                        
                        repo = Repository(
                            repo_id=repo_id,
                            name=name,
                            enabled=True,
                            url=line,
                            distro_type=self.distro_info.id.lower(),
                            repo_type=actual_repo_type
                        )
                        
                        self.repositories.append(repo)
            except Exception as e:
                logger.error(f"Error scanning APT repository file {repo_file}: {e}")
                
        # Check for additional APT sources using apt-key if available
        if shutil.which("apt-key"):
            try:
                result = subprocess.run(
                    ["apt-key", "list"], 
                    stdout=subprocess.PIPE, 
                    stderr=subprocess.PIPE,
                    text=True, 
                    check=False
                )
                
                if result.returncode == 0:
                    # Extract key info
                    key_entries = result.stdout.split("\n")
                    for entry in key_entries:
                        entry = entry.strip()
                        if "pub" in entry and "/" in entry:
                            # Extract key ID
                            key_id = entry.split("/")[1].split(" ")[0]
                            
                            # Skip if already included in a repository
                            if any(key_id in repo.url for repo in self.repositories):
                                continue
                                
                            # Add as repo with key info
                            repo = Repository(
                                repo_id=f"apt-key:{key_id}",
                                name=f"APT Key: {key_id}",
                                enabled=True,
                                url=f"apt-key:{key_id}",
                                distro_type=self.distro_info.id.lower(),
                                repo_type="apt-key"
                            )
                            
                            self.repositories.append(repo)
            except Exception as e:
                logger.error(f"Error scanning APT keys: {e}")
    
    def _scan_dnf_repositories(self, locations: List[str]) -> None:
        """Scan DNF/YUM repositories
        
        Args:
            locations: List of file paths to scan
        """
        repo_files = []
        
        # Expand glob patterns in locations
        for location in locations:
            expanded_path = os.path.expanduser(location)
            if '*' in expanded_path:
                import glob
                repo_files.extend(glob.glob(expanded_path))
            elif os.path.exists(expanded_path):
                repo_files.append(expanded_path)
        
        # Process each repo file
        for repo_file in repo_files:
            try:
                with open(repo_file, 'r') as f:
                    content = f.read()
                
                # Parse INI-style repo files
                current_repo = None
                name = ""
                enabled = False
                baseurl = ""
                
                lines = content.splitlines()
                for line in lines:
                    line = line.strip()
                    
                    # Skip comments and empty lines
                    if not line or line.startswith('#'):
                        continue
                    
                    # Check for section
                    if line.startswith('[') and line.endswith(']'):
                        # Save previous repo if applicable
                        if current_repo and name and baseurl:
                            repo = Repository(
                                repo_id=f"dnf:{current_repo}",
                                name=name,
                                enabled=enabled,
                                url=baseurl,
                                distro_type=self.distro_info.id.lower(),
                                repo_type="dnf"
                            )
                            
                            self.repositories.append(repo)
                            
                        # Start new repo
                        current_repo = line[1:-1]
                        name = current_repo
                        enabled = False
                        baseurl = ""
                    elif "=" in line:
                        key, value = line.split("=", 1)
                        key = key.strip().lower()
                        value = value.strip()
                        
                        if key == "name":
                            name = value
                        elif key == "enabled":
                            enabled = value == "1"
                        elif key == "baseurl":
                            baseurl = value
                
                # Save last repo
                if current_repo and name and baseurl:
                    repo = Repository(
                        repo_id=f"dnf:{current_repo}",
                        name=name,
                        enabled=enabled,
                        url=baseurl,
                        distro_type=self.distro_info.id.lower(),
                        repo_type="dnf"
                    )
                    
                    self.repositories.append(repo)
            except Exception as e:
                logger.error(f"Error scanning DNF repository file {repo_file}: {e}")
                
        # Check for additional repos using dnf repolist if available
        if shutil.which("dnf"):
            try:
                result = subprocess.run(
                    ["dnf", "repolist", "--all"], 
                    stdout=subprocess.PIPE, 
                    stderr=subprocess.PIPE,
                    text=True, 
                    check=False
                )
                
                if result.returncode == 0:
                    # Process repo list
                    lines = result.stdout.splitlines()
                    if len(lines) > 2:  # Skip header and separator lines
                        for line in lines[2:]:
                            if not line.strip():
                                continue
                                
                            # Extract repo ID and name
                            parts = line.split()
                            if not parts:
                                continue
                                
                            repo_id = parts[0]
                            
                            # Skip if already included
                            if any(repo.repo_id == f"dnf:{repo_id}" for repo in self.repositories):
                                continue
                                
                            # Add as repo
                            repo = Repository(
                                repo_id=f"dnf:{repo_id}",
                                name=repo_id,
                                enabled=True,
                                url=f"repo:{repo_id}",
                                distro_type=self.distro_info.id.lower(),
                                repo_type="dnf"
                            )
                            
                            self.repositories.append(repo)
            except Exception as e:
                logger.error(f"Error scanning DNF repos using dnf command: {e}")
    
    def _scan_pacman_repositories(self, locations: List[str]) -> None:
        """Scan Pacman repositories
        
        Args:
            locations: List of file paths to scan
        """
        repo_files = []
        
        # Expand glob patterns in locations
        for location in locations:
            expanded_path = os.path.expanduser(location)
            if '*' in expanded_path:
                import glob
                repo_files.extend(glob.glob(expanded_path))
            elif os.path.exists(expanded_path):
                repo_files.append(expanded_path)
        
        # Process pacman.conf for custom repositories
        pacman_conf = "/etc/pacman.conf"
        if pacman_conf in repo_files:
            try:
                with open(pacman_conf, 'r') as f:
                    content = f.read()
                
                # Parse repositories
                current_repo = None
                server = ""
                
                lines = content.splitlines()
                for line in lines:
                    line = line.strip()
                    
                    # Skip comments and empty lines
                    if not line or line.startswith('#'):
                        continue
                    
                    # Check for section
                    if line.startswith('[') and line.endswith(']'):
                        # Save previous repo if applicable
                        if current_repo and server and current_repo not in ['options', 'custom-options']:
                            repo = Repository(
                                repo_id=f"pacman:{current_repo}",
                                name=current_repo,
                                enabled=True,
                                url=server,
                                distro_type=self.distro_info.id.lower(),
                                repo_type="pacman"
                            )
                            
                            self.repositories.append(repo)
                            
                        # Start new repo
                        current_repo = line[1:-1]
                        server = ""
                    elif "=" in line:
                        key, value = line.split("=", 1)
                        key = key.strip().lower()
                        value = value.strip()
                        
                        if key == "server":
                            server = value
                
                # Save last repo
                if current_repo and server and current_repo not in ['options', 'custom-options']:
                    repo = Repository(
                        repo_id=f"pacman:{current_repo}",
                        name=current_repo,
                        enabled=True,
                        url=server,
                        distro_type=self.distro_info.id.lower(),
                        repo_type="pacman"
                    )
                    
                    self.repositories.append(repo)
            except Exception as e:
                logger.error(f"Error scanning Pacman config {pacman_conf}: {e}")
    
    def _scan_flatpak_remotes(self) -> None:
        """Scan Flatpak remotes"""
        if not shutil.which("flatpak"):
            logger.debug("Flatpak not found, skipping remote scan")
            return
            
        try:
            # Get system-wide remotes
            system_result = subprocess.run(
                ["flatpak", "remotes", "--system"], 
                stdout=subprocess.PIPE, 
                stderr=subprocess.PIPE,
                text=True, 
                check=False
            )
            
            # Get user remotes
            user_result = subprocess.run(
                ["flatpak", "remotes", "--user"], 
                stdout=subprocess.PIPE, 
                stderr=subprocess.PIPE,
                text=True, 
                check=False
            )
            
            remotes = []
            
            # Process system remotes
            if system_result.returncode == 0:
                for line in system_result.stdout.splitlines():
                    parts = line.split()
                    if len(parts) >= 2:
                        remotes.append((parts[0], parts[1], "system"))
            
            # Process user remotes
            if user_result.returncode == 0:
                for line in user_result.stdout.splitlines():
                    parts = line.split()
                    if len(parts) >= 2:
                        remotes.append((parts[0], parts[1], "user"))
            
            # Create repository objects for each remote
            for remote_name, url, remote_type in remotes:
                # Skip standard repositories like flathub
                if remote_name.lower() == "flathub" and "https://flathub.org" in url:
                    continue
                    
                repo = Repository(
                    repo_id=f"flatpak:{remote_name}:{remote_type}",
                    name=f"Flatpak remote: {remote_name}",
                    enabled=True,
                    url=url,
                    distro_type="common",  # Flatpak is distribution-agnostic
                    repo_type="flatpak"
                )
                
                self.repositories.append(repo)
                
        except Exception as e:
            logger.error(f"Error scanning Flatpak remotes: {e}")
    
    def _scan_snap_channels(self) -> None:
        """Scan Snap channels"""
        if not shutil.which("snap"):
            logger.debug("Snap not found, skipping channel scan")
            return
            
        try:
            # Get the list of installed snaps
            result = subprocess.run(
                ["snap", "list"], 
                stdout=subprocess.PIPE, 
                stderr=subprocess.PIPE,
                text=True, 
                check=False
            )
            
            if result.returncode == 0:
                # Process snap list
                lines = result.stdout.splitlines()
                if len(lines) > 1:  # Skip header line
                    for line in lines[1:]:
                        parts = line.split()
                        if len(parts) >= 4:
                            name = parts[0]
                            channel = parts[3]
                            
                            # Skip snaps using the default channel
                            if channel in ["stable", "latest/stable"]:
                                continue
                                
                            repo = Repository(
                                repo_id=f"snap:{name}:{channel}",
                                name=f"Snap channel: {name} ({channel})",
                                enabled=True,
                                url=f"snap:{channel}",
                                distro_type="common",  # Snap is distribution-agnostic
                                repo_type="snap"
                            )
                            
                            self.repositories.append(repo)
                
        except Exception as e:
            logger.error(f"Error scanning Snap channels: {e}")
    
    def export_repositories(self) -> Dict[str, Any]:
        """Export repositories to dictionary format for backup
        
        Returns:
            Dictionary representation of repositories
        """
        # Scan if no repositories
        if not self.repositories:
            self.scan_repositories()
            
        return {
            "distro_info": {
                "id": self.distro_info.id,
                "name": self.distro_info.name,
                "version": self.distro_info.version
            },
            "repositories": [repo.to_dict() for repo in self.repositories]
        }
    
    def check_compatibility(self, backup_data: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Check repository compatibility with current system
        
        Args:
            backup_data: Repository backup data
            
        Returns:
            List of compatibility issues
        """
        issues = []
        
        # Extract repositories from backup
        repositories = []
        for repo_data in backup_data.get("repositories", []):
            repo = Repository.from_dict(repo_data)
            repositories.append(repo)
            
        # Check each repository for compatibility
        for repo in repositories:
            issue = repo.get_compatibility_issue(self.distro_info)
            if issue:
                issues.append({
                    "repo_id": repo.repo_id,
                    "name": repo.name,
                    "repo_type": repo.repo_type,
                    "distro_type": repo.distro_type,
                    "issue": issue
                })
                
        return issues
    
    def restore_repositories(self, backup_data: Dict[str, Any], dry_run: bool = False) -> Tuple[List[str], List[Dict[str, Any]]]:
        """Restore repositories from backup data
        
        Args:
            backup_data: Repository backup data
            dry_run: If True, only simulate restoration
            
        Returns:
            Tuple of (success messages, errors/issues)
        """
        successes = []
        issues = []
        
        # Extract repositories from backup
        repositories = []
        for repo_data in backup_data.get("repositories", []):
            repo = Repository.from_dict(repo_data)
            repositories.append(repo)
            
        # Check compatibility first
        compatibility_issues = self.check_compatibility(backup_data)
        if compatibility_issues:
            for issue in compatibility_issues:
                issues.append({
                    "type": "compatibility",
                    "message": issue["issue"],
                    "repo_name": issue["name"]
                })
                
            # We'll still try to restore compatible repositories
            compatible_repos = [
                repo for repo in repositories 
                if not any(issue["repo_id"] == repo.repo_id for issue in compatibility_issues)
            ]
            repositories = compatible_repos
            
        # Group repositories by type for efficient restoration
        repos_by_type = {}
        for repo in repositories:
            if repo.repo_type not in repos_by_type:
                repos_by_type[repo.repo_type] = []
            repos_by_type[repo.repo_type].append(repo)
            
        # Restore by repository type
        if not dry_run:
            # APT repositories
            if "apt" in repos_by_type:
                apt_results = self._restore_apt_repositories(repos_by_type["apt"])
                successes.extend(apt_results[0])
                issues.extend(apt_results[1])
                
            # PPA repositories
            if "ppa" in repos_by_type:
                ppa_results = self._restore_ppa_repositories(repos_by_type["ppa"])
                successes.extend(ppa_results[0])
                issues.extend(ppa_results[1])
                
            # DNF repositories
            if "dnf" in repos_by_type:
                dnf_results = self._restore_dnf_repositories(repos_by_type["dnf"])
                successes.extend(dnf_results[0])
                issues.extend(dnf_results[1])
                
            # Pacman repositories
            if "pacman" in repos_by_type:
                pacman_results = self._restore_pacman_repositories(repos_by_type["pacman"])
                successes.extend(pacman_results[0])
                issues.extend(pacman_results[1])
                
            # Flatpak remotes
            if "flatpak" in repos_by_type:
                flatpak_results = self._restore_flatpak_remotes(repos_by_type["flatpak"])
                successes.extend(flatpak_results[0])
                issues.extend(flatpak_results[1])
                
            # Snap channels (just informational, can't really restore)
            if "snap" in repos_by_type:
                for repo in repos_by_type["snap"]:
                    parts = repo.url.split(":")
                    if len(parts) >= 2:
                        channel = parts[1]
                        successes.append(f"Snap channel info: To use {repo.name}, install with 'snap install --channel={channel}'")
        else:
            # In dry run mode, just list what would be restored
            for repo_type, repos in repos_by_type.items():
                for repo in repos:
                    successes.append(f"Would restore {repo_type} repository: {repo.name}")
                    
        return successes, issues
    
    def _restore_apt_repositories(self, repositories: List[Repository]) -> Tuple[List[str], List[Dict[str, Any]]]:
        """Restore APT repositories
        
        Args:
            repositories: List of APT repositories to restore
            
        Returns:
            Tuple of (success messages, errors/issues)
        """
        successes = []
        issues = []
        
        # Check if apt is available
        if not shutil.which("apt"):
            issues.append({
                "type": "system",
                "message": "APT package manager not available on this system"
            })
            return successes, issues
            
        # Create directory if it doesn't exist
        os.makedirs("/etc/apt/sources.list.d", exist_ok=True)
        
        # Restore each repository
        for repo in repositories:
            try:
                # Extract repository line
                repo_line = repo.url
                
                # Create a new file for this repository
                repo_id = repo.repo_id.replace("apt:", "").replace("/", "_")
                filename = f"/etc/apt/sources.list.d/migrator-{repo_id}.list"
                
                # Write the repository line to the file
                with open(filename, 'w') as f:
                    f.write(f"{repo_line}\n")
                    
                successes.append(f"Added APT repository: {repo.name}")
                
            except Exception as e:
                issues.append({
                    "type": "error",
                    "message": f"Failed to add APT repository {repo.name}: {str(e)}"
                })
                
        # Update APT cache
        try:
            result = subprocess.run(
                ["apt", "update"], 
                stdout=subprocess.PIPE, 
                stderr=subprocess.PIPE,
                text=True, 
                check=False
            )
            
            if result.returncode != 0:
                issues.append({
                    "type": "warning",
                    "message": f"APT update failed after adding repositories: {result.stderr}"
                })
        except Exception as e:
            issues.append({
                "type": "warning",
                "message": f"Failed to update APT cache: {str(e)}"
            })
            
        return successes, issues
    
    def _restore_ppa_repositories(self, repositories: List[Repository]) -> Tuple[List[str], List[Dict[str, Any]]]:
        """Restore PPA repositories
        
        Args:
            repositories: List of PPA repositories to restore
            
        Returns:
            Tuple of (success messages, errors/issues)
        """
        successes = []
        issues = []
        
        # Check if add-apt-repository is available
        if not shutil.which("add-apt-repository"):
            issues.append({
                "type": "system",
                "message": "add-apt-repository command not available on this system"
            })
            return successes, issues
            
        # Check if this is Ubuntu or compatible
        if self.distro_info.id.lower() not in ["ubuntu", "linuxmint", "pop", "elementary"]:
            issues.append({
                "type": "compatibility",
                "message": f"PPA repositories are only compatible with Ubuntu-based systems, not {self.distro_info.name}"
            })
            return successes, issues
            
        # Restore each PPA
        for repo in repositories:
            try:
                # Extract PPA name from URL or use directly
                ppa_name = repo.url
                if not ppa_name.startswith("ppa:"):
                    # Try to extract PPA from deb line
                    ppa_match = re.search(r'ppa:([^/]+/[^/]+)', ppa_name)
                    if ppa_match:
                        ppa_name = ppa_match.group(0)
                    else:
                        # Try to extract from URL
                        if "ppa.launchpad.net" in ppa_name:
                            # Format: deb http://ppa.launchpad.net/user/ppa/ubuntu distro component
                            parts = ppa_name.split()
                            if len(parts) >= 3:
                                url = parts[1]
                                user_ppa = url.split("/")
                                if len(user_ppa) >= 5:
                                    user = user_ppa[3]
                                    ppa = user_ppa[4]
                                    ppa_name = f"ppa:{user}/{ppa}"
                
                # Check if ppa_name is in correct format
                if not ppa_name.startswith("ppa:"):
                    issues.append({
                        "type": "error",
                        "message": f"Invalid PPA format: {ppa_name}"
                    })
                    continue
                    
                # Add the PPA
                result = subprocess.run(
                    ["add-apt-repository", "-y", ppa_name], 
                    stdout=subprocess.PIPE, 
                    stderr=subprocess.PIPE,
                    text=True, 
                    check=False
                )
                
                if result.returncode == 0:
                    successes.append(f"Added PPA: {ppa_name}")
                else:
                    issues.append({
                        "type": "error",
                        "message": f"Failed to add PPA {ppa_name}: {result.stderr}"
                    })
                    
            except Exception as e:
                issues.append({
                    "type": "error",
                    "message": f"Failed to add PPA {repo.name}: {str(e)}"
                })
                
        return successes, issues
    
    def _restore_dnf_repositories(self, repositories: List[Repository]) -> Tuple[List[str], List[Dict[str, Any]]]:
        """Restore DNF repositories
        
        Args:
            repositories: List of DNF repositories to restore
            
        Returns:
            Tuple of (success messages, errors/issues)
        """
        successes = []
        issues = []
        
        # Check if dnf is available
        if not shutil.which("dnf"):
            issues.append({
                "type": "system",
                "message": "DNF package manager not available on this system"
            })
            return successes, issues
            
        # Create directory if it doesn't exist
        os.makedirs("/etc/yum.repos.d", exist_ok=True)
        
        # Restore each repository
        for repo in repositories:
            try:
                # Extract repo ID and URL
                repo_id = repo.repo_id.replace("dnf:", "")
                baseurl = repo.url
                
                # Create a new repo file
                filename = f"/etc/yum.repos.d/migrator-{repo_id}.repo"
                
                # Write the repo file
                with open(filename, 'w') as f:
                    f.write(f"[{repo_id}]\n")
                    f.write(f"name={repo.name}\n")
                    f.write(f"baseurl={baseurl}\n")
                    f.write(f"enabled={'1' if repo.enabled else '0'}\n")
                    f.write("gpgcheck=0\n")
                    
                successes.append(f"Added DNF repository: {repo.name}")
                
            except Exception as e:
                issues.append({
                    "type": "error",
                    "message": f"Failed to add DNF repository {repo.name}: {str(e)}"
                })
                
        # Clean DNF cache
        try:
            subprocess.run(
                ["dnf", "clean", "all"], 
                stdout=subprocess.PIPE, 
                stderr=subprocess.PIPE,
                text=True, 
                check=False
            )
        except Exception as e:
            issues.append({
                "type": "warning",
                "message": f"Failed to clean DNF cache: {str(e)}"
            })
            
        return successes, issues
    
    def _restore_pacman_repositories(self, repositories: List[Repository]) -> Tuple[List[str], List[Dict[str, Any]]]:
        """Restore Pacman repositories
        
        Args:
            repositories: List of Pacman repositories to restore
            
        Returns:
            Tuple of (success messages, errors/issues)
        """
        successes = []
        issues = []
        
        # Check if pacman is available
        if not shutil.which("pacman"):
            issues.append({
                "type": "system",
                "message": "Pacman package manager not available on this system"
            })
            return successes, issues
            
        # Read current pacman.conf
        pacman_conf = "/etc/pacman.conf"
        if not os.path.exists(pacman_conf):
            issues.append({
                "type": "error",
                "message": f"Pacman configuration file not found: {pacman_conf}"
            })
            return successes, issues
            
        try:
            with open(pacman_conf, 'r') as f:
                content = f.readlines()
                
            # Check which repositories are already in the file
            existing_repos = []
            for line in content:
                if line.strip().startswith('[') and line.strip().endswith(']'):
                    repo_name = line.strip()[1:-1]
                    existing_repos.append(repo_name)
                    
            # Add repositories that don't already exist
            repos_to_add = []
            for repo in repositories:
                repo_id = repo.repo_id.replace("pacman:", "")
                if repo_id not in existing_repos and repo_id not in ['options', 'custom-options']:
                    repos_to_add.append(repo)
                    
            # Backup the original file
            shutil.copy2(pacman_conf, f"{pacman_conf}.migrator.bak")
            
            # Add new repositories to the end of the file
            with open(pacman_conf, 'a') as f:
                for repo in repos_to_add:
                    repo_id = repo.repo_id.replace("pacman:", "")
                    f.write(f"\n[{repo_id}]\n")
                    f.write(f"Server = {repo.url}\n")
                    
                    successes.append(f"Added Pacman repository: {repo.name}")
            
            # Update pacman database
            try:
                subprocess.run(
                    ["pacman", "-Sy"], 
                    stdout=subprocess.PIPE, 
                    stderr=subprocess.PIPE,
                    text=True, 
                    check=False
                )
            except Exception as e:
                issues.append({
                    "type": "warning",
                    "message": f"Failed to update Pacman database: {str(e)}"
                })
                
        except Exception as e:
            issues.append({
                "type": "error",
                "message": f"Failed to update Pacman configuration: {str(e)}"
            })
            
        return successes, issues
    
    def _restore_flatpak_remotes(self, repositories: List[Repository]) -> Tuple[List[str], List[Dict[str, Any]]]:
        """Restore Flatpak remotes
        
        Args:
            repositories: List of Flatpak remotes to restore
            
        Returns:
            Tuple of (success messages, errors/issues)
        """
        successes = []
        issues = []
        
        # Check if flatpak is available
        if not shutil.which("flatpak"):
            issues.append({
                "type": "system",
                "message": "Flatpak not available on this system"
            })
            return successes, issues
            
        # Get current remotes
        try:
            system_result = subprocess.run(
                ["flatpak", "remotes", "--system"], 
                stdout=subprocess.PIPE, 
                stderr=subprocess.PIPE,
                text=True, 
                check=False
            )
            
            user_result = subprocess.run(
                ["flatpak", "remotes", "--user"], 
                stdout=subprocess.PIPE, 
                stderr=subprocess.PIPE,
                text=True, 
                check=False
            )
            
            existing_remotes = []
            
            if system_result.returncode == 0:
                for line in system_result.stdout.splitlines():
                    parts = line.split()
                    if len(parts) >= 1:
                        existing_remotes.append(parts[0])
            
            if user_result.returncode == 0:
                for line in user_result.stdout.splitlines():
                    parts = line.split()
                    if len(parts) >= 1:
                        existing_remotes.append(parts[0])
                        
            # Add remotes that don't already exist
            for repo in repositories:
                parts = repo.repo_id.split(":")
                if len(parts) >= 3:
                    remote_name = parts[1]
                    remote_type = parts[2]  # system or user
                    
                    if remote_name not in existing_remotes:
                        # Add the remote
                        cmd = ["flatpak", "remote-add"]
                        if remote_type == "user":
                            cmd.append("--user")
                        else:
                            cmd.append("--system")
                            
                        cmd.extend([remote_name, repo.url])
                        
                        result = subprocess.run(
                            cmd, 
                            stdout=subprocess.PIPE, 
                            stderr=subprocess.PIPE,
                            text=True, 
                            check=False
                        )
                        
                        if result.returncode == 0:
                            successes.append(f"Added Flatpak remote: {remote_name}")
                        else:
                            issues.append({
                                "type": "error",
                                "message": f"Failed to add Flatpak remote {remote_name}: {result.stderr}"
                            })
                            
        except Exception as e:
            issues.append({
                "type": "error",
                "message": f"Failed to restore Flatpak remotes: {str(e)}"
            })
            
        return successes, issues 