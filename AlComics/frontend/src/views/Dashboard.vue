<template>
  <div class="max-w-6xl mx-auto px-4 py-8 space-y-6">
    <!-- 头部 -->
    <div class="flex items-center justify-between">
      <h1 class="text-2xl font-bold">我的项目</h1>
      <button @click="showCreate = true" class="btn-primary">新建项目</button>
    </div>

    <!-- 新建项目弹窗 -->
    <Teleport to="body">
      <div v-if="showCreate" class="fixed inset-0 z-50 flex items-center justify-center bg-black/60 px-4" @click.self="showCreate = false">
        <div class="w-full max-w-lg card space-y-4">
          <h2 class="text-lg font-semibold">新建项目</h2>
          <form @submit.prevent="handleCreate" class="space-y-4">
            <input v-model="form.title" class="input-field" placeholder="项目标题" required />
            <textarea v-model="form.script" class="input-field min-h-[120px] resize-y" placeholder="输入剧本内容…"></textarea>
            <div class="flex justify-end gap-3">
              <button type="button" @click="showCreate = false" class="btn-ghost">取消</button>
              <button type="submit" :disabled="creating" class="btn-primary">
                {{ creating ? '创建中…' : '创建' }}
              </button>
            </div>
          </form>
        </div>
      </div>
    </Teleport>

    <!-- 提示 -->
    <p v-if="!loading && !projects.length" class="text-center text-gray-500 py-16">
      还没有项目，点击「新建项目」开始创作吧 🎨
    </p>

    <!-- 加载中 -->
    <p v-if="loading" class="text-center text-gray-400 py-16">加载中…</p>

    <!-- 项目列表 -->
    <div v-else class="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
      <div
        v-for="p in projects"
        :key="p.id"
        class="card-hover cursor-pointer group"
        @click="$router.push(`/projects/${p.id}`)"
      >
        <div class="flex items-start justify-between">
          <h3 class="font-semibold truncate group-hover:text-indigo-400 transition-colors">{{ p.title }}</h3>
          <button
            @click.stop="handleDelete(p.id)"
            class="text-gray-500 hover:text-red-400 transition-colors shrink-0 ml-2"
            title="删除"
          >
            <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6M1 7h22M9 7V4a1 1 0 011-1h4a1 1 0 011 1v3" />
            </svg>
          </button>
        </div>
        <p class="text-sm text-gray-400 mt-1 line-clamp-2">{{ p.script || '无剧本' }}</p>
        <p class="text-xs text-gray-500 mt-3">{{ new Date(p.created_at).toLocaleDateString() }}</p>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { projects } from '../api.js'

const showCreate = ref(false)
const creating = ref(false)
const loading = ref(true)
const projectsList = ref([])
const form = ref({ title: '', script: '' })

onMounted(fetchProjects)

async function fetchProjects() {
  loading.value = true
  try {
    const { data } = await projects.list()
    projectsList.value = data || []
  } catch {
    // handled by interceptor
  } finally {
    loading.value = false
  }
}

async function handleCreate() {
  creating.value = true
  try {
    await projects.create(form.value)
    form.value = { title: '', script: '' }
    showCreate.value = false
    await fetchProjects()
  } catch {
    // handled globally
  } finally {
    creating.value = false
  }
}

async function handleDelete(id) {
  if (!confirm('确定删除该项目？')) return
  try {
    await projects.delete(id)
    await fetchProjects()
  } catch {
    // handled globally
  }
}
</script>
