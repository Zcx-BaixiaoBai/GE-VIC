# 启动本地依赖服务 (PostgreSQL from pgserver + Redis 3.2 + 真实 MinIO 持久化)

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

# 3. MinIO (真实 server, 持久化到 ./minio-data; 取代内存版 moto)
$pyExe = "$root\backend\.venv\Scripts\python.exe"
$minioExe = "$root\minio\minio.exe"
$minioData = "$root\minio-data"
if (Test-Path $minioExe) {
    $minioPort = (netstat -ano 2>$null | Select-String -Pattern "LISTENING" | Select-String -Pattern ":9000")
    if (-not $minioPort) {
        if (-not (Test-Path $minioData)) { New-Item -ItemType Directory -Path $minioData | Out-Null }
        $env:MINIO_ROOT_USER = "gevic_admin"
        $env:MINIO_ROOT_PASSWORD = "gevic_dev_password"
        Start-Process -FilePath $minioExe `
            -ArgumentList "server","$minioData","--address","127.0.0.1:9000","--console-address","127.0.0.1:9001" `
            -WorkingDirectory "$root" `
            -WindowStyle Hidden `
            -RedirectStandardOutput "$root\minio.log" `
            -RedirectStandardError "$root\minio.err"
        # 等待 MinIO 在 9000 监听 (最多 30s)
        for ($i = 0; $i -lt 30; $i++) {
            $p = (netstat -ano 2>$null | Select-String -Pattern "LISTENING" | Select-String -Pattern ":9000")
            if ($p) { break }
            Start-Sleep 1
        }
    }
    Write-Host "  MinIO: 127.0.0.1:9000 (console :9001, data: $minioData)"
} else {
    Write-Host "  MinIO binary not found at $minioExe (expected minio/minio.exe)." -ForegroundColor Red
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
