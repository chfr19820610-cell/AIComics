<template>
  <div class="max-w-4xl mx-auto px-4 py-8 space-y-6">
    <router-link to=".." class="inline-flex text-sm text-gray-400 hover:text-gray-200">&larr; 返回项目</router-link>

    <!-- 加载中 -->
    <div v-if="loading" class="text-center text-gray-400 py-16">加载中…</div>

    <!-- 视频播放区域 -->
    <template v-else-if="episode">
      <h1 class="text-xl font-bold">{{ episode.title || `第 ${episode.ep_number} 集` }}</h1>

      <div class="aspect-video rounded-xl overflow-hidden bg-dark-800 border border-dark-600 flex items-center justify-center">
        <video
          v-if="episode.output_path"
          :src="`/api/episodes/${episode.id}/view`"
          controls
          autoplay
          class="w-full h-full object-contain"
        ></video>
        <div v-else class="text-center text-gray-500">
          <svg class="w-16 h-16 mx-auto mb-3" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="1" d="M14.752 11.168l-3.197-2.132A1 1 0 0010 9.87v4.263a1 1 0 001.555.832l3.197-2.132a1 1 0 000-1.664z" />
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="1" d="M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
          </svg>
          <p>视频尚未生成</p>
          <p class="text-xs mt-1 text-gray-600">状态: {{ episode.status }}</p>
        </div>
      </div>

      <!-- 元信息 -->
      <div class="card space-y-2">
        <div class="flex flex-wrap gap-4 text-sm">
          <span class="text-gray-400">状态: <span class="text-gray-200">{{ episode.status }}</span></span>
          <span class="text-gray-400">创建时间: <span class="text-gray-200">{{ new Date(episode.created_at).toLocaleString() }}</span></span>
        </div>
        <p v-if="episode.duration" class="text-sm text-gray-400">时长: {{ episode.duration }}s</p>
      </div>
    </template>

    <!-- 未找到 -->
    <p v-else class="text-center text-gray-500 py-16">剧集不存在</p>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { useRoute } from 'vue-router'
import { episodes } from '../api.js'

const route = useRoute()
const episode = ref(null)
const loading = ref(true)

onMounted(fetchEpisode)

async function fetchEpisode() {
  try {
    const { data } = await episodes.get(route.params.id)
    episode.value = data
  } catch {
    episode.value = null
  } finally {
    loading.value = false
  }
}
</script>
