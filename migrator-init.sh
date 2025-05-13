#!/bin/bash
# migrator-init.sh - Unified installer and launcher for Migrator
#
# This script provides a simple way to install and run Migrator in one step,
# handling virtual environment creation and dependency installation automatically.

set -e

# Default locations
DEFAULT_VENV_PATH="$HOME/.venvs/migrator"
WRAPPER_PATH="$HOME/.local/bin/migrator"
PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
VERSION="0.1.0"  # Current version

# Colors for terminal output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Print section header
print_header() {
    echo -e "\n${BLUE}==== $1 ====${NC}\n"
}

# Print success message
print_success() {
    echo -e "${GREEN}✓ $1${NC}"
}

# Print warning message
print_warning() {
    echo -e "${YELLOW}! $1${NC}"
}

# Print error message
print_error() {
    echo -e "${RED}✗ $1${NC}"
}

# Check if we're already in a virtual environment
in_virtualenv() {
    if [ -n "$VIRTUAL_ENV" ]; then
        return 0
    else
        return 1
    fi
}

# Check if migrator is installed in the virtual environment
is_migrator_installed() {
    if [ -f "$WRAPPER_PATH" ]; then
        return 0
    elif [ -d "$DEFAULT_VENV_PATH" ]; then
        if [ -f "$DEFAULT_VENV_PATH/bin/migrator" ]; then
            return 0
        elif [ -d "$DEFAULT_VENV_PATH/lib/python"*"/site-packages/migrator" ] || \
             [ -d "$DEFAULT_VENV_PATH/lib/python"*"/site-packages/migrator.egg-info" ]; then
            # Migrator is installed in venv but wrapper script is missing
            print_warning "Migrator is installed but wrapper script is missing."
            return 0
        fi
    fi
    return 1
}

# Create the wrapper scripts if they're missing
create_wrapper_scripts() {
    print_header "Creating Wrapper Scripts"
    
    # Default target locations
    user_bin_dir="$HOME/.local/bin"
    
    # Ensure target directory exists
    mkdir -p "$user_bin_dir"
    
    # Copy the main script
    main_target_path="$user_bin_dir/migrator"
    if [ -f "$PROJECT_DIR/migrator.sh" ]; then
        cp "$PROJECT_DIR/migrator.sh" "$main_target_path"
        chmod 755 "$main_target_path"
        print_success "Main wrapper script created at $main_target_path"
    else
        print_warning "migrator.sh not found in project directory. Cannot create main wrapper."
    fi
    
    # Create a symlink to the unified script if it exists
    unified_target_path="$user_bin_dir/migrator-init"
    if [ -f "$UNIFIED_SCRIPT" ]; then
        if [ -L "$unified_target_path" ]; then
            rm "$unified_target_path"
        fi
        ln -s "$UNIFIED_SCRIPT" "$unified_target_path"
        print_success "Symlink to unified script created at $unified_target_path"
    fi
    
    # Check if the directory is in PATH
    if [[ ":$PATH:" != *":$user_bin_dir:"* ]]; then
        print_warning "$user_bin_dir is not in your PATH"
        print_warning "You may need to add this line to your ~/.bashrc:"
        echo "    export PATH=\"$user_bin_dir:\$PATH\""
        echo "Then restart your terminal or run:"
        echo "    source ~/.bashrc"
    else
        print_success "$user_bin_dir is in your PATH"
    fi
}

# Create virtual environment if it doesn't exist
ensure_virtualenv() {
    if [ ! -d "$DEFAULT_VENV_PATH" ]; then
        print_header "Creating Virtual Environment"
        echo "Creating virtual environment at $DEFAULT_VENV_PATH"
        python3 -m venv "$DEFAULT_VENV_PATH"
        
        # Install essential packages in the virtual environment
        print_header "Installing Essential Dependencies"
        "$DEFAULT_VENV_PATH/bin/pip" install --upgrade pip setuptools wheel
        
        print_success "Virtual environment created"
    else
        print_success "Using existing virtual environment at $DEFAULT_VENV_PATH"
        
        # Ensure essential packages are installed even in existing environments
        if ! "$DEFAULT_VENV_PATH/bin/pip" show setuptools >/dev/null 2>&1; then
            print_warning "Essential packages missing in virtual environment"
            "$DEFAULT_VENV_PATH/bin/pip" install --upgrade pip setuptools wheel
            print_success "Essential packages installed"
        fi
    fi
}

# Install Migrator and dependencies
install_migrator() {
    print_header "Installing Migrator"
    echo "Installing Migrator and dependencies..."
    
    # Make sure pip, setuptools, and wheel are up to date
    "$DEFAULT_VENV_PATH/bin/pip" install --upgrade pip setuptools wheel
    
    # Install requirements
    "$DEFAULT_VENV_PATH/bin/pip" install -r "$PROJECT_DIR/requirements.txt"
    
    # Install the package
    "$DEFAULT_VENV_PATH/bin/pip" install -e "$PROJECT_DIR"
    
    # Create wrapper scripts if needed
    if [ ! -f "$WRAPPER_PATH" ]; then
        create_wrapper_scripts
    fi
    
    print_success "Migrator installed successfully!"
}

# Update Migrator installation
update_migrator() {
    print_header "Updating Migrator"
    echo "Updating Migrator and dependencies..."
    
    # Update requirements
    "$DEFAULT_VENV_PATH/bin/pip" install -r "$PROJECT_DIR/requirements.txt" --upgrade
    
    # Reinstall the package
    "$DEFAULT_VENV_PATH/bin/pip" install -e "$PROJECT_DIR" --upgrade
    
    # Recreate wrapper scripts to ensure they're up to date
    create_wrapper_scripts
    
    print_success "Migrator updated successfully!"
}

# Uninstall Migrator (without removing repository or backups)
uninstall_migrator() {
    print_header "Uninstalling Migrator"
    echo "This will remove the virtual environment and wrapper scripts but keep your repository and backups."
    
    read -p "Are you sure you want to uninstall Migrator? (y/n) " choice
    if [[ ! $choice =~ ^[Yy]$ ]]; then
        echo "Uninstall cancelled."
        return
    fi
    
    # Check for and remove systemd services if they exist
    echo "Checking for systemd services..."
    if systemctl --user status migrator &>/dev/null; then
        echo "User-level systemd service found. Removing..."
        systemctl --user stop migrator &>/dev/null || true
        systemctl --user disable migrator &>/dev/null || true
        rm -f "$HOME/.config/systemd/user/migrator.service" "$HOME/.config/systemd/user/migrator.timer" 2>/dev/null || true
        systemctl --user daemon-reload
        print_success "User-level systemd service removed"
    fi
    
    if command -v sudo &>/dev/null && sudo systemctl status migrator &>/dev/null; then
        echo "System-level systemd service found. Removing..."
        sudo systemctl stop migrator &>/dev/null || true
        sudo systemctl disable migrator &>/dev/null || true
        sudo rm -f "/etc/systemd/system/migrator.service" "/etc/systemd/system/migrator.timer" 2>/dev/null || true
        sudo systemctl daemon-reload
        print_success "System-level systemd service removed"
    fi
    
    echo "Removing virtual environment at $DEFAULT_VENV_PATH..."
    if [ -d "$DEFAULT_VENV_PATH" ]; then
        rm -rf "$DEFAULT_VENV_PATH"
        print_success "Virtual environment removed successfully"
    else
        print_warning "Virtual environment not found at $DEFAULT_VENV_PATH"
    fi
    
    echo "Removing wrapper scripts..."
    if [ -f "$WRAPPER_PATH" ]; then
        rm -f "$WRAPPER_PATH"
        print_success "Wrapper script removed successfully"
    else
        print_warning "Wrapper script not found at $WRAPPER_PATH"
    fi
    
    echo "Cleaning up configuration files..."
    # Remove config and state files but NOT backups
    if [ -d "$HOME/.config/migrator" ]; then
        rm -rf "$HOME/.config/migrator"
        print_success "Configuration files removed"
    fi
    
    if [ -d "$HOME/.local/share/migrator" ]; then
        rm -rf "$HOME/.local/share/migrator"
        print_success "State files removed"
    fi
    
    print_success "Migrator has been uninstalled, but your repository at $PROJECT_DIR and any backups you created have been preserved."
    echo "If you want to completely remove Migrator, you can also delete:"
    echo "1. The repository directory at $PROJECT_DIR"
    echo "2. Your backup files (default location: ~/migrator_backups)"
}

# Check for required system packages and suggest installation
check_system_packages() {
    MISSING_PACKAGES=""
    
    # Check for Python venv module
    if ! python3 -c "import venv" 2>/dev/null; then
        MISSING_PACKAGES="$MISSING_PACKAGES python3-venv"
    fi
    
    # Check for pip
    if ! command -v pip3 &>/dev/null; then
        MISSING_PACKAGES="$MISSING_PACKAGES python3-pip"
    fi
    
    # Check for distro module
    if ! python3 -c "import distro" 2>/dev/null; then
        MISSING_PACKAGES="$MISSING_PACKAGES python3-distro"
    fi
    
    if [ -n "$MISSING_PACKAGES" ]; then
        print_header "Missing System Dependencies"
        print_warning "Some required packages are missing: $MISSING_PACKAGES"
        echo "On Debian/Ubuntu, run: sudo apt install$MISSING_PACKAGES"
        echo "On Fedora/RHEL, run: sudo dnf install$MISSING_PACKAGES"
        echo "On Arch Linux, run: sudo pacman -S${MISSING_PACKAGES//python3/python}"
        
        read -p "Would you like to try installing these packages now? (y/n) " -n 1 -r
        echo
        if [[ $REPLY =~ ^[Yy]$ ]]; then
            # Try to detect the distribution and install packages
            if command -v apt &>/dev/null; then
                sudo apt install $MISSING_PACKAGES
                print_success "Dependencies installed"
            elif command -v dnf &>/dev/null; then
                sudo dnf install $MISSING_PACKAGES
                print_success "Dependencies installed"
            elif command -v pacman &>/dev/null; then
                sudo pacman -S ${MISSING_PACKAGES//python3/python}
                print_success "Dependencies installed"
            else
                print_error "Could not detect package manager. Please install the required packages manually."
                exit 1
            fi
        else
            print_error "Please install the required packages manually and run this script again."
            exit 1
        fi
    fi
}

# First run check and setup wizard trigger
check_first_run() {
    STATE_FILE="$HOME/.local/share/migrator/system_state.json"
    CONFIG_FILE="$HOME/.config/migrator/config.json"
    
    # Check if state file exists
    if [ ! -f "$STATE_FILE" ] && [ ! -f "$CONFIG_FILE" ]; then
        print_header "First Run Detected"
        echo "It looks like this is your first time running Migrator."
        echo "Would you like to run the interactive setup wizard to configure Migrator?"
        read -p "This will help you set up backup content, destination, and scheduling (y/n): " choice
        
        if [[ $choice =~ ^[Yy] ]]; then
            # Run the setup wizard
            if [ -x "$WRAPPER_PATH" ]; then
                "$WRAPPER_PATH" setup
                return $?
            else
                # If wrapper not available, install first then run setup
                install_migrator
                if [ -x "$WRAPPER_PATH" ]; then
                    "$WRAPPER_PATH" setup
                    return $?
                else
                    print_error "Failed to run setup wizard. Please try again later."
                    return 1
                fi
            fi
        else
            print_warning "Setup wizard skipped. You can run 'migrator setup' anytime to configure Migrator."
            echo
        fi
    fi
    
    return 0
}

# Run Migrator command via the wrapper script
run_migrator() {
    if [ -x "$WRAPPER_PATH" ]; then
        # Check for first run
        if [ "$1" != "setup" ]; then
            check_first_run
        fi
        
        # If args provided, run the command
        if [ $# -gt 0 ]; then
            "$WRAPPER_PATH" "$@"
        else
            # Without args, show menu
            show_menu
        fi
    else
        print_error "Migrator wrapper script not found at $WRAPPER_PATH."
        print_warning "This could mean Migrator is not properly installed."
        
        echo -e "\nChoose an option:"
        echo "1) Install/repair Migrator (recommended)"
        echo "2) Create wrapper scripts only"
        echo "3) Fix PATH environment variable"
        echo "4) Exit"
        
        read -p "Enter your choice (1-4): " choice
        case $choice in
            1)
                install_migrator
                run_migrator "$@"
                ;;
            2)
                create_wrapper_scripts
                ;;
            3)
                fix_path
                ;;
            4)
                exit 0
                ;;
            *)
                print_error "Invalid choice. Exiting."
                exit 1
                ;;
        esac
    fi
}

# Fix PATH issues
fix_path() {
    print_header "Fixing PATH"
    local user_bin_dir="$HOME/.local/bin"
    
    if [[ ":$PATH:" != *":$user_bin_dir:"* ]]; then
        echo "Adding $user_bin_dir to PATH in your ~/.bashrc"
        echo -e '\nexport PATH="$HOME/.local/bin:$PATH"' >> ~/.bashrc
        print_success "PATH updated in ~/.bashrc"
        print_warning "You need to restart your terminal or run:"
        echo "source ~/.bashrc"
    else
        print_success "$user_bin_dir is already in your PATH"
        print_warning "There might be another issue preventing Migrator from running."
    fi
}

# Show a simple command line menu
show_menu() {
    while true; do
        clear
        print_header "Migrator Command Line Interface"
        
        echo "Welcome to Migrator - Linux System Migration Utility"
        echo "Version: $VERSION"
        echo
        
        # Print system information
        echo "System: $(uname -s) $(uname -r)"
        if command -v lsb_release &>/dev/null; then
            echo "Distribution: $(lsb_release -sd)"
        elif [ -f /etc/os-release ]; then
            echo "Distribution: $(grep -oP '(?<=^PRETTY_NAME=).+' /etc/os-release | tr -d '"')"
        fi
        echo
        
        # Check status
        echo "Migrator Status:"
        
        if is_migrator_installed; then
            print_success "Migrator: Installed"
        else
            print_warning "Migrator: Not installed"
        fi
        
        if [ -d "$DEFAULT_VENV_PATH" ]; then
            print_success "Virtual Environment: Exists"
        else
            print_warning "Virtual Environment: Not created"
        fi
        
        echo
        echo "Available commands:"
        echo "1) scan           - Scan system packages and configurations"
        echo "2) backup         - Create a backup of your system"
        echo "3) restore        - Restore from a backup"
        echo "4) compare        - Compare current system with a backup"
        echo "5) plan           - Generate an installation plan from a backup"
        echo "6) check          - Check for changes since last scan"
        echo "7) service        - Manage Migrator service"
        echo "8) setup          - Run the interactive setup wizard"
        echo "9) help           - Show detailed help"
        echo "q) quit           - Exit the menu"
        echo
        
        read -p "Enter your choice: " choice
        
        case $choice in
            1|scan)
                clear
                run_migrator_command "scan"
                ;;
            2|backup)
                clear
                run_migrator_command "backup"
                ;;
            3|restore)
                clear
                run_migrator_command "restore"
                ;;
            4|compare)
                clear
                run_migrator_command "compare"
                ;;
            5|plan)
                clear
                run_migrator_command "plan"
                ;;
            6|check)
                clear
                run_migrator_command "check"
                ;;
            7|service)
                clear
                run_migrator_command "service"
                ;;
            8|setup)
                clear
                run_migrator_command "setup"
                ;;
            9|help)
                clear
                run_migrator_command "help"
                ;;
            q|quit|exit)
                clear
                break
                ;;
            *)
                echo "Invalid choice. Press Enter to continue."
                read
                ;;
        esac
    done
}

# Run a migrator command
run_migrator_command() {
    local command="$1"
    shift
    
    # Ensure the virtual environment is active
    source "$DEFAULT_VENV_PATH/bin/activate"
    
    # Special handling for commands that need additional arguments
    if [ "$command" = "compare" ]; then
        echo "The compare command requires a backup file path."
        read -p "Enter the path to your backup file: " backup_path
        
        if [ -z "$backup_path" ]; then
            print_error "No backup file specified. Operation cancelled."
            read -p "Press Enter to continue..." _
            return
        fi
        
        if [ ! -f "$backup_path" ]; then
            print_error "The specified file does not exist: $backup_path"
            read -p "Press Enter to continue..." _
            return
        fi
        
        # Run the migrator command with the backup file path
        if [ -x "$DEFAULT_VENV_PATH/bin/migrator" ]; then
            "$DEFAULT_VENV_PATH/bin/migrator" "$command" "$backup_path" "$@"
        else
            # This is the fallback if the bin/migrator script doesn't exist
            python -m migrator "$command" "$backup_path" "$@"
        fi
    elif [ "$command" = "plan" ]; then
        echo "The plan command requires a backup file path."
        read -p "Enter the path to your backup file: " backup_path
        
        if [ -z "$backup_path" ]; then
            print_error "No backup file specified. Operation cancelled."
            read -p "Press Enter to continue..." _
            return
        fi
        
        if [ ! -f "$backup_path" ]; then
            print_error "The specified file does not exist: $backup_path"
            read -p "Press Enter to continue..." _
            return
        fi
        
        # Run the migrator command with the backup file path
        if [ -x "$DEFAULT_VENV_PATH/bin/migrator" ]; then
            "$DEFAULT_VENV_PATH/bin/migrator" "$command" "$backup_path" "$@"
        else
            # This is the fallback if the bin/migrator script doesn't exist
            python -m migrator "$command" "$backup_path" "$@"
        fi
    elif [ "$command" = "restore" ]; then
        echo "The restore command requires a backup file path."
        read -p "Enter the path to your backup file: " backup_path
        
        if [ -z "$backup_path" ]; then
            print_error "No backup file specified. Operation cancelled."
            read -p "Press Enter to continue..." _
            return
        fi
        
        if [ ! -f "$backup_path" ]; then
            print_error "The specified file does not exist: $backup_path"
            read -p "Press Enter to continue..." _
            return
        fi
        
        # Run the migrator command with the backup file path
        if [ -x "$DEFAULT_VENV_PATH/bin/migrator" ]; then
            "$DEFAULT_VENV_PATH/bin/migrator" "$command" "$backup_path" "$@"
        else
            # This is the fallback if the bin/migrator script doesn't exist
            python -m migrator "$command" "$backup_path" "$@"
        fi
    else
        # Run the migrator command
        if [ -x "$DEFAULT_VENV_PATH/bin/migrator" ]; then
            "$DEFAULT_VENV_PATH/bin/migrator" "$command" "$@"
        else
            # This is the fallback if the bin/migrator script doesn't exist
            python -m migrator "$command" "$@"
        fi
    fi
    
    # Wait for user to press Enter before returning to the menu
    echo
    read -p "Press Enter to continue..." _
}

# Show the diagnostic info about the installation
show_diagnostics() {
    print_header "Migrator Diagnostics"
    
    echo "System Information:"
    echo "$(uname -a)"
    if command -v lsb_release &>/dev/null; then
        echo "Distribution: $(lsb_release -sd)"
    elif [ -f /etc/os-release ]; then
        echo "Distribution: $(grep -oP '(?<=^PRETTY_NAME=).+' /etc/os-release | tr -d '"')"
    fi
    
    echo
    echo "Python Information:"
    echo "Python version: $(python3 --version 2>/dev/null || echo 'Not found')"
    echo "pip version: $(pip3 --version 2>/dev/null || echo 'Not found')"
    
    echo
    echo "Installation Status:"
    
    if [ -d "$DEFAULT_VENV_PATH" ]; then
        print_success "Virtual Environment: Exists at $DEFAULT_VENV_PATH"
        
        # Check Python version in venv
        if [ -x "$DEFAULT_VENV_PATH/bin/python" ]; then
            echo "Venv Python version: $("$DEFAULT_VENV_PATH/bin/python" --version 2>/dev/null)"
        fi
        
        # Check installed packages
        echo
        echo "Installed packages in venv:"
        if [ -x "$DEFAULT_VENV_PATH/bin/pip" ]; then
            "$DEFAULT_VENV_PATH/bin/pip" freeze | grep -E 'migrator|distro|tqdm|setuptools' || echo "No relevant packages found"
        else
            echo "Could not find pip in virtual environment"
        fi
    else
        print_warning "Virtual Environment: Not created at $DEFAULT_VENV_PATH"
    fi
    
    echo
    echo "Wrapper Scripts:"
    if [ -f "$WRAPPER_PATH" ]; then
        print_success "Main wrapper: Exists at $WRAPPER_PATH"
        echo "  Size: $(wc -c < "$WRAPPER_PATH") bytes"
        echo "  Permissions: $(ls -l "$WRAPPER_PATH" | awk '{print $1}')"
        echo "  Is executable: $(if [ -x "$WRAPPER_PATH" ]; then echo "Yes"; else echo "No"; fi)"
    else
        print_warning "Main wrapper: Missing from $WRAPPER_PATH"
    fi
    
    echo
    echo "PATH Environment Variable:"
    echo "$PATH" | tr ':' '\n'
    
    echo
    echo "End of diagnostics."
}

# Print help information
print_help() {
    echo "Usage: $0 [command] [options]"
    echo
    echo "Migrator Unified Installer and Launcher"
    echo
    echo "Commands:"
    echo "  help                  - Show this help message"
    echo "  install               - Install Migrator"
    echo "  update                - Update Migrator to the latest version"
    echo "  clean                 - Perform a clean installation (removes existing venv)"
    echo "  uninstall             - Uninstall Migrator (keeps repository and backups)"
    echo "  diagnostic            - Show diagnostic information"
    echo "  version               - Show version information"
    echo
    echo "If no command is provided, an interactive menu will be shown."
    echo
    echo "Examples:"
    echo "  $0                    - Show interactive menu"
    echo "  $0 install            - Install Migrator"
    echo "  $0 update             - Update Migrator"
    echo "  $0 uninstall          - Uninstall Migrator"
    echo "  $0 help               - Show this help message"
    echo
}

# Parse command line arguments
if [ $# -gt 0 ]; then
    case "$1" in
        help)
            print_help
            exit 0
            ;;
        install)
            check_system_packages
            ensure_virtualenv
            install_migrator
            ;;
        update)
            ensure_virtualenv
            update_migrator
            ;;
        clean)
            rm -rf "$DEFAULT_VENV_PATH"
            check_system_packages
            ensure_virtualenv
            install_migrator
            ;;
        uninstall)
            uninstall_migrator
            ;;
        diagnostic)
            show_diagnostics
            ;;
        version)
            echo "Migrator version $VERSION"
            ;;
        *)
            print_error "Unknown command: $1"
            print_help
            exit 1
            ;;
    esac
else
    # No arguments provided, show main menu
    print_header "Migrator Installer/Launcher"
    
    if ! is_migrator_installed; then
        echo "Migrator is not installed yet. Would you like to install it?"
        echo "1) Install Migrator (recommended)"
        echo "2) Run Migrator command line"
        echo "3) Update Migrator"
        echo "4) Clean installation (remove existing venv and reinstall)"
        echo "5) Exit"
        
        read -p "Enter your choice (1-5): " choice
        case $choice in
            1)
                check_system_packages
                ensure_virtualenv
                install_migrator
                ;;
            2)
                if [ -d "$DEFAULT_VENV_PATH" ]; then
                    show_menu
                else
                    print_warning "Migrator is not installed yet. Installing first..."
                    check_system_packages
                    ensure_virtualenv
                    install_migrator
                    show_menu
                fi
                ;;
            3)
                if [ -d "$DEFAULT_VENV_PATH" ]; then
                    update_migrator
                else
                    print_warning "Migrator is not installed yet. Installing first..."
                    check_system_packages
                    ensure_virtualenv
                    install_migrator
                fi
                ;;
            4)
                rm -rf "$DEFAULT_VENV_PATH"
                check_system_packages
                ensure_virtualenv
                install_migrator
                ;;
            5)
                exit 0
                ;;
            *)
                print_error "Invalid choice."
                exit 1
                ;;
        esac
    else
        echo "Migrator is already installed. What would you like to do?"
        echo "1) Run Migrator command line"
        echo "2) Update Migrator"
        echo "3) Clean installation (remove existing venv and reinstall)"
        echo "4) Diagnostic information"
        echo "5) Uninstall Migrator"
        echo "6) Exit"
        
        read -p "Enter your choice (1-6): " choice
        case $choice in
            1)
                show_menu
                ;;
            2)
                update_migrator
                ;;
            3)
                rm -rf "$DEFAULT_VENV_PATH"
                check_system_packages
                ensure_virtualenv
                install_migrator
                ;;
            4)
                show_diagnostics
                ;;
            5)
                uninstall_migrator
                ;;
            6)
                exit 0
                ;;
            *)
                print_error "Invalid choice."
                exit 1
                ;;
        esac
    fi
fi 