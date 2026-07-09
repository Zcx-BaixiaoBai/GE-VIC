# GE-VIC V1.1.0

修复了 mock 模式导致识别结果与图片不符的问题，并将 MinIO 替换为真实持久化服务。

## 🚀 新增与变更

- **feat(storage)**: Windows 本地开发改用真实 MinIO 二进制 (`minio/minio.exe`)，数据持久化到 `minio-data/`。
  - 重启后对象不丢失。
  - 控制台地址: http://127.0.0.1:9001。
  - `minio/` 与 `minio-data/` 已加入 `.gitignore`。
- **chore**: 彻底移除 LLM mock 模式与 `MockEngine`。
  - 删除 `LLM_MOCK_MODE`、`llm_mock_mode`、`mock_mode` 及相关代码。
  - 删除 `backend/app/engines/mock.py`。
  - 删除 `insulator-demo` / mock 引擎相关前端展示。
  - 更新 README，移除“演示模式”章节，改为“本地同步模式”。
- **feat(config)**: `start-app.ps1` 启动时自动加载 `.env.local` 中的 `LLM_*` 配置作为全局 LLM 入口，未配置时回退到占位默认值。
  - 在 `.env.local` 中设置真实 key 即可生效，无需修改脚本，也不会提交到仓库。

## 🐛 修复

- 修复 `minimax-test` 等配置了真实 key 的算法仍因全局 mock 返回预设结果（如“绝缘子破损”）的问题。
- 修复 `scripts/start-services.ps1` 使用内存版 moto 导致重启后图片丢失的问题。

## ⚠️ 破坏性/注意事项

- 升级到 V1.1.0 后，建议清空或忽略此前 moto 内存模式下生成的旧记录图片（已不可恢复）。
- 全局 LLM 测试端点 (`/api/v1/settings/llm/test`) 现在会调用真实的 `.env.local` 或占位配置；若使用占位 key，该端点会失败，但不影响配置了独立 key 的算法（`minimax-test`、`nvidia-mistral`）。

## 📦 部署

```bash
# 拉取 V1.1.0
git pull
git checkout v1.1.0

# 后端依赖与迁移
cd backend && .venv\Scripts\python.exe -m pip install -e ".[dev]"
.venv\Scripts\alembic.exe upgrade head

# 前端
cd ../frontend && npm ci && npm run build
```

## 📚 文档

- [README.md](./README.md) - 本地启动与 `.env.local` 配置说明
- [DEPLOYMENT.md](./DEPLOYMENT.md) - 生产部署指南
- [RELEASE_NOTES_V1.0.0.md](./RELEASE_NOTES_V1.0.0.md) - 上一版本说明

## 👥 贡献

V1.1.0 由 single dev (Zcx-BaixiaoBai) 在 2026-07 完成。
