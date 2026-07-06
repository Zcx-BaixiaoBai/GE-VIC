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

if (-not $env:LLM_BASE_URL) { $env:LLM_BASE_URL = "https://dashscope.aliyuncs.com/compatible-mode/v1" }
if (-not $env:LLM_MODEL) { $env:LLM_MODEL = "qwen-vl-plus" }
$env:PYTHONPATH = (Join-Path $PSScriptRoot "..")

Write-Host ("LLM config: model=" + $env:LLM_MODEL + " base=" + $env:LLM_BASE_URL) -ForegroundColor Cyan
Write-Host ""

# Write Python test to a temp file (avoids -c escaping issues)
$pyFile = Join-Path $env:TEMP "gevic_test_llm.py"
@"
import asyncio, base64, time, struct, zlib, sys
sys.path.insert(0, r"$env:PYTHONPATH")
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
        print("  TEXT OK in " + str(dt) + "ms")
        print("  model:", r.get("model"))
        print("  content:", r.get("content"))
        print("  usage:", r.get("usage"))
    except Exception as e:
        print("  TEXT FAILED:", e)
        await c.close()
        return
    print("")
    print("Test 2: multimodal (image + text)")
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
        r = await c.chat_with_images("Describe the image briefly.", "What color is this small image?", [url], temperature=0.0)
        dt = int((time.monotonic() - t0) * 1000)
        print("  IMAGE OK in " + str(dt) + "ms")
        print("  model:", r.get("model"))
        print("  content:", r.get("content")[:200])
        print("  usage:", r.get("usage"))
    except Exception as e:
        print("  IMAGE FAILED:", e)
    await c.close()

asyncio.run(main())
"@ | Set-Content -Path $pyFile -Encoding UTF8

Write-Host "Test 1: text-only chat" -ForegroundColor Cyan
& "$PSScriptRoot\..\backend\.venv\Scripts\python.exe" $pyFile
if ($LASTEXITCODE -ne 0) { Write-Host ("Exit code: " + $LASTEXITCODE) -ForegroundColor Red }

Write-Host ""
Write-Host "If you see TEXT OK + IMAGE OK with content, your LLM is working." -ForegroundColor Green