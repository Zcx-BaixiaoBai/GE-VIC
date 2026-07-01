<template>
  <div>
    <h2>上传识别</h2>
    <el-card>
      <el-form :model="form" label-width="100px">
        <el-form-item label="算法">
          <el-select v-model="form.algorithmCode" placeholder="选择算法" style="width: 100%">
            <el-option
              v-for="a in store.algorithms"
              :key="a.code"
              :label="`${a.name} (${a.code})`"
              :value="a.code"
            />
          </el-select>
        </el-form-item>
        <el-form-item label="资产 ID">
          <el-input v-model="form.assetId" placeholder="可选, 例如 BJ-SUBSTATION-001" />
        </el-form-item>
        <el-form-item label="巡检员 ID">
          <el-input v-model="form.inspectorId" placeholder="例如 INSP-001" />
        </el-form-item>
        <el-form-item label="文件">
          <el-upload
            :auto-upload="false"
            :limit="1"
            :on-change="(f: any) => (fileList = [f])"
            :file-list="fileList"
          >
            <el-button>选择文件</el-button>
            <template #tip>
              <div style="color: #909399; font-size: 12px; margin-top: 4px;">
                支持 jpg/png/mp4 等, 最大 20MB
              </div>
            </template>
          </el-upload>
        </el-form-item>
        <el-form-item>
          <el-button type="primary" :loading="uploading" @click="onSubmit">提交识别</el-button>
          <el-button @click="onReset">重置</el-button>
        </el-form-item>
      </el-form>
    </el-card>

    <el-card v-if="lastResult" style="margin-top: 16px;">
      <h3>提交结果</h3>
      <p>记录 ID: <strong>{{ lastResult.record_id }}</strong></p>
      <p>状态: <strong>{{ lastResult.status }}</strong></p>
      <p>状态 URL: <el-link :href="lastResult.status_url" target="_blank">{{ lastResult.status_url }}</el-link></p>
      <el-button type="primary" @click="goDashboard">前往仪表盘查看</el-button>
    </el-card>
  </div>
</template>

<script setup lang="ts">
import { onMounted, reactive, ref } from 'vue'
import { useRouter } from 'vue-router'
import { useRecordsStore } from '../stores/records'
import { ElMessage, type UploadFile } from 'element-plus'

const store = useRecordsStore()
const router = useRouter()

const form = reactive({
  algorithmCode: '',
  assetId: '',
  inspectorId: '',
})

const fileList = ref<UploadFile[]>([])
const uploading = ref(false)
const lastResult = ref<{ record_id: number; status: string; status_url: string } | null>(null)

onMounted(async () => {
  await store.fetchAlgorithms()
})

function onReset() {
  form.algorithmCode = ''
  form.assetId = ''
  form.inspectorId = ''
  fileList.value = []
  lastResult.value = null
}

async function onSubmit() {
  if (!form.algorithmCode) return ElMessage.warning('请选择算法')
  if (!fileList.value[0]?.raw) return ElMessage.warning('请选择文件')

  uploading.value = true
  try {
    if (form.inspectorId) {
      localStorage.setItem('inspector_id', form.inspectorId)
    }
    const meta: Record<string, any> = {}
    if (form.assetId) meta.asset_id = form.assetId
    if (form.inspectorId) meta.inspector_id_hint = form.inspectorId

    const r = await store.uploadFile(form.algorithmCode, fileList.value[0].raw, meta)
    ElMessage.success(`上传成功, record_id=${r.record_id}`)
    lastResult.value = r
  } catch (e) {
    // axios interceptor already showed error
  } finally {
    uploading.value = false
  }
}

function goDashboard() {
  router.push('/')
}
</script>
