let ws = null
let listeners = {}

function getWsUrl(projectId) {
  const proto = window.location.protocol === 'https:' ? 'wss:' : 'ws:'
  const host = window.location.host
  return `${proto}//${host}/api/projects/${projectId}/ws`
}

export function connect(projectId, token) {
  if (ws) {
    ws.close()
  }

  const url = getWsUrl(projectId)
  ws = new WebSocket(url)

  ws.onopen = () => {
    // authenticate
    ws.send(JSON.stringify({ type: 'auth', token }))
    emit('connected')
  }

  ws.onmessage = (e) => {
    try {
      const msg = JSON.parse(e.data)
      emit(msg.type, msg.payload || msg)
    } catch {
      emit('raw', e.data)
    }
  }

  ws.onclose = () => {
    emit('disconnected')
    ws = null
  }

  ws.onerror = () => {
    emit('error')
  }
}

export function disconnect() {
  if (ws) {
    ws.close()
    ws = null
  }
}

export function send(data) {
  if (ws && ws.readyState === WebSocket.OPEN) {
    ws.send(JSON.stringify(data))
  }
}

export function on(event, fn) {
  if (!listeners[event]) listeners[event] = []
  listeners[event].push(fn)
  return () => {
    listeners[event] = listeners[event].filter((f) => f !== fn)
  }
}

function emit(event, payload) {
  ;(listeners[event] || []).forEach((fn) => fn(payload))
}

export function isConnected() {
  return ws && ws.readyState === WebSocket.OPEN
}
