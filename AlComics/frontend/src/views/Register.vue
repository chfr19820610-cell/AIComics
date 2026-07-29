<template>
  <div class="flex items-center justify-center min-h-[calc(100vh-3.5rem)] px-4">
    <div class="w-full max-w-sm card space-y-6">
      <h1 class="text-2xl font-bold text-center text-indigo-400">注册</h1>

      <form @submit.prevent="handleRegister" class="space-y-4">
        <div>
          <label class="block text-sm text-gray-400 mb-1">用户名</label>
          <input v-model="username" class="input-field" placeholder="your name" required />
        </div>
        <div>
          <label class="block text-sm text-gray-400 mb-1">密码</label>
          <input v-model="password" type="password" class="input-field" placeholder="••••••••" required minlength="6" />
        </div>

        <p v-if="error" class="text-red-400 text-sm">{{ error }}</p>

        <button type="submit" :disabled="loading" class="btn-primary w-full">
          {{ loading ? '注册中…' : '注册' }}
        </button>
      </form>

      <p class="text-sm text-center text-gray-500">
        已有账号？
        <router-link to="/login" class="text-indigo-400 hover:text-indigo-300">登录</router-link>
      </p>
    </div>
  </div>
</template>

<script setup>
import { ref } from 'vue'
import { useRouter } from 'vue-router'
import { auth } from '../api.js'

const router = useRouter()
const username = ref('')
const password = ref('')
const error = ref('')
const loading = ref(false)

async function handleRegister() {
  error.value = ''
  loading.value = true
  try {
    const { data } = await auth.register({
      username: username.value,
      password: password.value,
    })
    localStorage.setItem('token', data.token)
    router.push('/')
  } catch (e) {
    error.value = e.response?.data?.message || '注册失败，请重试'
  } finally {
    loading.value = false
  }
}
</script>
