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
    positive: 'bg-emerald-400',
    uneasy: 'bg-amber-400',
    hostile: 'bg-red-400',
    conflicted: 'bg-violet-400',
    neutral: 'bg-slate-400',
  }[cat]
}

export function moodBgClass(state) {
  const cat = moodCategory(state)
  return {
    positive: 'bg-emerald-800 border-emerald-600 text-emerald-100',
    uneasy: 'bg-amber-800 border-amber-600 text-amber-100',
    hostile: 'bg-red-800 border-red-600 text-red-100',
    conflicted: 'bg-violet-800 border-violet-600 text-violet-100',
    neutral: 'bg-slate-700 border-slate-600 text-slate-300',
  }[cat]
}

export function moodNodeFill(state) {
  const cat = moodCategory(state)
  return {
    positive: '#059669',
    uneasy: '#d97706',
    hostile: '#dc2626',
    conflicted: '#7c3aed',
    neutral: '#64748b',
  }[cat]
}

export function moodNodeStroke(state) {
  const cat = moodCategory(state)
  return {
    positive: '#6ee7b7',
    uneasy: '#fbbf24',
    hostile: '#f87171',
    conflicted: '#a78bfa',
    neutral: '#94a3b8',
  }[cat]
}

export function speechBubbleClass(state) {
  const cat = moodCategory(state)
  return {
    positive: 'bg-emerald-100 text-emerald-950',
    uneasy: 'bg-amber-100 text-amber-950',
    hostile: 'bg-red-100 text-red-950',
    conflicted: 'bg-violet-100 text-violet-950',
    neutral: 'bg-slate-200 text-slate-900',
  }[cat]
}
