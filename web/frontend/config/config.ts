import { defineConfig } from '@umijs/max';

export default defineConfig({
  antd: {},
  access: {},
  model: {},
  initialState: {},
  request: {},
  layout: {
    title: 'AI漫剧创作者控制台',
    locale: false,
  },
  hash: true,
  routes: [
    { path: '/login', component: './Login', layout: false },
    { path: '/', redirect: '/dashboard' },
    { name: '总览', path: '/dashboard', component: './Dashboard' },
    { name: '创作台', path: '/creator', component: './CreatorWorkspace' },
    { name: '项目', path: '/projects', component: './Projects' },
    { name: '剧集', path: '/episodes', component: './Episodes' },
    { name: '任务', path: '/jobs', component: './Jobs' },
    { name: '批次', path: '/batches', component: './Batches' },
    { name: '模板', path: '/templates', component: './Templates' },
    { name: '发布', path: '/publish', component: './Publish' },
    { name: '小说导入', path: '/novel-import', component: './NovelImport' },
    { name: '服务商', path: '/provider', component: './Provider' },
    { name: '复盘', path: '/review', component: './Review' },
  ],
  npmClient: 'npm',
  proxy: {
    '/api': {
      target: 'http://127.0.0.1:7861',
      changeOrigin: true,
    },
  },
});
