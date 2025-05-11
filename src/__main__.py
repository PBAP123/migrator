#!/usr/bin/env python3
"""
Command-line interface for Migrator utility
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

from main import Migrator
from utils.service import create_systemd_service, remove_systemd_service

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
              migrator compare backup.json # Compare current system with backup
              migrator plan backup.json   # Generate installation plan from backup
              migrator install-service    # Install as a systemd service
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
    
    # Backup command
    backup_parser = subparsers.add_parser('backup', help='Backup system state')
    backup_parser.add_argument('backup_dir', help='Directory to store backup')
    backup_parser.add_argument('--include-desktop', action='store_true', 
                             help='Include desktop environment configs')
    backup_parser.add_argument('--desktop-environments', 
                             help='Comma-separated list of desktop environments to include (e.g., gnome,kde,i3)')
    backup_parser.add_argument('--exclude-desktop', 
                             help='Comma-separated list of desktop environments to exclude')
    
    # Restore command
    restore_parser = subparsers.add_parser('restore', help='Restore system state from backup')
    restore_parser.add_argument('backup_file', help='Backup file to restore from')
    
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
    install_service_parser.add_argument('--interval', '-i', type=int, default=86400,
                                      help='Interval between checks in seconds (default: 86400 - once per day)')
    install_service_parser.add_argument('--user', action='store_true',
                                      help='Install as a user service instead of system-wide')
    
    # Remove service command
    remove_service_parser = subparsers.add_parser('remove-service', 
                                                help='Remove Migrator systemd service')
    remove_service_parser.add_argument('--user', action='store_true',
                                     help='Remove user service instead of system-wide')
    
    return parser

def handle_scan(app: Migrator, args: argparse.Namespace) -> int:
    """Handle scan command"""
    # Process desktop environment options
    include_desktop = args.include_desktop if hasattr(args, 'include_desktop') else False
    desktop_envs = None
    exclude_desktop = None
    
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
    
    app.update_system_state(
        include_desktop=include_desktop,
        desktop_environments=desktop_envs,
        exclude_desktop=exclude_desktop
    )
    
    print("System state updated successfully.")
    return 0

def handle_backup(app: Migrator, args: argparse.Namespace) -> int:
    """Handle backup command"""
    print(f"Backing up system state to {args.backup_dir}...")
    
    # Process desktop environment options
    include_desktop = args.include_desktop if hasattr(args, 'include_desktop') else False
    desktop_envs = None
    exclude_desktop = None
    
    if hasattr(args, 'desktop_environments') and args.desktop_environments:
        desktop_envs = args.desktop_environments.split(',')
        
    if hasattr(args, 'exclude_desktop') and args.exclude_desktop:
        exclude_desktop = args.exclude_desktop.split(',')
    
    # Ensure state is up to date
    app.update_system_state(
        include_desktop=include_desktop,
        desktop_environments=desktop_envs,
        exclude_desktop=exclude_desktop
    )
    
    # Create backup
    backup_file = app.backup_state(args.backup_dir)
    
    if backup_file:
        print(f"Backup created successfully: {backup_file}")
        return 0
    else:
        print("Failed to create backup.")
        return 1

def handle_restore(app: Migrator, args: argparse.Namespace) -> int:
    """Handle restore command"""
    print(f"Restoring system state from {args.backup_file}...")
    
    success = app.restore_from_backup(args.backup_file)
    
    if success:
        print("System state restored successfully.")
        return 0
    else:
        print("Failed to restore system state.")
        return 1

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
    
    success, message = create_systemd_service(
        check_interval=args.interval,
        user_unit=args.user
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

def main() -> int:
    """Main CLI entry point"""
    parser = setup_argparse()
    args = parser.parse_args()
    
    if not args.command:
        parser.print_help()
        return 1
    
    # Initialize application
    app = Migrator()
    
    # Handle commands
    command_handlers = {
        'scan': handle_scan,
        'backup': handle_backup,
        'restore': handle_restore,
        'compare': handle_compare,
        'plan': handle_plan,
        'check': handle_check,
        'service': handle_service,
        'install-service': handle_install_service,
        'remove-service': handle_remove_service
    }
    
    handler = command_handlers.get(args.command)
    if handler:
        return handler(app, args)
    else:
        print(f"Unknown command: {args.command}")
        return 1

if __name__ == "__main__":
    sys.exit(main()) 