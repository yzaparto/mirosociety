const POSITIVE = ['calm', 'content', 'curious', 'satisfied', 'hopeful']
const UNEASY = ['restless', 'frustrated', 'dissatisfied', 'uneasy', 'anxious']
const HOSTILE = ['angry', 'fearful', 'hostile', 'desperate']
const CONFLICTED = ['conflicted', 'torn', 'confused']

function matchesMood(state, keywords) {
  if (!state) return false
  const s = String(state).toLowerCase()
  return keywords.some(m => s.includes(m))
}

export function moodCategory(state) {
  if (matchesMood(state, POSITIVE)) return 'positive'
  if (matchesMood(state, UNEASY)) return 'uneasy'
  if (matchesMood(state, HOSTILE)) return 'hostile'
  if (matchesMood(state, CONFLICTED)) return 'conflicted'
  return 'neutral'
}

export function moodDotClass(state) {
  const cat = moodCategory(state)
  return {
    positive: 'bg-emerald-500',
    uneasy: 'bg-amber-500',
    hostile: 'bg-red-500',
    conflicted: 'bg-violet-500',
    neutral: 'bg-slate-400',
  }[cat]
}

export function moodBgClass(state) {
  const cat = moodCategory(state)
  return {
    positive: 'bg-emerald-50 border-emerald-200 text-emerald-800',
    uneasy: 'bg-amber-50 border-amber-200 text-amber-800',
    hostile: 'bg-red-50 border-red-200 text-red-800',
    conflicted: 'bg-violet-50 border-violet-200 text-violet-800',
    neutral: 'bg-gray-100 border-gray-200 text-gray-700',
  }[cat]
}

export function moodNodeFill(state) {
  const cat = moodCategory(state)
  return {
    positive: '#34d399',
    uneasy: '#fbbf24',
    hostile: '#f87171',
    conflicted: '#a78bfa',
    neutral: '#94a3b8',
  }[cat]
}

export function moodNodeStroke(state) {
  const cat = moodCategory(state)
  return {
    positive: '#059669',
    uneasy: '#d97706',
    hostile: '#dc2626',
    conflicted: '#7c3aed',
    neutral: '#64748b',
  }[cat]
}

export function speechBubbleClass(state) {
  return 'bg-white text-slate-900 shadow-lg border border-gray-100'
}
