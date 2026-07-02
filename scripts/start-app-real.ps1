# GE-VIC M0 real-mode starter (uses real LLM API key)

# Difference from start-app.ps1 (demo mode):
#   - LLM_MOCK_MODE=false: actually calls the LLM (no preset responses)
#   - LLM_MODEL must be a vision-capable model (qwen-vl-plus / gpt-4o) for multimodal
#   - enrichment (LLM giving maintenance suggestions) uses the same model

# Usage:
#   1. Prepare .env.local in repo root, content:
#        LLM_API_KEY=sk-xxxxxxxxxxxxxxxxxxxx
#        LLM_BASE_URL=https://dashscope.aliyuncs.com/compatible-mode/v1   (optional, default DashScope)
#        LLM_MODEL=qwen-vl-plus                                          (optional, default qwen-vl-plus)
#   2. Run: powershell -ExecutionPolicy Bypass -File scripts\start-app-real.ps1
#   3. Open http://127.0.0.1:5173/upload
#   4. Upload an image to multimodal-inspector algorithm

# Recommended OpenAI-compatible providers:
#   - DashScope (Aliyun):  sk-xxx, base_url=https://dashscope.aliyuncs.com/compatible-mode/v1, vision=qwen-vl-plus
#   - OpenAI:              sk-xxx, base_url=https://api.openai.com/v1,                       vision=gpt-4o / gpt-4o-mini
#   - DeepSeek:            sk-xxx, base_url=https://api.deepseek.com/v1,                     text only (no multimodal)
#   - Ollama (local):      base_url=http://localhost:11434/v1,                              vision=llava

# ---- Load .env.local (if exists) ----
$envFile = Join-Path $PSScriptRoot "..\.env.local"
if (Test-Path $envFile) {
    Write-Host "Loading .env.local..." -ForegroundColor Cyan
    Get-Content $envFile | ForEach-Object {
        $line = $_.Trim()
        if ($line -and -not $line.StartsWith("#") -and $line -match "^([^=]+)=(.*)$") {
            $key = $matches[1].Trim()
            $val = $matches[2].Trim()
            [Environment]::SetEnvironmentVariable($key, $val, "Process")
            Write-Host ("  " + $key + " = " + $val) -ForegroundColor DarkGray
        }
    }
}

# ---- Required check ----
if (-not $env:LLM_API_KEY -or $env:LLM_API_KEY -like "*replace*" -or $env:LLM_API_KEY -like "*your-key*") {
    Write-Host ""
    Write-Host "ERROR: LLM_API_KEY not set or still placeholder" -ForegroundColor Red
    Write-Host ""
    Write-Host "Step 1: create .env.local in repo root:" -ForegroundColor Yellow
    Write-Host "  LLM_API_KEY=sk-xxxxxxxxxxxxxxxxxxxx" -ForegroundColor White
    Write-Host "  LLM_BASE_URL=https://dashscope.aliyuncs.com/compatible-mode/v1" -ForegroundColor White
    Write-Host "  LLM_MODEL=qwen-vl-plus" -ForegroundColor White
    Write-Host ""
    Write-Host "Step 2: re-run this script" -ForegroundColor Yellow
    Write-Host ""
    Write-Host "Free / easy providers:" -ForegroundColor Yellow
    Write-Host "  DashScope (Aliyun):  https://dashscope.console.aliyun.com  signup gives 2M free tokens" -ForegroundColor White
    Write-Host "  Ollama (local):      https://ollama.com                    free, but you download the model" -ForegroundColor White
    exit 1
}

# ---- Defaults ----
if (-not $env:LLM_BASE_URL) { $env:LLM_BASE_URL = "https://dashscope.aliyuncs.com/compatible-mode/v1" }
if (-not $env:LLM_MODEL)    { $env:LLM_MODEL = "qwen-vl-plus" }

# ---- DB / storage / Celery ----
$env:DATABASE_URL = "postgresql+asyncpg://postgres@127.0.0.1:5432/gevic"
$env:MINIO_ENDPOINT = "127.0.0.1:9000"
$env:MINIO_ACCESS_KEY = "gevic_admin"
$env:MINIO_SECRET_KEY = "gevic_dev_password"
$env:MINIO_BUCKET = "gevic"
$env:MINIO_SECURE = "false"
$env:CELERY_BROKER_URL = "redis://127.0.0.1:6379/0"
$env:PYTHONPATH = "."

# ---- Key: turn off mock ----
$env:LLM_MOCK_MODE = "false"
# Windows dev still runs tasks synchronously in the API process (no Celery worker needed).
# Set to "false" + start a Celery worker for true async.
$env:TASK_SYNC_MODE = "true"

# ---- Stop old backend ----
Get-CimInstance Win32_Process -Filter "Name='python.exe'" | Where-Object {
    $_.CommandLine -match "uvicorn" -and $_.CommandLine -match "127.0.0.1"
} | ForEach-Object { Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue }
Start-Sleep -Seconds 1

# ---- Start backend ----
Write-Host ""
Write-Host "Starting GE-VIC backend in REAL LLM mode..." -ForegroundColor Green
Write-Host ("  Base URL:  " + $env:LLM_BASE_URL) -ForegroundColor DarkGray
Write-Host ("  Model:     " + $env:LLM_MODEL) -ForegroundColor DarkGray
$keyPreview = $env:LLM_API_KEY.Substring(0, [Math]::Min(8, $env:LLM_API_KEY.Length)) + "..."
Write-Host ("  API Key:   " + $keyPreview) -ForegroundColor DarkGray
Write-Host "  Mock mode: OFF (real LLM calls)" -ForegroundColor DarkGray
Write-Host "  Sync mode: ON  (tasks in API process, no Celery worker)" -ForegroundColor DarkGray
Write-Host ""

Start-Process -FilePath "$PSScriptRoot\..\backend\.venv\Scripts\python.exe" `
    -ArgumentList "-m","uvicorn","app.main:app","--host","127.0.0.1","--port","8000" `
    -WorkingDirectory "$PSScriptRoot\..\backend" `
    -WindowStyle Hidden `
    -RedirectStandardOutput "$PSScriptRoot\..\backend.log" `
    -RedirectStandardError "$PSScriptRoot\..\backend.err"
Write-Host "  backend: http://127.0.0.1:8000" -ForegroundColor Green

# ---- Start frontend (if not running) ----
$npmCmd = (Get-Command npm.cmd -ErrorAction SilentlyContinue).Source
$frontendPort = 5173
$frontendRunning = (Get-NetTCPConnection -LocalPort $frontendPort -State Listen -ErrorAction SilentlyContinue) -ne $null
if ($npmCmd -and -not $frontendRunning) {
    Start-Process -FilePath $npmCmd `
        -ArgumentList "run","dev" `
        -WorkingDirectory "$PSScriptRoot\..\frontend" `
        -WindowStyle Hidden `
        -RedirectStandardOutput "$PSScriptRoot\..\frontend.log" `
        -RedirectStandardError "$PSScriptRoot\..\frontend.err"
    Write-Host "  frontend: http://127.0.0.1:5173" -ForegroundColor Green
} elseif ($frontendRunning) {
    Write-Host ("  frontend: already running on port " + $frontendPort) -ForegroundColor DarkGray
}

Write-Host ""
Write-Host "Open http://127.0.0.1:5173/upload" -ForegroundColor Green
Write-Host "Upload an image to multimodal-inspector to test real LLM" -ForegroundColor Green
Write-Host ""
Write-Host "Quick API test:" -ForegroundColor Yellow
Write-Host "  curl -X POST http://127.0.0.1:8000/api/v1/settings/llm/test -H "X-Inspector-Id: dev"" -ForegroundColor White
Write-Host ""