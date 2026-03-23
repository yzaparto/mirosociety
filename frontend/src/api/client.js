import axios from 'axios'

const API_BASE = import.meta.env.VITE_API_URL || ''

const api = axios.create({
  baseURL: `${API_BASE}/api`,
  headers: { 'Content-Type': 'application/json' },
})

export default {
  async simulate(rules, population = 25, durationDays = 365, proposedChange = null, segments = null, city = null) {
    const payload = { rules, population, duration_days: durationDays }
    if (proposedChange) payload.proposed_change = proposedChange
    if (segments && segments.length > 0) payload.segments = segments
    if (city) payload.city = city
    const { data } = await api.post('/simulate', payload)
    return data
  },

  streamSimulation(simulationId) {
    const url = `${API_BASE}/api/simulation/${simulationId}/stream`
    return new EventSource(url)
  },

  async getState(simulationId) {
    const { data } = await api.get(`/simulation/${simulationId}/state`)
    return data
  },

  async getAgents(simulationId) {
    const { data } = await api.get(`/simulation/${simulationId}/agents`)
    return data
  },

  async getAgent(simulationId, agentId) {
    const { data } = await api.get(`/simulation/${simulationId}/agent/${agentId}`)
    return data
  },

  async interview(simulationId, agentId, question) {
    const { data } = await api.post(`/simulation/${simulationId}/agent/${agentId}/interview`, { question })
    return data
  },

  async inject(simulationId, event) {
    const { data } = await api.post(`/simulation/${simulationId}/inject`, { event })
    return data
  },

  async fork(simulationId, forkAtDay, changes) {
    const { data } = await api.post(`/simulation/${simulationId}/fork`, { fork_at_day: forkAtDay, changes })
    return data
  },

  async setSpeed(simulationId, mode) {
    const { data } = await api.post(`/simulation/${simulationId}/speed`, { mode })
    return data
  },

  async pause(simulationId) {
    const { data } = await api.post(`/simulation/${simulationId}/pause`)
    return data
  },

  async resume(simulationId) {
    const { data } = await api.post(`/simulation/${simulationId}/resume`)
    return data
  },

  async stop(simulationId) {
    const { data } = await api.post(`/simulation/${simulationId}/stop`)
    return data
  },

  async cancel(simulationId) {
    const { data } = await api.post(`/simulation/${simulationId}/cancel`)
    return data
  },

  async getReport(simulationId) {
    const { data } = await api.get(`/simulation/${simulationId}/report`)
    return data
  },

  async pollReport(simulationId, interval = 3000, maxAttempts = 60) {
    for (let i = 0; i < maxAttempts; i++) {
      const data = await this.getReport(simulationId)
      if (data.status === 'ready' || data.executive_brief) {
        return data.executive_brief ? data : data.report
      }
      if (data.status === 'failed') {
        throw new Error(data.error || 'Report generation failed')
      }
      await new Promise(r => setTimeout(r, interval))
    }
    throw new Error('Report generation timed out')
  },

  async publish(simulationId) {
    const { data } = await api.post(`/simulation/${simulationId}/publish`)
    return data
  },

  async compare(simulationId, forkId) {
    const { data } = await api.get(`/simulation/${simulationId}/compare/${forkId}`)
    return data
  },

  async getGallery(sort = 'recent') {
    const { data } = await api.get(`/gallery`, { params: { sort } })
    return data
  },

  async getPresets() {
    const { data } = await api.get('/presets')
    return data
  },

  async getForecast(simulationId) {
    const { data } = await api.get(`/simulation/${simulationId}/forecast`)
    return data
  },
}
