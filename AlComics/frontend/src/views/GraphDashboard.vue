<template>
  <div class="max-w-6xl mx-auto px-4 py-6">
    <!-- Header -->
    <div class="flex items-center justify-between mb-6">
      <h1 class="text-xl font-bold text-indigo-400">Pipeline Graph</h1>
      <button @click="refresh" class="px-3 py-1.5 text-xs bg-indigo-600 rounded hover:bg-indigo-500 disabled:opacity-50" :disabled="loading">
        {{ loading ? '加载中…' : '刷新' }}
      </button>
    </div>

    <!-- Error -->
    <div v-if="error" class="text-center py-12">
      <p class="text-red-400 text-sm mb-3">{{ error }}</p>
      <button @click="refresh" class="text-xs text-indigo-400 hover:text-indigo-300">重试</button>
    </div>

    <!-- Initial loading (no data yet) -->
    <div v-else-if="loading && !hasData" class="text-center py-12 text-gray-500 text-sm">加载中…</div>

    <!-- Graph List (no gid) -->
    <div v-else-if="!currentGid" class="grid gap-3 mb-6">
      <div v-for="g in graphs" :key="g.id"
        class="p-4 bg-dark-800 border border-dark-600 rounded-lg cursor-pointer hover:border-indigo-500/50"
        @click="selectGraph(g.id)">
        <div class="flex justify-between items-start">
          <div>
            <div class="font-medium text-sm text-white">{{ g.name }}</div>
            <div class="text-xs text-gray-500 mt-1">ID: {{ g.id?.slice(0, 8) }}…</div>
          </div>
          <div class="flex gap-2">
            <span class="px-2 py-0.5 text-xs rounded-full"
              :class="g.status === 'running' ? 'bg-blue-500/20 text-blue-400' :
                      g.status === 'completed' ? 'bg-green-500/20 text-green-400' :
                      g.status === 'failed' ? 'bg-red-500/20 text-red-400' :
                      'bg-gray-500/20 text-gray-400'">{{ g.status }}</span>
            <span class="text-xs text-gray-500">{{ g.run_count || 0 }} runs</span>
          </div>
        </div>
        <div v-if="g.nodes?.length" class="flex gap-2 mt-2 flex-wrap">
          <span v-for="n in g.nodes" :key="n" class="px-2 py-0.5 text-xs bg-dark-700 rounded text-gray-400">{{ n }}</span>
        </div>
        <div v-if="g.updated_at" class="text-xs text-gray-600 mt-2">{{ g.updated_at }}</div>
      </div>
      <div v-if="graphs.length === 0" class="text-center py-12 text-gray-500 text-sm">
        还没有运行图。创建一个项目开始生成吧。
      </div>
    </div>

    <!-- Graph Detail (has gid) -->
    <div v-else class="space-y-4">
      <div class="flex items-center gap-3 mb-4">
        <button @click="backToList" class="text-sm text-gray-400 hover:text-white">← 返回</button>
        <h2 class="font-medium">{{ currentGraph?.name || 'Graph' }}</h2>
        <span class="px-2 py-0.5 text-xs rounded-full"
          :class="graphStatus === 'running' ? 'bg-blue-500/20 text-blue-400' :
                  graphStatus === 'completed' ? 'bg-green-500/20 text-green-400' :
                  graphStatus === 'failed' ? 'bg-red-500/20 text-red-400' :
                  'bg-gray-500/20 text-gray-400'">{{ graphStatus }}</span>
      </div>

      <!-- SVG DAG -->
      <div class="bg-dark-800 border border-dark-600 rounded-lg p-4 overflow-auto">
        <svg :width="svgWidth" :height="svgHeight" class="min-w-full" v-if="graphNodes.length">
          <defs>
            <marker id="arrow" markerWidth="8" markerHeight="6" refX="8" refY="3" orient="auto">
              <path d="M0,0 L8,3 L0,6" fill="#6b7280" />
            </marker>
          </defs>
          <g v-for="(edge, i) in graphEdges" :key="'e'+i">
            <line :x1="edge.x1" :y1="edge.y1" :x2="edge.x2" :y2="edge.y2"
              :stroke="edge.color" stroke-width="2" marker-end="url(#arrow)" />
          </g>
          <g v-for="node in graphNodes" :key="node.id"
            :transform="`translate(${node.x}, ${node.y})`"
            class="cursor-pointer" @click="selectedNode = node">
            <rect x="-60" y="-20" width="120" height="40" rx="6"
              :fill="node.fill" :stroke="node.stroke" stroke-width="2" />
            <text x="0" y="-2" text-anchor="middle" class="text-xs font-medium" :fill="node.textColor">{{ node.label }}</text>
            <text v-if="node.duration" x="0" y="12" text-anchor="middle" class="text-[10px]" :fill="node.detailColor">{{ node.duration }}</text>
            <circle v-if="node.status === 'running'" cx="55" cy="-12" r="4" fill="#60a5fa">
              <animate attributeName="opacity" values="1;0.3;1" dur="1.5s" repeatCount="indefinite" />
            </circle>
          </g>
        </svg>
        <div v-else class="text-center py-12 text-gray-500 text-sm">暂无节点数据</div>
      </div>

      <!-- Node Detail -->
      <div v-if="selectedNode" class="bg-dark-800 border border-dark-600 rounded-lg p-4">
        <div class="flex justify-between items-start mb-3">
          <h3 class="font-medium text-sm">{{ selectedNode.label }}</h3>
          <button @click="selectedNode = null" class="text-gray-500 hover:text-white text-sm">✕</button>
        </div>
        <div class="grid grid-cols-3 gap-3 text-xs">
          <div>
            <div class="text-gray-500 mb-1">类型</div>
            <div>{{ selectedNode.type }}</div>
          </div>
          <div>
            <div class="text-gray-500 mb-1">状态</div>
            <div :style="{color: (NODE_COLORS[selectedNode.status] || NODE_COLORS.idle).text}">{{ selectedNode.status }}</div>
          </div>
          <div>
            <div class="text-gray-500 mb-1">耗时</div>
            <div>{{ selectedNode.duration || '—' }}</div>
          </div>
          <div v-if="selectedNode.config" class="col-span-3">
            <div class="text-gray-500 mb-1">配置</div>
            <pre class="bg-dark-900 p-2 rounded text-[10px] text-gray-400 overflow-x-auto">{{ JSON.stringify(selectedNode.config, null, 2) }}</pre>
          </div>
          <div v-if="selectedNode.result" class="col-span-3">
            <div class="text-gray-500 mb-1">输出</div>
            <pre class="bg-dark-900 p-2 rounded text-[10px] text-gray-400 overflow-x-auto max-h-32 overflow-y-auto">{{ JSON.stringify(selectedNode.result, null, 2) }}</pre>
          </div>
        </div>
      </div>

      <!-- Run History -->
      <div v-if="runs.length" class="bg-dark-800 border border-dark-600 rounded-lg p-4">
        <h3 class="text-sm font-medium mb-3">运行历史</h3>
        <div class="space-y-2">
          <div v-for="r in runs" :key="r.id" class="flex items-center justify-between py-2 border-b border-dark-700 last:border-0 text-xs">
            <div class="flex items-center gap-2">
              <span class="w-2 h-2 rounded-full"
                :class="r.status === 'completed' ? 'bg-green-500' : r.status === 'failed' ? 'bg-red-500' : r.status === 'running' ? 'bg-blue-500' : 'bg-gray-500'"></span>
              <span class="text-gray-400">{{ r.started_at || r.created_at }}</span>
            </div>
            <span class="text-gray-500">{{ r.node_count || 0 }} nodes</span>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, onUnmounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import api, { graph } from '../api.js'

const route = useRoute()
const router = useRouter()
const graphs = ref([])
const currentGraph = ref(null)
const runs = ref([])
const selectedNode = ref(null)
const currentGid = ref(null)
const loading = ref(false)
const error = ref('')
let pollTimer = null

const NODE_COLORS = {
  completed:  { fill: '#065f4620', stroke: '#059669', text: '#34d399', detail: '#6ee7b7' },
  running:    { fill: '#1e3a5f20', stroke: '#3b82f6', text: '#60a5fa', detail: '#93c5fd' },
  waiting:    { fill: '#1f293720', stroke: '#6b7280', text: '#9ca3af', detail: '#d1d5db' },
  idle:       { fill: '#1f293720', stroke: '#374151', text: '#6b7280', detail: '#9ca3af' },
  failed:     { fill: '#450a0a20', stroke: '#dc2626', text: '#f87171', detail: '#fca5a5' },
  skipped:    { fill: '#1f293720', stroke: '#4b5563', text: '#6b7280', detail: '#9ca3af' },
}

const hasData = computed(() => currentGid.value ? !!currentGraph.value : !!graphs.value.length)

const graphStatus = computed(() => currentGraph.value?.status || 'idle')

async function refresh() {
  error.value = ''
  loading.value = true
  try {
    if (currentGid.value) {
      const { data } = await api.get(`/api/graph/${currentGid.value}`)
      currentGraph.value = data.graph
      runs.value = data.runs || []
    } else {
      const { data } = await api.get('/api/graph')
      graphs.value = data.graphs || []
    }
  } catch (e) {
    const msg = e?.response?.data?.detail || e.message || '请求失败'
    error.value = `加载失败: ${msg}`
  } finally {
    loading.value = false
  }
}

async function pollNodeStatus() {
  try {
    const { data } = await graph.nodes(currentGid.value)
    if (!currentGraph.value?.nodes || !data?.nodes) return
    for (const [nid, ns] of Object.entries(data.nodes)) {
      const target = currentGraph.value.nodes[nid]
      if (target) {
        target.status = ns.status
        if (ns.duration != null) target.duration = ns.duration
      }
    }
  } catch (_) {
    // silent — polling errors shouldn't surface
  }
}

function selectGraph(gid) {
  router.push(`/graph/${gid}`)
}

function backToList() {
  router.push('/graph')
}

const levels = computed(() => {
  if (!currentGraph.value?.nodes) return {}
  const g = currentGraph.value
  const inDeg = {}
  const level = {}
  for (const nid of Object.keys(g.nodes)) {
    inDeg[nid] = 0
    level[nid] = 0
  }
  for (const e of (g.edges || [])) {
    if (inDeg[e.to_node] !== undefined) inDeg[e.to_node]++
  }
  let queue = Object.keys(inDeg).filter(n => inDeg[n] === 0)
  while (queue.length) {
    const next = []
    for (const nid of queue) {
      for (const e of (g.edges || [])) {
        if (e.from_node === nid) {
          if (level[e.to_node] <= level[nid]) level[e.to_node] = level[nid] + 1
          inDeg[e.to_node]--
          if (inDeg[e.to_node] === 0) next.push(e.to_node)
        }
      }
    }
    queue = next
  }
  return level
})

const maxNodesPerLevel = computed(() => {
  if (!Object.keys(levels.value).length) return 1
  const count = {}
  for (const l of Object.values(levels.value)) {
    count[l] = (count[l] || 0) + 1
  }
  return Math.max(1, ...Object.values(count))
})

const svgWidth = computed(() => Math.max(800, (Math.max(...Object.values(levels.value), 0) + 1) * 200))
const svgHeight = computed(() => Math.max(400, maxNodesPerLevel.value * 80 + 80))

const graphNodes = computed(() => {
  if (!currentGraph.value?.nodes || !Object.keys(levels.value).length) return []
  const g = currentGraph.value
  const perLevel = {}
  for (const [nid, l] of Object.entries(levels.value)) {
    if (!perLevel[l]) perLevel[l] = []
    perLevel[l].push(nid)
  }
  const result = []
  for (const [l, nids] of Object.entries(perLevel)) {
    const level = parseInt(l)
    const spacing = Math.min(600, 600 / Math.max(1, nids.length))
    const startX = 400 - ((nids.length - 1) * spacing) / 2
    nids.forEach((nid, i) => {
      const node = g.nodes[nid] || { id: nid, type: 'unknown', label: nid }
      const c = NODE_COLORS[node.status] || NODE_COLORS.idle
      result.push({
        id: node.id,
        label: node.label || node.id,
        type: node.type,
        status: node.status || 'idle',
        x: startX + i * spacing,
        y: level * 80 + 60,
        fill: c.fill,
        stroke: c.stroke,
        textColor: c.text,
        detailColor: c.detail,
        duration: node.duration ? (Math.round(node.duration * 10) / 10 + 's') : '',
        config: node.config,
        result: node.result,
      })
    })
  }
  return result
})

const graphEdges = computed(() => {
  if (!currentGraph.value?.edges || !graphNodes.value.length) return []
  const nodeMap = {}
  for (const n of graphNodes.value) nodeMap[n.id] = n
  return currentGraph.value.edges.map(e => {
    const from = nodeMap[e.from_node]
    const to = nodeMap[e.to_node]
    if (!from || !to) return null
    const c = NODE_COLORS[from.status] || NODE_COLORS.idle
    return {
      x1: from.x, y1: from.y + 20,
      x2: to.x, y2: to.y - 20,
      color: c.stroke,
    }
  }).filter(Boolean)
})

onMounted(async () => {
  currentGid.value = route.params.gid || null
  await refresh()
  if (currentGid.value) {
    pollTimer = setInterval(pollNodeStatus, 5000)
  }
})

onUnmounted(() => {
  if (pollTimer) clearInterval(pollTimer)
})
</script>
