# 启动本地依赖服务 (PostgreSQL from pgserver + Redis 3.2 + moto S3)

$root = Split-Path $PSScriptRoot -Parent
$pgBin = "$root\backend\.venv\Lib\site-packages\pgserver\pginstall\bin"

# 1. PostgreSQL
$pgData = "$root\pgsql-data"
if (-not (Test-Path $pgData)) {
    Write-Host "Initializing PostgreSQL data dir at $pgData..." -ForegroundColor Yellow
    New-Item -ItemType Directory -Path $pgData | Out-Null
    & "$pgBin\initdb.exe" -D $pgData -U postgres -E UTF8 --auth=trust | Out-Null
}
& "$pgBin\pg_ctl.exe" -D $pgData -l "$root\pg.log" -o "-p 5432" start
Write-Host "  PostgreSQL: 127.0.0.1:5432"

# 2. Redis
$redisExe = "$root\redis\redis-server.exe"
if (Test-Path $redisExe) {
    $port = (netstat -ano 2>$null | Select-String -Pattern "LISTENING" | Select-String -Pattern ":6379")
    if (-not $port) {
        Start-Process -FilePath $redisExe -ArgumentList "--port","6379" `
            -WindowStyle Hidden `
            -RedirectStandardOutput "$root\redis.log" `
            -RedirectStandardError "$root\redis.err"
        Start-Sleep 1
    }
    Write-Host "  Redis: 127.0.0.1:6379"
} else {
    Write-Host "  Redis not found at $redisExe. Please install." -ForegroundColor Red
}

# 3. MinIO (moto S3 stand-in)
$pyExe = "$root\backend\.venv\Scripts\python.exe"
if (Test-Path $pyExe) {
    $motoPort = (netstat -ano 2>$null | Select-String -Pattern "LISTENING" | Select-String -Pattern ":9000")
    if (-not $motoPort) {
        Start-Process -FilePath $pyExe `
            -ArgumentList "-m","moto.server","-p","9000","-H","127.0.0.1" `
            -WorkingDirectory "$root\backend" `
            -WindowStyle Hidden `
            -RedirectStandardOutput "$root\moto.log" `
            -RedirectStandardError "$root\moto.err"
        Start-Sleep 2
    }
    Write-Host "  MinIO/moto: 127.0.0.1:9000"
}

# 4. Create database & bucket
$env:Path = "$pgBin;$env:Path"
& "$pgBin\createdb.exe" -U postgres -h 127.0.0.1 gevic 2>$null
& "$pgBin\psql.exe" -U postgres -h 127.0.0.1 gevic -c "SELECT 1;" 2>$null | Out-Null
& $pyExe -c "from minio import Minio; c = Minio('127.0.0.1:9000', access_key='gevic_admin', secret_key='gevic_dev_password', secure=False); c.make_bucket('gevic') if not c.bucket_exists('gevic') else None" 2>$null
Write-Host "  Database & bucket ready"

# 5. Run migrations
& $pyExe -m alembic upgrade head 2>$null | Out-Null
Write-Host "  Migrations applied"

Write-Host ""
Write-Host "Services ready. Run scripts\start-app.ps1 to start backend + frontend." -ForegroundColor Green