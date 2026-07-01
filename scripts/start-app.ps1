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

# Windows 演示模式: 跳过 Celery worker, 任务在 API 进程内直接跑
# (生产部署用 Linux/Docker 时改回 false, 由 Celery worker 异步消费)
$env:LLM_MOCK_MODE = "true"
$env:TASK_SYNC_MODE = "true"

Write-Host "Starting GE-VIC services (Windows demo mode)..." -ForegroundColor Green

Start-Process -FilePath "$PSScriptRoot\..\backend\.venv\Scripts\python.exe" `
    -ArgumentList "-m","uvicorn","app.main:app","--host","127.0.0.1","--port","8000" `
    -WorkingDirectory "$PSScriptRoot\..\backend" `
    -WindowStyle Hidden `
    -RedirectStandardOutput "$PSScriptRoot\..\backend.log" `
    -RedirectStandardError "$PSScriptRoot\..\backend.err"
Write-Host "  backend: http://127.0.0.1:8000"

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
Write-Host "Demo mode enabled (LLM_MOCK_MODE=true, TASK_SYNC_MODE=true):" -ForegroundColor Yellow
Write-Host "  - 使用 insulator-demo 算法 (Mock 引擎) 可看到完整 SUCCESS 流程" -ForegroundColor Yellow
Write-Host "  - LLM 富化返回预设的运维建议 (无需真实 LLM API key)" -ForegroundColor Yellow
Write-Host "  - 任务在 API 进程内同步执行 (不依赖 Celery worker)" -ForegroundColor Yellow
Write-Host ""
Write-Host "Open http://127.0.0.1:5173 in your browser." -ForegroundColor Green
Write-Host "API docs: http://127.0.0.1:8000/docs" -ForegroundColor Green
Write-Host ""
Write-Host "Logs: backend.log, frontend.log (in repo root)" -ForegroundColor Yellow