# Create Deployment Package for Teams Bot
# Includes updated code and baseline files

Write-Host "Creating deployment package..." -ForegroundColor Cyan

# Create temp dir for deployment
$deployDir = 'deploy_temp'
if (Test-Path $deployDir) {
    Remove-Item -Recurse -Force $deployDir
}
New-Item -ItemType Directory -Path $deployDir | Out-Null

# Copy files
Write-Host "Copying requirements.txt..." -ForegroundColor Yellow
Copy-Item requirements.txt $deployDir\

Write-Host "Copying runtime.txt..." -ForegroundColor Yellow
Copy-Item runtime.txt $deployDir\

Write-Host "Copying execution folder..." -ForegroundColor Yellow
Copy-Item -Recurse execution $deployDir\

# Create .tmp and copy baseline files only
Write-Host "Copying baseline files..." -ForegroundColor Yellow
New-Item -ItemType Directory -Path $deployDir\.tmp | Out-Null
Copy-Item .tmp\baseline_*.json $deployDir\.tmp\

# Create ZIP
Write-Host "Creating ZIP file..." -ForegroundColor Yellow
if (Test-Path teams-bot-deploy.zip) {
    Remove-Item teams-bot-deploy.zip -Force
}
Compress-Archive -Path $deployDir\* -DestinationPath teams-bot-deploy.zip -Force

# Cleanup
Write-Host "Cleaning up..." -ForegroundColor Yellow
Remove-Item -Recurse -Force $deployDir

Write-Host ""
Write-Host "SUCCESS!" -ForegroundColor Green
Write-Host "Deployment package created: teams-bot-deploy.zip" -ForegroundColor Green
Write-Host ""
Write-Host "Next steps:" -ForegroundColor Cyan
Write-Host "1. Upload to Azure Cloud Shell" -ForegroundColor White
Write-Host "2. Run: az webapp deployment source config-zip --resource-group bug-position-bot-rg --name bug-bot-rb --src ~/teams-bot-deploy.zip" -ForegroundColor White
