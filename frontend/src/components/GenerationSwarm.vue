<template>
  <div class="absolute inset-0 overflow-hidden" ref="containerRef">
    <canvas ref="canvasRef" class="w-full h-full" />
  </div>
</template>

<script setup>
import { ref, watch, onMounted, onUnmounted, nextTick } from 'vue'
import { moodNodeFill } from '../utils/mood'

const props = defineProps({
  citizens: { type: Array, default: () => [] },
})

const containerRef = ref(null)
const canvasRef = ref(null)

let bubbles = []
let animFrame = null
let dpr = 1
let W = 0
let H = 0

const GLOW_ALPHA = {
  '#34d399': 'rgba(52,211,153,0.12)',
  '#fbbf24': 'rgba(251,191,36,0.12)',
  '#f87171': 'rgba(248,113,113,0.12)',
  '#a78bfa': 'rgba(167,139,250,0.12)',
  '#94a3b8': 'rgba(148,163,184,0.12)',
}

function addBubble(citizen) {
  if (!W || !H) return
  const padding = 60
  const color = moodNodeFill(citizen.emotional_state) || '#94a3b8'
  bubbles.push({
    id: citizen.id,
    name: citizen.name,
    initial: citizen.name.charAt(0),
    role: citizen.role,
    color,
    glow: GLOW_ALPHA[color] || 'rgba(148,163,184,0.12)',
    x: padding + Math.random() * (W - padding * 2),
    y: padding + Math.random() * (H - padding * 2),
    vx: (Math.random() - 0.5) * 0.4,
    vy: (Math.random() - 0.5) * 0.4,
    radius: 0,
    targetRadius: 16,
    opacity: 0,
    targetOpacity: 1,
  })
}

watch(() => props.citizens.length, (newLen, oldLen) => {
  for (let i = oldLen || 0; i < newLen; i++) {
    addBubble(props.citizens[i])
  }
})

function tick() {
  const cx = W / 2
  const cy = H / 2
  const padding = 30

  for (const b of bubbles) {
    b.radius += (b.targetRadius - b.radius) * 0.08
    b.opacity += (b.targetOpacity - b.opacity) * 0.06

    const dx = cx - b.x
    const dy = cy - b.y
    const dist = Math.sqrt(dx * dx + dy * dy) || 1
    b.vx += (dx / dist) * 0.002
    b.vy += (dy / dist) * 0.002

    for (const other of bubbles) {
      if (other.id === b.id) continue
      const ox = b.x - other.x
      const oy = b.y - other.y
      const od = Math.sqrt(ox * ox + oy * oy) || 1
      if (od < 55) {
        const force = 0.1 / od
        b.vx += (ox / od) * force
        b.vy += (oy / od) * force
      }
    }

    b.vx *= 0.988
    b.vy *= 0.988
    b.x += b.vx
    b.y += b.vy

    if (b.x < padding) { b.x = padding; b.vx *= -0.5 }
    if (b.x > W - padding) { b.x = W - padding; b.vx *= -0.5 }
    if (b.y < padding) { b.y = padding; b.vy *= -0.5 }
    if (b.y > H - padding) { b.y = H - padding; b.vy *= -0.5 }
  }
}

function draw(ctx) {
  ctx.clearRect(0, 0, W * dpr, H * dpr)
  ctx.save()
  ctx.scale(dpr, dpr)

  for (const b of bubbles) {
    if (b.opacity <= 0.01) continue

    ctx.globalAlpha = b.opacity

    ctx.beginPath()
    ctx.arc(b.x, b.y, b.radius + 8, 0, Math.PI * 2)
    ctx.fillStyle = b.glow
    ctx.fill()

    ctx.beginPath()
    ctx.arc(b.x, b.y, b.radius, 0, Math.PI * 2)
    ctx.fillStyle = b.color
    ctx.fill()

    ctx.fillStyle = '#fff'
    ctx.font = `bold ${Math.round(b.radius * 0.85)}px Inter, system-ui, sans-serif`
    ctx.textAlign = 'center'
    ctx.textBaseline = 'middle'
    ctx.fillText(b.initial, b.x, b.y + 0.5)

    ctx.fillStyle = `rgba(100,116,139,${b.opacity * 0.7})`
    ctx.font = `500 9px Inter, system-ui, sans-serif`
    ctx.textBaseline = 'top'
    ctx.fillText(b.name.split(' ')[0], b.x, b.y + b.radius + 5)

    ctx.globalAlpha = 1
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

onMounted(async () => {
  await nextTick()
  resize()
  for (const c of props.citizens) {
    addBubble(c)
  }
  loop()
  window.addEventListener('resize', resize)
})

onUnmounted(() => {
  if (animFrame) cancelAnimationFrame(animFrame)
  window.removeEventListener('resize', resize)
})
</script>
