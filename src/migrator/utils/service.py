#!/usr/bin/env python3
"""
Utilities for setting up Migrator as a system service
"""

import os
import sys
import getpass
import subprocess
import logging
try:
    from importlib.metadata import version
except ImportError:
    # Fallback for Python < 3.8
    from importlib_metadata import version
import shutil
from pathlib import Path

logger = logging.getLogger(__name__)

# Standard service template that runs periodically
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

# Timer-based template for scheduled operation
SYSTEMD_TIMER_TEMPLATE = """[Unit]
Description=Migrator System Migration Utility Timer
After=network.target

[Timer]
OnCalendar={schedule}
Persistent=true
Unit=migrator.service

[Install]
WantedBy=timers.target
"""

# Service template for timer-based execution (runs once per invocation)
SYSTEMD_TIMER_SERVICE_TEMPLATE = """[Unit]
Description=Migrator System Migration Utility (Timer-activated)
After=network.target

[Service]
Type=oneshot
Environment="PATH={venv_path}/bin:$PATH"
ExecStart={exec_path} scan
ExecStart={exec_path} check
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

def create_systemd_service(check_interval=None, user_unit=False, schedule=None):
    """
    Create a systemd service file for Migrator
    
    Args:
        check_interval: Optional interval in seconds between checks
        user_unit: Whether to install as a user unit (no sudo required)
        schedule: Optional systemd timer schedule string (e.g., "daily" or "Mon *-*-* 14:30:00")
                 If provided, creates a timer-based service instead of an interval service
    
    Returns:
        Tuple of (success, message)
    """
    username = get_current_username()
    venv_path = get_virtual_env_path() or sys.prefix
    exec_path = get_executable_path()
    
    # Determine if we're creating a timer-based or interval-based service
    use_timer = schedule is not None
    
    if use_timer:
        # Create timer-based service (executes at scheduled times)
        service_content = SYSTEMD_TIMER_SERVICE_TEMPLATE.format(
            venv_path=venv_path,
            exec_path=exec_path,
            username=username
        )
        
        timer_content = SYSTEMD_TIMER_TEMPLATE.format(
            schedule=schedule
        )
    else:
        # Create interval-based service (continuously running)
        extra_args = f"--interval {check_interval}" if check_interval else ""
        
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
        if use_timer:
            timer_path = os.path.join(service_dir, "migrator.timer")
            enable_cmd = ["systemctl", "--user", "enable", "migrator.timer"]
            start_cmd = ["systemctl", "--user", "start", "migrator.timer"]
        else:
            enable_cmd = ["systemctl", "--user", "enable", "migrator.service"]
            start_cmd = ["systemctl", "--user", "start", "migrator.service"]
        sudo_needed = False
    else:
        # System-wide unit
        service_dir = "/etc/systemd/system"
        service_path = os.path.join(service_dir, "migrator.service")
        if use_timer:
            timer_path = os.path.join(service_dir, "migrator.timer")
            enable_cmd = ["sudo", "systemctl", "enable", "migrator.timer"]
            start_cmd = ["sudo", "systemctl", "start", "migrator.timer"]
        else:
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
            
            # Write the timer file if using a schedule
            if use_timer:
                with open(timer_path, 'w') as f:
                    f.write(timer_content)
        else:
            # Need sudo to write to system directory
            with open('migrator.service.tmp', 'w') as f:
                f.write(service_content)
            
            result = subprocess.run(["sudo", "mv", "migrator.service.tmp", service_path], 
                                   check=True, 
                                   capture_output=True)
            
            # Create timer file if using a schedule
            if use_timer:
                with open('migrator.timer.tmp', 'w') as f:
                    f.write(timer_content)
                
                result = subprocess.run(["sudo", "mv", "migrator.timer.tmp", timer_path],
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
                if use_timer:
                    print("Timer file created at:", timer_path)
                    print(f"Service scheduled to run: {schedule}")
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
            if use_timer:
                msg = (f"Migrator timer service successfully installed and started.\n"
                      f"Service will run according to schedule: {schedule}\n"
                      f"Service file created at: {service_path}\n"
                      f"Timer file created at: {timer_path}")
            else:
                msg = (f"Migrator service successfully installed and started.\n"
                      f"Service will check every {check_interval} seconds.\n"
                      f"Service file created at: {service_path}")
        else:
            commands = "\n".join([" ".join(enable_cmd), " ".join(start_cmd)])
            if use_timer:
                msg = (f"Migrator timer service file created at: {service_path}\n"
                      f"Timer file created at: {timer_path}\n"
                      f"Service scheduled to run: {schedule}\n"
                      f"To enable and start the service, run:\n{commands}")
            else:
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
            timer_path = os.path.expanduser("~/.config/systemd/user/migrator.timer")
            
            # Check if timer exists and stop/disable it first
            if os.path.exists(timer_path):
                subprocess.run(["systemctl", "--user", "stop", "migrator.timer"], check=False)
                subprocess.run(["systemctl", "--user", "disable", "migrator.timer"], check=False)
            
            subprocess.run(["systemctl", "--user", "stop", "migrator.service"], check=False)
            subprocess.run(["systemctl", "--user", "disable", "migrator.service"], check=False)
        else:
            service_path = "/etc/systemd/system/migrator.service"
            timer_path = "/etc/systemd/system/migrator.timer"
            
            # Check if timer exists and stop/disable it first
            if os.path.exists(timer_path):
                subprocess.run(["sudo", "systemctl", "stop", "migrator.timer"], check=False)
                subprocess.run(["sudo", "systemctl", "disable", "migrator.timer"], check=False)
            
            subprocess.run(["sudo", "systemctl", "stop", "migrator.service"], check=False)
            subprocess.run(["sudo", "systemctl", "disable", "migrator.service"], check=False)
        
        # Remove the service and timer files
        files_removed = 0
        
        # Remove service file
        if os.path.exists(service_path):
            if user_unit or os.access(os.path.dirname(service_path), os.W_OK):
                os.remove(service_path)
                files_removed += 1
            else:
                subprocess.run(["sudo", "rm", service_path], check=True)
                files_removed += 1
        
        # Remove timer file if it exists
        if os.path.exists(timer_path):
            if user_unit or os.access(os.path.dirname(timer_path), os.W_OK):
                os.remove(timer_path)
                files_removed += 1
            else:
                subprocess.run(["sudo", "rm", timer_path], check=True)
                files_removed += 1
        
        # Reload systemd
        if user_unit:
            subprocess.run(["systemctl", "--user", "daemon-reload"], check=True)
        else:
            subprocess.run(["sudo", "systemctl", "daemon-reload"], check=True)
        
        if files_removed > 0:
            return True, f"Migrator service removed successfully."
        else:
            return False, f"Service files not found at {service_path} or {timer_path}"
            
    except (IOError, subprocess.SubprocessError) as e:
        error_msg = f"Failed to remove systemd service: {str(e)}"
        logger.error(error_msg)
        return False, error_msg 