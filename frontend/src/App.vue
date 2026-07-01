<template>
  <el-container>
    <el-header style="background: #409eff; color: white; display: flex; align-items: center;">
      <h2 style="margin: 0;">GE-VIC 图像识别平台</h2>
    </el-header>
    <el-container>
      <el-aside width="200px" style="background: #f5f5f5;">
        <el-menu :default-active="route.path" router>
          <el-menu-item index="/">仪表盘</el-menu-item>
          <el-menu-item index="/upload">上传识别</el-menu-item>
        </el-menu>
      </el-aside>
      <el-main>
        <router-view />
      </el-main>
    </el-container>
  </el-container>
</template>

<script setup lang="ts">
import { useRoute } from 'vue-router'
const route = useRoute()
</script>

<style>
body { margin: 0; font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif; }
</style>
