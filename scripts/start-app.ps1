# GE-VIC M0 一键启动 (本地开发版, 需先 start-services.ps1)

$env:DATABASE_URL = "postgresql+asyncpg://postgres@127.0.0.1:5432/gevic"
$env:LLM_BASE_URL = "https://dashscope.aliyuncs.com/compatible-mode/v1"
$env:LLM_API_KEY = "sk-replace-with-your-key"
$env:LLM_MODEL = "qwen-plus"
$env:LLM_MAX_INPUT_TOKENS = "4000"
$env:LLM_MAX_OUTPUT_TOKENS = "1000"
$env:MINIO_ENDPOINT = "127.0.0.1:9000"
$env:MINIO_ACCESS_KEY = "gevic_admin"
$env:MINIO_SECRET_KEY = "gevic_dev_password"
$env:MINIO_BUCKET = "gevic"
$env:MINIO_SECURE = "false"
$env:CELERY_BROKER_URL = "redis://127.0.0.1:6379/0"
$env:PYTHONPATH = "."

Write-Host "Starting GE-VIC services..." -ForegroundColor Green

# Backend
Start-Process -FilePath "$PSScriptRoot\..\backend\.venv\Scripts\python.exe" `
    -ArgumentList "-m","uvicorn","app.main:app","--host","127.0.0.1","--port","8000","--reload" `
    -WorkingDirectory "$PSScriptRoot\..\backend" `
    -WindowStyle Hidden `
    -RedirectStandardOutput "$PSScriptRoot\..\backend.log" `
    -RedirectStandardError "$PSScriptRoot\..\backend.err"
Write-Host "  backend: http://127.0.0.1:8000"

Start-Sleep 2
# Celery worker (Windows 需 -P solo -c 1 避免 prefork 权限问题)
Start-Process -FilePath "$PSScriptRoot\..\backend\.venv\Scripts\python.exe" `
    -ArgumentList "-m","celery","-A","app.tasks.celery_app","worker","-Q","inspect_queue,stats_queue","-P","solo","-c","1","--loglevel=info" `
    -WorkingDirectory "$PSScriptRoot\..\backend" `
    -WindowStyle Hidden `
    -RedirectStandardOutput "$PSScriptRoot\..\worker.log" `
    -RedirectStandardError "$PSScriptRoot\..\worker.err"
Write-Host "  celery worker: started"

Start-Sleep 2
# Frontend
$npmCmd = (Get-Command npm.cmd -ErrorAction SilentlyContinue).Source
if ($npmCmd) {
    Start-Process -FilePath $npmCmd `
        -ArgumentList "run","dev" `
        -WorkingDirectory "$PSScriptRoot\..\frontend" `
        -WindowStyle Hidden `
        -RedirectStandardOutput "$PSScriptRoot\..\frontend.log" `
        -RedirectStandardError "$PSScriptRoot\..\frontend.err"
    Write-Host "  frontend: http://127.0.0.1:5173"
}

Write-Host ""
Write-Host "All services started. Open http://127.0.0.1:5173 in your browser." -ForegroundColor Green
Write-Host "API docs: http://127.0.0.1:8000/docs" -ForegroundColor Green