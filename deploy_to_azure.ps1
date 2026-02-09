# Azure Web App Deployment Script
# Deploys the Teams bot to Azure using ZIP Deploy API

param(
    [Parameter(Mandatory=$true)]
    [string]$Username,

    [Parameter(Mandatory=$true)]
    [SecureString]$Password,

    [string]$AppName = "bug-bot-rb",
    [string]$ZipFile = "teams-bot-deploy.zip"
)

Write-Host "Deploying Teams Bot to Azure Web App: $AppName" -ForegroundColor Green
Write-Host "=" * 60

# Construct the deployment URL for newer Azure region format
$deployUrl = "https://bug-bot-rb-f0ajb5beazbadmb0.scm.uksouth-01.azurewebsites.net/api/zipdeploy"

# Check if ZIP file exists
if (-not (Test-Path $ZipFile)) {
    Write-Host "ERROR: ZIP file not found: $ZipFile" -ForegroundColor Red
    exit 1
}

Write-Host "ZIP file found: $ZipFile" -ForegroundColor Green
$zipSize = (Get-Item $ZipFile).Length / 1KB
Write-Host "File size: $([math]::Round($zipSize, 2)) KB"
Write-Host ""

# Create credentials
# Convert SecureString to plain text for Basic Auth (only in memory)
$PlainPassword = [System.Net.NetworkCredential]::new('', $Password).Password
$base64Auth = [Convert]::ToBase64String([Text.Encoding]::ASCII.GetBytes("$Username`:$PlainPassword"))
$headers = @{
    Authorization = "Basic $base64Auth"
}

Write-Host "Uploading to Azure..." -ForegroundColor Yellow
Write-Host "This may take 1-2 minutes..."
Write-Host ""

try {
    # Deploy using Invoke-RestMethod
    Invoke-RestMethod -Uri $deployUrl `
        -Method POST `
        -InFile $ZipFile `
        -Headers $headers `
        -ContentType "application/zip" `
        -TimeoutSec 300 `
        -Verbose | Out-Null

    Write-Host ""
    Write-Host "=" * 60 -ForegroundColor Green
    Write-Host "SUCCESS! Bot deployed to Azure!" -ForegroundColor Green
    Write-Host "=" * 60 -ForegroundColor Green
    Write-Host ""
    Write-Host "Next steps:" -ForegroundColor Cyan
    Write-Host "1. Go to Azure Portal > bug-bot-rb > Log stream" -ForegroundColor White
    Write-Host "2. Restart the Web App" -ForegroundColor White
    Write-Host "3. Watch for 'Teams Bug Position Bot is running' message" -ForegroundColor White
    Write-Host ""

} catch {
    Write-Host ""
    Write-Host "ERROR: Deployment failed" -ForegroundColor Red
    Write-Host $_.Exception.Message -ForegroundColor Red
    Write-Host ""
    Write-Host "Troubleshooting:" -ForegroundColor Yellow
    Write-Host "- Check that username/password are correct" -ForegroundColor White
    Write-Host "- Verify app name is: $AppName" -ForegroundColor White
    Write-Host "- Ensure you have internet connection" -ForegroundColor White
    exit 1
}
