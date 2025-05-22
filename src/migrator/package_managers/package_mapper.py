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
        self.custom_mappings = {}  # Initialize custom_mappings attribute
        
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
            
            # Additional Debian/Ubuntu to Fedora mappings
            'apt': {
                'apt': 'apt',
                'dnf': 'dnf',
                'pacman': 'pacman',
            },
            'apt-utils': {
                'apt': 'apt-utils',
                'dnf': 'dnf-utils',
                'pacman': 'pacman-contrib',
            },
            'aptitude': {
                'apt': 'aptitude',
                'dnf': 'dnf',
                'pacman': 'pacman',
            },
            'nautilus': {
                'apt': 'nautilus',
                'dnf': 'nautilus',
                'pacman': 'nautilus',
            },
            'gnome-terminal': {
                'apt': 'gnome-terminal',
                'dnf': 'gnome-terminal',
                'pacman': 'gnome-terminal',
            },
            'gnome-tweaks': {
                'apt': 'gnome-tweaks',
                'dnf': 'gnome-tweaks',
                'pacman': 'gnome-tweaks',
            },
            'software-properties-common': {
                'apt': 'software-properties-common',
                'dnf': 'dnf-plugins-core',
                'pacman': 'pacman-contrib',
            },
            'gdebi': {
                'apt': 'gdebi',
                'dnf': 'dnf',
                'pacman': 'pacman',
            },
            'apt-transport-https': {
                'apt': 'apt-transport-https',
                'dnf': 'dnf-plugins-core',
                'pacman': 'pacman-contrib',
            },
            'xorg': {
                'apt': 'xorg',
                'dnf': 'xorg-x11-server-Xorg',
                'pacman': 'xorg',
            },
            'build-essential': {
                'apt': 'build-essential',
                'dnf': 'gcc gcc-c++ make',
                'pacman': 'base-devel',
            },
            'libssl-dev': {
                'apt': 'libssl-dev',
                'dnf': 'openssl-devel',
                'pacman': 'openssl',
            },
            'ubuntu-restricted-extras': {
                'apt': 'ubuntu-restricted-extras',
                'dnf': 'rpmfusion-free-release rpmfusion-nonfree-release',
                'pacman': 'base-devel',
            },
            'ubuntu-restricted-addons': {
                'apt': 'ubuntu-restricted-addons',
                'dnf': 'rpmfusion-free-release rpmfusion-nonfree-release',
                'pacman': 'base-devel',
            },
            'gnome-software': {
                'apt': 'gnome-software',
                'dnf': 'gnome-software',
                'pacman': 'gnome-software',
            },
            'packagekit': {
                'apt': 'packagekit',
                'dnf': 'PackageKit',
                'pacman': 'packagekit',
            },
            'synaptic': {
                'apt': 'synaptic',
                'dnf': 'dnfdragora',
                'pacman': 'pamac-gtk',
            },
            'zsh': {
                'apt': 'zsh',
                'dnf': 'zsh',
                'pacman': 'zsh',
            },
            'gparted': {
                'apt': 'gparted',
                'dnf': 'gparted',
                'pacman': 'gparted',
            },
            
            # Extended Ubuntu to Fedora mappings
            '7zip': {
                'apt': '7zip',
                'dnf': 'p7zip',
                'pacman': 'p7zip',
            },
            'p7zip': {
                'apt': 'p7zip',
                'dnf': 'p7zip',
                'pacman': 'p7zip',
            },
            'p7zip-full': {
                'apt': 'p7zip-full',
                'dnf': 'p7zip',
                'pacman': 'p7zip',
            },
            'audacity': {
                'apt': 'audacity',
                'dnf': 'audacity',
                'pacman': 'audacity',
            },
            'autoconf': {
                'apt': 'autoconf',
                'dnf': 'autoconf',
                'pacman': 'autoconf',
            },
            'automake': {
                'apt': 'automake',
                'dnf': 'automake',
                'pacman': 'automake',
            },
            'baobab': {
                'apt': 'baobab',
                'dnf': 'baobab',
                'pacman': 'baobab',
            },
            'bison': {
                'apt': 'bison',
                'dnf': 'bison',
                'pacman': 'bison',
            },
            'blender': {
                'apt': 'blender',
                'dnf': 'blender',
                'pacman': 'blender',
            },
            'bzip2': {
                'apt': 'bzip2',
                'dnf': 'bzip2',
                'pacman': 'bzip2',
            },
            'clamav': {
                'apt': 'clamav',
                'dnf': 'clamav',
                'pacman': 'clamav',
            },
            'clang': {
                'apt': 'clang',
                'dnf': 'clang',
                'pacman': 'clang',
            },
            'clementine': {
                'apt': 'clementine',
                'dnf': 'clementine',
                'pacman': 'clementine',
            },
            'code': {
                'apt': 'code',
                'dnf': 'code',
                'pacman': 'code',
            },
            'dbus': {
                'apt': 'dbus',
                'dnf': 'dbus',
                'pacman': 'dbus',
            },
            'dconf-editor': {
                'apt': 'dconf-editor',
                'dnf': 'dconf-editor',
                'pacman': 'dconf-editor',
            },
            'deluge': {
                'apt': 'deluge',
                'dnf': 'deluge',
                'pacman': 'deluge',
            },
            'evince': {
                'apt': 'evince',
                'dnf': 'evince',
                'pacman': 'evince',
            },
            'exfat-utils': {
                'apt': 'exfat-utils',
                'dnf': 'exfatprogs',
                'pacman': 'exfatprogs',
            },
            'exfat-fuse': {
                'apt': 'exfat-fuse',
                'dnf': 'fuse-exfat',
                'pacman': 'fuse-exfat',
            },
            'fdupes': {
                'apt': 'fdupes',
                'dnf': 'fdupes',
                'pacman': 'fdupes',
            },
            'flex': {
                'apt': 'flex',
                'dnf': 'flex',
                'pacman': 'flex',
            },
            'fonts-liberation': {
                'apt': 'fonts-liberation',
                'dnf': 'liberation-fonts',
                'pacman': 'ttf-liberation',
            },
            'gimp': {
                'apt': 'gimp',
                'dnf': 'gimp',
                'pacman': 'gimp',
            },
            'gitk': {
                'apt': 'gitk',
                'dnf': 'git-gui',
                'pacman': 'git-gui',
            },
            'gnome-calculator': {
                'apt': 'gnome-calculator',
                'dnf': 'gnome-calculator',
                'pacman': 'gnome-calculator',
            },
            'gnome-disk-utility': {
                'apt': 'gnome-disk-utility',
                'dnf': 'gnome-disk-utility',
                'pacman': 'gnome-disk-utility',
            },
            'gnome-system-monitor': {
                'apt': 'gnome-system-monitor',
                'dnf': 'gnome-system-monitor',
                'pacman': 'gnome-system-monitor',
            },
            'gpg': {
                'apt': 'gpg',
                'dnf': 'gnupg2',
                'pacman': 'gnupg',
            },
            'gstreamer1.0-alsa': {
                'apt': 'gstreamer1.0-alsa',
                'dnf': 'gstreamer1-plugins-base',
                'pacman': 'gst-plugins-base',
            },
            'gstreamer1.0-plugins-base': {
                'apt': 'gstreamer1.0-plugins-base',
                'dnf': 'gstreamer1-plugins-base',
                'pacman': 'gst-plugins-base',
            },
            'gstreamer1.0-plugins-good': {
                'apt': 'gstreamer1.0-plugins-good',
                'dnf': 'gstreamer1-plugins-good',
                'pacman': 'gst-plugins-good',
            },
            'gstreamer1.0-plugins-bad': {
                'apt': 'gstreamer1.0-plugins-bad',
                'dnf': 'gstreamer1-plugins-bad-free',
                'pacman': 'gst-plugins-bad',
            },
            'gstreamer1.0-plugins-ugly': {
                'apt': 'gstreamer1.0-plugins-ugly',
                'dnf': 'gstreamer1-plugins-ugly',
                'pacman': 'gst-plugins-ugly',
            },
            'gvfs-backends': {
                'apt': 'gvfs-backends',
                'dnf': 'gvfs',
                'pacman': 'gvfs',
            },
            'inkscape': {
                'apt': 'inkscape',
                'dnf': 'inkscape',
                'pacman': 'inkscape',
            },
            'iotop': {
                'apt': 'iotop',
                'dnf': 'iotop',
                'pacman': 'iotop',
            },
            'iperf': {
                'apt': 'iperf',
                'dnf': 'iperf',
                'pacman': 'iperf',
            },
            'keepassxc': {
                'apt': 'keepassxc',
                'dnf': 'keepassxc',
                'pacman': 'keepassxc',
            },
            'krita': {
                'apt': 'krita',
                'dnf': 'krita',
                'pacman': 'krita',
            },
            'libavcodec-dev': {
                'apt': 'libavcodec-dev',
                'dnf': 'ffmpeg-devel',
                'pacman': 'ffmpeg',
            },
            'libcurl4-openssl-dev': {
                'apt': 'libcurl4-openssl-dev',
                'dnf': 'libcurl-devel',
                'pacman': 'curl',
            },
            'libgtk-3-dev': {
                'apt': 'libgtk-3-dev',
                'dnf': 'gtk3-devel',
                'pacman': 'gtk3',
            },
            'libjpeg-dev': {
                'apt': 'libjpeg-dev',
                'dnf': 'libjpeg-turbo-devel',
                'pacman': 'libjpeg-turbo',
            },
            'libncurses5-dev': {
                'apt': 'libncurses5-dev',
                'dnf': 'ncurses-devel',
                'pacman': 'ncurses',
            },
            'libpng-dev': {
                'apt': 'libpng-dev',
                'dnf': 'libpng-devel',
                'pacman': 'libpng',
            },
            'libsqlite3-dev': {
                'apt': 'libsqlite3-dev',
                'dnf': 'sqlite-devel',
                'pacman': 'sqlite',
            },
            'libtool': {
                'apt': 'libtool',
                'dnf': 'libtool',
                'pacman': 'libtool',
            },
            'libxml2-dev': {
                'apt': 'libxml2-dev',
                'dnf': 'libxml2-devel',
                'pacman': 'libxml2',
            },
            'lightdm': {
                'apt': 'lightdm',
                'dnf': 'lightdm',
                'pacman': 'lightdm',
            },
            'mlocate': {
                'apt': 'mlocate',
                'dnf': 'mlocate',
                'pacman': 'mlocate',
            },
            'mpv': {
                'apt': 'mpv',
                'dnf': 'mpv',
                'pacman': 'mpv',
            },
            'neofetch': {
                'apt': 'neofetch',
                'dnf': 'neofetch',
                'pacman': 'neofetch',
            },
            'neovim': {
                'apt': 'neovim',
                'dnf': 'neovim',
                'pacman': 'neovim',
            },
            'net-tools': {
                'apt': 'net-tools',
                'dnf': 'net-tools',
                'pacman': 'net-tools',
            },
            'network-manager': {
                'apt': 'network-manager',
                'dnf': 'NetworkManager',
                'pacman': 'networkmanager',
            },
            'network-manager-gnome': {
                'apt': 'network-manager-gnome',
                'dnf': 'network-manager-applet',
                'pacman': 'network-manager-applet',
            },
            'nmap': {
                'apt': 'nmap',
                'dnf': 'nmap',
                'pacman': 'nmap',
            },
            'npm': {
                'apt': 'npm',
                'dnf': 'npm',
                'pacman': 'npm',
            },
            'ntfs-3g': {
                'apt': 'ntfs-3g',
                'dnf': 'ntfs-3g',
                'pacman': 'ntfs-3g',
            },
            'okular': {
                'apt': 'okular',
                'dnf': 'okular',
                'pacman': 'okular',
            },
            'openssh-server': {
                'apt': 'openssh-server',
                'dnf': 'openssh-server',
                'pacman': 'openssh',
            },
            'pavucontrol': {
                'apt': 'pavucontrol',
                'dnf': 'pavucontrol',
                'pacman': 'pavucontrol',
            },
            'pulseaudio': {
                'apt': 'pulseaudio',
                'dnf': 'pulseaudio',
                'pacman': 'pulseaudio',
            },
            'pv': {
                'apt': 'pv',
                'dnf': 'pv',
                'pacman': 'pv',
            },
            'rar': {
                'apt': 'rar',
                'dnf': 'unrar',
                'pacman': 'unrar',
            },
            'rhythmbox': {
                'apt': 'rhythmbox',
                'dnf': 'rhythmbox',
                'pacman': 'rhythmbox',
            },
            'rsync': {
                'apt': 'rsync',
                'dnf': 'rsync',
                'pacman': 'rsync',
            },
            'rygel': {
                'apt': 'rygel',
                'dnf': 'rygel',
                'pacman': 'rygel',
            },
            'scribus': {
                'apt': 'scribus',
                'dnf': 'scribus',
                'pacman': 'scribus',
            },
            'sddm': {
                'apt': 'sddm',
                'dnf': 'sddm',
                'pacman': 'sddm',
            },
            'shotwell': {
                'apt': 'shotwell',
                'dnf': 'shotwell',
                'pacman': 'shotwell',
            },
            'sqlite3': {
                'apt': 'sqlite3',
                'dnf': 'sqlite',
                'pacman': 'sqlite',
            },
            'steam': {
                'apt': 'steam',
                'dnf': 'steam',
                'pacman': 'steam',
            },
            'texlive': {
                'apt': 'texlive',
                'dnf': 'texlive',
                'pacman': 'texlive-core',
            },
            'thunar': {
                'apt': 'thunar',
                'dnf': 'thunar',
                'pacman': 'thunar',
            },
            'tmux': {
                'apt': 'tmux',
                'dnf': 'tmux',
                'pacman': 'tmux',
            },
            'transmission-gtk': {
                'apt': 'transmission-gtk',
                'dnf': 'transmission-gtk',
                'pacman': 'transmission-gtk',
            },
            'unrar': {
                'apt': 'unrar',
                'dnf': 'unrar',
                'pacman': 'unrar',
            },
            'unzip': {
                'apt': 'unzip',
                'dnf': 'unzip',
                'pacman': 'unzip',
            },
            'upower': {
                'apt': 'upower',
                'dnf': 'upower',
                'pacman': 'upower',
            },
            'usbutils': {
                'apt': 'usbutils',
                'dnf': 'usbutils',
                'pacman': 'usbutils',
            },
            'valgrind': {
                'apt': 'valgrind',
                'dnf': 'valgrind',
                'pacman': 'valgrind',
            },
            'virt-manager': {
                'apt': 'virt-manager',
                'dnf': 'virt-manager',
                'pacman': 'virt-manager',
            },
            'vscode': {
                'apt': 'code',
                'dnf': 'code',
                'pacman': 'code',
            },
            'wine': {
                'apt': 'wine',
                'dnf': 'wine',
                'pacman': 'wine',
            },
            'xfce4-terminal': {
                'apt': 'xfce4-terminal',
                'dnf': 'xfce4-terminal',
                'pacman': 'xfce4-terminal',
            },
            'xz-utils': {
                'apt': 'xz-utils',
                'dnf': 'xz',
                'pacman': 'xz',
            },
            'zlib1g-dev': {
                'apt': 'zlib1g-dev',
                'dnf': 'zlib-devel',
                'pacman': 'zlib',
            },
            'zstd': {
                'apt': 'zstd',
                'dnf': 'zstd',
                'pacman': 'zstd',
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
                    
                    # Also add to custom_mappings for separate tracking
                    self.custom_mappings[pkg] = mappings
                    
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
            List of tuples (source_package, target_package, mapping_type, is_available)
        """
        results = []
        total = len(packages)
        
        logger.info(f"Processing {total} packages from {source_type} to {target_type}")
        
        # Lookup table for manual mappings from common Ubuntu packages to Fedora packages
        ubuntu_to_fedora = {
            'synaptic': 'dnfdragora',  # Package manager GUI
            'apt': 'dnf',  # Package manager
            'apt-utils': 'dnf-utils',  # Package manager utilities
            'software-center': 'gnome-software',  # Software center
            'ubuntu-restricted-addons': 'rpmfusion-free-release rpmfusion-nonfree-release',  # Restricted addons
            'ubuntu-restricted-extras': 'rpmfusion-free-release rpmfusion-nonfree-release',  # Restricted extras
            'ffmpeg': 'ffmpeg',  # Media converter
            'vlc': 'vlc',  # Media player
            'gdebi': 'dnf',  # Package installer
            'gdebi-core': 'dnf-plugins-core',  # Package installer core
            'nautilus': 'nautilus',  # File manager
            'thunar': 'thunar',  # File manager
            'dolphin': 'dolphin',  # File manager
            'python3-pip': 'python3-pip',  # Python package manager
            'python-pip': 'python3-pip',  # Python package manager
            'virt-manager': 'virt-manager',  # Virtual machine manager
            'vim': 'vim',  # Text editor
            'nano': 'nano',  # Text editor
            'emacs': 'emacs',  # Text editor
            'wget': 'wget',  # Download tool
            'curl': 'curl',  # Download tool
            'gcc': 'gcc',  # C compiler
            'g++': 'gcc-c++',  # C++ compiler
            'make': 'make',  # Build tool
            'git': 'git',  # Version control
            'subversion': 'subversion',  # Version control
            'firefox': 'firefox',  # Web browser
            'chromium-browser': 'chromium',  # Web browser
            'gimp': 'gimp',  # Image editor
            'inkscape': 'inkscape',  # Vector editor
            'audacity': 'audacity',  # Audio editor
            'obs-studio': 'obs-studio',  # Streaming software
            'steam': 'steam',  # Gaming platform
        }
        
        # Reverse mapping for Fedora to Ubuntu
        fedora_to_ubuntu = {v: k for k, v in ubuntu_to_fedora.items() if ' ' not in v}  # Exclude multi-package values
        
        # Count statistics for different mapping types
        mapping_stats = {
            'custom': 0,
            'builtin': 0,
            'user': 0,
            'pattern': 0,
            'original': 0,
            'variation': 0,
            'unavailable': 0
        }
        
        # First preprocess packages to ensure consistent format
        processed_packages = []
        for pkg in packages:
            if isinstance(pkg, dict):
                processed_packages.append(pkg)
            else:
                # Convert string to dict
                processed_packages.append({
                    'name': str(pkg),
                    'source': source_type
                })
        
        for i, package in enumerate(processed_packages):
            source_pkg = package
            if isinstance(package, dict):
                source_pkg_name = package.get('name', '')
            else:
                source_pkg_name = str(package)
            
            # Skip empty package names
            if not source_pkg_name:
                logger.warning(f"Skipping empty package name: {package}")
                continue
                
            # Skip system packages
            if self.is_system_package(source_pkg_name):
                logger.info(f"Skipping system package: {source_pkg_name}")
                continue
            
            # Try to find an equivalent package name for the target system
            target_pkg = None
            mapping_type = None
            is_available = False
            
            # 1. First check manual mappings based on source and target
            if source_type == 'apt' and target_type == 'dnf' and source_pkg_name in ubuntu_to_fedora:
                target_pkg = ubuntu_to_fedora[source_pkg_name]
                mapping_type = 'custom'
                mapping_stats['custom'] += 1
                logger.debug(f"Package {source_pkg_name}: Found custom apt→dnf mapping to {target_pkg}")
            elif source_type == 'dnf' and target_type == 'apt' and source_pkg_name in fedora_to_ubuntu:
                target_pkg = fedora_to_ubuntu[source_pkg_name]
                mapping_type = 'custom'
                mapping_stats['custom'] += 1
                logger.debug(f"Package {source_pkg_name}: Found custom dnf→apt mapping to {target_pkg}")
            
            # 2. Next check built-in equivalence map
            if not target_pkg and source_pkg_name in self.equiv_map:
                if target_type in self.equiv_map[source_pkg_name]:
                    target_pkg = self.equiv_map[source_pkg_name][target_type]
                    mapping_type = 'builtin'
                    mapping_stats['builtin'] += 1
                    logger.debug(f"Package {source_pkg_name}: Found built-in mapping to {target_pkg}")
            
            # 3. Check user custom mappings
            if not target_pkg and source_pkg_name in self.custom_mappings:
                if target_type in self.custom_mappings[source_pkg_name]:
                    target_pkg = self.custom_mappings[source_pkg_name][target_type]
                    mapping_type = 'user'
                    mapping_stats['user'] += 1
                    logger.debug(f"Package {source_pkg_name}: Found user-defined mapping to {target_pkg}")
            
            # 4. Try pattern matching - many packages have the same name across distributions
            if not target_pkg:
                # For most common packages, the name is the same
                target_pkg = source_pkg_name
                mapping_type = 'original'
                mapping_stats['original'] += 1
                
                # Handle special cases with pattern matching
                if target_type == 'dnf' and source_pkg_name.startswith('lib') and source_pkg_name.endswith('-dev'):
                    # Convert Ubuntu lib*-dev to Fedora lib*-devel
                    target_pkg = f"{source_pkg_name[:-4]}-devel"
                    mapping_type = 'pattern'
                    mapping_stats['pattern'] += 1
                    logger.debug(f"Package {source_pkg_name}: Applied lib-dev→lib-devel pattern, mapped to {target_pkg}")
                elif target_type == 'apt' and source_pkg_name.startswith('lib') and source_pkg_name.endswith('-devel'):
                    # Convert Fedora lib*-devel to Ubuntu lib*-dev
                    target_pkg = f"{source_pkg_name[:-6]}-dev"
                    mapping_type = 'pattern'
                    mapping_stats['pattern'] += 1
                    logger.debug(f"Package {source_pkg_name}: Applied lib-devel→lib-dev pattern, mapped to {target_pkg}")
                    
                # Handle python packages
                if target_type == 'dnf' and source_pkg_name.startswith('python3-'):
                    # Ubuntu python3 packages usually have the same name in Fedora
                    target_pkg = source_pkg_name
                    mapping_type = 'pattern'
                    mapping_stats['pattern'] += 1
                    logger.debug(f"Package {source_pkg_name}: Python package pattern match to {target_pkg}")
                elif target_type == 'apt' and source_pkg_name.startswith('python3-'):
                    # Fedora python3 packages usually have the same name in Ubuntu
                    target_pkg = source_pkg_name
                    mapping_type = 'pattern'
                    mapping_stats['pattern'] += 1
                    logger.debug(f"Package {source_pkg_name}: Python package pattern match to {target_pkg}")
            
            # Check if the target package is available
            if target_pkg and available_check_fn:
                try:
                    # Check availability for each package if space-separated
                    if ' ' in target_pkg:
                        packages_to_check = target_pkg.split()
                        is_available = any(available_check_fn(pkg) for pkg in packages_to_check)
                        
                        # Log which specific package is available
                        if is_available:
                            for pkg in packages_to_check:
                                if available_check_fn(pkg):
                                    logger.debug(f"Package {source_pkg_name} → {target_pkg}: Found available package: {pkg}")
                                    break
                        else:
                            logger.debug(f"Package {source_pkg_name} → {target_pkg}: None of the packages are available")
                    else:
                        is_available = available_check_fn(target_pkg)
                        
                    # Log detailed diagnostics about availability check
                    logger.info(f"Package {source_pkg_name} → {target_pkg} (mapping: {mapping_type}, available: {is_available})")
                    
                    # If not available, try some common variations
                    if not is_available and target_type == 'dnf':
                        # Try common Fedora variations for unavailable packages
                        variations = []
                        
                        # Check if removing lib prefix helps (some packages don't have lib prefix in Fedora)
                        if target_pkg.startswith('lib') and len(target_pkg) > 3:
                            variations.append(target_pkg[3:])
                            
                        # Check if adding 'python3-' prefix helps
                        if not target_pkg.startswith('python'):
                            variations.append(f"python3-{target_pkg}")
                            
                        # Try variations
                        for variation in variations:
                            logger.debug(f"Package {source_pkg_name}: Trying variation {variation}")
                            if available_check_fn(variation):
                                target_pkg = variation
                                is_available = True
                                mapping_type = 'variation'
                                mapping_stats['variation'] += 1
                                logger.info(f"Found available variation: {source_pkg_name} → {target_pkg}")
                                break
                        
                        if not is_available:
                            logger.warning(f"Package {source_pkg_name} → {target_pkg}: Not available and no variations found")
                            mapping_stats['unavailable'] += 1
                    
                    # If not available, try direct search (experimental)
                    if not is_available and target_type == 'dnf':
                        # This would require a new method to search repositories
                        pass
                            
                except Exception as e:
                    logger.error(f"Error checking availability for {target_pkg}: {e}")
            
            results.append((source_pkg, target_pkg, mapping_type, is_available))
            
            # Report progress
            if progress_callback and i % 10 == 0:
                progress_callback(i, total)
        
        # Report final progress
        if progress_callback:
            progress_callback(total, total)
            
        # Log mapping summary and statistics
        available_count = sum(1 for _, _, _, avail in results if avail)
        logger.info(f"Package mapping complete: {len(results)}/{total} packages mapped ({available_count} available)")
        logger.info(f"Mapping statistics: {mapping_stats}")
        
        return results

    def is_system_package(self, pkg_name: str) -> bool:
        """Check if a package is a system package that shouldn't be mapped between distributions
        
        Args:
            pkg_name: Name of the package to check
            
        Returns:
            True if the package is a system package, False otherwise
        """
        # Convert to lowercase for case-insensitive matching
        pkg_lower = pkg_name.lower()
        
        # Define patterns for system packages
        system_patterns = [
            # Kernel packages
            '-kernel', 'kernel-', 'linux-image', 'linux-headers',
            # Firmware and drivers
            '-firmware', 'firmware-', '-driver', 'driver-', 
            'nvidia-', 'amd-', 'intel-', 'broadcom-',
            # Hardware-specific packages
            'alsa-', 'pulseaudio-', 'xorg-', 'wayland-',
            # System core packages
            'systemd-', 'udev-', 'dbus-', 'policykit-',
            # Boot packages
            'grub-', 'grub2-', 'shim-', 'efi-'
        ]
        
        # Check if package name contains any system pattern
        for pattern in system_patterns:
            if pattern in pkg_lower:
                return True
                
        # Explicit list of system packages (exact matches)
        system_packages = {
            'linux-firmware', 'nvidia-driver', 'amdgpu', 'xserver-xorg',
            'linux-generic', 'linux-headers-generic', 'linux-image-generic',
            'linux-restricted-modules', 'linux-backports-modules',
            'firmware-linux', 'firmware-iwlwifi', 'firmware-atheros',
            'firmware-brcm80211', 'firmware-realtek', 'firmware-amd-graphics',
            'xorg-x11-drv-nvidia', 'akmod-nvidia', 'dkms-nvidia',
            'xorg-x11-drv-amdgpu', 'xorg-x11-drv-intel',
            'amdgpu-pro', 'amdgpu-pro-core', 'amdgpu-pro-dkms'
        }
        
        return pkg_lower in system_packages

    def _get_equivalent_package_with_reason(self, pkg_name: str, source_type: str, target_type: str) -> Tuple[Optional[str], str]:
        """Get the equivalent package name with the reason for the mapping
        
        Args:
            pkg_name: Original package name
            source_type: Source package manager type (apt, dnf, pacman)
            target_type: Target package manager type (apt, dnf, pacman)
            
        Returns:
            Tuple of (equivalent package name or None, reason for mapping)
        """
        try:
            # Safety checks
            if not isinstance(pkg_name, str) or not pkg_name:
                logger.warning(f"Invalid package name: {pkg_name}")
                return None, "invalid"
                
            if not isinstance(source_type, str) or not source_type:
                logger.warning(f"Invalid source type: {source_type}")
                return None, "invalid"
                
            if not isinstance(target_type, str) or not target_type:
                logger.warning(f"Invalid target type: {target_type}")
                return None, "invalid"
            
            # Direct mapping if both source and target are the same
            if source_type == target_type:
                return pkg_name, "direct"
                
            # Strip architecture suffix if present
            clean_pkg_name = pkg_name
            if ':' in clean_pkg_name:
                clean_pkg_name = clean_pkg_name.split(':')[0]
            
            # Check the equiv_map directly first
            if clean_pkg_name in self.equiv_map:
                mapping = self.equiv_map[clean_pkg_name]
                if isinstance(mapping, dict) and target_type in mapping:
                    target_name = mapping[target_type]
                    if target_name:
                        return target_name, "custom"
            
            # Check custom mappings using the format "source:target:package"
            custom_mapping_key = f"{source_type}:{target_type}:{clean_pkg_name}"
            if custom_mapping_key in self.equiv_map:
                return self.equiv_map[custom_mapping_key], "custom"
                
            # Try pattern matching
            pattern_match = self._pattern_match_package(clean_pkg_name, source_type, target_type)
            if pattern_match:
                return pattern_match, "pattern"
        
            # Try general normalization
            normalized = self._normalize_package_name(clean_pkg_name, source_type, target_type)
            if normalized and normalized != clean_pkg_name:
                return normalized, "normalized"
            
            # No mapping found
            return clean_pkg_name, "original"  # Return the original name (without arch suffix) as fallback
            
        except Exception as e:
            logger.error(f"Error getting equivalent package for {pkg_name}: {e}")
            return None, "error"
    
    def get_equivalent_package(self, pkg_name: str, source_type: str, target_type: str) -> Optional[str]:
        """Get the equivalent package name in a different package manager
        
        Args:
            pkg_name: Original package name
            source_type: Source package manager type (apt, dnf, pacman)
            target_type: Target package manager type (apt, dnf, pacman)
            
        Returns:
            Equivalent package name or None if no mapping exists
        """
        result, _ = self._get_equivalent_package_with_reason(pkg_name, source_type, target_type)
        return result
        
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
                    
                    # Debian-specific package normalization
                    if normalized.startswith('libssl-dev'):
                        normalized = 'openssl-devel'
                    elif normalized.startswith('libpq-dev'):
                        normalized = 'libpq-devel'
                    elif normalized.startswith('libsqlite3-dev'):
                        normalized = 'sqlite-devel'
                    elif normalized == 'build-essential':
                        normalized = 'gcc'
                    
                elif target_type == 'apt' and source_type == 'dnf':
                    # Debian/Ubuntu use -dev instead of -devel
                    normalized = re.sub(r'-devel$', '-dev', normalized)
                    
                    # Fedora-specific package normalization
                    if normalized.startswith('openssl-devel'):
                        normalized = 'libssl-dev'
                    elif normalized.startswith('libpq-devel'):
                        normalized = 'libpq-dev'
                    elif normalized.startswith('sqlite-devel'):
                        normalized = 'libsqlite3-dev'
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

    def create_custom_mapping(self, source_name: str, source_type: str, target_name: str, target_type: str) -> bool:
        """Create a custom mapping between two packages
        
        Args:
            source_name: Original package name
            source_type: Source package manager type (apt, dnf, pacman)
            target_name: Target package name
            target_type: Target package manager type (apt, dnf, pacman)
            
        Returns:
            True if mapping was created successfully, False otherwise
        """
        try:
            # Ensure source_name and target_name are strings
            if not isinstance(source_name, str) or not source_name:
                logger.error("Invalid source package name")
                return False
                
            if not isinstance(target_name, str) or not target_name:
                logger.error("Invalid target package name")
                return False
                
            # Ensure source_type and target_type are valid
            if source_type not in ('apt', 'dnf', 'pacman'):
                logger.error(f"Invalid source package manager type: {source_type}")
                return False
                
            if target_type not in ('apt', 'dnf', 'pacman'):
                logger.error(f"Invalid target package manager type: {target_type}")
                return False
                
            # Create the user mappings directory if it doesn't exist
            user_map_dir = os.path.expanduser('~/.config/migrator')
            user_map_path = os.path.join(user_map_dir, 'package_mappings.json')
            
            if not os.path.exists(user_map_dir):
                os.makedirs(user_map_dir)
                
            # Load existing mappings or create empty dict
            user_map = {}
            if os.path.exists(user_map_path):
                try:
                    with open(user_map_path, 'r') as f:
                        user_map = json.load(f)
                except Exception as e:
                    logger.error(f"Error loading existing mappings: {e}")
                    user_map = {}
                    
            # Add or update the mapping
            if source_name not in user_map:
                user_map[source_name] = {}
            
            user_map[source_name][target_type] = target_name
            
            # Also add the key format for direct lookup
            custom_key = f"{source_type}:{target_type}:{source_name}"
            user_map[custom_key] = target_name
            
            # Save the updated mappings
            with open(user_map_path, 'w') as f:
                json.dump(user_map, f, indent=2)
                
            # Update the in-memory map
            if source_name not in self.equiv_map:
                self.equiv_map[source_name] = {}
            self.equiv_map[source_name][target_type] = target_name
            self.equiv_map[custom_key] = target_name
            
            logger.info(f"Created custom mapping: {source_name} ({source_type}) -> {target_name} ({target_type})")
            return True
            
        except Exception as e:
            logger.error(f"Error creating custom mapping: {e}")
            return False 