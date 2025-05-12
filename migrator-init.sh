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
TUI_PATH="$PROJECT_DIR/migrator-tui.py"
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
    
    # Create TUI wrapper script
    tui_content='#!/bin/bash
# Wrapper script for migrator-tui

# Path to the unified installer
SCRIPT_DIR=$(dirname "$(readlink -f "$0")")
UNIFIED_SCRIPT="${SCRIPT_DIR}/../migrator-init.sh"

# If the unified script exists and is executable, use it
if [ -f "$UNIFIED_SCRIPT" ] && [ -x "$UNIFIED_SCRIPT" ]; then
    exec "$UNIFIED_SCRIPT" tui "$@"
else
    # Otherwise, find the migrator-tui.py file
    # Directory of the original repository
    REPO_DIR="$(cd "$(dirname "$(dirname "$(readlink -f "$0")")")"/.. && pwd)"
    TUI_SCRIPT="${REPO_DIR}/migrator-tui.py"
    
    # Check if we'"'"'re in a virtual environment
    if [ -z "$VIRTUAL_ENV" ]; then
        # Try to find and activate the migrator virtual environment
        VENV_PATH="$HOME/.venvs/migrator"
        if [ -d "$VENV_PATH" ] && [ -f "$VENV_PATH/bin/activate" ]; then
            source "$VENV_PATH/bin/activate"
        else
            echo "Error: Not in a virtual environment and could not find the Migrator virtual environment."
            echo "Please run the migrator-init.sh script first to set up the environment."
            exit 1
        fi
    fi
    
    # Run the TUI script
    if [ -f "$TUI_SCRIPT" ]; then
        exec python3 "$TUI_SCRIPT" "$@"
    else
        echo "Error: Could not find the migrator-tui.py script."
        echo "Please run the migrator-init.sh script to set up Migrator properly."
        exit 1
    fi
fi'
    
    # Write and install the TUI wrapper
    tui_target_path="$user_bin_dir/migrator-tui"
    echo "$tui_content" > "$tui_target_path"
    chmod 755 "$tui_target_path"
    print_success "TUI wrapper script created at $tui_target_path"
    
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
    
    # Ask user if they want TUI support
    echo
    print_header "Interface Options"
    echo "Migrator can be used in two ways:"
    echo "1. Command Line Interface (CLI): A simple text-based menu system"
    echo "   ✓ Works reliably on all systems"
    echo "   ✓ Provides all core functionality"
    echo "   ✓ Recommended for most users"
    echo
    echo "2. Terminal User Interface (TUI): A more visual, menu-based interface"
    echo "   ⚠ Experimental feature"
    echo "   ⚠ Has compatibility issues on many terminals"
    echo "   ⚠ Not recommended for regular use"
    echo
    print_warning "We strongly recommend using the CLI for normal operation"
    echo "You can always access the CLI even if you install TUI support."
    echo
    read -p "Would you like to install experimental TUI support? (y/n) [n]: " install_tui
    install_tui=${install_tui:-n}
    
    if [[ $install_tui =~ ^[Yy]$ ]]; then
        echo "Installing TUI dependencies..."
        "$DEFAULT_VENV_PATH/bin/pip" install "py_cui" --no-deps
        print_success "TUI dependencies installed"
        echo "Note: If you encounter issues with the TUI, you can always use the CLI."
    else
        echo "Skipping TUI installation. You can still use Migrator through the CLI."
    fi
    
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
    
    # Check if TUI dependencies are already installed
    if "$DEFAULT_VENV_PATH/bin/pip" freeze | grep -q "py_cui"; then
        echo "Updating TUI dependencies..."
        "$DEFAULT_VENV_PATH/bin/pip" install "py_cui>=0.1.4" --upgrade
    fi
    
    # Reinstall the package
    "$DEFAULT_VENV_PATH/bin/pip" install -e "$PROJECT_DIR" --upgrade
    
    # Recreate wrapper scripts to ensure they're up to date
    create_wrapper_scripts
    
    print_success "Migrator updated successfully!"
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

# Run Migrator command via the wrapper script
run_migrator() {
    if [ -x "$WRAPPER_PATH" ]; then
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

# Create and install a minimal py_cui implementation
create_minimal_pycui() {
    print_header "Creating Minimal py_cui Implementation"
    
    echo "Setting up minimal py_cui package..."
    
    # Create a temporary directory for our package
    TMP_DIR=$(mktemp -d)
    PACKAGE_DIR="$TMP_DIR/py_cui"
    
    # Create package structure
    mkdir -p "$PACKAGE_DIR"
    
    # Create __init__.py
    cat > "$PACKAGE_DIR/__init__.py" << 'EOL'
# Minimal py_cui implementation for compatibility
try:
    import curses
except ImportError:
    raise ImportError("Could not import curses. Your terminal might not support it.")

VERSION = "0.0.1"
__version__ = VERSION

# Base key constants for compatibility
class keys:
    KEY_ENTER = 10
    KEY_SPACE = ord(' ')
    KEY_ESC = 27
    KEY_BACKSPACE = 8
    KEY_DELETE = 127
    KEY_UP = 259
    KEY_DOWN = 258
    KEY_LEFT = 260
    KEY_RIGHT = 261
    
    @staticmethod
    def get_char_code(char):
        return ord(char)

class PyCUI:
    def __init__(self, rows, cols):
        self.rows = rows
        self.cols = cols
        self._widgets = {}
        
    def add_scroll_menu(self, title, row, column, row_span=1, column_span=1):
        widget = ScrollMenu(title, self)
        self._widgets[(row, column)] = widget
        return widget
        
    def add_menu(self, title, row, column, row_span=1, column_span=1):
        return self.add_scroll_menu(title, row, column, row_span, column_span)
    
    def add_text_block(self, title, row, column, row_span=1, column_span=1):
        widget = TextBlock(title, self)
        self._widgets[(row, column)] = widget
        return widget
        
    def add_block(self, title, row, column, row_span=1, column_span=1):
        return self.add_text_block(title, row, column, row_span, column_span)
        
    def add_key_command(self, *args, **kwargs):
        pass
        
    def start(self):
        try:
            import py_cui
            print("Cannot initialize TUI. Using CLI mode instead.")
        except:
            pass
        raise RuntimeError("TUI initialization failed")
        
    def stop(self):
        pass
    
    def set_title(self, title):
        pass
    
    def set_status_bar_text(self, text):
        pass
    
    def show_message_popup(self, *args, **kwargs):
        pass
    
    def show_warning_popup(self, *args, **kwargs):
        pass
    
    def show_error_popup(self, *args, **kwargs):
        pass
        
class ScrollMenu:
    def __init__(self, title, parent):
        self.title = title
        self._parent = parent
        self.items = []
        
    def add_item_list(self, items):
        self.items = items
        
    def add_key_command(self, *args, **kwargs):
        pass
        
    def get(self):
        return self.items[0] if self.items else ""
        
class TextBlock:
    def __init__(self, title, parent):
        self.title = title
        self._parent = parent
        self._text = ""
        
    def set_text(self, text):
        self._text = text
        
    def get_text(self):
        return self._text
EOL
    
    # Create setup.py
    cat > "$TMP_DIR/setup.py" << 'EOL'
from setuptools import setup, find_packages

setup(
    name="py_cui",
    version="0.0.1",
    packages=find_packages(),
    description="Minimal py_cui implementation for Migrator compatibility",
)
EOL
    
    # Install the package
    echo "Installing minimal py_cui package..."
    (cd "$TMP_DIR" && "$DEFAULT_VENV_PATH/bin/pip" install -e .)
    
    # Clean up
    rm -rf "$TMP_DIR"
    
    print_success "Minimal py_cui package installed"
}

# Launch the TUI directly
run_tui() {
    print_header "Launching Migrator TUI"
    
    # First, check if the TUI script exists
    if [ ! -f "$TUI_PATH" ]; then
        print_error "TUI script not found at $TUI_PATH"
        print_warning "Using command line interface instead."
        show_cli_menu
        return
    fi
    
    # Check if py_cui is installed
    source "$DEFAULT_VENV_PATH/bin/activate"
    if ! "$DEFAULT_VENV_PATH/bin/pip" freeze | grep -q "py_cui"; then
        print_warning "TUI dependencies not installed."
        echo "The Terminal User Interface requires the py_cui library."
        read -p "Would you like to install it now? (y/n) [y]: " install_tui
        install_tui=${install_tui:-y}
        
        if [[ $install_tui =~ ^[Yy]$ ]]; then
            echo "Installing TUI dependencies..."
            "$DEFAULT_VENV_PATH/bin/pip" install "py_cui" --no-deps
            print_success "TUI dependencies installed"
        else
            print_warning "Using command line interface instead."
            show_cli_menu
            return
        fi
    fi
    
    # Try to run TUI with error handling
    if python3 "$TUI_PATH" 2>/tmp/migrator_tui_error.log; then
        # TUI launched successfully
        return 0
    else
        print_error "TUI failed to launch due to compatibility issues."
        print_warning "This is often due to py_cui library version mismatches or terminal limitations."
        
        # Show error details if available
        if [ -f "/tmp/migrator_tui_error.log" ] && [ -s "/tmp/migrator_tui_error.log" ]; then
            echo
            echo "Error details:"
            tail -5 /tmp/migrator_tui_error.log
            echo
        fi
        
        # Offer to try an alternative py_cui version
        echo
        echo "Would you like to try installing a different version of py_cui?"
        echo "1) Try version 0.1.4 (newest recommended)"
        echo "2) Try version 0.0.3 (more compatible with some systems)"
        echo "3) Try minimal version (most compatible)"
        echo "4) Skip and use CLI instead"
        
        read -p "Enter your choice (1-4): " cui_version
        case $cui_version in
            1)
                "$DEFAULT_VENV_PATH/bin/pip" uninstall -y py_cui || true
                "$DEFAULT_VENV_PATH/bin/pip" install "py_cui==0.1.4" --no-deps
                print_success "Installed py_cui 0.1.4"
                echo "Trying TUI again..."
                if python3 "$TUI_PATH" 2>/dev/null; then
                    return 0
                else
                    print_error "TUI still fails to launch. Using CLI instead."
                fi
                ;;
            2)
                "$DEFAULT_VENV_PATH/bin/pip" uninstall -y py_cui || true
                "$DEFAULT_VENV_PATH/bin/pip" install "py_cui==0.0.3" --no-deps
                print_success "Installed py_cui 0.0.3"
                echo "Trying TUI again..."
                if python3 "$TUI_PATH" 2>/dev/null; then
                    return 0
                else
                    print_error "TUI still fails to launch. Using CLI instead."
                fi
                ;;
            3)
                # Install our minimal py_cui implementation
                "$DEFAULT_VENV_PATH/bin/pip" uninstall -y py_cui || true
                create_minimal_pycui
                echo "Trying TUI again..."
                if python3 "$TUI_PATH" 2>/dev/null; then
                    return 0
                else
                    print_error "TUI still fails to launch. Using CLI instead."
                fi
                ;;
            4)
                print_warning "Using command line interface instead."
                ;;
        esac
        
        echo
        echo "You can use the command line interface instead:"
        show_cli_menu
    fi
}

# Show a simple command line menu as fallback when TUI fails
show_cli_menu() {
    echo
    echo "Available commands:"
    echo "1) scan           - Scan system packages and configurations"
    echo "2) backup         - Create a backup of your system"
    echo "3) restore        - Restore from a backup"
    echo "4) compare        - Compare current system with a backup"
    echo "5) check          - Check for changes since last scan"
    echo "6) service        - Manage Migrator service"
    echo "7) help           - Show detailed help"
    echo "q) quit           - Exit the menu"
    echo
    read -p "Enter command (or q to quit): " cmd
    
    case $cmd in
        1|scan)
            run_migrator scan
            ;;
        2|backup)
            read -p "Backup directory (leave empty for default): " backup_dir
            if [ -z "$backup_dir" ]; then
                # Run with no arguments to use default directory
                run_migrator backup
            else
                run_migrator backup "$backup_dir"
            fi
            ;;
        3|restore)
            read -p "Path to backup file: " backup_file
            if [ -n "$backup_file" ]; then
                run_migrator restore "$backup_file" --dry-run
                read -p "Proceed with restore? (y/n): " confirm
                if [[ $confirm =~ ^[Yy]$ ]]; then
                    run_migrator restore "$backup_file" --execute
                fi
            else
                print_error "No backup file specified."
            fi
            ;;
        4|compare)
            read -p "Path to backup file: " backup_file
            if [ -n "$backup_file" ]; then
                run_migrator compare "$backup_file"
            else
                print_error "No backup file specified."
            fi
            ;;
        5|check)
            run_migrator check
            ;;
        6|service)
            echo "Service options:"
            echo "a) Install as system service"
            echo "b) Install as user service"
            echo "c) Remove service"
            echo "d) Check service status"
            read -p "Enter option: " svc_opt
            
            case $svc_opt in
                a)
                    run_migrator install-service
                    ;;
                b)
                    run_migrator install-service --user
                    ;;
                c)
                    run_migrator remove-service
                    ;;
                d)
                    if [ -f "/etc/systemd/system/migrator.service" ]; then
                        systemctl status migrator.service
                    elif [ -f "$HOME/.config/systemd/user/migrator.service" ]; then
                        systemctl --user status migrator.service
                    else
                        print_error "No Migrator service found."
                    fi
                    ;;
                *)
                    print_error "Invalid option."
                    ;;
            esac
            ;;
        7|help)
            show_help
            ;;
        q|quit|exit)
            return 0
            ;;
        *)
            print_error "Invalid command."
            ;;
    esac
    
    # Show the menu again
    echo
    read -p "Press Enter to continue..." _
    show_cli_menu
}

# Clean installation (remove virtual env and reinstall)
clean_install() {
    print_header "Performing Clean Installation"
    echo "This will remove the existing virtual environment and create a fresh installation."
    read -p "Continue? (y/n) " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        echo "Removing existing installation..."
        rm -rf "$DEFAULT_VENV_PATH"
        print_success "Old installation removed"
        
        ensure_virtualenv
        install_migrator
        print_success "Clean installation completed successfully!"
    else
        echo "Clean installation cancelled."
    fi
}

# Show the main menu
show_menu() {
    clear
    print_header "Migrator - Linux System Migration Utility v$VERSION"
    
    echo "This utility helps you track and migrate your Linux system configuration."
    echo
    
    # Check installation status
    venv_exists=false
    if [ -d "$DEFAULT_VENV_PATH" ]; then
        venv_exists=true
        print_success "Virtual environment: Installed"
    else
        print_warning "Virtual environment: Not found"
    fi
    
    migrator_installed=false
    if is_migrator_installed; then
        migrator_installed=true
        print_success "Migrator: Installed"
    else
        print_warning "Migrator: Not properly installed"
    fi
    
    if [ -x "$WRAPPER_PATH" ]; then
        print_success "Wrapper script: Found"
    else
        print_warning "Wrapper script: Not found"
    fi
    
    # Check for TUI dependencies
    if [ -d "$DEFAULT_VENV_PATH" ] && "$DEFAULT_VENV_PATH/bin/pip" freeze 2>/dev/null | grep -q "py_cui"; then
        print_success "TUI support: Installed"
    else
        print_warning "TUI support: Not installed"
    fi
    
    echo -e "\nSelect an option:"
    echo "1) Launch Migrator TUI (Terminal User Interface - Experimental)"
    echo "2) Run Migrator command line (CLI - Recommended)"
    
    if [ "$migrator_installed" = true ]; then
        echo "3) Update Migrator (when you've pulled new changes)"
    else
        echo "3) Install Migrator"
    fi
    
    echo "4) Clean installation (remove and reinstall)"
    echo "5) Fix PATH environment variable"
    echo "6) Exit"
    
    read -p "Enter your choice (1-6): " choice
    case $choice in
        1)
            if [ "$migrator_installed" = true ]; then
                run_tui
            else
                print_warning "Migrator not installed. Installing first..."
                ensure_virtualenv
                install_migrator
                run_tui
            fi
            ;;
        2)
            if [ "$migrator_installed" = true ]; then
                echo
                print_header "Migrator Command Line Interface"
                echo "The CLI provides access to all Migrator functionality in a simple text format."
                show_cli_menu
            else
                print_warning "Migrator not installed. Installing first..."
                ensure_virtualenv
                install_migrator
                echo
                print_header "Migrator Command Line Interface"
                echo "The CLI provides access to all Migrator functionality in a simple text format."
                show_cli_menu
            fi
            ;;
        3)
            if [ "$migrator_installed" = true ]; then
                update_migrator
            else
                ensure_virtualenv
                install_migrator
            fi
            show_menu
            ;;
        4)
            clean_install
            show_menu
            ;;
        5)
            fix_path
            show_menu
            ;;
        6)
            exit 0
            ;;
        *)
            print_error "Invalid choice. Please try again."
            show_menu
            ;;
    esac
}

# Show help information
show_help() {
    print_header "Migrator Help"
    echo "Migrator is a system migration utility for Linux that tracks installed packages"
    echo "and configuration files, making it easy to migrate to a new system."
    echo
    echo "Core Features:"
    echo "  • Multi-Distribution Support - Works on any Linux distribution"
    echo "  • Package Tracking - Monitors packages from various sources"
    echo "  • Configuration Tracking - Saves and restores your configuration files"
    echo "  • Desktop Environment Backup - Preserves your desktop setup"
    echo
    echo "Basic Commands:"
    echo "  scan                  - Scan your system for packages and configurations"
    echo "  backup [directory]    - Create a backup (optionally specify a directory)"
    echo "  restore <backup_file> - Restore from a backup file (use --dry-run first!)"
    echo "  check                 - Check for system changes since last scan"
    echo "  compare <backup_file> - Compare current system with a backup"
    echo
    echo "Installation/Service:"
    echo "  update                - Update Migrator after pulling code changes"
    echo "  install-service       - Install Migrator as a system service"
    echo "  remove-service        - Remove the Migrator service"
    echo
    echo "Special Commands:"
    echo "  tui                   - Launch the Terminal User Interface"
    echo "  help                  - Show this help message"
    echo
    echo "For more detailed information, see the README.md file."
}

# Main function
main() {
    # Check for system packages first
    check_system_packages
    
    # If arguments are provided, handle them directly
    if [ $# -gt 0 ]; then
        # If first argument is "tui", run the TUI
        if [ "$1" = "tui" ]; then
            shift  # Remove 'tui' argument
            
            # Make sure migrator is installed
            if ! is_migrator_installed; then
                # If not in virtualenv and it doesn't exist yet, create it
                if ! in_virtualenv && [ ! -d "$DEFAULT_VENV_PATH" ]; then
                    ensure_virtualenv
                    install_migrator
                # If virtualenv exists but migrator not installed
                elif [ -d "$DEFAULT_VENV_PATH" ]; then
                    print_warning "Migrator not properly installed in existing virtualenv."
                    install_migrator
                fi
            fi
            
            run_tui "$@"
        # If first argument is "update", update migrator
        elif [ "$1" = "update" ]; then
            shift  # Remove 'update' argument
            
            if [ -d "$DEFAULT_VENV_PATH" ]; then
                update_migrator
            else
                print_warning "No existing installation found. Installing fresh..."
                ensure_virtualenv
                install_migrator
            fi
        # If first argument is "help", show help
        elif [ "$1" = "help" ]; then
            show_help
        # Otherwise, run migrator with all arguments
        else
            # Make sure migrator is installed
            if ! is_migrator_installed; then
                # If not in virtualenv and it doesn't exist yet, create it
                if ! in_virtualenv && [ ! -d "$DEFAULT_VENV_PATH" ]; then
                    ensure_virtualenv
                    install_migrator
                # If virtualenv exists but migrator not installed
                elif [ -d "$DEFAULT_VENV_PATH" ]; then
                    print_warning "Migrator not properly installed in existing virtualenv."
                    install_migrator
                fi
            fi
            
            run_migrator "$@"
        fi
    else
        # Show the interactive menu
        show_menu
    fi
}

# Run the main function
main "$@" 