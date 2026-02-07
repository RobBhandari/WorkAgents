#!/bin/bash
# Azure App Service startup script for Teams Bot

cd /home/site/wwwroot
python execution/teams_bug_bot.py
