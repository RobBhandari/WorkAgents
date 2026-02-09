$ErrorActionPreference = "Stop"
$kuduUrl = "https://bug-bot-rb-f0ajb5beazbadmb0.scm.uksouth-01.azurewebsites.net"

Write-Host "Uploading baseline files to Azure..." -ForegroundColor Cyan

Get-ChildItem ".\.tmp\baseline_*.json" | ForEach-Object {
    $fileName = $_.Name
    $remotePath = "/site/wwwroot/.tmp/$fileName"
    $url = "$kuduUrl/api/vfs$remotePath"
    
    Write-Host "  Uploading $fileName..." -NoNewline
    
    try {
        $content = Get-Content $_.FullName -Raw
        Invoke-WebRequest -Uri $url -Method PUT -Body $content -ContentType "application/json" -UseDefaultCredentials -ErrorAction Stop | Out-Null
        Write-Host " OK" -ForegroundColor Green
    } catch {
        Write-Host " FAILED" -ForegroundColor Red
        Write-Host "  Error: $_"
    }
}

Write-Host "`nDone!" -ForegroundColor Cyan
