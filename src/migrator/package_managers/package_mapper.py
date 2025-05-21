#!/usr/bin/env python3
"""
Package mapper module for mapping packages between different package managers
"""

import logging
import os
import json
import re
import time
import sys
from typing import Dict, List, Optional, Tuple, Any, Callable
import subprocess

logger = logging.getLogger(__name__)

class PackageMapper:
    """Maps packages between different package managers and distributions
    
    This class handles the cross-distribution package mapping functionality by:
    
    1. Using a built-in dictionary of known equivalent packages across package managers
       (apt → dnf → pacman)
    2. Applying common naming pattern transformations (e.g., python3-foo in apt → python-foo in pacman)
    3. Using package name normalization to handle common differences in naming conventions
    4. Performing package availability checks to find the best match
    5. Supporting user customization through the ~/.config/migrator/package_mappings.json file
    
    During backup restoration planning, if packages from one system (e.g., Ubuntu with apt) 
    are being restored to a different system (e.g., Fedora with dnf), this mapper will
    attempt to find the equivalent packages in the target system's repositories.
    
    Users can customize the mapping by editing their mappings file with:
    migrator edit-mappings
    """
    
    def __init__(self):
        self.equiv_map = {}
        self.load_equivalence_map()
        self.search_cache = {}  # Cache for package search results
        
    def load_equivalence_map(self):
        """Load the package equivalence map from built-in data and user customizations"""
        # Load built-in equivalence mappings
        self.equiv_map = {
            # Format: 'source_pkg_name': {'apt': 'apt_pkg_name', 'dnf': 'dnf_pkg_name', 'pacman': 'pacman_pkg_name'}
            
            # Common desktop applications
            'libreoffice': {
                'apt': 'libreoffice',
                'dnf': 'libreoffice',
                'pacman': 'libreoffice-still',
            },
            'firefox': {
                'apt': 'firefox',
                'dnf': 'firefox',
                'pacman': 'firefox',
            },
            'chromium': {
                'apt': 'chromium-browser',
                'dnf': 'chromium',
                'pacman': 'chromium',
            },
            'thunderbird': {
                'apt': 'thunderbird',
                'dnf': 'thunderbird',
                'pacman': 'thunderbird',
            },
            'vlc': {
                'apt': 'vlc',
                'dnf': 'vlc',
                'pacman': 'vlc',
            },
            
            # Development tools
            'git': {
                'apt': 'git',
                'dnf': 'git',
                'pacman': 'git',
            },
            'gcc': {
                'apt': 'gcc',
                'dnf': 'gcc',
                'pacman': 'gcc',
            },
            'g++': {
                'apt': 'g++',
                'dnf': 'gcc-c++',
                'pacman': 'gcc',
            },
            'make': {
                'apt': 'make',
                'dnf': 'make',
                'pacman': 'make',
            },
            'cmake': {
                'apt': 'cmake',
                'dnf': 'cmake',
                'pacman': 'cmake',
            },
            'python3': {
                'apt': 'python3',
                'dnf': 'python3',
                'pacman': 'python',
            },
            'python3-pip': {
                'apt': 'python3-pip',
                'dnf': 'python3-pip',
                'pacman': 'python-pip',
            },
            
            # System utilities
            'htop': {
                'apt': 'htop',
                'dnf': 'htop',
                'pacman': 'htop',
            },
            'curl': {
                'apt': 'curl',
                'dnf': 'curl',
                'pacman': 'curl',
            },
            'wget': {
                'apt': 'wget',
                'dnf': 'wget',
                'pacman': 'wget',
            },
            'nano': {
                'apt': 'nano',
                'dnf': 'nano',
                'pacman': 'nano',
            },
            'vim': {
                'apt': 'vim',
                'dnf': 'vim',
                'pacman': 'vim',
            },
            
            # Media codecs and drivers
            'ffmpeg': {
                'apt': 'ffmpeg',
                'dnf': 'ffmpeg',
                'pacman': 'ffmpeg',
            },
            'gstreamer': {
                'apt': 'gstreamer1.0-plugins-good',
                'dnf': 'gstreamer1-plugins-good',
                'pacman': 'gst-plugins-good',
            },
        }
        
        # Try to load user custom mappings and merge them
        user_map_path = os.path.expanduser('~/.config/migrator/package_mappings.json')
        if os.path.exists(user_map_path):
            try:
                with open(user_map_path, 'r') as f:
                    user_map = json.load(f)
                # Merge user map with built-in map (user mappings take precedence)
                for pkg, mappings in user_map.items():
                    if pkg in self.equiv_map:
                        self.equiv_map[pkg].update(mappings)
                    else:
                        self.equiv_map[pkg] = mappings
                logger.info(f"Loaded {len(user_map)} custom package mappings from {user_map_path}")
            except Exception as e:
                logger.error(f"Error loading custom package mappings: {e}")
    
    def process_package_batch(self, packages: List[Dict], source_type: str, target_type: str, 
                             available_check_fn: Callable = None, 
                             progress_callback: Callable = None) -> List[Tuple[Dict, Optional[str]]]:
        """Process a batch of packages to find equivalent names
        
        Args:
            packages: List of package dictionaries
            source_type: Source package manager type
            target_type: Target package manager type
            available_check_fn: Function to check if a package is available
            progress_callback: Function to report progress
            
        Returns:
            List of tuples containing (original package dict, equivalent package name or None)
        """
        results = []
        total_packages = len(packages)
        
        # Print initial progress message
        if progress_callback:
            progress_callback(0, total_packages, "Starting package mapping")
        else:
            print(f"Finding equivalent packages: 0/{total_packages} (0%)")
            sys.stdout.flush()
        
        # Keep track of last progress update time to avoid too frequent updates
        last_update_time = time.time()
        
        # Process each package
        for i, pkg in enumerate(packages):
            pkg_name = pkg.get('name', '')
            if not pkg_name:
                results.append((pkg, None))
                continue
                
            # Find equivalent package name
            equivalent_name = self.get_equivalent_package(
                pkg_name, source_type, target_type)
                
            # Check if the equivalent package is available (if a check function was provided)
            if equivalent_name and available_check_fn and not available_check_fn(equivalent_name):
                # Try to find a similar package
                similar_name = self.find_package_with_similar_name(
                    equivalent_name, target_type, available_check_fn)
                
                if similar_name:
                    equivalent_name = similar_name
                else:
                    # If no similar package found, just keep the equivalent name
                    # The calling code will handle it as unavailable
                    pass
            
            # Add result
            results.append((pkg, equivalent_name))
            
            # Update progress
            current_time = time.time()
            if current_time - last_update_time >= 0.5 or i == total_packages - 1:  # Update every 0.5s or last item
                progress_percent = (i + 1) / total_packages * 100
                
                if progress_callback:
                    progress_callback(i + 1, total_packages, f"Mapped {i + 1}/{total_packages} packages")
                else:
                    print(f"\rFinding equivalent packages: {i + 1}/{total_packages} ({progress_percent:.1f}%)", end="")
                    sys.stdout.flush()
                
                last_update_time = current_time
        
        # Final progress update
        if not progress_callback:
            print()  # Add newline after progress reporting
        
        return results
    
    def get_equivalent_package(self, pkg_name: str, source_type: str, target_type: str) -> Optional[str]:
        """Get the equivalent package name in a different package manager
        
        Args:
            pkg_name: Original package name
            source_type: Source package manager type (apt, dnf, pacman)
            target_type: Target package manager type (apt, dnf, pacman)
            
        Returns:
            Equivalent package name or None if no mapping exists
        """
        # Direct mapping if both source and target are the same
        if source_type == target_type:
            return pkg_name
            
        # Check if there's a direct mapping in the equivalence map
        pkg_name_lower = pkg_name.lower()
        if pkg_name_lower in self.equiv_map and target_type in self.equiv_map[pkg_name_lower]:
            return self.equiv_map[pkg_name_lower][target_type]
            
        # Try to find any normalized name that might match
        for norm_name, mappings in self.equiv_map.items():
            # Check if this package has a mapping for the source type that matches our package
            if source_type in mappings and mappings[source_type].lower() == pkg_name_lower:
                # If so, return the corresponding target mapping if it exists
                if target_type in mappings:
                    return mappings[target_type]
        
        # No direct mapping found, try pattern matching
        equiv_name = self._pattern_match_package(pkg_name, source_type, target_type)
        if equiv_name:
            return equiv_name
            
        # Finally, try name normalization as a fallback
        return self._normalize_package_name(pkg_name, source_type, target_type)
        
    def _pattern_match_package(self, pkg_name: str, source_type: str, target_type: str) -> Optional[str]:
        """Apply pattern matching to find equivalent packages
        
        This method applies common transformations between package managers
        """
        # Common prefixes/suffixes that differ between distributions
        transformations = {
            'apt': {
                'prefix_map': {
                    'python3-': {'dnf': 'python3-', 'pacman': 'python-'},
                    'python-': {'dnf': 'python-', 'pacman': 'python-'},
                    'lib': {'dnf': 'lib', 'pacman': 'lib'},
                },
                'suffix_map': {
                    '-dev': {'dnf': '-devel', 'pacman': '-devel'},
                    '-dbg': {'dnf': '-debuginfo', 'pacman': '-debug'},
                }
            },
            'dnf': {
                'prefix_map': {
                    'python3-': {'apt': 'python3-', 'pacman': 'python-'},
                    'python-': {'apt': 'python-', 'pacman': 'python-'},
                    'lib': {'apt': 'lib', 'pacman': 'lib'},
                },
                'suffix_map': {
                    '-devel': {'apt': '-dev', 'pacman': '-devel'},
                    '-debuginfo': {'apt': '-dbg', 'pacman': '-debug'},
                }
            },
            'pacman': {
                'prefix_map': {
                    'python-': {'apt': 'python3-', 'dnf': 'python3-'},
                    'lib': {'apt': 'lib', 'dnf': 'lib'},
                },
                'suffix_map': {
                    '-devel': {'apt': '-dev', 'dnf': '-devel'},
                    '-debug': {'apt': '-dbg', 'dnf': '-debuginfo'},
                }
            }
        }
        
        if source_type in transformations:
            # Check for prefix transformations
            for prefix, target_map in transformations[source_type]['prefix_map'].items():
                if pkg_name.startswith(prefix) and target_type in target_map:
                    target_prefix = target_map[target_type]
                    pkg_base = pkg_name[len(prefix):]
                    return f"{target_prefix}{pkg_base}"
                    
            # Check for suffix transformations
            for suffix, target_map in transformations[source_type]['suffix_map'].items():
                if pkg_name.endswith(suffix) and target_type in target_map:
                    target_suffix = target_map[target_type]
                    pkg_base = pkg_name[:-len(suffix)]
                    return f"{pkg_base}{target_suffix}"
        
        return None
    
    def _normalize_package_name(self, pkg_name: str, source_type: str, target_type: str) -> Optional[str]:
        """Normalize package name between different package managers
        
        Some basic normalization rules:
        - Replace underscores with hyphens
        - Strip version numbers
        - Do some common transformations based on package manager conventions
        
        Returns normalized name or None if no transformation is known
        """
        # Start with the original name
        normalized = pkg_name
        
        # Basic normalization: replace underscores with hyphens
        normalized = normalized.replace('_', '-')
        
        # Strip version numbers in parentheses
        normalized = re.sub(r'\([^)]*\)', '', normalized).strip()
        
        # Specific transformations depending on target package manager
        if target_type == 'pacman' and source_type == 'apt':
            # Arch Linux typically doesn't use lib prefixes for packages
            if normalized.startswith('lib') and not normalized.startswith('libreoffice'):
                # Try to keep lib prefix but remove architecture indicators
                normalized = re.sub(r'lib(\w+)(?:-dev)?(?:-[0-9.]+)?', r'lib\1', normalized)
                
        elif target_type == 'dnf' and source_type == 'apt':
            # RPM-based systems use -devel instead of -dev
            normalized = re.sub(r'-dev$', '-devel', normalized)
            
        elif target_type == 'apt' and source_type == 'dnf':
            # Debian/Ubuntu use -dev instead of -devel
            normalized = re.sub(r'-devel$', '-dev', normalized)
        
        # If the name is too generic after normalization, return None
        if len(normalized) < 3 or normalized in {'lib', 'dev', 'bin', 'core'}:
            return None
            
        # If the name hasn't changed, and it doesn't seem to have a cross-package-manager equivalent,
        # we'll just return the original name and let the package manager handle availability checking
        return normalized if normalized != pkg_name else pkg_name
        
    def find_package_with_similar_name(self, pkg_name: str, target_type: str, available_check_fn=None) -> Optional[str]:
        """Find a package with a similar name that exists in the target system
        
        Args:
            pkg_name: Original package name
            target_type: Target package manager type (apt, dnf, pacman)
            available_check_fn: Function to check if a package is available
            
        Returns:
            Similar package name that exists or None if no similar package is found
        """
        if not available_check_fn:
            return None
            
        # Try direct match first
        if available_check_fn(pkg_name):
            return pkg_name
            
        # Try common variations
        variations = []
        
        # 1. Remove lib prefix if it exists
        if pkg_name.startswith('lib') and len(pkg_name) > 3:
            variations.append(pkg_name[3:])
            
        # 2. Try with different prefixes
        if target_type == 'apt':
            if not pkg_name.startswith('lib'):
                variations.append(f"lib{pkg_name}")
            if not pkg_name.startswith('python'):
                variations.append(f"python3-{pkg_name}")
        elif target_type == 'dnf':
            if not pkg_name.startswith('lib'):
                variations.append(f"lib{pkg_name}")
            if not pkg_name.startswith('python'):
                variations.append(f"python3-{pkg_name}")
        elif target_type == 'pacman':
            if not pkg_name.startswith('python'):
                variations.append(f"python-{pkg_name}")
                
        # 3. Try with different suffixes
        if target_type == 'apt':
            if not pkg_name.endswith('-dev'):
                variations.append(f"{pkg_name}-dev")
        elif target_type == 'dnf':
            if not pkg_name.endswith('-devel'):
                variations.append(f"{pkg_name}-devel")
        elif target_type == 'pacman':
            if not pkg_name.endswith('-devel'):
                variations.append(f"{pkg_name}-devel")
                
        # Check all variations
        for var in variations:
            if available_check_fn(var):
                return var
                
        # Try to search for package
        cache_key = f"{target_type}:{pkg_name}"
        if cache_key in self.search_cache:
            return self.search_cache[cache_key]
            
        result = self._search_for_package(pkg_name, target_type, timeout=3)
        self.search_cache[cache_key] = result
        return result
        
    def _search_for_package(self, pkg_name: str, target_type: str, timeout: int = 5) -> Optional[str]:
        """Search for a package by name in the target package manager
        
        Args:
            pkg_name: Package name to search for
            target_type: Target package manager type
            timeout: Timeout in seconds for the search command
            
        Returns:
            Found package name or None
        """
        search_cmd = None
        if target_type == 'apt':
            search_cmd = ['apt-cache', 'search', '--names-only', pkg_name]
        elif target_type == 'dnf':
            search_cmd = ['dnf', 'search', pkg_name]
        elif target_type == 'pacman':
            search_cmd = ['pacman', '-Ss', f"^{pkg_name}"]
            
        if not search_cmd:
            return None
            
        try:
            # Run the search command with timeout
            result = subprocess.run(
                search_cmd, 
                stdout=subprocess.PIPE, 
                stderr=subprocess.PIPE,
                text=True,
                check=False,
                timeout=timeout  # Add timeout to prevent hanging
            )
            
            if result.returncode != 0:
                return None
                
            # Parse results to find the most similar package name
            if target_type == 'apt':
                # Parse apt-cache search output
                for line in result.stdout.splitlines():
                    if ' - ' in line:
                        pkg, _ = line.split(' - ', 1)
                        if pkg.strip() == pkg_name:
                            # Exact match
                            return pkg.strip()
                        elif pkg_name.lower() in pkg.lower():
                            # Partial match
                            return pkg.strip()
                            
            elif target_type == 'dnf':
                # Parse dnf search output
                for line in result.stdout.splitlines():
                    if ':' in line and line.split(':')[0].strip() == 'Name':
                        pkg = line.split(':')[1].strip()
                        if pkg == pkg_name:
                            # Exact match
                            return pkg
                        elif pkg_name.lower() in pkg.lower():
                            # Partial match
                            return pkg
                            
            elif target_type == 'pacman':
                # Parse pacman -Ss output
                for line in result.stdout.splitlines():
                    if line.startswith(('/','repo')):
                        parts = line.split()
                        if len(parts) >= 2:
                            pkg = parts[1].split('/')[1] if '/' in parts[1] else parts[1]
                            if pkg == pkg_name:
                                # Exact match
                                return pkg
                            elif pkg_name.lower() in pkg.lower():
                                # Partial match
                                return pkg
        except subprocess.TimeoutExpired:
            logger.warning(f"Search for package {pkg_name} timed out after {timeout} seconds")
            return None
        except Exception as e:
            logger.error(f"Error searching for package {pkg_name}: {e}")
            return None
            
        return None 