# DDR Intelligence Engine - Live Demo Runner for Windows
# This script validates your environment and starts the web server.

Write-Host ""
Write-Host "=========================================================" -ForegroundColor Cyan
Write-Host "  DDR Intelligence Engine - Live Demo" -ForegroundColor Cyan
Write-Host "=========================================================" -ForegroundColor Cyan
Write-Host ""

Write-Host "[1/3] Checking Python environment..." -ForegroundColor Yellow
try {
    $PythonVersion = python --version 2>&1
    Write-Host "OK - $PythonVersion" -ForegroundColor Green
} catch {
    Write-Host "ERROR - Python not found. Please install Python 3.11+ first." -ForegroundColor Red
    exit 1
}
Write-Host ""

Write-Host "[2/3] Validating configuration..." -ForegroundColor Yellow
if (-not (Test-Path ".env")) {
    if (Test-Path ".env.example") {
        Copy-Item ".env.example" ".env"
        Write-Host "OK - .env file created from template" -ForegroundColor Green
    } else {
        Write-Host "ERROR - .env.example not found" -ForegroundColor Red
        exit 1
    }
} else {
    Write-Host "OK - .env file found" -ForegroundColor Green
}

# Check GROQ_API_KEY
$EnvContent = Get-Content ".env" -Raw
if (($EnvContent -notmatch "GROQ_API_KEY=") -or ($EnvContent -match "GROQ_API_KEY=your_api_key_here")) {
    Write-Host ""
    Write-Host "WARN - GROQ_API_KEY not configured in .env" -ForegroundColor Yellow
    Write-Host "  Get a free key at: https://console.groq.com" -ForegroundColor Gray
    Write-Host "  Then edit .env and add your key" -ForegroundColor Gray
    Write-Host ""
}
Write-Host ""

Write-Host "[3/3] Starting Flask Web Server..." -ForegroundColor Yellow
Write-Host ""
Write-Host "=========================================================" -ForegroundColor Green
Write-Host "            Environment Ready - Server Starting" -ForegroundColor Green
Write-Host "=========================================================" -ForegroundColor Green
Write-Host ""
Write-Host "OPEN IN BROWSER: http://localhost:5000" -ForegroundColor Cyan
Write-Host ""
Write-Host "Steps:" -ForegroundColor Cyan
Write-Host "  1. Upload inspection PDF + thermal PDF" -ForegroundColor Cyan
Write-Host "  2. Click 'Generate DDR Report'" -ForegroundColor Cyan
Write-Host "  3. Download the generated PDF when complete" -ForegroundColor Cyan
Write-Host ""
Write-Host "Press CTRL+C to stop the server." -ForegroundColor Cyan
Write-Host "=========================================================" -ForegroundColor Green
Write-Host ""

python app.py
