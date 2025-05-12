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
import argparse
import json
import logging
import time
import textwrap
from datetime import datetime
from typing import List, Dict, Any

from .main import Migrator
from .utils.service import create_systemd_service, remove_systemd_service
from .utils.setup_wizard import run_setup_wizard

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
    scan_parser = subparsers.add_parser('scan', help='Scan system and update state')
    scan_parser.add_argument('--include-desktop', action='store_true', 
                           help='Include desktop environment configs')
    scan_parser.add_argument('--desktop-environments', 
                           help='Comma-separated list of desktop environments to include (e.g., gnome,kde,i3)')
    scan_parser.add_argument('--exclude-desktop', 
                           help='Comma-separated list of desktop environments to exclude')
    scan_parser.add_argument('--test-mode', action='store_true',
                           help='Run in test mode with limited package scanning (for development/debugging)')
    scan_parser.add_argument('--skip-setup-check', action='store_true',
                           help='Skip the first-run setup wizard check')
    
    # Backup command
    backup_parser = subparsers.add_parser('backup', help='Backup system state')
    backup_parser.add_argument('backup_dir', nargs='?', default=None, help='Directory to store backup (defaults to configured backup directory)')
    backup_parser.add_argument('--include-desktop', action='store_true', 
                             help='Include desktop environment configs')
    backup_parser.add_argument('--desktop-environments', 
                             help='Comma-separated list of desktop environments to include (e.g., gnome,kde,i3)')
    backup_parser.add_argument('--exclude-desktop', 
                             help='Comma-separated list of desktop environments to exclude')
    backup_parser.add_argument('--no-path-variables', action='store_true',
                             help='Disable dynamic path variable substitution for improved portability')
    backup_parser.add_argument('--no-fstab-portability', action='store_true',
                             help='Disable selective backup of portable fstab entries')
    backup_parser.add_argument('--skip-setup-check', action='store_true',
                             help='Skip the first-run setup wizard check')
    
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
    
    # Compare command
    compare_parser = subparsers.add_parser('compare', help='Compare current system with backup')
    compare_parser.add_argument('backup_file', help='Backup file to compare with')
    compare_parser.add_argument('--output', '-o', help='Output file for comparison results')
    
    # Plan command
    plan_parser = subparsers.add_parser('plan', help='Generate installation plan from backup')
    plan_parser.add_argument('backup_file', help='Backup file to use for planning')
    plan_parser.add_argument('--output', '-o', help='Output file for installation plan')
    
    # Check command
    check_parser = subparsers.add_parser('check', help='Check for system changes since last scan')
    check_parser.add_argument('--include-desktop', action='store_true', 
                            help='Include desktop environment configs in check')
    
    # Service command (for background scanning)
    service_parser = subparsers.add_parser('service', help='Run as a service for periodic checking')
    service_parser.add_argument('--interval', '-i', type=int, default=86400,
                                help='Interval between checks in seconds (default: 86400 - once per day)')
    service_parser.add_argument('--include-desktop', action='store_true', 
                              help='Include desktop environment configs in service checks')
    
    # Install service command
    install_service_parser = subparsers.add_parser('install-service', 
                                                 help='Install Migrator as a systemd service')
    
    # Create a scheduling option group so users choose EITHER interval OR schedule
    schedule_group = install_service_parser.add_mutually_exclusive_group()
    
    schedule_group.add_argument('--interval', '-i', type=int, default=86400,
                              help='Interval between checks in seconds (default: 86400 - once per day)')
    
    schedule_group.add_argument('--schedule', '-s', 
                              help='Systemd timer schedule (e.g., "daily", "weekly", "Mon *-*-* 14:30:00"). '
                                   'For time of day, use "hourly", "daily@3:00", "Sun 14:30", etc.')
    
    schedule_group.add_argument('--daily', type=str, metavar='HH:MM',
                              help='Run daily at specified time (24-hour format, e.g. "14:30")')
    
    schedule_group.add_argument('--weekly', type=str, metavar='DAY,HH:MM',
                              help='Run weekly on specified day and time (e.g., "Mon,09:00")')
    
    schedule_group.add_argument('--monthly', type=str, metavar='DAY,HH:MM',
                              help='Run monthly on specified day and time (e.g., "1,00:30" for 1st day of month)')
    
    install_service_parser.add_argument('--user', action='store_true',
                                      help='Install as a user service instead of system-wide')
    
    # Remove service command
    remove_service_parser = subparsers.add_parser('remove-service', 
                                                help='Remove Migrator systemd service')
    remove_service_parser.add_argument('--user', action='store_true',
                                     help='Remove user service instead of system-wide')
    
    # Config command
    config_parser = subparsers.add_parser('config', help='Configure Migrator settings')
    config_subparsers = config_parser.add_subparsers(dest='subcommand', help='Configuration command')
    
    # Get backup directory command
    get_backup_dir_parser = config_subparsers.add_parser('get-backup-dir', 
                                                      help='Get the current backup directory')
    
    # Set backup directory command
    set_backup_dir_parser = config_subparsers.add_parser('set-backup-dir', 
                                                       help='Set the default backup directory')
    set_backup_dir_parser.add_argument('backup_dir', help='Path to backup directory')
    
    # Backup retention commands
    retention_group = config_subparsers.add_parser('backup-retention', 
                                                help='Configure backup retention rules')
    retention_subparsers = retention_group.add_subparsers(dest='retention_command', help='Retention command')
    
    # Get backup retention settings
    get_retention_parser = retention_subparsers.add_parser('get', 
                                                        help='Show current backup retention settings')
    
    # Enable backup retention
    enable_retention_parser = retention_subparsers.add_parser('enable', 
                                                          help='Enable backup retention')
    
    # Disable backup retention
    disable_retention_parser = retention_subparsers.add_parser('disable', 
                                                           help='Disable backup retention')
    
    # Set retention mode to count
    set_count_retention_parser = retention_subparsers.add_parser('set-count', 
                                                              help='Keep only the most recent N backups')
    set_count_retention_parser.add_argument('count', type=int, help='Number of backups to keep')
    
    # Set retention mode to age
    set_age_retention_parser = retention_subparsers.add_parser('set-age', 
                                                            help='Keep backups newer than X days')
    set_age_retention_parser.add_argument('days', type=int, help='Number of days to keep backups')
    
    # List hosts command
    list_hosts_parser = config_subparsers.add_parser('list-hosts',
                                                  help='List all hosts that have backups')
    
    # Get host backups command
    get_host_backups_parser = config_subparsers.add_parser('get-host-backups',
                                                        help='List backups for a specific host')
    get_host_backups_parser.add_argument('hostname', help='Hostname to get backups for')
    get_host_backups_parser.add_argument('--show-detail', '-d', action='store_true',
                                      help='Show detailed metadata for each backup')
    
    # List backups command
    list_backups_parser = subparsers.add_parser('list-backups', 
                                              help='List available backups with metadata')
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
    
    # Process desktop environment options
    include_desktop = args.include_desktop if hasattr(args, 'include_desktop') else False
    desktop_envs = None
    exclude_desktop = None
    test_mode = args.test_mode if hasattr(args, 'test_mode') else False
    
    if hasattr(args, 'desktop_environments') and args.desktop_environments:
        desktop_envs = args.desktop_environments.split(',')
        
    if hasattr(args, 'exclude_desktop') and args.exclude_desktop:
        exclude_desktop = args.exclude_desktop.split(',')
    
    print("Scanning system for packages and configuration files...")
    
    if include_desktop:
        print("Including desktop environment configurations")
        if desktop_envs:
            print(f"Specific environments: {', '.join(desktop_envs)}")
        if exclude_desktop:
            print(f"Excluding environments: {', '.join(exclude_desktop)}")
    
    if test_mode:
        print("WARNING: Using TEST MODE - only scanning a limited number of packages")
    
    app.update_system_state(
        include_desktop=include_desktop,
        desktop_environments=desktop_envs,
        exclude_desktop=exclude_desktop,
        test_mode=test_mode
    )
    
    print("System state updated successfully.")
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
    include_desktop = args.include_desktop if hasattr(args, 'include_desktop') else False
    desktop_envs = None
    exclude_desktop = None
    
    if hasattr(args, 'desktop_environments') and args.desktop_environments:
        desktop_envs = args.desktop_environments.split(',')
        
    if hasattr(args, 'exclude_desktop') and args.exclude_desktop:
        exclude_desktop = args.exclude_desktop.split(',')
    
    # Handle path variables option
    use_path_variables = not args.no_path_variables if hasattr(args, 'no_path_variables') else True
    if not use_path_variables:
        print("Dynamic path variable substitution disabled")
    
    # Handle fstab portability option
    include_fstab_portability = not args.no_fstab_portability if hasattr(args, 'no_fstab_portability') else True
    if not include_fstab_portability:
        print("Portable fstab entries backup disabled")
    
    # Ensure state is up to date
    app.update_system_state(
        include_desktop=include_desktop,
        desktop_environments=desktop_envs,
        exclude_desktop=exclude_desktop,
        include_fstab_portability=include_fstab_portability
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
        print(f"  • {report['packages']['to_install']} packages will be installed")
        print(f"  • {report['packages']['unavailable']} packages are unavailable")
        
        if report['packages']['installation_commands']:
            print("\nInstallation commands that would be executed:")
            for i, cmd in enumerate(report['packages']['installation_commands'][:5], 1):
                print(f"  {i}. {cmd}")
            if len(report['packages']['installation_commands']) > 5:
                print(f"  ... and {len(report['packages']['installation_commands']) - 5} more commands")
        
        # Config files section
        print("\nCONFIGURATION FILES:")
        print(f"  • {report['config_files']['to_restore']} configuration files will be restored")
        print(f"  • {report['config_files']['conflicts']} configuration files have conflicts")
        
        if report['config_files']['paths']:
            print("\nSample of configuration files to be restored:")
            for path in report['config_files']['paths'][:5]:
                print(f"  • {path}")
            if len(report['config_files']['paths']) > 5:
                print(f"  ... and {len(report['config_files']['paths']) - 5} more files")
        
        # Path transformations section
        if report['path_transformations']:
            print("\nPATH TRANSFORMATIONS:")
            print("The following path transformations would be applied:")
            for i, (src_path, tgt_path) in enumerate(list(report['path_transformations'].items())[:5], 1):
                print(f"  {i}. {src_path} -> {tgt_path}")
            if len(report['path_transformations']) > 5:
                print(f"  ... and {len(report['path_transformations']) - 5} more transformations")
        
        # Fstab entries section
        if report['fstab_entries']:
            print("\nFSTAB ENTRIES:")
            print("The following portable fstab entries would be appended:")
            for i, entry in enumerate(report['fstab_entries'][:5], 1):
                print(f"  {i}. {entry}")
            if len(report['fstab_entries']) > 5:
                print(f"  ... and {len(report['fstab_entries']) - 5} more entries")
        
        # Conflicts section
        if report['conflicts']:
            print("\nPOTENTIAL ISSUES AND CONFLICTS:")
            for i, conflict in enumerate(report['conflicts'], 1):
                if conflict['type'] == 'package_unavailable':
                    print(f"  {i}. Package '{conflict['name']}' ({conflict['source']}) is unavailable: {conflict['reason']}")
                elif conflict['type'] == 'version_downgrade_required':
                    print(f"  {i}. Package '{conflict['name']}' would require downgrade from {conflict['available_version']} to {conflict['backup_version']}")
                elif conflict['type'] == 'config_conflict':
                    print(f"  {i}. Config file '{conflict['path']}' has conflict: {conflict['status']}")
        
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
    
    # Get version policy options
    version_policy = args.version_policy if hasattr(args, 'version_policy') else 'prefer-newer'
    allow_downgrade = args.allow_downgrade if hasattr(args, 'allow_downgrade') else False
    
    # Print version policy
    print(f"Using version policy: {version_policy}")
    if allow_downgrade:
        print("Package downgrades allowed if needed")
    
    # Process path transformation options
    transform_paths = not args.no_path_transform if hasattr(args, 'no_path_transform') else True
    preview_only = args.path_transform_preview if hasattr(args, 'path_transform_preview') else False
    
    if not transform_paths:
        print("Path transformation disabled - paths will be kept as-is")
    elif preview_only:
        print("Path transformation preview mode - no changes will be made")
    else:
        print("Path transformation enabled - system-specific paths will be adapted")
    
    # Process fstab options
    restore_fstab = not args.no_fstab_restore if hasattr(args, 'no_fstab_restore') else True
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
    if execute_plan or (hasattr(args, 'packages_only') and args.packages_only):
        print("Installing packages from backup...")
        app.execute_installation_plan(
            args.backup_file,
            version_policy=version_policy,
            allow_downgrade=allow_downgrade
        )
    
    # Execute config restoration if requested
    if execute_plan or (hasattr(args, 'configs_only') and args.configs_only):
        print("Restoring configuration files from backup...")
        app.execute_config_restoration(
            args.backup_file,
            transform_paths=transform_paths,
            preview_only=preview_only,
            restore_fstab=restore_fstab,
            preview_fstab=preview_fstab
        )
    
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
    
    # Print summary
    print("Package Installation Plan:")
    print(f"  Available packages: {len(pkg_plan['available'])}")
    print(f"  Upgradable packages: {len(pkg_plan['upgradable'])}")
    print(f"  Unavailable packages: {len(pkg_plan['unavailable'])}")
    print(f"  Installation commands: {len(pkg_plan['installation_commands'])}")
    
    print("\nConfiguration Restoration Plan:")
    print(f"  Restorable configs: {len(cfg_plan['restorable'])}")
    print(f"  Problematic configs: {len(cfg_plan['problematic'])}")
    print(f"  Restoration commands: {len(cfg_plan['commands'])}")
    
    # Save to file if specified
    if args.output:
        try:
            with open(args.output, 'w') as f:
                json.dump(plan, f, indent=2)
            print(f"Installation plan saved to {args.output}")
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
            print(f"\n[{datetime.now().isoformat()}] Performing routine check...")
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
    if not hasattr(args, 'subcommand') or not args.subcommand:
        print("Error: No configuration subcommand specified")
        return 1
        
    if args.subcommand == 'get-backup-dir':
        backup_dir = app.get_backup_dir()
        print(f"Current backup directory: {backup_dir}")
        return 0
        
    elif args.subcommand == 'set-backup-dir':
        if not hasattr(args, 'backup_dir') or not args.backup_dir:
            print("Error: No backup directory specified")
            return 1
            
        backup_dir = os.path.expanduser(args.backup_dir)
        success = app.set_backup_dir(backup_dir)
        
        if success:
            print(f"Backup directory set to: {backup_dir}")
            return 0
        else:
            print(f"Failed to set backup directory to: {backup_dir}")
            return 1
            
    elif args.subcommand == 'list-hosts':
        hosts = app.list_backup_hosts()
        
        if not hosts:
            print("No backup hosts found.")
            return 0
            
        print(f"Found {len(hosts)} hosts with backups:")
        for i, host in enumerate(hosts, 1):
            print(f"{i}. {host}")
            
        return 0
        
    elif args.subcommand == 'get-host-backups':
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
            mod_time = datetime.fromtimestamp(os.path.getmtime(backup_file))
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
            
    elif args.subcommand == 'backup-retention':
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
        print(f"Unknown configuration subcommand: {args.subcommand}")
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
                    include_fstab_portability=config.get("include_fstab_portability", True)
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
        mod_time = datetime.fromtimestamp(os.path.getmtime(backup_file))
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
    else:
        # Show help if no command specified
        parser.print_help()
        return 0

if __name__ == "__main__":
    sys.exit(main()) 