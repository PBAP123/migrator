#!/bin/bash
# migrator.sh - Wrapper script for Migrator that handles virtual environment activation
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU Affero General Public License for more details.
#
# You should have received a copy of the GNU Affero General Public License
# along with this program.  If not, see <https://www.gnu.org/licenses/>.

# Default location for the virtual environment
DEFAULT_VENV_PATH="$HOME/.venvs/migrator"
SCRIPT_DIR=$(dirname "$(readlink -f "$0")")
UNIFIED_SCRIPT="$SCRIPT_DIR/migrator-init.sh"

# Function to find the migrator virtual environment
find_venv() {
    # First check if MIGRATOR_VENV environment variable is set
    if [ -n "$MIGRATOR_VENV" ] && [ -d "$MIGRATOR_VENV" ]; then
        echo "$MIGRATOR_VENV"
        return 0
    fi
    
    # Check default location
    if [ -d "$DEFAULT_VENV_PATH" ]; then
        echo "$DEFAULT_VENV_PATH"
        return 0
    fi
    
    # Check common alternative locations
    for path in "$HOME/.virtualenvs/migrator" "$HOME/venvs/migrator" "$HOME/.local/share/virtualenvs/migrator"; do
        if [ -d "$path" ]; then
            echo "$path"
            return 0
        fi
    done
    
    # No virtual environment found
    return 1
}

# Check if the unified script exists and is executable
if [ -f "$UNIFIED_SCRIPT" ] && [ -x "$UNIFIED_SCRIPT" ]; then
    # If no virtual environment exists, suggest using the unified script instead
    if ! find_venv >/dev/null; then
        echo "No Migrator virtual environment found. Using the unified installer/launcher instead."
        echo "Running: $UNIFIED_SCRIPT $@"
        exec "$UNIFIED_SCRIPT" "$@"
    fi
fi

# Check if already in a virtual environment
if [ -z "$VIRTUAL_ENV" ]; then
    # Find and activate the migrator virtual environment
    VENV_PATH=$(find_venv)
    if [ $? -eq 0 ]; then
        # Activate the virtual environment without modifying the current shell
        if [ -f "$VENV_PATH/bin/activate" ]; then
            # Run the command with the activated environment
            source "$VENV_PATH/bin/activate"
            migrator "$@"
            exit $?
        fi
    fi
    
    # If no virtual environment found or activation failed, show error with helpful message
    if [ -f "$UNIFIED_SCRIPT" ]; then
        echo "Error: Migrator virtual environment not found or not properly set up."
        echo "Please run the unified installer/launcher script instead:"
        echo "$UNIFIED_SCRIPT"
        exit 1
    else
        echo "Error: Migrator virtual environment not found or not properly set up."
        echo "Please set up a virtual environment using:"
        echo "python3 -m venv ~/.venvs/migrator"
        echo "source ~/.venvs/migrator/bin/activate"
        echo "pip install -r requirements.txt"
        echo "pip install -e ."
        exit 1
    fi
else
    # Already in a virtual environment, run migrator directly
    migrator "$@"
    exit $?
fi 