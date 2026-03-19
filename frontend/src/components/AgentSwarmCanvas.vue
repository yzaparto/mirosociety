<template>
  <div class="absolute inset-0 overflow-hidden" ref="containerRef">
    <canvas ref="canvasRef" class="w-full h-full" />
    <Transition name="popover">
      <div
        v-if="selectedAgent"
        class="absolute z-30 bg-white rounded-xl shadow-2xl border border-gray-200 p-4 w-64"
        :style="popoverStyle"
        @click.stop
      >
        <div class="flex items-center gap-2.5 mb-3">
          <div
            class="w-9 h-9 rounded-full flex items-center justify-center text-white text-sm font-bold shadow-sm"
            :style="{ background: selectedAgent.color }"
          >
            {{ selectedAgent.name[0] }}
          </div>
          <div class="min-w-0 flex-1">
            <div class="font-semibold text-sm text-slate-900 truncate">{{ selectedAgent.name }}</div>
            <div class="text-xs text-slate-500 capitalize">{{ selectedAgent.mood }}</div>
          </div>
        </div>
        <div class="space-y-1.5 text-xs text-slate-600">
          <div v-for="trait in selectedAgent.traits" :key="trait" class="flex items-center gap-1.5">
            <span class="w-1 h-1 rounded-full bg-slate-300"></span>
            {{ trait }}
          </div>
        </div>
        <div v-if="selectedAgent.recentActions.length" class="mt-3 pt-3 border-t border-gray-100 space-y-1">
          <div v-for="action in selectedAgent.recentActions" :key="action" class="text-[11px] text-slate-500 italic">
            {{ action }}
          </div>
        </div>
        <div class="mt-3 pt-2 border-t border-gray-100">
          <p class="text-[10px] text-slate-400">This is what your agents will do</p>
        </div>
      </div>
    </Transition>
  </div>
</template>

<script setup>
import { ref, onMounted, onUnmounted, nextTick } from 'vue'

const containerRef = ref(null)
const canvasRef = ref(null)
const selectedAgent = ref(null)
const popoverStyle = ref({})

const NAMES = [
  'Elena', 'Marcus', 'Dara', 'Jin', 'Sofia', 'Kai', 'Lena', 'Omar',
  'Priya', 'Tomás', 'Anika', 'Ravi', 'Mika', 'Zara', 'Leo', 'Ines',
  'Yuki', 'Nate', 'Amara', 'Felix'
]

const MOODS = ['calm', 'curious', 'restless', 'frustrated', 'hopeful', 'anxious', 'content', 'conflicted', 'angry']

const MOOD_COLORS = {
  calm: '#34d399', content: '#34d399', curious: '#34d399', satisfied: '#34d399', hopeful: '#34d399',
  restless: '#fbbf24', frustrated: '#fbbf24', anxious: '#fbbf24', uneasy: '#fbbf24',
  angry: '#f87171', hostile: '#f87171', fearful: '#f87171', desperate: '#f87171',
  conflicted: '#a78bfa', torn: '#a78bfa', confused: '#a78bfa',
}

const MOOD_GLOW = {
  calm: 'rgba(52,211,153,0.15)', content: 'rgba(52,211,153,0.15)', curious: 'rgba(52,211,153,0.15)',
  satisfied: 'rgba(52,211,153,0.15)', hopeful: 'rgba(52,211,153,0.15)',
  restless: 'rgba(251,191,36,0.15)', frustrated: 'rgba(251,191,36,0.15)',
  anxious: 'rgba(251,191,36,0.15)', uneasy: 'rgba(251,191,36,0.15)',
  angry: 'rgba(248,113,113,0.15)', hostile: 'rgba(248,113,113,0.15)',
  fearful: 'rgba(248,113,113,0.15)', desperate: 'rgba(248,113,113,0.15)',
  conflicted: 'rgba(167,139,250,0.15)', torn: 'rgba(167,139,250,0.15)', confused: 'rgba(167,139,250,0.15)',
}

const ACTIONS = [
  'speaks publicly', 'trades', 'proposes a rule', 'protests',
  'forms a group', 'observes', 'complies', 'defects', 'votes',
  'builds', 'whispers'
]

const TRAITS = [
  'High ambition, low empathy', 'Conformist, risk-averse', 'Rebellious, high confrontation',
  'Empathetic mediator', 'Quiet observer, high curiosity', 'Charismatic leader',
  'Pragmatic survivor', 'Idealist reformer', 'Cautious diplomat',
  'Fiery dissenter', 'Patient strategist', 'Community builder',
  'Lone wolf, self-reliant', 'Trusting optimist', 'Skeptical analyst',
  'Creative improviser', 'Rule-following traditionalist', 'Ambitious climber',
  'Compassionate healer', 'Cunning negotiator'
]

let agents = []
let interactions = []
let floatingLabels = []
let animFrame = null
let dpr = 1
let W = 0
let H = 0

function initAgents(w, h) {
  const padding = 80
  agents = NAMES.map((name, i) => {
    const mood = MOODS[Math.floor(Math.random() * MOODS.length)]
    return {
      id: i,
      name,
      mood,
      color: MOOD_COLORS[mood] || '#94a3b8',
      glow: MOOD_GLOW[mood] || 'rgba(148,163,184,0.15)',
      x: padding + Math.random() * (w - padding * 2),
      y: padding + Math.random() * (h - padding * 2),
      vx: (Math.random() - 0.5) * 0.6,
      vy: (Math.random() - 0.5) * 0.6,
      wanderAngle: Math.random() * Math.PI * 2,
      radius: 14,
      targetRadius: 14,
      traits: [TRAITS[i % TRAITS.length]],
      recentActions: [],
    }
  })
}

function spawnInteraction() {
  if (agents.length < 2) return
  const a = Math.floor(Math.random() * agents.length)
  let b = Math.floor(Math.random() * agents.length)
  while (b === a) b = Math.floor(Math.random() * agents.length)

  const action = ACTIONS[Math.floor(Math.random() * ACTIONS.length)]
  const agent = agents[a]
  agent.recentActions.unshift(`${action}`)
  if (agent.recentActions.length > 2) agent.recentActions.pop()

  interactions.push({
    a, b,
    progress: 0,
    duration: 90 + Math.random() * 60,
  })

  const midX = (agents[a].x + agents[b].x) / 2
  const midY = (agents[a].y + agents[b].y) / 2
  floatingLabels.push({
    text: action,
    x: midX,
    y: midY,
    startY: midY,
    opacity: 1,
    life: 0,
    maxLife: 80,
  })

  agents[a].targetRadius = 17
  agents[b].targetRadius = 17
  setTimeout(() => {
    agents[a].targetRadius = 14
    agents[b].targetRadius = 14
  }, 1500)
}

function spawnMoodShift() {
  const agent = agents[Math.floor(Math.random() * agents.length)]
  const newMood = MOODS[Math.floor(Math.random() * MOODS.length)]
  agent.mood = newMood
  agent.color = MOOD_COLORS[newMood] || '#94a3b8'
  agent.glow = MOOD_GLOW[newMood] || 'rgba(148,163,184,0.15)'
}

function tick() {
  const padding = 40

  for (const agent of agents) {
    agent.wanderAngle += (Math.random() - 0.5) * 0.6
    agent.vx += Math.cos(agent.wanderAngle) * 0.012
    agent.vy += Math.sin(agent.wanderAngle) * 0.012

    for (const other of agents) {
      if (other.id === agent.id) continue
      const ox = agent.x - other.x
      const oy = agent.y - other.y
      const od = Math.sqrt(ox * ox + oy * oy) || 1
      if (od < 60) {
        const force = 0.15 / od
        agent.vx += (ox / od) * force
        agent.vy += (oy / od) * force
      }
    }

    const speed = Math.sqrt(agent.vx * agent.vx + agent.vy * agent.vy)
    const maxSpeed = 1.2
    if (speed > maxSpeed) {
      agent.vx = (agent.vx / speed) * maxSpeed
      agent.vy = (agent.vy / speed) * maxSpeed
    }

    agent.vx *= 0.992
    agent.vy *= 0.992
    agent.x += agent.vx
    agent.y += agent.vy

    if (agent.x < padding) { agent.x = padding; agent.vx = Math.abs(agent.vx) * 0.8; agent.wanderAngle = Math.random() * Math.PI - Math.PI / 2 }
    if (agent.x > W - padding) { agent.x = W - padding; agent.vx = -Math.abs(agent.vx) * 0.8; agent.wanderAngle = Math.PI / 2 + Math.random() * Math.PI }
    if (agent.y < padding) { agent.y = padding; agent.vy = Math.abs(agent.vy) * 0.8; agent.wanderAngle = Math.random() * Math.PI }
    if (agent.y > H - padding) { agent.y = H - padding; agent.vy = -Math.abs(agent.vy) * 0.8; agent.wanderAngle = -Math.random() * Math.PI }

    agent.radius += (agent.targetRadius - agent.radius) * 0.1
  }

  for (const inter of interactions) {
    const a = agents[inter.a]
    const b = agents[inter.b]
    const dx = b.x - a.x
    const dy = b.y - a.y
    const dist = Math.sqrt(dx * dx + dy * dy) || 1
    if (dist > 100) {
      const pull = 0.002
      a.vx += (dx / dist) * pull
      a.vy += (dy / dist) * pull
      b.vx -= (dx / dist) * pull
      b.vy -= (dy / dist) * pull
    }
    inter.progress++
  }
  interactions = interactions.filter(i => i.progress < i.duration)

  for (const label of floatingLabels) {
    label.life++
    label.y = label.startY - (label.life / label.maxLife) * 30
    label.opacity = label.life < 10 ? label.life / 10 : Math.max(0, 1 - (label.life - 50) / 30)
  }
  floatingLabels = floatingLabels.filter(l => l.life < l.maxLife)
}

function draw(ctx) {
  ctx.clearRect(0, 0, W * dpr, H * dpr)
  ctx.save()
  ctx.scale(dpr, dpr)

  for (const inter of interactions) {
    const a = agents[inter.a]
    const b = agents[inter.b]
    const progress = inter.progress / inter.duration
    const alpha = progress < 0.15 ? progress / 0.15 : progress > 0.7 ? (1 - progress) / 0.3 : 1
    const dx = b.x - a.x
    const dy = b.y - a.y
    const dist = Math.sqrt(dx * dx + dy * dy) || 1
    const offset = Math.max(15, dist * 0.12)
    const mx = (a.x + b.x) / 2 + (-dy / dist) * offset
    const my = (a.y + b.y) / 2 + (dx / dist) * offset

    ctx.beginPath()
    ctx.moveTo(a.x, a.y)
    ctx.quadraticCurveTo(mx, my, b.x, b.y)
    ctx.strokeStyle = `rgba(0,0,0,${0.06 * alpha})`
    ctx.lineWidth = 1.5
    ctx.stroke()
  }

  for (const agent of agents) {
    ctx.beginPath()
    ctx.arc(agent.x, agent.y, agent.radius + 8, 0, Math.PI * 2)
    ctx.fillStyle = agent.glow
    ctx.fill()

    ctx.beginPath()
    ctx.arc(agent.x, agent.y, agent.radius, 0, Math.PI * 2)
    ctx.fillStyle = agent.color
    ctx.fill()

    ctx.fillStyle = '#fff'
    ctx.font = `bold ${Math.round(agent.radius * 0.85)}px Inter, system-ui, sans-serif`
    ctx.textAlign = 'center'
    ctx.textBaseline = 'middle'
    ctx.fillText(agent.name[0], agent.x, agent.y + 0.5)

    ctx.fillStyle = '#64748b'
    ctx.font = `500 10px Inter, system-ui, sans-serif`
    ctx.textAlign = 'center'
    ctx.textBaseline = 'top'
    ctx.fillText(agent.name.split(' ')[0], agent.x, agent.y + agent.radius + 6)
  }

  for (const label of floatingLabels) {
    if (label.opacity <= 0) continue
    ctx.fillStyle = `rgba(100,116,139,${label.opacity * 0.8})`
    ctx.font = `500 11px Inter, system-ui, sans-serif`
    ctx.textAlign = 'center'
    ctx.textBaseline = 'middle'
    ctx.fillText(label.text, label.x, label.y)
  }

  ctx.restore()
}

function loop() {
  const canvas = canvasRef.value
  if (!canvas) return
  const ctx = canvas.getContext('2d')
  tick()
  draw(ctx)
  animFrame = requestAnimationFrame(loop)
}

function handleClick(e) {
  const rect = canvasRef.value?.getBoundingClientRect()
  if (!rect) return
  const x = e.clientX - rect.left
  const y = e.clientY - rect.top

  let hit = null
  for (const agent of agents) {
    const dx = x - agent.x
    const dy = y - agent.y
    if (Math.sqrt(dx * dx + dy * dy) < agent.radius + 8) {
      hit = agent
      break
    }
  }

  if (hit) {
    selectedAgent.value = { ...hit }
    const popX = Math.min(hit.x + 20, W - 280)
    const popY = Math.max(hit.y - 100, 10)
    popoverStyle.value = {
      left: Math.max(10, popX) + 'px',
      top: popY + 'px',
    }
  } else {
    selectedAgent.value = null
  }
}

function resize() {
  const container = containerRef.value
  const canvas = canvasRef.value
  if (!container || !canvas) return
  dpr = window.devicePixelRatio || 1
  W = container.clientWidth
  H = container.clientHeight
  canvas.width = W * dpr
  canvas.height = H * dpr
  canvas.style.width = W + 'px'
  canvas.style.height = H + 'px'
}

let interactionTimer = null
let moodTimer = null

onMounted(async () => {
  await nextTick()
  resize()
  initAgents(W, H)
  loop()

  canvasRef.value?.addEventListener('click', handleClick)
  window.addEventListener('resize', () => { resize() })

  interactionTimer = setInterval(spawnInteraction, 2000 + Math.random() * 1500)
  moodTimer = setInterval(spawnMoodShift, 6000 + Math.random() * 4000)
})

onUnmounted(() => {
  if (animFrame) cancelAnimationFrame(animFrame)
  if (interactionTimer) clearInterval(interactionTimer)
  if (moodTimer) clearInterval(moodTimer)
  canvasRef.value?.removeEventListener('click', handleClick)
})
</script>

<style scoped>
.popover-enter-active,
.popover-leave-active {
  transition: all 0.2s ease;
}
.popover-enter-from,
.popover-leave-to {
  opacity: 0;
  transform: scale(0.95) translateY(4px);
}
</style>
