# Quick LLM connectivity test (no browser needed)
# Usage: powershell -ExecutionPolicy Bypass -File scripts\test-llm.ps1

# Load .env.local if present
$envFile = Join-Path $PSScriptRoot "..\.env.local"
if (Test-Path $envFile) {
    Get-Content $envFile | ForEach-Object {
        $line = $_.Trim()
        if ($line -and -not $line.StartsWith("#") -and $line -match "^([^=]+)=(.*)$") {
            [Environment]::SetEnvironmentVariable($matches[1].Trim(), $matches[2].Trim(), "Process")
        }
    }
}

# Fill in defaults (matching start-app-real.ps1)
$env:DATABASE_URL = "postgresql+asyncpg://postgres@127.0.0.1:5432/gevic"
if (-not $env:LLM_BASE_URL) { $env:LLM_BASE_URL = "https://dashscope.aliyuncs.com/compatible-mode/v1" }
if (-not $env:LLM_MODEL) { $env:LLM_MODEL = "qwen-vl-plus" }
$env:PYTHONPATH = ".."

Write-Host "Test 1: text-only chat" -ForegroundColor Cyan
Write-Host ("  model=" + $env:LLM_MODEL) -ForegroundColor DarkGray
& "..\backend\.venv\Scripts\python.exe" -c @'
import asyncio, time
from app.config import get_settings
from app.services.llm_client import LLMClient
async def main():
    s = get_settings()
    print("  LLM_MOCK_MODE:", s.llm_mock_mode)
    c = LLMClient(s)
    t0 = time.monotonic()
    try:
        r = await c.chat("You are a test assistant.", "Reply with one word: PONG", temperature=0.0)
        dt = int((time.monotonic() - t0) * 1000)
        print("  OK in " + str(dt) + "ms")
        print("  model:", r.get("model"))
        print("  content:", r.get("content"))
        print("  usage:", r.get("usage"))
    except Exception as e:
        print("  FAILED:", e)
    finally:
        await c.close()
asyncio.run(main())
'@
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

Write-Host ""
Write-Host "Test 2: multimodal (image + text)" -ForegroundColor Cyan
& "..\backend\.venv\Scripts\python.exe" -c @'
import asyncio, base64, time, struct, zlib
from app.config import get_settings
from app.services.llm_client import LLMClient
async def main():
    s = get_settings()
    c = LLMClient(s)
    def make_png():
        w, h = 4, 4
        raw = b"".join(b"\xff\x00\x00" * w for _ in range(h))
        def chunk(t, d):
            return struct.pack(">I", len(d)) + t + d + struct.pack(">I", zlib.crc32(t + d) & 0xffffffff)
        sig = b"\x89PNG\r\n\x1a\n"
        ihdr = struct.pack(">IIBBBBB", w, h, 8, 2, 0, 0, 0)
        idat = zlib.compress(raw)
        return sig + chunk(b"IHDR", ihdr) + chunk(b"IDAT", idat) + chunk(b"IEND", b"")
    b64 = base64.b64encode(make_png()).decode()
    url = "data:image/png;base64," + b64
    t0 = time.monotonic()
    try:
        r = await c.chat_with_images("Describe the image.", "What color is this?", [url], temperature=0.0)
        dt = int((time.monotonic() - t0) * 1000)
        print("  OK in " + str(dt) + "ms")
        print("  model:", r.get("model"))
        print("  content:", r.get("content")[:200])
        print("  usage:", r.get("usage"))
    except Exception as e:
        print("  FAILED:", e)
    finally:
        await c.close()
asyncio.run(main())
'@

Write-Host ""
Write-Host "Both tests done. If you see OK + content, your LLM is working." -ForegroundColor Green