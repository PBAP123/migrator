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
    
    def process_package_batch(self, packages: List, source_type: str, target_type: str, 
                             available_check_fn: Callable = None, 
                             progress_callback: Callable = None) -> List[Tuple]:
        """Process a batch of packages to find equivalent names
        
        Args:
            packages: List of package dictionaries or strings
            source_type: Source package manager type
            target_type: Target package manager type
            available_check_fn: Function to check if a package is available
            progress_callback: Function to report progress
            
        Returns:
            List of tuples containing (original package dict or string, equivalent package name or None)
        """
        # Initialize an empty results list
        results = []
        
        # If no packages, return empty results
        if not packages:
            return results
        
        # Get the total number of packages
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
            # Default to no equivalent name found
            equivalent_name = None
            
            try:
                # Extract package name based on package type
                pkg_name = ""
                
                # Handle dictionary packages
                if isinstance(pkg, dict):
                    if 'name' in pkg:
                        pkg_name = str(pkg['name'])
                # Handle string packages
                elif isinstance(pkg, str):
                    pkg_name = pkg
                # Try to handle any other type by converting to string
                else:
                    try:
                        pkg_name = str(pkg)
                    except:
                        # If conversion fails, skip this package
                        logger.warning(f"Cannot process package of type {type(pkg)}")
                        results.append((pkg, None))
                        continue
                
                # Skip if we couldn't extract a package name
                if not pkg_name:
                    results.append((pkg, None))
                    continue
                    
                # Handle architecture specifiers like ":amd64"
                if ':' in pkg_name:
                    pkg_name = pkg_name.split(':')[0]
                
                # Get equivalent package name - this is the simplest and safest approach
                try:
                    equivalent_name = self.get_equivalent_package(pkg_name, source_type, target_type)
                except Exception as e:
                    logger.error(f"Error finding equivalent package for {pkg_name}: {e}")
                    equivalent_name = None
                
                # Check if the equivalent package is available if a check function was provided
                if equivalent_name and available_check_fn:
                    try:
                        if not available_check_fn(equivalent_name):
                            # Try to find a similar package
                            try:
                                similar_name = self.find_package_with_similar_name(
                                    equivalent_name, target_type, available_check_fn
                                )
                                if similar_name:
                                    equivalent_name = similar_name
                                else:
                                    # If no similar package found with the equivalent name, try with the original
                                    similar_name = self.find_package_with_similar_name(
                                        pkg_name, target_type, available_check_fn
                                    )
                                    if similar_name:
                                        equivalent_name = similar_name
                            except Exception as e:
                                logger.error(f"Error finding similar package for {equivalent_name}: {e}")
                    except Exception as e:
                        logger.error(f"Error checking availability for {equivalent_name}: {e}")
                
            except Exception as e:
                logger.error(f"Error mapping package {str(pkg)[:30]}: {e}")
                equivalent_name = None
            
            # Add the package and its equivalent name to results
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
        try:
            # Safety checks
            if not isinstance(pkg_name, str) or not pkg_name:
                logger.warning(f"Invalid package name: {pkg_name}")
                return None
                
            if not isinstance(source_type, str) or not source_type:
                logger.warning(f"Invalid source type: {source_type}")
                return None
                
            if not isinstance(target_type, str) or not target_type:
                logger.warning(f"Invalid target type: {target_type}")
                return None
            
            # Direct mapping if both source and target are the same
            if source_type == target_type:
                return pkg_name
                
            # Strip architecture suffix if present
            clean_pkg_name = pkg_name
            if ':' in clean_pkg_name:
                clean_pkg_name = clean_pkg_name.split(':')[0]
            
            # Check custom mappings first
            custom_mapping_key = f"{source_type}:{target_type}:{clean_pkg_name}"
            if custom_mapping_key in self.equiv_map:
                return self.equiv_map[custom_mapping_key]
                
            # Try pattern matching
            pattern_match = self._pattern_match_package(clean_pkg_name, source_type, target_type)
            if pattern_match:
                return pattern_match
        
            # Try general normalization
            normalized = self._normalize_package_name(clean_pkg_name, source_type, target_type)
            if normalized and normalized != clean_pkg_name:
                return normalized
            
            # No mapping found
            return clean_pkg_name  # Return the original name (without arch suffix) as fallback
            
        except Exception as e:
            logger.error(f"Error getting equivalent package for {pkg_name}: {e}")
            return None
        
    def _pattern_match_package(self, pkg_name: str, source_type: str, target_type: str) -> Optional[str]:
        """Apply pattern matching to find equivalent packages
        
        This method applies common transformations between package managers
        """
        try:
            # Safety check: ensure pkg_name is a string
            if not isinstance(pkg_name, str):
                logger.warning(f"Expected string for package name, got {type(pkg_name)}")
                return None
                
            # Handle package names with architecture specifiers like ":amd64"
            if ':' in pkg_name:
                # Strip the architecture suffix for mapping
                pkg_name = pkg_name.split(':')[0]
                
            # Create dictionary structure for transformations
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
            
            # Ensure source_type is a valid key in transformations
            if source_type not in transformations:
                return None
                
            # Check if transformations[source_type] has the right structure
            if not isinstance(transformations[source_type], dict):
                logger.warning(f"Invalid transformations structure for source_type: {source_type}")
                return None
                
            # Check for prefix_map and suffix_map in transformations[source_type]
            if 'prefix_map' not in transformations[source_type] or 'suffix_map' not in transformations[source_type]:
                logger.warning(f"Missing prefix_map or suffix_map in transformations for source_type: {source_type}")
                return None
                
            # Check for prefix transformations
            prefix_map = transformations[source_type].get('prefix_map', {})
            for prefix, target_map in prefix_map.items():
                if pkg_name.startswith(prefix) and isinstance(target_map, dict) and target_type in target_map:
                    target_prefix = target_map[target_type]
                    pkg_base = pkg_name[len(prefix):]
                    return f"{target_prefix}{pkg_base}"
                    
            # Check for suffix transformations
            suffix_map = transformations[source_type].get('suffix_map', {})
            for suffix, target_map in suffix_map.items():
                if pkg_name.endswith(suffix) and isinstance(target_map, dict) and target_type in target_map:
                    target_suffix = target_map[target_type]
                    pkg_base = pkg_name[:-len(suffix)]
                    return f"{pkg_base}{target_suffix}"
                    
            return None
            
        except Exception as e:
            logger.error(f"Error in pattern matching for package {pkg_name}: {e}")
            return None
    
    def _normalize_package_name(self, pkg_name: str, source_type: str, target_type: str) -> Optional[str]:
        """Normalize package name between different package managers
        
        Some basic normalization rules:
        - Replace underscores with hyphens
        - Strip version numbers
        - Do some common transformations based on package manager conventions
        
        Returns normalized name or None if no transformation is known
        """
        try:
            # Safety check: ensure pkg_name is a string
            if not isinstance(pkg_name, str):
                logger.warning(f"Expected string for package name, got {type(pkg_name)}")
                return None
                
            # Handle package names with architecture specifiers like ":amd64"
            if ':' in pkg_name:
                # Strip the architecture suffix for mapping
                pkg_name = pkg_name.split(':')[0]
                
            # Start with the original name
            normalized = pkg_name
            
            # Basic normalization: replace underscores with hyphens
            normalized = normalized.replace('_', '-')
            
            # Strip version numbers in parentheses
            normalized = re.sub(r'\([^)]*\)', '', normalized).strip()
            
            # Specific transformations depending on target package manager
            try:
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
            except Exception as e:
                logger.error(f"Error in specific transformations for package {pkg_name}: {e}")
            
            # If the name is too generic after normalization, return None
            if len(normalized) < 3 or normalized in {'lib', 'dev', 'bin', 'core'}:
                return None
                
            # If the name hasn't changed, and it doesn't seem to have a cross-package-manager equivalent,
            # we'll just return the original name and let the package manager handle availability checking
            return normalized if normalized != pkg_name else pkg_name
            
        except Exception as e:
            logger.error(f"Error normalizing package name {pkg_name}: {e}")
            return None
        
    def find_package_with_similar_name(self, pkg_name: str, target_type: str, available_check_fn=None) -> Optional[str]:
        """Find a package with a similar name that exists in the target system
        
        Args:
            pkg_name: Original package name
            target_type: Target package manager type (apt, dnf, pacman)
            available_check_fn: Function to check if a package is available
            
        Returns:
            Similar package name that exists or None if no similar package is found
        """
        try:
            # Safety check for inputs
            if not isinstance(pkg_name, str) or not pkg_name or not available_check_fn:
                return None
                
            # Handle package names with architecture specifiers like ":amd64"
            arch_suffix = ""
            if ':' in pkg_name:
                # Store the architecture suffix in case we need it later
                pkg_parts = pkg_name.split(':')
                pkg_name = pkg_parts[0]
                arch_suffix = pkg_parts[1] if len(pkg_parts) > 1 else ""
                logger.debug(f"Removed architecture specifier from package name: {pkg_name} (arch: {arch_suffix})")
                
            # Try direct match first
            if available_check_fn(pkg_name):
                # Re-add architecture suffix for apt packages if it existed and the target is apt
                if target_type == 'apt' and arch_suffix:
                    return f"{pkg_name}:{arch_suffix}"
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
                    # Re-add architecture suffix for apt packages if it existed and the target is apt
                    if target_type == 'apt' and arch_suffix:
                        return f"{var}:{arch_suffix}"
                    return var
                    
            # Try to search for package
            cache_key = f"{target_type}:{pkg_name}"
            if cache_key in self.search_cache:
                result = self.search_cache[cache_key]
                # Re-add architecture suffix for apt packages if it existed and the target is apt
                if result and target_type == 'apt' and arch_suffix:
                    return f"{result}:{arch_suffix}"
                return result
                
            result = self._search_for_package(pkg_name, target_type, timeout=3)
            self.search_cache[cache_key] = result
                
            # Re-add architecture suffix for apt packages if it existed and the target is apt
            if result and target_type == 'apt' and arch_suffix:
                return f"{result}:{arch_suffix}"
            return result
            
        except Exception as e:
            logger.error(f"Error finding similar package for {pkg_name}: {e}")
            return None
        
    def _search_for_package(self, pkg_name: str, target_type: str, timeout: int = 5) -> Optional[str]:
        """Search for a package by name in the target package manager
        
        Args:
            pkg_name: Package name to search for
            target_type: Target package manager type
            timeout: Timeout in seconds for the search command
            
        Returns:
            Found package name or None
        """
        try:
            # Safety check for inputs
            if not isinstance(pkg_name, str) or not pkg_name:
                return None
                
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
                logger.error(f"Error executing search command for {pkg_name}: {e}")
                return None
                
            return None
        except Exception as e:
            logger.error(f"Error searching for package {pkg_name}: {e}")
            return None 