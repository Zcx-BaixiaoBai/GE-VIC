# Real LLM testing guide

## Current state

M0 demo mode (default):
- `LLM_MOCK_MODE=true`: all LLM calls return preset responses, no token usage, no API key needed
- `TASK_SYNC_MODE=true`: tasks run synchronously in the API process, no Celery worker
- Database/Redis/MinIO are all real

Good for: demo, UI debugging, end-to-end flow validation

## Switch to real mode

### 1. Get an API key

Recommended providers (in order):

| Provider | Sign up | Vision model | Notes |
|----------|---------|--------------|-------|
| **DashScope (Aliyun)** | https://dashscope.console.aliyun.com | `qwen-vl-plus` | China direct, 2M free tokens on signup |
| OpenAI | https://platform.openai.com | `gpt-4o-mini` | Needs VPN, paid |
| Ollama (local) | https://ollama.com | `llava` | Free, but you download the model (~4GB) |
| DeepSeek | https://platform.deepseek.com | - | Text only, no multimodal |

### 2. Create `.env.local`

```bash
cp .env.local.example .env.local
# edit .env.local, fill in your key
```

**DashScope example:**
```
LLM_API_KEY=sk-abc123def456...
LLM_BASE_URL=https://dashscope.aliyuncs.com/compatible-mode/v1
LLM_MODEL=qwen-vl-plus
```

**OpenAI example:**
```
LLM_API_KEY=sk-proj-...
LLM_BASE_URL=https://api.openai.com/v1
LLM_MODEL=gpt-4o-mini
```

**Ollama local example:**
```
LLM_API_KEY=ollama
LLM_BASE_URL=http://localhost:11434/v1
LLM_MODEL=llava
```

### 3. One-click start (real mode)

```powershell
powershell -ExecutionPolicy Bypass -File scripts\start-app-real.ps1
```

Script will:
1. Load key from `.env.local`
2. Disable mock (`LLM_MOCK_MODE=false`)
3. Kill any old backend
4. Start backend (real mode)
5. Start frontend (if not running)

### 4. No browser needed - quick key check

```powershell
powershell -ExecutionPolicy Bypass -File scripts\test-llm.ps1
```

Runs two tests: text chat + image chat. Seeing `OK` + real content means your LLM is configured correctly.

### 5. Verify via API

```powershell
curl -X POST http://127.0.0.1:8000/api/v1/settings/llm/test -H "X-Inspector-Id: dev"
```

Or browser: http://127.0.0.1:5173/settings -> LLM model tab -> "Run test"

### 6. Full flow (upload + recognize + enrich)

1. Open http://127.0.0.1:5173/upload
2. Pick `multimodal-inspector` algorithm (uses LLM to recognize)
3. Pick a jpg/png < 20MB
4. Click "Submit"
5. Within seconds dashboard shows new record. Click to view:
   - **Recognition result**: real LLM output - description + observations
   - **LLM enrichment**: real maintenance suggestions
   - **Token usage**: real billing numbers (prompt_tokens + completion_tokens)

## Model selection tips

- **Testing multimodal**: must use a vision model (qwen-vl-plus, gpt-4o, llava)
- **Testing enrichment**: any chat model works, vision models also fine
- **Saving money**: use `qwen-turbo` (cheaper text) - but M0 uses one model for both

## Cost estimate (DashScope)

| Model | Input (per 1K tokens) | Output (per 1K tokens) |
|-------|----------------------|------------------------|
| qwen-turbo | 0.003 RMB | 0.006 RMB |
| qwen-plus | 0.004 RMB | 0.012 RMB |
| qwen-vl-plus | 0.008 RMB | 0.008 RMB |

Typical recognition (1 image + ~500 token prompt + ~300 token output):
- qwen-vl-plus: ~0.01 RMB / call
- Free signup 2M tokens: ~25K recognitions

## Troubleshooting

**"401 Unauthorized"**:
- Check `LLM_API_KEY` in `.env.local`
- Check `LLM_BASE_URL` matches the provider

**"404 model not found"**:
- Check `LLM_MODEL` spelling
- DashScope: use `qwen-vl-plus` (not `qwen-vl-plus-latest`)

**"Network timeout"**:
- Check if `LLM_BASE_URL` is reachable (curl it)
- Use a proxy or different provider

## Switch back to demo mode

```powershell
powershell -ExecutionPolicy Bypass -File scripts\start-app.ps1
```

## Advanced: start Celery worker (async processing)

Currently `TASK_SYNC_MODE=true` runs tasks in the API process (fine for dev).
For production-style async:

1. Set `TASK_SYNC_MODE=false` in `.env.local`
2. Start worker:
```powershell
cd backend
.venv\Scripts\celery.exe -A app.tasks.celery_app worker --loglevel=info -Q inspections
```