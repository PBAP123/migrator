#!/usr/bin/env python3
"""
User configuration tracker for user-specific configuration files
"""

import os
import glob
import logging
from typing import List, Dict, Any, Optional, Set

from .base import ConfigTracker, ConfigFile

logger = logging.getLogger(__name__)

class UserConfigTracker(ConfigTracker):
    """Track user-specific configuration files"""
    
    def __init__(self):
        super().__init__("user_config")
        self.tracked_files: Dict[str, ConfigFile] = {}
        
        # Get user's home directory
        self.home_dir = os.path.expanduser("~")
        
        # Define common locations for user configuration
        self.config_dirs = [
            os.path.join(self.home_dir, ".config"),
            os.path.join(self.home_dir, ".local/share"),
            self.home_dir  # For dot files
        ]
        
        # Define allow/deny lists for ~/.local/share directories
        # These are used to provide more granular control over what gets backed up
        self.local_share_allowlist = [
            "applications",  # Desktop entries
            "fonts",         # User-installed fonts
            "icons",         # User-installed icons
            "themes",        # User-installed themes
            "mime",          # Custom MIME type definitions
            "keyrings",      # Password keyrings
            "gnome-shell",   # GNOME Shell extensions and settings
            "plasma",        # KDE Plasma customizations
            "kwin",          # KWin scripts and settings
            "cinnamon",      # Cinnamon desktop settings
            "nemo",          # Nemo file manager settings
            "nautilus",      # Nautilus scripts and extensions
            "vlc",           # VLC media player config
            "TelegramDesktop", # Telegram settings
            "kscreen",       # KDE screen layouts
            "evolution",     # Evolution mail client settings
            "geary",         # Geary mail client settings
            "fish",          # Fish shell completions and configs
            "sounds",        # Custom notification sounds
            "gvfs-metadata", # File manager metadata
            "recently-used.xbel", # Recent documents
            "user-places.xbel", # Bookmarked places
        ]
        
        # Directories to explicitly deny even if they match a pattern
        self.local_share_denylist = [
            "Steam",         # Game installations (very large)
            "Trash",         # Deleted files
            "flatpak",       # Flatpak runtime data
            "containers",    # Container images and data
            "baloo",         # KDE file indexer data
            "tracker",       # GNOME tracker database
            "akonadi",       # KDE PIM storage service data
            "webkit",        # Browser cache and data
            "gstreamer-1.0", # Media cache
            "gvfs-metadata", # GVFS metadata (can be large)
        ]
        
        # Paths with potential portability warnings for users
        self.warning_paths = {
            "~/.local/share/keyrings": (
                "WARNING: Keyring files are encrypted with your login password and may not be usable "
                "on a different system if your password changes. Consider manually exporting sensitive "
                "passwords through your password manager application instead."
            ),
            "~/.gnupg": (
                "WARNING: GPG keys may require additional setup after restore, including setting correct "
                "permissions and ensuring you have the correct passphrases."
            ),
            "~/.mozilla": (
                "WARNING: Full Mozilla/Firefox profile backups can be very large and may contain "
                "cached content. Consider using Firefox Sync instead for profile migration."
            ),
            "~/.thunderbird": (
                "WARNING: Email client profiles may contain large amounts of data if emails are stored locally. "
                "Consider using IMAP for email access instead of backing up local mail stores."
            ),
            "~/.config/chromium": (
                "WARNING: Chromium/Chrome profiles can be very large and contain cached data. "
                "Consider using Chrome Sync instead for profile migration."
            ),
            "~/.docker": (
                "WARNING: Docker configuration may include authentication tokens that are machine-specific. "
                "You may need to re-authenticate after restore."
            ),
            "~/.config/pulse": (
                "WARNING: PulseAudio configuration is often tied to specific hardware. "
                "These settings may not work correctly on a different system."
            ),
            "~/.ssh": (
                "WARNING: SSH keys should have correct permissions (0600) set after restore. "
                "Ensure that private keys remain secure during the backup/restore process."
            )
        }
        
        # Common important user configuration files to track
        self.important_configs = [
            # Shell and terminal
            "~/.bashrc",
            "~/.bash_profile",
            "~/.profile",
            "~/.zshrc",
            "~/.zprofile",
            "~/.zshenv",
            "~/.inputrc",
            "~/.tmux.conf",
            "~/.screenrc",
            
            # Editor configs
            "~/.vimrc",
            "~/.vim/*/",
            "~/.emacs",
            "~/.emacs.d/init.el",
            "~/.config/nvim/init.vim",
            "~/.config/nano/nanorc",
            
            # Git and version control
            "~/.gitconfig",
            "~/.gitignore_global",
            
            # Window managers and desktop environments
            "~/.config/i3/config",
            "~/.config/sway/config",
            "~/.config/awesome/rc.lua",
            "~/.config/bspwm/bspwmrc",
            "~/.config/openbox/rc.xml",
            "~/.config/plasma-org.kde.plasma.desktop-appletsrc",
            "~/.config/xfce4/xfconf/xfce-perchannel-xml/*",
            "~/.config/gtk-3.0/settings.ini",
            "~/.gtkrc-2.0",
            
            # Terminal emulators
            "~/.config/alacritty/alacritty.yml",
            "~/.config/kitty/kitty.conf",
            "~/.config/terminator/config",
            
            # Application configs - browsers
            "~/.config/chromium/*/Preferences",
            "~/.config/google-chrome/*/Preferences",
            "~/.mozilla/firefox/*/prefs.js",
            
            # Application configs - development
            "~/.config/Code/User/settings.json",
            "~/.config/Code/User/keybindings.json",
            "~/.config/sublime-text-3/Packages/User/Preferences.sublime-settings",
            "~/.config/JetBrains/*/options/editor.xml",
            
            # Application configs - other
            "~/.config/pulse/daemon.conf",
            "~/.config/vlc/vlcrc",
            "~/.config/mpv/mpv.conf",
            
            # SSH configuration
            "~/.ssh/config",
            
            # Desktop files
            "~/.local/share/applications/*.desktop",
            
            # Local share directories - NEW
            "~/.local/share/fonts/*",
            "~/.local/share/icons/*",
            "~/.local/share/themes/*",
            "~/.local/share/mime/*",
            "~/.local/share/keyrings/*",
            
            # User scripts - NEW
            "~/bin/*",
            "~/.local/bin/*",
            
            # Application specific directories - NEW
            "~/.mozilla/*",
            "~/.thunderbird/*",
            "~/.gnupg/*",
            "~/.cups/*",
            "~/.docker/config.json",
            
            # User systemd units - NEW
            "~/.config/systemd/user/*.service",
            "~/.config/systemd/user/*.timer",
            "~/.config/systemd/user/*.target"
        ]
    
    def find_config_files(self, include_paths=None, exclude_paths=None) -> List[ConfigFile]:
        """Find user configuration files to track
        
        Args:
            include_paths: List of additional paths to include
            exclude_paths: List of paths to exclude
            
        Returns:
            List of found configuration files
        """
        config_files = []
        
        # Expand globs and find files
        for pattern in self.important_configs:
            # Expand home directory
            pattern = os.path.expanduser(pattern)
            
            if pattern.endswith("/*/"):
                # Special case for directories with subdirectories
                base_dir = pattern[:-2]  # Remove /*/ suffix
                if os.path.isdir(base_dir):
                    for item in os.listdir(base_dir):
                        item_path = os.path.join(base_dir, item)
                        if os.path.isdir(item_path):
                            # Track configuration files in these subdirectories
                            for subfile in self._find_config_files_in_dir(item_path):
                                config_files.append(subfile)
                                self.tracked_files[subfile.path] = subfile
            elif "*" in pattern:
                try:
                    for file_path in glob.glob(pattern):
                        if os.path.isfile(file_path) and os.access(file_path, os.R_OK):
                            # Create config file object
                            config = self._create_config_file(file_path)
                            if config:
                                config_files.append(config)
                                self.tracked_files[config.path] = config
                except Exception as e:
                    logger.error(f"Error processing glob pattern {pattern}: {e}")
            else:
                if os.path.isfile(pattern) and os.access(pattern, os.R_OK):
                    # Create config file object
                    config = self._create_config_file(pattern)
                    if config:
                        config_files.append(config)
                        self.tracked_files[config.path] = config
        
        # Also scan .config directory for common app configs
        config_dir = os.path.join(self.home_dir, ".config")
        if os.path.isdir(config_dir):
            for app_dir in os.listdir(config_dir):
                app_config_dir = os.path.join(config_dir, app_dir)
                if os.path.isdir(app_config_dir):
                    # Look for main config files like config, settings.json, etc.
                    main_config_names = ["config", "settings.json", f"{app_dir}.conf", f"{app_dir}.ini"]
                    for config_name in main_config_names:
                        config_path = os.path.join(app_config_dir, config_name)
                        if os.path.isfile(config_path) and os.access(config_path, os.R_OK):
                            config = self._create_config_file(config_path)
                            if config and config.path not in self.tracked_files:
                                config_files.append(config)
                                self.tracked_files[config.path] = config
        
        # Selectively scan .local/share based on allowlist
        local_share_dir = os.path.join(self.home_dir, ".local/share")
        if os.path.isdir(local_share_dir):
            # Check each directory in the allowlist
            for allowed_dir in self.local_share_allowlist:
                dir_path = os.path.join(local_share_dir, allowed_dir)
                
                # Skip if in denylist or doesn't exist
                if (allowed_dir in self.local_share_denylist or 
                    not os.path.exists(dir_path)):
                    continue
                    
                # For files, just add them directly
                if os.path.isfile(dir_path) and os.access(dir_path, os.R_OK):
                    config = self._create_config_file(dir_path)
                    if config and config.path not in self.tracked_files:
                        config_files.append(config)
                        self.tracked_files[config.path] = config
                # For directories, scan them for config files
                elif os.path.isdir(dir_path):
                    for subfile in self._find_config_files_in_dir(dir_path):
                        if subfile.path not in self.tracked_files:
                            config_files.append(subfile)
                            self.tracked_files[subfile.path] = subfile
        
        # Also scan for all dot files in home directory that look like configs
        for item in os.listdir(self.home_dir):
            if item.startswith(".") and not item.startswith(".."):
                item_path = os.path.join(self.home_dir, item)
                # Skip directories like .cache, .local, etc.
                if os.path.isfile(item_path) and os.access(item_path, os.R_OK):
                    # Skip known non-config dot files
                    if item not in [".bash_history", ".lesshst", ".viminfo", ".python_history", ".wget-hsts", ".xsession-errors"]:
                        config = self._create_config_file(item_path)
                        if config and config.path not in self.tracked_files:
                            config_files.append(config)
                            self.tracked_files[config.path] = config
        
        # Process additional include paths if provided
        if include_paths:
            for path in include_paths:
                # Expand path and handle globs
                expanded_path = os.path.expanduser(path)
                
                if '*' in expanded_path:
                    # Handle glob patterns
                    for matching_path in glob.glob(expanded_path):
                        if os.path.isfile(matching_path) and os.access(matching_path, os.R_OK):
                            config = self._create_config_file(matching_path)
                            if config and config.path not in self.tracked_files:
                                config_files.append(config)
                                self.tracked_files[config.path] = config
                elif os.path.isfile(expanded_path) and os.access(expanded_path, os.R_OK):
                    # Handle direct file paths
                    config = self._create_config_file(expanded_path)
                    if config and config.path not in self.tracked_files:
                        config_files.append(config)
                        self.tracked_files[config.path] = config
                elif os.path.isdir(expanded_path):
                    # Handle directories
                    for subfile in self._find_config_files_in_dir(expanded_path):
                        if subfile.path not in self.tracked_files:
                            config_files.append(subfile)
                            self.tracked_files[subfile.path] = subfile
        
        return config_files
    
    def _find_config_files_in_dir(self, directory: str) -> List[ConfigFile]:
        """Find configuration files in a directory recursively"""
        configs = []
        
        try:
            for root, dirs, files in os.walk(directory):
                for file in files:
                    if file.endswith((".conf", ".cfg", ".ini", ".json", ".yml", ".yaml", ".xml", ".toml")):
                        file_path = os.path.join(root, file)
                        if os.access(file_path, os.R_OK):
                            config = self._create_config_file(file_path)
                            if config:
                                configs.append(config)
        except Exception as e:
            logger.error(f"Error walking directory {directory}: {e}")
        
        return configs
    
    def _create_config_file(self, path: str) -> Optional[ConfigFile]:
        """Create a ConfigFile object with appropriate metadata"""
        try:
            # Determine category based on path
            category = "user"
            rel_path = os.path.relpath(path, self.home_dir)
            
            # Shell and terminal configurations
            if any(name in rel_path for name in ["bash", "zsh", "profile", "tmux", "screen", "inputrc"]):
                category = "shell"
            # Editor configurations
            elif any(name in rel_path for name in ["vim", "emacs", "nano", "code", "sublime", "jetbrains"]):
                category = "editor"
            # Window manager & DE configurations
            elif any(name in rel_path for name in ["i3", "sway", "awesome", "bspwm", "openbox", "kde", "xfce", "gtk"]):
                category = "desktop_environment"
            # Browser configurations
            elif any(name in rel_path for name in ["chrom", "firefox", "mozilla"]):
                category = "browser"
            # Terminal emulator configurations
            elif any(name in rel_path for name in ["alacritty", "kitty", "terminator", "terminal"]):
                category = "terminal"
            # Media player configurations
            elif any(name in rel_path for name in ["pulse", "vlc", "mpv", "audio"]):
                category = "media"
            # Git and version control
            elif "git" in rel_path:
                category = "git"
            # SSH configuration
            elif ".ssh" in rel_path:
                category = "ssh"
            # Desktop files
            elif rel_path.endswith(".desktop"):
                category = "application"
            # General .config files
            elif ".config/" in rel_path:
                app_name = rel_path.split(".config/", 1)[1].split("/", 1)[0]
                category = f"application:{app_name}"
            
            # Generate a description
            description = f"User configuration file: {os.path.basename(path)}"
            if category.startswith("application:"):
                app_name = category.split(":", 1)[1]
                description = f"Configuration for {app_name}: {os.path.basename(path)}"
            
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
        path = os.path.abspath(os.path.expanduser(path))
        return self.tracked_files.get(path)
    
    def track_config_file(self, path: str, description: str = "", category: str = "") -> Optional[ConfigFile]:
        """Add a configuration file to be tracked"""
        path = os.path.abspath(os.path.expanduser(path))
        
        if not os.path.isfile(path):
            logger.error(f"Cannot track non-existent file: {path}")
            return None
        
        if not os.access(path, os.R_OK):
            logger.error(f"Cannot track unreadable file: {path}")
            return None
        
        # Create default description and category if not provided
        if not description:
            description = f"User configuration file: {os.path.basename(path)}"
        
        if not category:
            # Check if it's in the home directory
            if path.startswith(self.home_dir):
                category = "user"
            else:
                category = "other"
        
        config = ConfigFile(
            path=path,
            description=description,
            category=category,
            is_system_config=False
        )
        
        self.tracked_files[path] = config
        return config
    
    def stop_tracking_config_file(self, path: str) -> bool:
        """Stop tracking a configuration file"""
        path = os.path.abspath(os.path.expanduser(path))
        if path in self.tracked_files:
            del self.tracked_files[path]
            return True
        return False
    
    def get_changed_files(self) -> List[ConfigFile]:
        """Get list of tracked files that have changed since last check"""
        changed_files = []
        
        for path, config in self.tracked_files.items():
            if config.has_changed():
                changed_files.append(config)
        
        return changed_files
    
    def update_all(self) -> None:
        """Update checksums for all tracked files"""
        for config in self.tracked_files.values():
            config.update()
    
    def get_path_warnings(self, paths: List[str]) -> Dict[str, str]:
        """Get warnings for specific paths that may have portability issues
        
        Args:
            paths: List of paths to check for warnings
            
        Returns:
            Dictionary mapping paths to warning messages
        """
        warnings = {}
        
        for path in paths:
            # Expand the path to compare with warning patterns
            expanded_path = os.path.expanduser(path)
            
            # Check against warning patterns
            for warning_pattern, warning_message in self.warning_paths.items():
                # Expand the warning pattern
                expanded_warning = os.path.expanduser(warning_pattern)
                
                # If path exactly matches or is a subdirectory of the warning pattern
                if expanded_path == expanded_warning or (
                    os.path.isdir(expanded_warning) and
                    expanded_path.startswith(expanded_warning + '/')
                ):
                    warnings[path] = warning_message
                    break 