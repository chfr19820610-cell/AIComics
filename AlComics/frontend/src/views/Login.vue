<template>
  <div class="flex items-center justify-center min-h-[calc(100vh-3.5rem)] px-4">
    <div class="w-full max-w-sm card space-y-6">
      <h1 class="text-2xl font-bold text-center text-indigo-400">登录</h1>

      <form @submit.prevent="handleLogin" class="space-y-4">
        <div>
          <label class="block text-sm text-gray-400 mb-1">邮箱</label>
          <input v-model="email" type="email" class="input-field" placeholder="name@example.com" required />
        </div>
        <div>
          <label class="block text-sm text-gray-400 mb-1">密码</label>
          <input v-model="password" type="password" class="input-field" placeholder="••••••••" required />
        </div>

        <p v-if="error" class="text-red-400 text-sm">{{ error }}</p>

        <button type="submit" :disabled="loading" class="btn-primary w-full">
          {{ loading ? '登录中…' : '登录' }}
        </button>
      </form>

      <p class="text-sm text-center text-gray-500">
        还没有账号？
        <router-link to="/register" class="text-indigo-400 hover:text-indigo-300">注册</router-link>
      </p>
    </div>
  </div>
</template>

<script setup>
import { ref } from 'vue'
import { useRouter } from 'vue-router'
import { auth } from '../api.js'

const router = useRouter()
const email = ref('')
const password = ref('')
const error = ref('')
const loading = ref(false)

async function handleLogin() {
  error.value = ''
  loading.value = true
  try {
    const { data } = await auth.login({ username: email.value, password: password.value })
    localStorage.setItem('token', data.token)
    router.push('/')
  } catch (e) {
    error.value = e.response?.data?.message || '登录失败，请重试'
  } finally {
    loading.value = false
  }
}
</script>
