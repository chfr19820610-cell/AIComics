<template>
  <div class="max-w-6xl mx-auto px-4 py-8 space-y-6">
    <!-- 项目信息 -->
    <div class="flex items-center justify-between flex-wrap gap-4">
      <div>
        <router-link to="/" class="text-sm text-gray-400 hover:text-gray-200">&larr; 返回</router-link>
        <h1 class="text-2xl font-bold mt-1">{{ project?.title || '加载中…' }}</h1>
      </div>
      <button @click="handleGenerate" :disabled="generating" class="btn-primary">
        {{ generating ? '生成中…' : '一键生成' }}
      </button>
    </div>

    <!-- WebSocket 进度条 -->
    <div v-if="generating" class="card space-y-3">
      <div class="flex items-center justify-between text-sm">
        <span class="text-gray-300">{{ progressMsg || '准备中…' }}</span>
        <span class="text-indigo-400 font-mono">{{ progressPercent }}%</span>
      </div>
      <div class="w-full h-2 rounded-full bg-dark-600 overflow-hidden">
        <div
          class="h-full rounded-full bg-indigo-500 transition-all duration-300 ease-out"
          :style="{ width: progressPercent + '%' }"
        ></div>
      </div>
    </div>

    <!-- 加载中 -->
    <p v-if="loading" class="text-center text-gray-400 py-16">加载中…</p>

    <!-- 无剧集 -->
    <p v-else-if="!episodesList.length" class="text-center text-gray-500 py-16">
      还没有剧集，点击「一键生成」开始创作
    </p>

    <!-- 剧集列表 -->
    <div v-else class="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
      <div
        v-for="ep in episodesList"
        :key="ep.id"
        class="card-hover cursor-pointer"
        @click="$router.push(`/episodes/${ep.id}`)"
      >
        <div class="aspect-video rounded-lg bg-dark-700 mb-3 flex items-center justify-center overflow-hidden">
          <img
            v-if="ep.thumbnail"
            :src="ep.thumbnail"
            class="w-full h-full object-cover"
            alt="thumbnail"
          />
          <svg v-else class="w-10 h-10 text-gray-500" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="1.5" d="M14.752 11.168l-3.197-2.132A1 1 0 0010 9.87v4.263a1 1 0 001.555.832l3.197-2.132a1 1 0 000-1.664z" />
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="1.5" d="M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
          </svg>
        </div>
        <h3 class="font-semibold truncate">第 {{ ep.ep_number }} 集</h3>
        <p class="text-xs text-gray-500 mt-1">{{ ep.status || 'draft' }}</p>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted, onUnmounted } from 'vue'
import { useRoute } from 'vue-router'
import { projects, episodes } from '../api.js'
import { connect, disconnect, on } from '../ws.js'

const route = useRoute()
const projectId = route.params.id
const project = ref(null)
const episodesList = ref([])
const loading = ref(true)
const generating = ref(false)
const progressPercent = ref(0)
const progressMsg = ref('')

onMounted(() => {
  fetchProject()
  fetchEpisodes()
})

onUnmounted(() => {
  disconnect()
})

async function fetchProject() {
  try {
    const { data } = await projects.get(projectId)
    project.value = data
  } catch {
    // handled globally
  }
}

async function fetchEpisodes() {
  try {
    const { data } = await episodes.list(projectId)
    episodesList.value = data || []
  } catch {
    // handled globally
  } finally {
    loading.value = false
  }
}

async function handleGenerate() {
  generating.value = true
  progressPercent.value = 0
  progressMsg.value = ''

  const token = localStorage.getItem('token')
  connect(projectId, token)

  const unsub = on('progress', (msg) => {
    if (msg.percent !== undefined) progressPercent.value = msg.percent
    if (msg.message) progressMsg.value = msg.message
  })

  on('complete', () => {
    progressPercent.value = 100
    progressMsg.value = '生成完成'
    generating.value = false
    disconnect()
    unsub()
    fetchEpisodes()
  })

  on('error', (msg) => {
    progressMsg.value = msg?.message || '生成出错'
    generating.value = false
    disconnect()
    unsub()
  })

  try {
    await episodes.generate(projectId)
  } catch {
    generating.value = false
    disconnect()
    unsub()
  }
}
</script>
