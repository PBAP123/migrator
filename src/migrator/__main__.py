#!/usr/bin/env python3
"""
Command-line interface for Migrator utility

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
import sys
import json
import time
import argparse
import textwrap
import platform
import datetime
import logging
import fnmatch
import subprocess
from typing import List, Dict, Any, Optional, Tuple
from pathlib import Path

from migrator.main import Migrator
from migrator.utils.service import create_systemd_service, remove_systemd_service
from migrator.utils.setup_wizard import run_setup_wizard, setup_package_mappings
from migrator.utils.config import config

logger = logging.getLogger(__name__)

def setup_argparse() -> argparse.ArgumentParser:
    """Set up command-line argument parser"""
    parser = argparse.ArgumentParser(
        description="Migrator - A system migration utility",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=textwrap.dedent("""\
            Examples:
              migrator scan               # Scan and update system state
              migrator scan --include-desktop  # Include desktop environment configs
              migrator backup ~/backups   # Backup system state to directory
              migrator restore backup.json # Restore from backup
              migrator restore backup.json --execute  # Restore and install packages/configs
              migrator restore backup.json --packages-only  # Only install packages
              migrator compare backup.json # Compare current system with backup
              migrator plan backup.json   # Generate installation plan from backup
              migrator install-service    # Install as a systemd service
              migrator setup              # Launch the interactive setup wizard
              migrator config get-backup-dir  # Display the current backup directory
              migrator config set-backup-dir PATH  # Set a new backup directory
        """)
    )
    
    subparsers = parser.add_subparsers(dest='command', help='Command to execute')
    
    # Scan command
    scan_parser = subparsers.add_parser('scan', help='Scan system for installed packages')
    scan_parser.add_argument('--include-desktop', action='store_true',
                           help='Include desktop environment configs')
    scan_parser.add_argument('--desktop-environments', 
                           help='Comma-separated list of desktop environments to include (e.g., gnome,kde,i3)')
    scan_parser.add_argument('--exclude-desktop', 
                           help='Comma-separated list of desktop environments to exclude')
    scan_parser.add_argument('--include-paths',
                           help='Comma-separated list of additional paths to include in the config scan')
    scan_parser.add_argument('--exclude-paths',
                           help='Comma-separated list of paths to exclude from the config scan')
    scan_parser.add_argument('--test-mode', action='store_true',
                           help='Run in test mode with limited package scanning (for development/debugging)')
    scan_parser.add_argument('--skip-setup-check', action='store_true',
                           help='Skip the first-run setup wizard check')
    scan_parser.add_argument('--no-repo-backup', action='store_true',
                           help='Skip scanning and backing up software repositories')
    
    # Backup command
    backup_parser = subparsers.add_parser('backup', help='Backup system state')
    backup_parser.add_argument('backup_dir', nargs='?', default=None, help='Directory to store backup (defaults to configured backup directory)')
    backup_parser.add_argument('--apps-only', action='store_true',
                             help='Backup only installed applications list, no config files')
    backup_parser.add_argument('--no-desktop', action='store_true', 
                             help='Skip desktop environment configs (included by default)')
    backup_parser.add_argument('--desktop-environments', 
                             help='Comma-separated list of desktop environments to include (e.g., gnome,kde,i3)')
    backup_parser.add_argument('--exclude-desktop', 
                             help='Comma-separated list of desktop environments to exclude')
    backup_parser.add_argument('--include-paths',
                             help='Comma-separated list of additional paths to include in the config scan')
    backup_parser.add_argument('--exclude-paths',
                             help='Comma-separated list of paths to exclude from the config scan')
    backup_parser.add_argument('--no-path-variables', action='store_true',
                             help='Disable dynamic path variable substitution for improved portability (enabled by default)')
    backup_parser.add_argument('--no-fstab-portability', action='store_true',
                             help='Disable selective backup of portable fstab entries (enabled by default)')
    backup_parser.add_argument('--no-repo-backup', action='store_true',
                             help='Skip scanning and backing up software repositories (included by default)')
    backup_parser.add_argument('--skip-setup-check', action='store_true',
                             help='Skip the first-run setup wizard check')
    backup_parser.add_argument('--minimal', action='store_true',
                             help='Create a minimal backup with only essential preferences (no application data)')
    
    # Restore command
    restore_parser = subparsers.add_parser('restore', help='Restore system state from backup')
    restore_parser.add_argument('backup_file', help='Backup file to restore from')
    restore_parser.add_argument('--execute', '-e', action='store_true', 
                             help='Automatically install packages and restore config files')
    restore_parser.add_argument('--packages-only', action='store_true',
                             help='Only install packages, skip config files')
    restore_parser.add_argument('--configs-only', action='store_true',
                             help='Only restore config files, skip packages')
    restore_parser.add_argument('--dry-run', action='store_true',
                              help='Perform a dry run showing all changes that would be made without actually applying them')
    restore_parser.add_argument('--skip-setup-check', action='store_true',
                              help='Skip the first-run setup wizard check')
    # Version handling options
    version_group = restore_parser.add_argument_group('version handling')
    version_group.add_argument('--version-policy', type=str, default='prefer-newer',
                            choices=['exact', 'prefer-same', 'prefer-newer', 'always-newest'],
                            help='Package version policy: exact=only install exact versions, '
                                'prefer-same=try exact version first but allow newer if needed, '
                                'prefer-newer=prefer newer versions but allow downgrade if needed, '
                                'always-newest=always use newest available version')
    version_group.add_argument('--allow-downgrade', action='store_true',
                            help='Allow downgrading packages if newer versions are installed')
    
    # Path variables options
    path_group = restore_parser.add_argument_group('path handling')
    path_group.add_argument('--no-path-transform', action='store_true',
                          help='Disable automatic transformation of paths in config files')
    path_group.add_argument('--path-transform-preview', action='store_true',
                          help='Show what paths would be transformed without making changes')
    
    # Fstab options
    fstab_group = restore_parser.add_argument_group('fstab handling')
    fstab_group.add_argument('--no-fstab-restore', action='store_true',
                           help='Skip restoration of portable fstab entries')
    fstab_group.add_argument('--preview-fstab', action='store_true',
                           help='Preview portable fstab entries without applying changes')
    
    # Repository options
    repo_group = restore_parser.add_argument_group('repository handling')
    repo_group.add_argument('--no-repo-restore', action='store_true',
                          help='Skip restoration of software repositories')
    repo_group.add_argument('--preview-repos', action='store_true',
                          help='Preview repository restoration without applying changes')
    repo_group.add_argument('--force-incompatible-repos', action='store_true',
                          help='Attempt to restore incompatible repositories (may cause system issues)')
    
    # Compare command
    compare_parser = subparsers.add_parser('compare', help='Compare current system with a backup')
    compare_parser.add_argument('backup_file', help='Backup file to compare against')
    compare_parser.add_argument('--output', '-o', help='Output file for comparison results')
    
    # Generate plan command
    plan_parser = subparsers.add_parser('plan', 
                                      help='Generate installation plan from backup without applying changes')
    plan_parser.add_argument('backup_file', help='Backup file to use for planning')
    plan_parser.add_argument('--output', '-o', help='Output file for installation plan')
    plan_parser.add_argument('--format', '-f', choices=['text', 'json'], default='text',
                           help='Output format (text or JSON)')
    
    # System check command
    check_parser = subparsers.add_parser('check', help='Check system for potential migration issues')
    check_parser.add_argument('--output', '-o', help='Output file for check results')
    check_parser.add_argument('--verbose', '-v', action='store_true', help='Show detailed output')
    
    # Service management command
    service_parser = subparsers.add_parser('service', help='Manage scheduled backup service')
    service_subparsers = service_parser.add_subparsers(dest='service_command', help='Service command')
    
    # Service status command
    service_status_parser = service_subparsers.add_parser('status', help='Check status of backup service')
    
    # Service enable command
    service_enable_parser = service_subparsers.add_parser('enable', help='Enable scheduled backups')
    service_enable_parser.add_argument('--schedule', choices=['daily', 'weekly', 'monthly'], default='daily',
                                     help='Backup schedule frequency')
    service_enable_parser.add_argument('--time', help='Time to run backup (HH:MM format, 24-hour clock)')
    service_enable_parser.add_argument('--day', 
                                     help='Day to run backup (day of week for weekly, day of month for monthly)')
    
    # Service disable command
    service_disable_parser = service_subparsers.add_parser('disable', help='Disable scheduled backups')
    
    # Install service command
    install_service_parser = subparsers.add_parser('install-service', help='Install systemd service for scheduled backups')
    install_service_parser.add_argument('--schedule', choices=['daily', 'weekly', 'monthly'], default='daily',
                                      help='Backup schedule frequency')
    install_service_parser.add_argument('--time', help='Time to run backup (HH:MM format, 24-hour clock)')
    install_service_parser.add_argument('--day', 
                                      help='Day to run backup (day of week for weekly, day of month for monthly)')
    
    # Remove service command
    remove_service_parser = subparsers.add_parser('remove-service', help='Remove systemd service for scheduled backups')
    
    # Config command
    config_parser = subparsers.add_parser('config', help='Manage Migrator configuration')
    config_subparsers = config_parser.add_subparsers(dest='config_command', help='Config command')
    
    # Backup dir configuration
    config_get_backup_dir_parser = config_subparsers.add_parser('get-backup-dir', 
                                                             help='Show the current backup directory')
    
    config_set_backup_dir_parser = config_subparsers.add_parser('set-backup-dir',
                                                             help='Set the default backup directory')
    config_set_backup_dir_parser.add_argument('path', help='Path to use for backups')
    
    # Backup retention configuration
    config_backup_retention_parser = config_subparsers.add_parser('backup-retention',
                                                               help='Configure backup retention policy')
    retention_subparsers = config_backup_retention_parser.add_subparsers(dest='retention_command', 
                                                                    help='Retention command')
    
    retention_get_parser = retention_subparsers.add_parser('get', help='Show current retention settings')
    
    retention_enable_parser = retention_subparsers.add_parser('enable', 
                                                          help='Enable automatic cleanup of old backups')
    
    retention_disable_parser = retention_subparsers.add_parser('disable',
                                                           help='Disable automatic cleanup of old backups')
    
    retention_set_mode_parser = retention_subparsers.add_parser('set-mode',
                                                           help='Set retention mode (count or age)')
    retention_set_mode_parser.add_argument('mode', choices=['count', 'age'],
                                        help='Retention mode: count=keep N most recent backups, '
                                            'age=keep backups newer than N days')
    
    retention_set_count_parser = retention_subparsers.add_parser('set-count',
                                                            help='Set number of backups to keep (for count mode)')
    retention_set_count_parser.add_argument('count', type=int, help='Number of backups to keep')
    
    retention_set_age_parser = retention_subparsers.add_parser('set-age',
                                                          help='Set age in days for backups to keep (for age mode)')
    retention_set_age_parser.add_argument('days', type=int, help='Age in days')
    
    # Multi-host configuration
    config_get_hosts_parser = config_subparsers.add_parser('list-hosts',
                                                      help='List all hosts with backups')
    
    config_get_host_backups_parser = config_subparsers.add_parser('get-host-backups',
                                                            help='Show backups for a specific host')
    config_get_host_backups_parser.add_argument('hostname', help='Hostname to query')
    config_get_host_backups_parser.add_argument('--show-detail', '-d', action='store_true',
                                          help='Show detailed metadata for each backup')
    
    # List backups command
    list_backups_parser = subparsers.add_parser('list-backups', help='List available backups')
    list_backups_parser.add_argument('--backup-dir', 
                                   help='Directory to search for backups (defaults to configured backup directory)')
    list_backups_parser.add_argument('--show-detail', '-d', action='store_true',
                                   help='Show detailed metadata for each backup')
    list_backups_parser.add_argument('--by-host', '-b', action='store_true',
                                   help='Group backups by hostname')
    list_backups_parser.add_argument('--host', 
                                   help='Show backups only for the specified hostname')
    
    # Locate backups command
    locate_parser = subparsers.add_parser('locate-backup', 
                                        help='Scan common locations for Migrator backups')
    locate_parser.add_argument('--include-network', action='store_true',
                             help='Include network shares in the search (may be slow)')
    locate_parser.add_argument('--output', '-o', 
                             help='Output file for found backup paths')
    
    # Setup command
    setup_parser = subparsers.add_parser('setup', help='Run the interactive setup wizard')
    
    # Edit mappings command
    mappings_parser = subparsers.add_parser('edit-mappings', help='Edit package mappings for cross-distribution equivalence')
    
    return parser

def handle_scan(app: Migrator, args: argparse.Namespace) -> int:
    """Handle scan command"""
    # Check if this appears to be a first run on a new system
    if app.is_first_run() and not args.skip_setup_check:
        print("It appears this is the first time running Migrator.")
        print("Would you like to run the setup wizard first to configure Migrator?")
        choice = input("This will help you set up backup preferences (y/n): ")
        
        if choice.lower() in ['y', 'yes']:
            # Create setup args and call handle_setup
            setup_args = argparse.Namespace()
            handle_setup(app, setup_args)
    
    # Process desktop environment options - default is now TRUE (include desktop)
    include_desktop = not args.no_desktop if hasattr(args, 'no_desktop') else True
    desktop_envs = None
    exclude_desktop = None
    
    if hasattr(args, 'desktop_environments') and args.desktop_environments:
        desktop_envs = args.desktop_environments.split(',')
        
    if hasattr(args, 'exclude_desktop') and args.exclude_desktop:
        exclude_desktop = args.exclude_desktop.split(',')
    
    # Process include/exclude paths
    include_paths = None
    exclude_paths = None
    
    if hasattr(args, 'include_paths') and args.include_paths:
        include_paths = args.include_paths.split(',')
    
    if hasattr(args, 'exclude_paths') and args.exclude_paths:
        exclude_paths = args.exclude_paths.split(',')
    
    # Handle repository backup option
    include_repos = not args.no_repo_backup if hasattr(args, 'no_repo_backup') else True
    
    # For test mode (used for development/debugging)
    test_mode = args.test_mode if hasattr(args, 'test_mode') else False
    
    # Scan packages
    packages = app.scan_packages(test_mode=test_mode)
    print(f"Found {len(packages)} installed packages")
    
    # Scan configuration files
    configs = app.scan_config_files(
        include_desktop=include_desktop,
        desktop_environments=desktop_envs,
        exclude_desktop=exclude_desktop,
        include_paths=include_paths,
        exclude_paths=exclude_paths
    )
    print(f"Found {len(configs)} configuration files")
    
    # Scan repositories if not disabled
    if include_repos:
        repo_data = app.scan_repo_sources()
        repos = repo_data.get("repositories", [])
        print(f"Found {len(repos)} repository sources")
    
    # Update the system state
    app.update_system_state(
        include_desktop=include_desktop,
        desktop_environments=desktop_envs,
        exclude_desktop=exclude_desktop,
        include_paths=include_paths,
        exclude_paths=exclude_paths,
        include_fstab_portability=True,
        include_repos=include_repos
    )
    
    print("System scan complete. Run 'migrator backup' to create a backup.")
    
    return 0

def handle_backup(app: Migrator, args: argparse.Namespace) -> int:
    """Handle backup command"""
    # Check if this appears to be a first run on a new system
    if app.is_first_run() and not args.skip_setup_check:
        print("It appears this is the first time running Migrator.")
        print("Would you like to run the setup wizard first to configure Migrator?")
        choice = input("This will help you set up backup preferences (y/n): ")
        
        if choice.lower() in ['y', 'yes']:
            # Create setup args and call handle_setup
            setup_args = argparse.Namespace()
            handle_setup(app, setup_args)
    
    backup_dir = args.backup_dir
    
    if backup_dir is None:
        # Use default backup directory
        backup_dir = app.get_backup_dir()
        print(f"Using default backup directory: {backup_dir}")
    else:
        print(f"Backing up system state to {backup_dir}...")
    
    # Process desktop environment options
    include_desktop = not args.no_desktop if hasattr(args, 'no_desktop') else True
    desktop_envs = None
    exclude_desktop = None
    
    # Check if command line args should override saved config
    has_command_line_override = hasattr(args, 'apps_only') and args.apps_only
    
    # Initialize apps_only variable 
    apps_only = False
    
    # If command line flag is specified, it overrides saved config
    if has_command_line_override:
        apps_only = True
        print("Apps-only mode selected from command line: backing up only installed applications list")
        include_desktop = False
        include_fstab_portability = False
    else:
        # Check saved configuration for backup mode
        saved_backup_mode = config.get("backup_mode", "standard")
        
        if saved_backup_mode == "apps_only":
            print("Apps-only mode (from saved configuration): backing up only installed applications list")
            apps_only = True
            include_desktop = False
            include_fstab_portability = False
        elif saved_backup_mode == "standard":
            print("Standard backup mode (from saved configuration): apps + essential configs")
            apps_only = False
            include_desktop = False  # Standard mode doesn't include desktop configs
            include_fstab_portability = config.get("include_fstab_portability", True)
        elif saved_backup_mode == "complete":
            print("Complete backup mode (from saved configuration): all apps and configurations")
            apps_only = False
            include_desktop = config.get("include_desktop_configs", True)
            include_fstab_portability = config.get("include_fstab_portability", True)
        else:
            # Default if no recognized mode
            apps_only = False
    
    if hasattr(args, 'desktop_environments') and args.desktop_environments:
        desktop_envs = args.desktop_environments.split(',')
    
    if hasattr(args, 'exclude_desktop') and args.exclude_desktop:
        exclude_desktop = args.exclude_desktop.split(',')
    
    # Process include/exclude paths
    include_paths = None
    exclude_paths = None
    
    if hasattr(args, 'include_paths') and args.include_paths:
        include_paths = args.include_paths.split(',')
        print(f"Including additional user-specified paths: {args.include_paths}")
    
    if hasattr(args, 'exclude_paths') and args.exclude_paths:
        exclude_paths = args.exclude_paths.split(',')
        print(f"Excluding user-specified paths: {args.exclude_paths}")
    
    # Check for minimal backup mode
    if hasattr(args, 'minimal') and args.minimal:
        print("Creating minimal backup with essential preferences only")
        # Add essential directories to exclude_paths to create a minimal backup
        minimal_excludes = [
            "~/.local/share",
            "~/.mozilla",
            "~/.thunderbird",
            "~/.cache",
            "~/.var",
        ]
        if exclude_paths:
            exclude_paths.extend(minimal_excludes)
        else:
            exclude_paths = minimal_excludes
    
    # Handle path variables option
    use_path_variables = not args.no_path_variables if hasattr(args, 'no_path_variables') else True
    if not use_path_variables:
        print("Dynamic path variable substitution disabled")
    
    # Handle fstab portability option
    include_fstab_portability = not args.no_fstab_portability if hasattr(args, 'no_fstab_portability') else True
    # If apps-only is set, override this setting
    if apps_only:
        include_fstab_portability = False
    
    if not include_fstab_portability:
        print("Portable fstab entries backup disabled")
    
    # Handle repository backup option
    include_repos = not args.no_repo_backup if hasattr(args, 'no_repo_backup') else True
    if not include_repos:
        print("Software repository backup disabled")
    
    # Ensure state is up to date
    app.update_system_state(
        include_desktop=include_desktop,
        desktop_environments=desktop_envs,
        exclude_desktop=exclude_desktop,
        include_paths=include_paths,
        exclude_paths=exclude_paths,
        include_fstab_portability=include_fstab_portability,
        include_repos=include_repos,
        apps_only=apps_only
    )
    
    # Create backup
    backup_file = app.backup_state(backup_dir)
    
    if backup_file:
        print(f"Backup created successfully: {backup_file}")
        if use_path_variables:
            print("Path variables applied to configuration files for improved portability")
        return 0
    else:
        print("Failed to create backup.")
        return 1

def handle_restore(app: Migrator, args: argparse.Namespace) -> int:
    """Handle restore command"""
    # Check if this appears to be a first run on a new system
    if app.is_first_run() and not hasattr(args, 'dry_run') and not args.skip_setup_check:
        print("It appears this is the first time running Migrator on this system.")
        
        # Check if the specified backup file exists
        if not os.path.exists(args.backup_file):
            print(f"The specified backup file does not exist: {args.backup_file}")
            print("\nWould you like to:")
            print("1. Scan for backup files on connected drives")
            print("2. Specify a different backup file path")
            print("3. Run the setup wizard first")
            print("4. Cancel restore operation")
            
            choice = input("Enter your choice (1-4): ")
            
            if choice == '1':
                # Create locate_args and call handle_locate_backup
                locate_args = argparse.Namespace()
                locate_args.include_network = False
                return handle_locate_backup(app, locate_args)
            elif choice == '2':
                new_path = input("Enter the full path to your backup file: ")
                if os.path.exists(new_path):
                    args.backup_file = new_path
                else:
                    print(f"File not found: {new_path}")
                    return 1
            elif choice == '3':
                # Run the setup wizard first
                setup_args = argparse.Namespace()
                handle_setup(app, setup_args)
                
                # Continue with restore after setup if the file exists
                if os.path.exists(args.backup_file):
                    print(f"Continuing with restore from {args.backup_file}...")
                else:
                    print(f"The specified backup file does not exist: {args.backup_file}")
                    return 1
            else:
                print("Restore operation cancelled.")
                return 0
    
    print(f"Restoring system state from {args.backup_file}...")
    
    # Offer options to compare or plan before continuing with restore
    print("\nBefore restoring, would you like to:")
    print("1. Continue with restore")
    print("2. Generate an installation plan first")
    print("3. Compare with current system first")
    print("4. Cancel restore operation")
    
    choice = input("Enter your choice (1-4): ")
    
    if choice == '2':
        # Create plan args and call handle_plan
        plan_args = argparse.Namespace()
        plan_args.backup_file = args.backup_file
        handle_plan(app, plan_args)
        
        # Ask if they want to continue
        continue_restore = input("\nDo you want to continue with the restore? (yes/no): ").lower().strip()
        if continue_restore != 'yes':
            print("Restore operation cancelled.")
            return 0
        
    elif choice == '3':
        # Create compare args and call handle_compare
        compare_args = argparse.Namespace()
        compare_args.backup_file = args.backup_file
        compare_args.output = None
        handle_compare(app, compare_args)
        
        # Ask if they want to continue
        continue_restore = input("\nDo you want to continue with the restore? (yes/no): ").lower().strip()
        if continue_restore != 'yes':
            print("Restore operation cancelled.")
            return 0
            
    elif choice == '4':
        print("Restore operation cancelled.")
        return 0
    
    # Check for dry run mode
    dry_run = args.dry_run if hasattr(args, 'dry_run') else False
    
    if dry_run:
        print("DRY RUN MODE - No changes will be made to your system")
        print("Generating comprehensive restore preview...")
        
        # Get options from arguments
        version_policy = args.version_policy if hasattr(args, 'version_policy') else 'prefer-newer'
        allow_downgrade = args.allow_downgrade if hasattr(args, 'allow_downgrade') else False
        transform_paths = not args.no_path_transform if hasattr(args, 'no_path_transform') else True
        
        # Generate dry run report
        report = app.generate_dry_run_report(
            args.backup_file,
            version_policy=version_policy,
            allow_downgrade=allow_downgrade,
            transform_paths=transform_paths
        )
        
        # Display the report
        print("\n=== DRY RUN RESTORE REPORT ===\n")
        
        # Package section
        print("PACKAGES:")
        print(f"  • {report['packages'].get('to_install', 0)} packages will be installed")
        print(f"  • {report['packages'].get('unavailable', 0)} packages are unavailable")
        
        if report['packages'].get('installation_commands', []):
            print("\nInstallation commands that would be executed:")
            for i, cmd in enumerate(report['packages']['installation_commands'][:5], 1):
                print(f"  {i}. {cmd}")
            if len(report['packages']['installation_commands']) > 5:
                print(f"  ... and {len(report['packages']['installation_commands']) - 5} more commands")
        
        # Config files section
        print("\nCONFIGURATION FILES:")
        print(f"  • {report['config_files'].get('to_restore', 0)} configuration files will be restored")
        print(f"  • {report['config_files'].get('conflicts', 0)} configuration files have conflicts")
        
        # Path transformations section
        if report.get('path_transformations', {}).get('examples', []):
            print("\nPATH TRANSFORMATIONS:")
            examples = report['path_transformations']['examples'][:3]
            for from_path, to_path in examples:
                print(f"  • {from_path} → {to_path}")
            if len(report['path_transformations']['examples']) > 3:
                print(f"  ... and {len(report['path_transformations']['examples']) - 3} more transformations")
        
        # Fstab entries section
        if "fstab" in report:
            print("\nFSTAB ENTRIES:")
            entries = report["fstab"].get("portable_entries", [])
            if entries:
                print(f"  • {len(entries)} portable fstab entries will be appended to /etc/fstab")
            else:
                print("  • No portable fstab entries found in backup")
        
        # Repositories section
        if "repositories" in report:
            print("\nSOFTWARE REPOSITORIES:")
            print(f"  • {report['repositories'].get('total', 0)} repositories found in backup")
            print(f"  • {report['repositories'].get('compatible', 0)} repositories are compatible with your system")
            print(f"  • {report['repositories'].get('incompatible', 0)} repositories have compatibility issues")
        
        # Conflicts section
        if report.get('conflicts', []):
            print("\nPOTENTIAL ISSUES AND CONFLICTS:")
            for i, conflict in enumerate(report['conflicts'], 1):
                if conflict['type'] == 'package_unavailable':
                    print(f"  {i}. Package '{conflict['name']}' ({conflict['source']}) is unavailable: {conflict['reason']}")
                elif conflict['type'] == 'version_downgrade_required':
                    print(f"  {i}. Package '{conflict['name']}' would require downgrade from {conflict['available_version']} to {conflict['backup_version']}")
                elif conflict['type'] == 'config_conflict':
                    print(f"  {i}. Config file '{conflict['path']}' has conflict: {conflict['status']}")
                elif conflict['type'] == 'repository_compatibility':
                    print(f"  {i}. Repository '{conflict['name']}' is incompatible: {conflict['reason']}")
                elif conflict['type'] == 'system_compatibility':
                    print(f"  {i}. {conflict['reason']}")
        
        # Ask for confirmation to proceed with actual restore
        print("\n===================================\n")
        proceed = input("Do you want to proceed with the actual restore? (yes/no): ").lower().strip()
        if proceed != 'yes':
            print("Restore operation cancelled.")
            return 0
        else:
            print("Proceeding with actual restore...")
            # Continue with the regular restore process...
    
    # Default behavior: just restore the state without execution
    execute_plan = args.execute if hasattr(args, 'execute') else False
    
    # Check if any specific command line arguments were provided for restore categories
    has_category_args = any([
        hasattr(args, 'packages_only') and args.packages_only,
        hasattr(args, 'configs_only') and args.configs_only,
        hasattr(args, 'no_repo_restore') and args.no_repo_restore,
        hasattr(args, 'no_fstab_restore') and args.no_fstab_restore,
        hasattr(args, 'path_transform_preview') and args.path_transform_preview,
        hasattr(args, 'preview_fstab') and args.preview_fstab,
        hasattr(args, 'preview_repos') and args.preview_repos
    ])
    
    # If execution is requested but no specific categories were specified via command line,
    # enter interactive mode to ask about each category
    if execute_plan and not has_category_args:
        print("\nInteractive Restore Mode:")
        print("-----------------------")
        print("You can choose which parts of the backup to restore.")
        
        # Load backup file to get info about what's available
        try:
            with open(args.backup_file, 'r') as f:
                backup_data = json.load(f)
            
            packages_available = len(backup_data.get('packages', [])) > 0
            configs_available = len(backup_data.get('config_files', [])) > 0
            repos_available = 'repositories' in backup_data and len(backup_data['repositories'].get('repositories', [])) > 0
            
            has_fstab = False
            for cfg in backup_data.get('config_files', []):
                if cfg.get('path') == '/etc/fstab.portable' and 'fstab_data' in cfg:
                    fstab_entries = cfg.get('fstab_data', {}).get('portable_entries', [])
                    has_fstab = len(fstab_entries) > 0
                    break
            
            # Check for high-risk restore items
            high_risk_items = {}
            
            # Check for GNOME extensions
            has_gnome_extensions = False
            for cfg in backup_data.get('config_files', []):
                path = cfg.get('path', '')
                if '/.local/share/gnome-shell/extensions/' in path or '/gnome-shell/extensions/' in path:
                    has_gnome_extensions = True
                    high_risk_items['gnome_extensions'] = True
                    break
            
            # Check for keyrings
            has_keyrings = False
            for cfg in backup_data.get('config_files', []):
                path = cfg.get('path', '')
                if '/.local/share/keyrings/' in path or '/keyrings/' in path:
                    has_keyrings = True
                    high_risk_items['keyrings'] = True
                    break
            
            # Check for SSH keys
            has_ssh_keys = False
            for cfg in backup_data.get('config_files', []):
                path = cfg.get('path', '')
                if '/.ssh/' in path:
                    has_ssh_keys = True
                    high_risk_items['ssh_keys'] = True
                    break
            
            # Check for GPG keys
            has_gpg_keys = False
            for cfg in backup_data.get('config_files', []):
                path = cfg.get('path', '')
                if '/.gnupg/' in path:
                    has_gpg_keys = True
                    high_risk_items['gpg_keys'] = True
                    break
                    
            # Now ask about each category
            restore_packages = False
            restore_configs = False
            restore_repos = True  # Default is True
            restore_fstab = True  # Default is True
            transform_paths = True  # Default is True
            
            # High-risk configurations
            restore_gnome_extensions = False
            restore_keyrings = False
            restore_ssh_keys = False
            restore_gpg_keys = False
            
            if packages_available:
                print(f"\nPackages: The backup contains {len(backup_data.get('packages', []))} packages.")
                restore_packages = input("Restore packages? (yes/no): ").lower().strip() == 'yes'
            else:
                print("\nPackages: No packages found in the backup.")
            
            if configs_available:
                print(f"\nConfiguration files: The backup contains {len(backup_data.get('config_files', []))} configuration files.")
                restore_configs = input("Restore configuration files? (yes/no): ").lower().strip() == 'yes'
                
                if restore_configs:
                    transform_paths = input("Transform paths for the current system? (yes/no): ").lower().strip() == 'yes'
                    
                    # Ask about high-risk configuration items
                    if high_risk_items:
                        print("\nHigh-risk configuration items:")
                        print("------------------------------")
                        print("The following items may have compatibility issues or might not work correctly after restore.")
                        
                        if high_risk_items.get('gnome_extensions'):
                            print("\nGNOME Shell extensions: These may not be compatible with your current GNOME version.")
                            restore_gnome_extensions = input("Restore GNOME extensions? (yes/no): ").lower().strip() == 'yes'
                        
                        if high_risk_items.get('keyrings'):
                            print("\nKeyrings: These are encrypted with your login password and may not be usable on a different system.")
                            print("Consider manually exporting sensitive passwords through your password manager application instead.")
                            restore_keyrings = input("Restore keyrings? (yes/no): ").lower().strip() == 'yes'
                        
                        if high_risk_items.get('ssh_keys'):
                            print("\nSSH keys: These will need correct permissions (0600) after restore.")
                            restore_ssh_keys = input("Restore SSH keys? (yes/no): ").lower().strip() == 'yes'
                        
                        if high_risk_items.get('gpg_keys'):
                            print("\nGPG keys: These may require additional setup after restore, including setting correct permissions.")
                            restore_gpg_keys = input("Restore GPG keys? (yes/no): ").lower().strip() == 'yes'
            else:
                print("\nConfiguration files: No configuration files found in the backup.")
            
            if repos_available:
                print(f"\nSoftware repositories: The backup contains {len(backup_data['repositories'].get('repositories', []))} software repositories.")
                restore_repos = input("Restore software repositories? (yes/no): ").lower().strip() == 'yes'
            else:
                print("\nSoftware repositories: No repositories found in the backup.")
                restore_repos = False
            
            if has_fstab:
                print("\nFstab entries: The backup contains portable fstab entries.")
                restore_fstab = input("Restore portable fstab entries? (yes/no): ").lower().strip() == 'yes'
            else:
                print("\nFstab entries: No portable fstab entries found in the backup.")
                restore_fstab = False
            
            # Set the values based on interactive input
            packages_only = restore_packages and not restore_configs
            configs_only = restore_configs and not restore_packages
            no_repo_restore = not restore_repos
            no_fstab_restore = not restore_fstab
            no_path_transform = not transform_paths
            
            # Create exclude paths list for high-risk items that user doesn't want to restore
            exclude_paths = []
            
            if not restore_gnome_extensions and high_risk_items.get('gnome_extensions'):
                exclude_paths.append('*/.local/share/gnome-shell/extensions/*')
            
            if not restore_keyrings and high_risk_items.get('keyrings'):
                exclude_paths.append('*/.local/share/keyrings/*')
            
            if not restore_ssh_keys and high_risk_items.get('ssh_keys'):
                exclude_paths.append('*/.ssh/*')
            
            if not restore_gpg_keys and high_risk_items.get('gpg_keys'):
                exclude_paths.append('*/.gnupg/*')
            
            # Set the exclude_paths argument if we have paths to exclude
            if exclude_paths and not hasattr(args, 'exclude_paths'):
                args.exclude_paths = exclude_paths
            elif exclude_paths and hasattr(args, 'exclude_paths'):
                args.exclude_paths.extend(exclude_paths)
            
        except Exception as e:
            logger.error(f"Error reading backup file: {e}")
            print(f"Error reading backup file: {e}")
            return 1
    else:
        # Use the command line arguments
        packages_only = args.packages_only if hasattr(args, 'packages_only') else False
        configs_only = args.configs_only if hasattr(args, 'configs_only') else False
        no_repo_restore = args.no_repo_restore if hasattr(args, 'no_repo_restore') else False
        no_fstab_restore = args.no_fstab_restore if hasattr(args, 'no_fstab_restore') else False
        no_path_transform = args.no_path_transform if hasattr(args, 'no_path_transform') else False
    
    # Get version policy options
    version_policy = args.version_policy if hasattr(args, 'version_policy') else 'prefer-newer'
    allow_downgrade = args.allow_downgrade if hasattr(args, 'allow_downgrade') else False
    
    # Print version policy
    print(f"Using version policy: {version_policy}")
    if allow_downgrade:
        print("Package downgrades allowed if needed")
    
    # Process path transformation options
    transform_paths = not no_path_transform
    preview_only = args.path_transform_preview if hasattr(args, 'path_transform_preview') else False
    
    if not transform_paths:
        print("Path transformation disabled - paths will be kept as-is")
    elif preview_only:
        print("Path transformation preview mode - no changes will be made")
    else:
        print("Path transformation enabled - system-specific paths will be adapted")
    
    # Process fstab options
    restore_fstab = not no_fstab_restore
    preview_fstab = args.preview_fstab if hasattr(args, 'preview_fstab') else False
    
    if not restore_fstab:
        print("Portable fstab entries restoration disabled")
    elif preview_fstab:
        print("Portable fstab entries preview mode - no changes will be made")
    else:
        print("Portable fstab entries will be appended if available")
    
    # Restore the state without executing installation
    success = app.restore_from_backup(args.backup_file, execute_plan=False)
    
    if not success:
        print("Failed to restore system state.")
        return 1
    
    print("System state restored successfully.")
    
    # Execute installation plan if requested
    if execute_plan and not configs_only:
        print("Installing packages from backup...")
        app.execute_installation_plan(
            args.backup_file,
            version_policy=version_policy,
            allow_downgrade=allow_downgrade
        )
    
    # Execute config restoration if requested
    if execute_plan and not packages_only:
        print("Restoring configuration files from backup...")
        app.execute_config_restoration(
            args.backup_file,
            transform_paths=transform_paths,
            preview_only=preview_only,
            restore_fstab=restore_fstab,
            preview_fstab=preview_fstab,
            exclude_paths=args.exclude_paths if hasattr(args, 'exclude_paths') else None
        )
    
    # Handle repository restoration if requested
    restore_repos = not no_repo_restore
    preview_repos = args.preview_repos if hasattr(args, 'preview_repos') else False
    force_incompatible = args.force_incompatible_repos if hasattr(args, 'force_incompatible_repos') else False
    
    if (execute_plan or preview_repos) and restore_repos:
        from migrator.utils.repositories import RepositoryManager
        repo_manager = RepositoryManager()
        
        # Load backup file
        try:
            with open(args.backup_file, 'r') as f:
                backup_data = json.load(f)
                
            # Check for repositories in backup
            repos_info = backup_data.get("repositories", {})
            repositories = repos_info.get("repositories", [])
            
            if repositories:
                if preview_repos:
                    print("\nPreview of repository restoration (no changes will be made):")
                    
                # Check repository compatibility
                compatibility_issues = repo_manager.check_compatibility(repos_info)
                
                if compatibility_issues and not preview_repos:
                    if force_incompatible:
                        print(f"\nWARNING: Found {len(compatibility_issues)} incompatible repositories")
                        print("Attempting to restore ALL repositories (--force-incompatible-repos was specified)")
                    else:
                        print(f"\nFound {len(compatibility_issues)} incompatible repositories")
                        print("These incompatible repositories will be skipped (use --force-incompatible-repos to override)")
                        for issue in compatibility_issues:
                            print(f"  - {issue['name']}: {issue['issue']}")
                
                # Restore repositories
                successes, issues = repo_manager.restore_repositories(
                    repos_info, 
                    dry_run=preview_repos,
                    force_incompatible=force_incompatible
                )
                
                # Print success messages
                if successes:
                    print(f"\nSuccessfully restored {len(successes)} repositories:")
                    for i, success in enumerate(successes[:5], 1):
                        print(f"  {i}. {success}")
                    if len(successes) > 5:
                        print(f"  ... and {len(successes) - 5} more repositories")
                
                # Print issues
                if issues:
                    print(f"\nEncountered {len(issues)} issues during repository restoration:")
                    for i, issue in enumerate(issues[:5], 1):
                        print(f"  {i}. {issue['message']}")
                    if len(issues) > 5:
                        print(f"  ... and {len(issues) - 5} more issues")
        except Exception as e:
            logger.error(f"Error restoring repositories: {e}")
            print(f"Error restoring repositories: {e}")
    
    print("\nRestore operation completed.")
    return 0

def handle_compare(app: Migrator, args: argparse.Namespace) -> int:
    """Handle compare command"""
    print(f"Comparing current system with backup {args.backup_file}...")
    
    added_pkgs, removed_pkgs, added_configs, removed_configs = app.compare_with_backup(args.backup_file)
    
    # Format results
    results = {
        "added_packages": added_pkgs,
        "removed_packages": removed_pkgs,
        "added_config_files": added_configs,
        "removed_config_files": removed_configs
    }
    
    # Print summary
    print(f"Added packages: {len(added_pkgs)}")
    print(f"Removed packages: {len(removed_pkgs)}")
    print(f"Added config files: {len(added_configs)}")
    print(f"Removed config files: {len(removed_configs)}")
    
    # Save to file if specified
    if args.output:
        try:
            with open(args.output, 'w') as f:
                json.dump(results, f, indent=2)
            print(f"Comparison results saved to {args.output}")
        except IOError as e:
            print(f"Error saving comparison results: {e}")
            return 1
    
    return 0

def handle_plan(app: Migrator, args: argparse.Namespace) -> int:
    """Handle plan command"""
    print(f"Generating installation plan from backup {args.backup_file}...")
    
    # Generate package installation plan
    pkg_plan = app.generate_installation_plan(args.backup_file)
    
    # Generate config restoration plan
    cfg_plan = app.generate_config_restoration_plan(args.backup_file)
    
    # Combine plans
    plan = {
        "packages": pkg_plan,
        "configs": cfg_plan
    }
    
    # Group packages by source for better display
    available_by_source = {}
    unavailable_by_source = {}
    
    # Process available packages
    for pkg in pkg_plan['available']:
        # Handle cases where the package could be a string or a dictionary
        if isinstance(pkg, dict):
            source = pkg.get('source', 'unknown')
        elif isinstance(pkg, str):
            # If it's a string, assume it's a package name and use unknown source
            logger.warning(f"Received package as string instead of dict: {pkg}")
            source = 'unknown'
        else:
            # If it's some other type, log it and use unknown
            logger.warning(f"Unexpected package type: {type(pkg)}, value: {pkg}")
            source = 'unknown'
            
        if source not in available_by_source:
            available_by_source[source] = []
        available_by_source[source].append(pkg)
    
    # Process unavailable packages
    for pkg in pkg_plan['unavailable']:
        # Handle cases where the package could be a string or a dictionary
        if isinstance(pkg, dict):
            source = pkg.get('source', 'unknown')
        elif isinstance(pkg, str):
            # If it's a string, assume it's a package name and use unknown source
            logger.warning(f"Received package as string instead of dict: {pkg}")
            source = 'unknown'
        else:
            # If it's some other type, log it and use unknown
            logger.warning(f"Unexpected package type: {type(pkg)}, value: {pkg}")
            source = 'unknown'
            
        if source not in unavailable_by_source:
            unavailable_by_source[source] = []
        unavailable_by_source[source].append(pkg)
    
    # Print summary
    print("\nPackage Installation Plan:")
    print(f"  Total Available packages: {len(pkg_plan['available'])}")
    
    # Print available packages by source
    if available_by_source:
        print("  Available packages by source:")
        for source, pkgs in sorted(available_by_source.items()):
            print(f"    • {source}: {len(pkgs)} packages")
    
    # Print unavailable packages by source
    print(f"\n  Total Unavailable packages: {len(pkg_plan['unavailable'])}")
    if unavailable_by_source:
        print("  Unavailable packages by source:")
        for source, pkgs in sorted(unavailable_by_source.items()):
            print(f"    • {source}: {len(pkgs)} packages")
    
    print(f"\n  Upgradable packages: {len(pkg_plan['upgradable'])}")
    print(f"  Installation commands: {len(pkg_plan['installation_commands'])}")
    
    # Extract commands grouped by package source
    command_groups = {}
    current_group = "unknown"
    
    for cmd in pkg_plan['installation_commands']:
        # Skip comments
        if isinstance(cmd, str) and cmd.startswith('#'):
            # Check if this is a source marker
            if "Found " in cmd and " Flatpak remotes" in cmd:
                current_group = "flatpak"
            elif any(marker in cmd for marker in ["apt", "snap", "flatpak", "dnf", "yum", "pacman"]):
                # Extract the package manager from the comment
                for pm in ["apt", "snap", "flatpak", "dnf", "yum", "pacman"]:
                    if pm in cmd.lower():
                        current_group = pm
                        break
            
            # Start a new group if this is a header comment
            if current_group not in command_groups:
                command_groups[current_group] = []
            command_groups[current_group].append(cmd)
        else:
            # Add to current group
            if current_group not in command_groups:
                command_groups[current_group] = []
            command_groups[current_group].append(cmd)
    
    # Print command count by group
    if command_groups:
        print("\n  Installation commands by source:")
        for source, cmds in sorted(command_groups.items()):
            if source != "unknown":
                # Count actual commands (not comments)
                actual_commands = [c for c in cmds if not isinstance(c, str) or not c.startswith('#')]
                print(f"    • {source}: {len(actual_commands)} commands")
    
    print("\nConfiguration Restoration Plan:")
    print(f"  Restorable configs: {len(cfg_plan['restorable'])}")
    print(f"  Problematic configs: {len(cfg_plan['problematic'])}")
    print(f"  Restoration commands: {len(cfg_plan['commands'])}")
    
    # Save to file if specified
    if args.output:
        try:
            with open(args.output, 'w') as f:
                json.dump(plan, f, indent=2)
            print(f"\nInstallation plan saved to {args.output}")
        except IOError as e:
            print(f"Error saving installation plan: {e}")
            return 1
    
    return 0

def handle_check(app: Migrator, args: argparse.Namespace) -> int:
    """Handle check command"""
    print("Checking for system changes since last scan...")
    
    # Process desktop environment options
    include_desktop = args.include_desktop if hasattr(args, 'include_desktop') else False
    
    changed_packages, changed_configs = app.execute_routine_check()
    
    # Print summary
    print(f"Changed packages: {len(changed_packages)}")
    print(f"Changed config files: {len(changed_configs)}")
    
    if changed_packages:
        print("\nPackage Changes:")
        for pkg in changed_packages[:5]:  # Show first 5 only
            print(f"  {pkg['name']} {pkg['version']} [{pkg['source']}]")
        if len(changed_packages) > 5:
            print(f"  ... and {len(changed_packages) - 5} more")
    
    if changed_configs:
        print("\nConfig Changes:")
        for cfg in changed_configs[:5]:  # Show first 5 only
            status = cfg.get('status', 'changed')
            print(f"  {cfg['path']} - {status}")
        if len(changed_configs) > 5:
            print(f"  ... and {len(changed_configs) - 5} more")
    
    return 0

def handle_service(app: Migrator, args: argparse.Namespace) -> int:
    """Handle service command (periodic checking)"""
    interval = args.interval
    include_desktop = args.include_desktop if hasattr(args, 'include_desktop') else False
    
    print(f"Running as a service, checking every {interval} seconds...")
    if include_desktop:
        print("Including desktop environment configurations in checks")
    
    try:
        while True:
            print(f"\n[{datetime.datetime.now().isoformat()}] Performing routine check...")
            changed_packages, changed_configs = app.execute_routine_check()
            
            # Print summary if changes detected
            if changed_packages or changed_configs:
                print(f"Changes detected: {len(changed_packages)} packages, {len(changed_configs)} configs")
            else:
                print("No changes detected.")
            
            print(f"Next check in {interval} seconds...")
            time.sleep(interval)
    
    except KeyboardInterrupt:
        print("\nService stopped by user.")
        return 0
    
    return 0

def handle_install_service(app: Migrator, args: argparse.Namespace) -> int:
    """Handle install-service command"""
    print("Installing Migrator as a systemd service...")

    # Process schedule options to translate them into systemd timer syntax
    schedule = None
    
    if hasattr(args, 'daily') and args.daily:
        # Format: "daily@HH:MM:00"
        time = args.daily.strip()
        if ":" not in time:
            print("Error: Invalid time format for daily schedule. Use HH:MM format.")
            return 1
        schedule = f"*-*-* {time}:00"
    
    elif hasattr(args, 'weekly') and args.weekly:
        # Format: "DAY,HH:MM" -> "DAY *-*-* HH:MM:00"
        try:
            day, time = args.weekly.split(',')
            day = day.strip().capitalize()
            time = time.strip()
            
            # Validate day
            valid_days = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun']
            if day not in valid_days:
                print(f"Error: Invalid day '{day}'. Use one of: {', '.join(valid_days)}")
                return 1
                
            schedule = f"{day} *-*-* {time}:00"
        except ValueError:
            print("Error: Invalid format for weekly schedule. Use DAY,HH:MM format.")
            return 1
    
    elif hasattr(args, 'monthly') and args.monthly:
        # Format: "DAY,HH:MM" -> "*-*-DAY HH:MM:00"
        try:
            day, time = args.monthly.split(',')
            day = day.strip()
            time = time.strip()
            
            # Validate day
            try:
                day_num = int(day)
                if day_num < 1 or day_num > 31:
                    print(f"Error: Invalid day of month '{day}'. Use a value between 1 and 28 to ensure it works in all months.")
                    return 1
            except ValueError:
                print(f"Error: Invalid day of month '{day}'. Use a number between 1 and 28.")
                return 1
                
            schedule = f"*-*-{day} {time}:00"
        except ValueError:
            print("Error: Invalid format for monthly schedule. Use DAY,HH:MM format.")
            return 1
    
    elif hasattr(args, 'schedule') and args.schedule:
        # Direct systemd timer specification
        schedule = args.schedule
    
    # Call the service creation function
    success, message = create_systemd_service(
        check_interval=args.interval if not schedule else None,
        user_unit=args.user,
        schedule=schedule
    )
    
    if success:
        print(message)
        return 0
    else:
        print(f"Error: {message}")
        return 1

def handle_remove_service(app: Migrator, args: argparse.Namespace) -> int:
    """Handle remove-service command"""
    print("Removing Migrator systemd service...")
    
    success, message = remove_systemd_service(
        user_unit=args.user
    )
    
    if success:
        print(message)
        return 0
    else:
        print(f"Error: {message}")
        return 1

def handle_config(app: Migrator, args: argparse.Namespace) -> int:
    """Handle config command"""
    if not hasattr(args, 'config_command') or not args.config_command:
        print("Error: No configuration subcommand specified")
        return 1
        
    if args.config_command == 'get-backup-dir':
        backup_dir = app.get_backup_dir()
        print(f"Current backup directory: {backup_dir}")
        return 0
        
    elif args.config_command == 'set-backup-dir':
        if not hasattr(args, 'path') or not args.path:
            print("Error: No backup directory specified")
            return 1
            
        backup_dir = os.path.expanduser(args.path)
        success = app.set_backup_dir(backup_dir)
        
        if success:
            print(f"Backup directory set to: {backup_dir}")
            return 0
        else:
            print(f"Failed to set backup directory to: {backup_dir}")
            return 1
            
    elif args.config_command == 'list-hosts':
        hosts = app.list_backup_hosts()
        
        if not hosts:
            print("No backup hosts found.")
            return 0
            
        print(f"Found {len(hosts)} hosts with backups:")
        for i, host in enumerate(hosts, 1):
            print(f"{i}. {host}")
            
        return 0
        
    elif args.config_command == 'get-host-backups':
        if not hasattr(args, 'hostname') or not args.hostname:
            print("Error: No hostname specified")
            return 1
            
        hostname = args.hostname
        backups = app.get_host_specific_backups(hostname)
        
        if not backups:
            print(f"No backups found for host: {hostname}")
            return 0
            
        print(f"Found {len(backups)} backup{'s' if len(backups) > 1 else ''} for host {hostname}:")
        
        # Sort by modification time (newest first)
        backups.sort(key=lambda f: os.path.getmtime(f), reverse=True)
        
        show_detail = args.show_detail if hasattr(args, 'show_detail') else False
        
        for i, backup_file in enumerate(backups, 1):
            # Get basic file info
            mod_time = datetime.datetime.fromtimestamp(os.path.getmtime(backup_file))
            size = os.path.getsize(backup_file)
            size_str = f"{size/1024/1024:.1f}MB" if size > 1024*1024 else f"{size/1024:.1f}KB"
            
            if show_detail:
                # Get detailed metadata
                metadata = app.get_backup_metadata(backup_file)
                
                distro = f"{metadata.get('distro_name', 'Unknown')} {metadata.get('distro_version', '')}"
                packages = metadata.get('package_count', 0)
                configs = metadata.get('config_count', 0)
                
                print(f"{i}. {os.path.basename(backup_file)}")
                print(f"   Created: {mod_time.strftime('%Y-%m-%d %H:%M:%S')}")
                print(f"   Size: {size_str}")
                print(f"   System: {distro.strip()}")
                print(f"   Contents: {packages} packages, {configs} config files")
                print("")
            else:
                # Simple listing
                print(f"{i}. {os.path.basename(backup_file)} - {mod_time.strftime('%Y-%m-%d %H:%M:%S')} ({size_str})")
        
        return 0
            
    elif args.config_command == 'backup-retention':
        if not hasattr(args, 'retention_command') or not args.retention_command:
            print("Error: No retention command specified")
            return 1
        
        if args.retention_command == 'get':
            retention_settings = app.get_backup_retention_settings()
            print("Current backup retention settings:")
            for mode, details in retention_settings.items():
                print(f"{mode}: {details}")
            return 0
        
        elif args.retention_command == 'enable':
            app.enable_backup_retention()
            print("Backup retention enabled.")
            return 0
        
        elif args.retention_command == 'disable':
            app.disable_backup_retention()
            print("Backup retention disabled.")
            return 0
        
        elif args.retention_command == 'set-mode':
            if not hasattr(args, 'mode') or not args.mode:
                print("Error: No retention mode specified")
                return 1
            
            mode = args.mode
            if mode not in ['count', 'age']:
                print("Error: Invalid retention mode specified. Use 'count' or 'age'.")
                return 1
            
            if mode == 'count':
                if not hasattr(args, 'count') or not args.count:
                    print("Error: No count specified for count mode")
                    return 1
                
                app.set_backup_retention_count(args.count)
                print(f"Backup retention set to keep only the most recent {args.count} backups.")
            else:
                if not hasattr(args, 'days') or not args.days:
                    print("Error: No days specified for age mode")
                    return 1
                
                app.set_backup_retention_age(args.days)
                print(f"Backup retention set to keep backups newer than {args.days} days.")
            
            return 0
        
        elif args.retention_command == 'set-count':
            if not hasattr(args, 'count') or not args.count:
                print("Error: No count specified for set-count command")
                return 1
            
            app.set_backup_retention_count(args.count)
            print(f"Backup retention set to keep only the most recent {args.count} backups.")
            return 0
        
        elif args.retention_command == 'set-age':
            if not hasattr(args, 'days') or not args.days:
                print("Error: No days specified for set-age command")
                return 1
            
            app.set_backup_retention_age(args.days)
            print(f"Backup retention set to keep backups newer than {args.days} days.")
            return 0
        
        else:
            print(f"Unknown retention command: {args.retention_command}")
            return 1
    
    else:
        print(f"Unknown configuration subcommand: {args.config_command}")
        return 1

def handle_locate_backup(app: Migrator, args: argparse.Namespace) -> int:
    """Handle locate-backup command"""
    print("Scanning for Migrator backups in common locations...")
    
    search_network = args.include_network if hasattr(args, 'include_network') else False
    
    if search_network:
        print("Including network shares in search (this may take a while)...")
    
    backup_files = app.scan_for_backups(search_removable=True, search_network=search_network)
    
    if not backup_files:
        print("No backup files found.")
        print("\nTips for locating your backup:")
        print("1. Make sure your external drive is properly mounted")
        print("2. If your backup is in a custom location, you can specify the full path:")
        print("   migrator restore /path/to/your/backup.json")
        print("3. You can also set a custom backup directory:")
        print("   migrator config set-backup-dir /path/to/backup/dir")
        return 1
    
    print(f"\nFound {len(backup_files)} Migrator backup file{'s' if len(backup_files) > 1 else ''}:")
    print("-" * 80)
    
    for i, backup_path in enumerate(backup_files, 1):
        try:
            # Get backup metadata
            metadata = app.get_backup_metadata(backup_path)
            
            # Format size
            file_size = metadata.get("file_size", 0) / (1024 * 1024)  # Convert to MB
            
            # Format and display timestamp
            date_str = "unknown date"
            if "timestamp" in metadata:
                timestamp = metadata["timestamp"]
                # Check if timestamp contains date and time parts
                if len(timestamp) >= 15:  # Old format with full YYYYMMDD_HHMMSS
                    date_str = f"{timestamp[:4]}-{timestamp[4:6]}-{timestamp[6:8]} {timestamp[9:11]}:{timestamp[11:13]}"
                else:  # New format with separate date part
                    # Try to find the time part in the filename
                    filename = metadata.get("filename", "")
                    parts = filename.replace(".json", "").split("_backup_")[1].split("_")
                    if len(parts) >= 2:
                        date_str = f"{timestamp[:4]}-{timestamp[4:6]}-{timestamp[6:8]} {parts[1][:2]}:{parts[1][2:4]}"
                    else:
                        date_str = f"{timestamp[:4]}-{timestamp[4:6]}-{timestamp[6:8]}"
            
            # Display info
            print(f"{i}. {os.path.basename(backup_path)}")
            print(f"   Path: {backup_path}")
            print(f"   Created: {date_str}")
            
            # Show source system info if available
            hostname = metadata.get("hostname", "unknown")
            distro_name = metadata.get("distro_name", "")
            distro_version = metadata.get("distro_version", "")
            if distro_name or hostname != "unknown":
                print(f"   Source: {hostname}, {distro_name} {distro_version}")
            
            print(f"   Size: {file_size:.2f} MB")
            print("-" * 80)
            
        except Exception as e:
            # Fallback to basic display if metadata can't be retrieved
            print(f"{i}. {os.path.basename(backup_path)}")
            print(f"   Path: {backup_path}")
            print("-" * 80)
    
    # Save to file if specified
    if hasattr(args, 'output') and args.output:
        try:
            with open(args.output, 'w') as f:
                for path in backup_files:
                    f.write(f"{path}\n")
            print(f"\nBackup paths saved to {args.output}")
        except Exception as e:
            print(f"\nError saving backup paths to file: {e}")
    
    print("\nTo restore from a backup, use:")
    print(f"migrator restore PATH_TO_BACKUP")
    
    # Ask if they want to restore from one of the found backups
    choice = input("\nWould you like to restore from one of these backups? (y/n): ")
    if choice.lower() == 'y':
        while True:
            backup_num = input(f"Enter backup number (1-{len(backup_files)}): ")
            try:
                idx = int(backup_num) - 1
                if 0 <= idx < len(backup_files):
                    selected_backup = backup_files[idx]
                    print(f"\nRestoring from: {selected_backup}")
                    
                    # First do a dry run
                    restore_args = argparse.Namespace()
                    restore_args.backup_file = selected_backup
                    restore_args.dry_run = True
                    handle_restore(app, restore_args)
                    
                    # Ask for confirmation to execute the restore
                    execute = input("\nDo you want to execute this restore? (yes/no): ").lower().strip()
                    if execute == 'yes':
                        exec_args = argparse.Namespace()
                        exec_args.backup_file = selected_backup
                        exec_args.execute = True
                        exec_args.dry_run = False
                        return handle_restore(app, exec_args)
                    else:
                        print("Restore cancelled.")
                        return 0
                else:
                    print(f"Please enter a number between 1 and {len(backup_files)}")
            except ValueError:
                print("Please enter a valid number")
    
    return 0

def handle_setup(app: Migrator, args: argparse.Namespace) -> int:
    """Handle setup command"""
    print("Starting interactive setup wizard...")
    
    # Run the setup wizard
    config = run_setup_wizard()
    
    if config:
        # If wizard completed successfully
        print("Setup complete. You can now use Migrator with the configured settings.")
        
        # Check if a first scan is needed
        if app.is_first_run():
            print("\nWould you like to perform an initial system scan now?")
            choice = input("This will scan your system for packages and configuration files (y/n): ")
            
            if choice.lower() in ['y', 'yes']:
                # Use the settings from the wizard
                print("\nScanning system for packages and configuration files...")
                app.update_system_state(
                    include_desktop=config.get("include_desktop_configs", True),
                    include_fstab_portability=config.get("include_fstab_portability", True),
                    include_repos=config.get("include_repos", True),
                    include_paths=config.get("include_paths"),
                    exclude_paths=config.get("exclude_paths")
                )
                print("System state updated successfully.")
        return 0
    else:
        # If wizard was cancelled
        print("Setup was cancelled. You can run 'migrator setup' anytime to configure Migrator.")
        return 1

def handle_list_backups(app: Migrator, args: argparse.Namespace) -> int:
    """Handle list-backups command"""
    # Determine which backup directory to use
    if hasattr(args, 'backup_dir') and args.backup_dir:
        backup_dir = os.path.expanduser(args.backup_dir)
    else:
        backup_dir = app.get_backup_dir()
    
    print(f"Listing backups in: {backup_dir}")
    
    if not os.path.exists(backup_dir):
        print(f"Error: Backup directory {backup_dir} does not exist")
        return 1
    
    # Check if we should filter by host
    selected_host = args.host if hasattr(args, 'host') and args.host else None
    
    # Check if we should organize by host
    by_host = args.by_host if hasattr(args, 'by_host') else False
    
    # If filtering by host, use the host-specific function
    if selected_host:
        backups = app.get_host_specific_backups(selected_host)
        if not backups:
            print(f"No backups found for host: {selected_host}")
            return 0
        
        print(f"\nFound {len(backups)} backup{'s' if len(backups) > 1 else ''} for host {selected_host}:")
        print("-" * 80)
        
        # Sort by modification time (newest first)
        backups.sort(key=lambda f: os.path.getmtime(f), reverse=True)
        
        # Show details for each backup
        show_detail = args.show_detail if hasattr(args, 'show_detail') else False
        _display_backups(app, backups, show_detail)
        
        return 0
    
    # If organizing by host
    elif by_host:
        hosts = app.list_backup_hosts()
        
        if not hosts:
            print("No backup hosts found.")
            return 0
        
        print(f"\nFound {len(hosts)} hosts with backups:")
        print("-" * 80)
        
        for host in hosts:
            backups = app.get_host_specific_backups(host)
            
            # Sort by modification time (newest first)
            backups.sort(key=lambda f: os.path.getmtime(f), reverse=True)
            
            print(f"\nHost: {host} ({len(backups)} backups)")
            print("-" * 40)
            
            # Show details for each backup
            show_detail = args.show_detail if hasattr(args, 'show_detail') else False
            _display_backups(app, backups, show_detail)
        
        return 0
    
    # Find all backup files using the scan_for_backups method (which recursively looks for backups)
    backup_files = app.scan_for_backups(search_removable=False, search_network=False)
    
    if not backup_files:
        print("No backup files found.")
        return 0
    
    # Sort by modification time (newest first)
    backup_files.sort(key=lambda f: os.path.getmtime(f), reverse=True)
    
    print(f"\nFound {len(backup_files)} backup{'s' if len(backup_files) > 1 else ''}:")
    print("-" * 80)
    
    # Show details for each backup
    show_detail = args.show_detail if hasattr(args, 'show_detail') else False
    _display_backups(app, backup_files, show_detail)
    
    return 0

def _display_backups(app: Migrator, backup_files: List[str], show_detail: bool = False) -> None:
    """Helper function to display backup files
    
    Args:
        app: Migrator instance
        backup_files: List of backup files to display
        show_detail: Whether to show detailed metadata
    """
    for i, backup_file in enumerate(backup_files, 1):
        # Get basic file info
        mod_time = datetime.datetime.fromtimestamp(os.path.getmtime(backup_file))
        size = os.path.getsize(backup_file)
        size_str = f"{size/1024/1024:.1f}MB" if size > 1024*1024 else f"{size/1024:.1f}KB"
        
        # Get file path info
        filename = os.path.basename(backup_file)
        dir_name = os.path.basename(os.path.dirname(backup_file))
        parent_dir = os.path.basename(os.path.dirname(os.path.dirname(backup_file)))
        
        # Determine if this is in a host-specific directory
        is_in_host_dir = False
        host_name = None
        if dir_name != parent_dir and dir_name != "backups" and dir_name != "migrator_backups":
            is_in_host_dir = True
            host_name = dir_name
        
        if show_detail:
            # Get detailed metadata
            metadata = app.get_backup_metadata(backup_file)
            
            # Extract relevant information
            distro = f"{metadata.get('distro_name', 'Unknown')} {metadata.get('distro_version', '')}"
            hostname = metadata.get('hostname', host_name or 'Unknown')
            packages = metadata.get('package_count', 0)
            configs = metadata.get('config_count', 0)
            
            print(f"{i}. {filename}")
            print(f"   Created: {mod_time.strftime('%Y-%m-%d %H:%M:%S')}")
            print(f"   Size: {size_str}")
            print(f"   Host: {hostname}")
            if is_in_host_dir:
                print(f"   Directory: {dir_name}/")
            print(f"   System: {distro.strip()}")
            print(f"   Contents: {packages} packages, {configs} config files")
            print("")
        else:
            # Simple listing with host information when available
            host_info = f"[{host_name}] " if is_in_host_dir else ""
            print(f"{i}. {host_info}{filename} - {mod_time.strftime('%Y-%m-%d %H:%M:%S')} ({size_str})")

def handle_edit_mappings(args: argparse.Namespace) -> int:
    """Handle edit mappings command"""
    mappings_file = os.path.expanduser("~/.config/migrator/package_mappings.json")
    
    # Ensure the file exists
    if not os.path.exists(mappings_file):
        print("Package mappings file doesn't exist. Creating it now...")
        setup_package_mappings()
    
    # Open the file in the default editor
    try:
        editor = os.environ.get('EDITOR', 'nano')
        subprocess.call([editor, mappings_file])
        print(f"Package mappings file edited successfully at {mappings_file}")
        return 0
    except Exception as e:
        print(f"Error opening editor: {e}")
        return 1

def main() -> int:
    """Main entry point for the application"""
    parser = setup_argparse()
    args = parser.parse_args()
    
    # Set up data directory
    os.makedirs(os.path.expanduser("~/.local/share/migrator"), exist_ok=True)
    
    # Create Migrator instance
    app = Migrator()
    
    # If first run and no command specified, suggest the setup command
    if app.is_first_run() and args.command is None:
        print("It looks like this is your first time running Migrator.")
        print("Would you like to run the setup wizard to configure Migrator?")
        choice = input("(y/n): ")
        
        if choice.lower() in ['y', 'yes']:
            # Run the setup wizard
            return handle_setup(app, args)
        else:
            print("You can run 'migrator setup' anytime to configure Migrator.")
    
    # Handle command
    if args.command == 'scan':
        return handle_scan(app, args)
    elif args.command == 'backup':
        return handle_backup(app, args)
    elif args.command == 'restore':
        return handle_restore(app, args)
    elif args.command == 'compare':
        return handle_compare(app, args)
    elif args.command == 'plan':
        return handle_plan(app, args)
    elif args.command == 'check':
        return handle_check(app, args)
    elif args.command == 'service':
        return handle_service(app, args)
    elif args.command == 'install-service':
        return handle_install_service(app, args)
    elif args.command == 'remove-service':
        return handle_remove_service(app, args)
    elif args.command == 'config':
        return handle_config(app, args)
    elif args.command == 'locate-backup':
        return handle_locate_backup(app, args)
    elif args.command == 'setup':
        return handle_setup(app, args)
    elif args.command == 'list-backups':
        return handle_list_backups(app, args)
    elif args.command == 'edit-mappings':
        return handle_edit_mappings(args)
    else:
        # Show help if no command specified
        parser.print_help()
        return 0

if __name__ == "__main__":
    sys.exit(main()) 