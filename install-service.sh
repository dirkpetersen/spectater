#!/bin/bash

# Exit on any error
set -e

# Get the current directory and user
CURRENT_DIR=$(pwd)
CURRENT_USER=$(whoami)

# Ensure Python is installed
if ! command -v python3 &> /dev/null; then
  echo "Python3 is not installed. Please install it first."
  exit 1
fi

if ! [[ -f .env ]]; then 
  echo ".env file does not exist in current directory"
  exit 1
fi

source .env
app_lower=${APP_NAME,,}

# Create the systemd user directory if it doesn't exist
mkdir -p ~/.config/systemd/user/

# Create the service file
cat > ~/.config/systemd/user/${app_lower}.service << EOL
[Unit]
Description=EasyGrouper App Service
After=network.target

[Service]
Type=simple
WorkingDirectory=${CURRENT_DIR}
Environment=PYTHONUNBUFFERED=1
EnvironmentFile=${CURRENT_DIR}/.env
ExecStart=${CURRENT_DIR}/app.py
Restart=always
RestartSec=1

[Install]
WantedBy=default.target
EOL

# Reload systemd daemon
systemctl --user daemon-reload

# Enable and start the service
systemctl --user enable ${app_lower}.service
systemctl --user start ${app_lower}.service

# Check the service status
systemctl --user status ${app_lower}.service

echo "${APP_NAME} has been installed as a user service."
echo "You can check the logs using: journalctl --user-unit ${app_lower}.service"
echo "To stop the service: systemctl --user stop ${app_lower}.service"
echo "To start the service: systemctl --user start ${app_lower}.service"
echo "To restart the service: systemctl --user restart ${app_lower}.service"
echo ""
echo "This service requires OS packages python3-flask and python3-dotenv"
