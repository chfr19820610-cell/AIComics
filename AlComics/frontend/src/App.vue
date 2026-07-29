<template>
  <div class="min-h-screen flex flex-col">
    <nav v-if="isLoggedIn" class="sticky top-0 z-50 border-b border-dark-600 bg-dark-900/80 backdrop-blur-md">
      <div class="max-w-6xl mx-auto px-4 h-14 flex items-center justify-between">
        <router-link to="/" class="text-lg font-bold tracking-tight text-indigo-400 hover:text-indigo-300">
          AIComics
        </router-link>
        <button @click="handleLogout" class="text-sm text-gray-400 hover:text-gray-200 transition-colors">
          退出登录
        </button>
      </div>
    </nav>
    <main class="flex-1">
      <router-view />
    </main>
  </div>
</template>

<script setup>
import { computed } from 'vue'
import { useRouter } from 'vue-router'

const router = useRouter()
const isLoggedIn = computed(() => !!localStorage.getItem('token'))

function handleLogout() {
  localStorage.removeItem('token')
  router.push('/login')
}
</script>
