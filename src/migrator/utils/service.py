#!/usr/bin/env python3
"""
Utilities for setting up Migrator as a system service
"""

import os
import sys
import getpass
import subprocess
import logging
import pkg_resources
import shutil
from pathlib import Path

logger = logging.getLogger(__name__)

SYSTEMD_SERVICE_TEMPLATE = """[Unit]
Description=Migrator System Migration Utility
After=network.target

[Service]
Type=simple
Environment="PATH={venv_path}/bin:$PATH"
ExecStart={exec_path} service {extra_args}
Restart=on-failure
User={username}

[Install]
WantedBy=multi-user.target
"""

def get_current_username():
    """Get the current username"""
    return getpass.getuser()

def get_virtual_env_path():
    """Get the path to the current virtual environment, if any"""
    # Check if we're running in a virtual environment
    if hasattr(sys, 'real_prefix') or (hasattr(sys, 'base_prefix') and sys.base_prefix != sys.prefix):
        return sys.prefix
    return None

def get_executable_path():
    """Get the path to the migrator executable"""
    # If in a virtualenv, use the virtualenv's migrator
    venv_path = get_virtual_env_path()
    if venv_path:
        return os.path.join(venv_path, 'bin', 'migrator')
    
    # Otherwise use the sys.executable to get Python and call the module directly
    return f"{sys.executable} -m src.__main__"

def create_systemd_service(check_interval=None, user_unit=False):
    """
    Create a systemd service file for Migrator
    
    Args:
        check_interval: Optional interval in seconds between checks
        user_unit: Whether to install as a user unit (no sudo required)
    
    Returns:
        Tuple of (success, message)
    """
    username = get_current_username()
    venv_path = get_virtual_env_path() or sys.prefix
    exec_path = get_executable_path()
    
    # Add any extra arguments
    extra_args = f"--interval {check_interval}" if check_interval else ""
    
    # Create the service file content
    service_content = SYSTEMD_SERVICE_TEMPLATE.format(
        venv_path=venv_path,
        exec_path=exec_path,
        username=username,
        extra_args=extra_args
    )
    
    # Determine where to install the service
    if user_unit:
        # User systemd unit
        service_dir = os.path.expanduser("~/.config/systemd/user")
        service_path = os.path.join(service_dir, "migrator.service")
        enable_cmd = ["systemctl", "--user", "enable", "migrator.service"]
        start_cmd = ["systemctl", "--user", "start", "migrator.service"]
        sudo_needed = False
    else:
        # System-wide unit
        service_dir = "/etc/systemd/system"
        service_path = os.path.join(service_dir, "migrator.service")
        enable_cmd = ["sudo", "systemctl", "enable", "migrator.service"]
        start_cmd = ["sudo", "systemctl", "start", "migrator.service"]
        sudo_needed = True
    
    try:
        # Create the directory if it doesn't exist (for user units)
        if user_unit:
            os.makedirs(service_dir, exist_ok=True)
        
        # Write the service file
        if user_unit or os.access(service_dir, os.W_OK):
            with open(service_path, 'w') as f:
                f.write(service_content)
        else:
            # Need sudo to write to system directory
            with open('migrator.service.tmp', 'w') as f:
                f.write(service_content)
            
            result = subprocess.run(["sudo", "mv", "migrator.service.tmp", service_path], 
                                   check=True, 
                                   capture_output=True)
        
        # Reload systemd to recognize the new service
        if user_unit:
            subprocess.run(["systemctl", "--user", "daemon-reload"], check=True)
        else:
            subprocess.run(["sudo", "systemctl", "daemon-reload"], check=True)
        
        # Build instruction message based on whether service was automatically started
        try:
            if user_unit:
                subprocess.run(enable_cmd, check=True)
                subprocess.run(start_cmd, check=True)
                started = True
            else:
                # Ask for confirmation before enabling/starting system-wide service
                print("Service file created at:", service_path)
                response = input("Do you want to enable and start the service now? (y/n): ")
                if response.lower().startswith('y'):
                    subprocess.run(enable_cmd, check=True)
                    subprocess.run(start_cmd, check=True)
                    started = True
                else:
                    started = False
        except subprocess.SubprocessError:
            started = False
        
        # Build the success message
        if started:
            msg = (f"Migrator service successfully installed and started.\n"
                   f"Service file created at: {service_path}")
        else:
            commands = "\n".join([" ".join(enable_cmd), " ".join(start_cmd)])
            msg = (f"Migrator service file created at: {service_path}\n"
                   f"To enable and start the service, run:\n{commands}")
        
        return True, msg
        
    except (IOError, subprocess.SubprocessError) as e:
        error_msg = f"Failed to create systemd service: {str(e)}"
        logger.error(error_msg)
        return False, error_msg

def remove_systemd_service(user_unit=False):
    """
    Remove the systemd service for Migrator
    
    Args:
        user_unit: Whether it was installed as a user unit
    
    Returns:
        Tuple of (success, message)
    """
    try:
        # Stop and disable the service
        if user_unit:
            service_path = os.path.expanduser("~/.config/systemd/user/migrator.service")
            subprocess.run(["systemctl", "--user", "stop", "migrator.service"], check=False)
            subprocess.run(["systemctl", "--user", "disable", "migrator.service"], check=False)
        else:
            service_path = "/etc/systemd/system/migrator.service"
            subprocess.run(["sudo", "systemctl", "stop", "migrator.service"], check=False)
            subprocess.run(["sudo", "systemctl", "disable", "migrator.service"], check=False)
        
        # Remove the service file
        if os.path.exists(service_path):
            if user_unit or os.access(os.path.dirname(service_path), os.W_OK):
                os.remove(service_path)
            else:
                subprocess.run(["sudo", "rm", service_path], check=True)
            
            # Reload systemd
            if user_unit:
                subprocess.run(["systemctl", "--user", "daemon-reload"], check=True)
            else:
                subprocess.run(["sudo", "systemctl", "daemon-reload"], check=True)
            
            return True, f"Migrator service removed successfully."
        else:
            return False, f"Service file not found at {service_path}"
            
    except (IOError, subprocess.SubprocessError) as e:
        error_msg = f"Failed to remove systemd service: {str(e)}"
        logger.error(error_msg)
        return False, error_msg 