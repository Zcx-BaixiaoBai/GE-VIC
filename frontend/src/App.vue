<template>
  <div class="app-shell">
    <aside class="app-sidebar">
      <div class="brand">
        <div class="brand-mark">GV</div>
        <div class="brand-text">
          <strong>GE-VIC</strong>
          <span>图像识别平台</span>
        </div>
      </div>

      <nav class="app-nav">
        <router-link to="/" class="nav-item">
          <el-icon><DataLine /></el-icon>
          <span>仪表盘</span>
        </router-link>
        <router-link to="/upload" class="nav-item">
          <el-icon><Upload /></el-icon>
          <span>上传识别</span>
        </router-link>
        <router-link to="/settings" class="nav-item">
          <el-icon><Setting /></el-icon>
          <span>系统设置</span>
        </router-link>
      </nav>

      <div class="brand-footer">
        <div class="env-pill">
          <span class="env-dot"></span>
          演示模式
        </div>
        <div class="brand-meta">M0 · v0.1.0</div>
      </div>
    </aside>

    <main class="app-main">
      <router-view v-slot="{ Component }">
        <transition name="fade" mode="out-in">
          <component :is="Component" />
        </transition>
      </router-view>
    </main>
  </div>
</template>

<script setup lang="ts">
import { DataLine, Setting, Upload } from '@element-plus/icons-vue'
</script>

<style>
* { box-sizing: border-box; }
html, body, #app {
  margin: 0;
  height: 100%;
  font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', 'PingFang SC',
    'Hiragino Sans GB', 'Microsoft YaHei', sans-serif;
  color: #0f172a;
  background: #f6f8fb;
  font-size: 14px;
  -webkit-font-smoothing: antialiased;
  -moz-osx-font-smoothing: grayscale;
}
a { color: inherit; text-decoration: none; }
button { font-family: inherit; }
::-webkit-scrollbar { width: 8px; height: 8px; }
::-webkit-scrollbar-thumb { background: #cbd5e1; border-radius: 999px; }
::-webkit-scrollbar-thumb:hover { background: #94a3b8; }
::-webkit-scrollbar-track { background: transparent; }

.fade-enter-active, .fade-leave-active { transition: opacity 0.18s ease; }
.fade-enter-from, .fade-leave-to { opacity: 0; }
</style>

<style scoped>
.app-shell {
  display: grid;
  grid-template-columns: 240px 1fr;
  min-height: 100vh;
  background: #f6f8fb;
}

.app-sidebar {
  position: sticky;
  top: 0;
  align-self: start;
  height: 100vh;
  display: flex;
  flex-direction: column;
  background: #ffffff;
  border-right: 1px solid #eef2f6;
  padding: 20px 16px 16px;
}

.brand {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 0 8px 18px;
  border-bottom: 1px solid #f1f5f9;
  margin-bottom: 14px;
}
.brand-mark {
  width: 36px;
  height: 36px;
  border-radius: 10px;
  background: linear-gradient(135deg, #6366f1, #4338ca);
  color: #ffffff;
  font-weight: 800;
  font-size: 13px;
  letter-spacing: 0.02em;
  display: grid;
  place-items: center;
  box-shadow: 0 4px 10px rgba(79, 70, 229, 0.25);
}
.brand-text { display: flex; flex-direction: column; line-height: 1.1; }
.brand-text strong { font-size: 14px; color: #0f172a; }
.brand-text span { font-size: 11.5px; color: #94a3b8; margin-top: 2px; }

.app-nav {
  display: flex;
  flex-direction: column;
  gap: 2px;
  flex: 1;
}
.nav-item {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 9px 12px;
  border-radius: 10px;
  color: #475569;
  font-size: 13.5px;
  font-weight: 500;
  transition: background 0.15s ease, color 0.15s ease;
}
.nav-item .el-icon { font-size: 16px; color: #94a3b8; transition: color 0.15s ease; }
.nav-item:hover { background: #f8fafc; color: #0f172a; }
.nav-item:hover .el-icon { color: #6366f1; }
.nav-item.router-link-exact-active {
  background: linear-gradient(135deg, #eef2ff, #f5f3ff);
  color: #4338ca;
  font-weight: 600;
}
.nav-item.router-link-exact-active .el-icon { color: #4f46e5; }

.brand-footer {
  border-top: 1px solid #f1f5f9;
  padding-top: 12px;
  display: flex;
  flex-direction: column;
  gap: 6px;
}
.env-pill {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  padding: 4px 10px;
  background: #fffbeb;
  color: #b45309;
  border: 1px solid #fde68a;
  border-radius: 999px;
  font-size: 11.5px;
  font-weight: 600;
  width: fit-content;
}
.env-dot {
  width: 6px;
  height: 6px;
  border-radius: 50%;
  background: #f59e0b;
  box-shadow: 0 0 0 3px rgba(245, 158, 11, 0.18);
}
.brand-meta {
  font-size: 11.5px;
  color: #94a3b8;
  padding: 0 8px;
}

.app-main {
  padding: 28px 32px 40px;
  min-width: 0;
}

@media (max-width: 768px) {
  .app-shell { grid-template-columns: 1fr; }
  .app-sidebar { position: static; height: auto; flex-direction: row; align-items: center; padding: 12px 16px; }
  .brand { border: 0; padding: 0; margin: 0; }
  .app-nav { flex-direction: row; gap: 4px; flex: 1; margin-left: 16px; }
  .nav-item span { display: none; }
  .brand-footer { display: none; }
  .app-main { padding: 16px; }
}
</style>
