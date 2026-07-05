# ارسال پروژه به GitHub
# ۱) Git for Windows را نصب کنید: https://git-scm.com/download/win
# ۲) یک repo خالی در GitHub بسازید (بدون README)
# ۳) اجرا از ریشه پروژه:
#    powershell -ExecutionPolicy Bypass -File hosting/push-github.ps1

$ErrorActionPreference = "Stop"
Set-Location (Split-Path $PSScriptRoot -Parent)

if (-not (Get-Command git -ErrorAction SilentlyContinue)) {
    Write-Host "Git is not installed. Download: https://git-scm.com/download/win" -ForegroundColor Red
    exit 1
}

if (-not (Test-Path ".git")) {
    git init
    git branch -M main
}

git add .
git status

$msg = "Initial commit: same-Dashboard (Django + React)"
git commit -m $msg 2>$null
if ($LASTEXITCODE -ne 0) {
    Write-Host "No new commit (maybe already committed or nothing to commit)." -ForegroundColor Yellow
}

$remote = git remote get-url origin 2>$null
if (-not $remote) {
    $url = Read-Host "GitHub repo URL (e.g. https://github.com/USERNAME/same-Dashboard.git)"
    if ($url) {
        git remote add origin $url
    } else {
        Write-Host "Remote URL required." -ForegroundColor Red
        exit 1
    }
}

git push -u origin main
Write-Host "Pushed to GitHub." -ForegroundColor Green
