#!/usr/bin/env python3
"""
Desktop Environment and Window Manager configuration tracker

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU Affero General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.

This program is distributed in the hope that it will be useful,
but WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
GNU Affero General Public License for more details.

You should have received a copy of the GNU Affero General Public License
along with this program.  If not, see <https://www.gnu.org/licenses/>.
"""

import os
import glob
import logging
import subprocess
import json
from pathlib import Path
from typing import List, Dict, Any, Optional, Set, Tuple

from .base import ConfigTracker, ConfigFile

logger = logging.getLogger(__name__)

class DesktopEnvironmentTracker(ConfigTracker):
    """Track desktop environment and window manager configurations"""
    
    def __init__(self):
        super().__init__("desktop_environment")
        self.tracked_files: Dict[str, ConfigFile] = {}
        self.home_dir = os.path.expanduser("~")
        
        # Define mapping of desktop environments to their config paths
        self.de_config_paths = {
            "gnome": [
                "~/.config/dconf/user",
                "~/.config/gnome-*",
                "~/.local/share/gnome-shell/extensions/*",
                "~/.config/gtk-3.0/settings.ini",
            ],
            "kde": [
                "~/.config/plasma-*",
                "~/.config/kdeglobals",
                "~/.config/kwinrc",
                "~/.config/kglobalshortcutsrc",
                "~/.config/khotkeysrc",
                "~/.config/plasmarc",
                "~/.config/kcminputrc",
                "~/.config/ksmserverrc",
                "~/.config/katerc",
                "~/.config/konsolerc",
                "~/.local/share/kwin/*",
                "~/.local/share/plasma/*",
            ],
            "xfce": [
                "~/.config/xfce4/xfconf/xfce-perchannel-xml/*",
                "~/.config/xfce4/panel/*",
                "~/.config/xfce4/terminal/*",
                "~/.config/Thunar/*",
            ],
            "cinnamon": [
                "~/.config/cinnamon-*",
                "~/.cinnamon/*",
                "~/.local/share/cinnamon/*",
            ],
            "mate": [
                "~/.config/mate/*",
                "~/.mate/*",
                "~/.local/share/mate/*",
            ],
            "lxde": [
                "~/.config/lxde/*",
                "~/.config/lxpanel/*",
                "~/.config/lxsession/*",
                "~/.config/openbox/lxde-rc.xml",
                "~/.config/pcmanfm/*",
            ],
            "lxqt": [
                "~/.config/lxqt/*",
            ],
            # Window managers
            "i3": [
                "~/.config/i3/*",
                "~/.i3/*",
            ],
            "sway": [
                "~/.config/sway/*",
            ],
            "awesome": [
                "~/.config/awesome/*",
            ],
            "bspwm": [
                "~/.config/bspwm/*",
                "~/.config/sxhkd/*",
            ],
            "openbox": [
                "~/.config/openbox/*",
            ],
            "xmonad": [
                "~/.xmonad/*",
            ],
            "dwm": [
                "~/.dwm/*",
            ],
            "qtile": [
                "~/.config/qtile/*",
            ],
            # Common X configurations
            "x11": [
                "~/.xinitrc",
                "~/.xsession",
                "~/.Xresources",
                "~/.Xdefaults",
                "~/.gtkrc-2.0",
                "~/.config/gtk-3.0/settings.ini",
                "~/.config/gtk-3.0/bookmarks",
                "~/.config/gtk-4.0/*",
            ],
            # Desktop entry files
            "applications": [
                "~/.local/share/applications/*.desktop",
            ],
            # Session managers
            "session": [
                "~/.config/autostart/*",
            ],
        }
        
        # Hardware-specific paths to exclude
        self.hardware_specific_paths = [
            # Display configurations with resolution/position info
            "**/monitors.xml",
            "**/xrandr*",
            "**/display*",
            "**/screen*",
            # Device-specific configs
            "**/input-devices*",
            "**/touchpad*",
            "**/mouse*",
            "**/keyboard*",
            "**/wacom*",
            "**/tablet*",
            "**/printer*",
            # Network hardware configs
            "**/network-connections*",
            "**/NetworkManager/system-connections*",
            # Machine IDs and hardware addresses
            "**/machine-id*",
            "**/machineid*",
            "**/host*",
            "**/uuid*",
            # Graphics drivers
            "**/nvidia*",
            "**/amdgpu*",
            "**/intel-*",
            "**/xorg.conf*",
        ]
    
    def detect_desktop_environments(self) -> List[str]:
        """Detect which desktop environments are installed on the system"""
        installed_des = []
        
        # Check process environment variables
        desktop = os.environ.get('XDG_CURRENT_DESKTOP', '').lower()
        session = os.environ.get('DESKTOP_SESSION', '').lower()
        
        if "gnome" in desktop or "gnome" in session:
            installed_des.append("gnome")
        if "kde" in desktop or "plasma" in desktop or "kde" in session:
            installed_des.append("kde")
        if "xfce" in desktop or "xfce" in session:
            installed_des.append("xfce")
        if "cinnamon" in desktop or "cinnamon" in session:
            installed_des.append("cinnamon")
        if "mate" in desktop or "mate" in session:
            installed_des.append("mate")
        if "lxde" in desktop or "lxde" in session:
            installed_des.append("lxde")
        if "lxqt" in desktop or "lxqt" in session:
            installed_des.append("lxqt")
        
        # Check for window managers by looking for their configs
        wm_checks = {
            "i3": ["~/.config/i3/config", "~/.i3/config"],
            "sway": ["~/.config/sway/config"],
            "awesome": ["~/.config/awesome/rc.lua"],
            "bspwm": ["~/.config/bspwm/bspwmrc"],
            "openbox": ["~/.config/openbox/rc.xml"],
            "xmonad": ["~/.xmonad/xmonad.hs"],
            "dwm": ["~/.dwm/config.h"],
            "qtile": ["~/.config/qtile/config.py"],
        }
        
        for wm, config_paths in wm_checks.items():
            for path in config_paths:
                if os.path.exists(os.path.expanduser(path)):
                    installed_des.append(wm)
                    break
        
        # Always include X11 configs if we're in a graphical environment
        if os.environ.get('DISPLAY') or desktop or session:
            installed_des.append("x11")
            installed_des.append("applications")
            installed_des.append("session")
        
        logger.info(f"Detected desktop environments and window managers: {installed_des}")
        return installed_des
    
    def find_config_files(self, 
                          include_desktop: bool = True, 
                          desktop_environments: Optional[List[str]] = None,
                          exclude_desktop: Optional[List[str]] = None) -> List[ConfigFile]:
        """Find desktop environment configuration files to track
        
        Args:
            include_desktop: Whether to include desktop environment configs at all
            desktop_environments: Specific environments to include, or None for all detected
            exclude_desktop: Environments to exclude
        """
        if not include_desktop:
            logger.info("Desktop environment tracking disabled")
            return []
        
        config_files = []
        tracked_paths = set()
        
        # Determine which desktop environments to track
        if desktop_environments:
            des_to_track = desktop_environments
        else:
            des_to_track = self.detect_desktop_environments()
        
        # Apply exclusions
        if exclude_desktop:
            des_to_track = [de for de in des_to_track if de not in exclude_desktop]
        
        logger.info(f"Tracking configurations for: {des_to_track}")
        
        # Find config files for each desktop environment
        for de in des_to_track:
            if de in self.de_config_paths:
                for pattern in self.de_config_paths[de]:
                    expanded_pattern = os.path.expanduser(pattern)
                    try:
                        matching_paths = glob.glob(expanded_pattern, recursive=True)
                        for path in matching_paths:
                            # Skip directories, we only want files
                            if os.path.isdir(path):
                                # But recurse into them to find config files
                                for root, dirs, files in os.walk(path):
                                    for file in files:
                                        file_path = os.path.join(root, file)
                                        if self._should_track_path(file_path) and file_path not in tracked_paths:
                                            tracked_paths.add(file_path)
                                            config = self._create_config_file(file_path, de)
                                            if config:
                                                config_files.append(config)
                                                self.tracked_files[config.path] = config
                            elif self._should_track_path(path) and path not in tracked_paths:
                                tracked_paths.add(path)
                                config = self._create_config_file(path, de)
                                if config:
                                    config_files.append(config)
                                    self.tracked_files[config.path] = config
                    except Exception as e:
                        logger.error(f"Error processing pattern {pattern} for {de}: {e}")
        
        # Special handling for dconf settings (GNOME and others)
        if "gnome" in des_to_track or "cinnamon" in des_to_track or "mate" in des_to_track:
            try:
                # Export dconf settings to a temporary file
                dconf_path = os.path.expanduser("~/.local/share/migrator/dconf-settings.ini")
                os.makedirs(os.path.dirname(dconf_path), exist_ok=True)
                
                # Exclude hardware-specific dconf paths
                dconf_exclude_args = []
                for path in [
                    "/org/gnome/settings-daemon/plugins/power/",
                    "/org/gnome/desktop/peripherals/",
                    "/org/gnome/desktop/input-sources/",
                    "/org/gnome/desktop/media-handling/",
                    "/org/gnome/desktop/sound/",
                    "/org/gnome/settings-daemon/peripherals/",
                ]:
                    dconf_exclude_args.extend(["-v", path])
                
                # Run dconf dump with exclusions
                subprocess.run(
                    ["dconf", "dump", "/", ">", dconf_path], 
                    shell=True, 
                    stderr=subprocess.PIPE,
                    check=False
                )
                
                if os.path.exists(dconf_path) and os.path.getsize(dconf_path) > 0:
                    config = self._create_config_file(dconf_path, "gnome")
                    if config:
                        config_files.append(config)
                        self.tracked_files[config.path] = config
            except Exception as e:
                logger.error(f"Error exporting dconf settings: {e}")
        
        logger.info(f"Found {len(config_files)} desktop environment configuration files")
        return config_files
    
    def _should_track_path(self, path: str) -> bool:
        """Determine if a path should be tracked based on exclusion rules"""
        # Skip if not a file or not readable
        if not os.path.isfile(path) or not os.access(path, os.R_OK):
            return False
            
        # Skip if empty
        if os.path.getsize(path) == 0:
            return False
            
        # Skip backup/temporary files
        if path.endswith(("~", ".bak", ".old", ".tmp", ".swp")):
            return False
            
        # Skip hardware-specific paths
        for pattern in self.hardware_specific_paths:
            if self._path_matches_pattern(path, pattern):
                logger.debug(f"Skipping hardware-specific path: {path}")
                return False
                
        return True
    
    def _path_matches_pattern(self, path: str, pattern: str) -> bool:
        """Check if a path matches a glob-like pattern"""
        # Convert the pattern to a real glob pattern
        if pattern.startswith("**/"):
            # Check if any part of the path contains the pattern after **/
            return pattern[3:] in path
        elif "*" in pattern:
            # Use simple string matching for now
            pattern_parts = pattern.split("*")
            return all(part in path for part in pattern_parts if part)
        else:
            return pattern in path
    
    def _create_config_file(self, path: str, de_name: str) -> Optional[ConfigFile]:
        """Create a ConfigFile object for a desktop environment config file"""
        try:
            if not os.path.exists(path) or not os.access(path, os.R_OK):
                return None
                
            # Generate a description
            description = f"Desktop environment configuration: {os.path.basename(path)}"
            
            # Set the category based on the desktop environment
            category = f"desktop_environment:{de_name}"
            
            return ConfigFile(
                path=path,
                description=description,
                category=category,
                is_system_config=False
            )
        except Exception as e:
            logger.error(f"Error creating config file for {path}: {e}")
            return None

    def get_config_file(self, path: str) -> Optional[ConfigFile]:
        """Get a specific configuration file by path"""
        abs_path = os.path.abspath(os.path.expanduser(path))
        return self.tracked_files.get(abs_path)
    
    def track_config_file(self, path: str, description: str = "", category: str = "") -> Optional[ConfigFile]:
        """Add a configuration file to be tracked"""
        abs_path = os.path.abspath(os.path.expanduser(path))
        if not os.path.exists(abs_path) or not os.access(abs_path, os.R_OK):
            logger.warning(f"Cannot track non-existent or unreadable file: {abs_path}")
            return None
        
        # Default to generic desktop environment category if none provided
        if not category:
            category = "desktop_environment:other"
            
        # Create a new config file object
        config_file = ConfigFile(
            path=abs_path,
            description=description,
            category=category,
            is_system_config=False
        )
        
        self.tracked_files[abs_path] = config_file
        return config_file
    
    def stop_tracking_config_file(self, path: str) -> bool:
        """Stop tracking a configuration file"""
        abs_path = os.path.abspath(os.path.expanduser(path))
        if abs_path in self.tracked_files:
            del self.tracked_files[abs_path]
            return True
        return False
    
    def get_changed_files(self) -> List[ConfigFile]:
        """Get list of tracked files that have changed since last check"""
        changed_files = []
        
        for path, config_file in list(self.tracked_files.items()):
            if not os.path.exists(path):
                # File was deleted
                changed_files.append(config_file)
                # Keep tracking it to note the deletion
            elif config_file.has_changed():
                # File was modified
                changed_files.append(config_file)
                # Update the checksum
                config_file.update()
        
        return changed_files
    
    def update_all(self) -> None:
        """Update checksums for all tracked files"""
        for config_file in self.tracked_files.values():
            config_file.update() 