import axios from 'axios'

const client = axios.create({ baseURL: '/api', timeout: 10000 })

export default {
  async checkHealth() {
    try {
      const { data } = await axios.get('/health')
      return data.status === 'healthy'
    } catch { return false }
  },
  async getStats() {
    const { data } = await client.get('/stats')
    if (!data || typeof data !== 'object') throw new Error('Invalid stats response')
    return data
  },
  async listConversations(params = {}) {
    const mergedParams = { limit: 50, offset: 0, ...params }
    const { data } = await client.get('/conversations/list', { params: mergedParams })
    if (!data || typeof data !== 'object') throw new Error('Invalid conversations response')
    return data
  },
  async getConversationFilters() {
    const { data } = await client.get('/conversations/filters')
    return data
  },
  async getConversation(id) {
    if (!id) throw new Error('Conversation ID is required')
    const { data } = await client.get(`/conversations/${id}`)
    if (!data || typeof data !== 'object') throw new Error('Invalid conversation response')
    return data
  },
  async deleteConversation(id) {
    const { data } = await client.delete(`/conversations/${id}`)
    return data
  },
  async updateConversationMemoryTier(id, memoryTier) {
    const { data } = await client.post(`/conversations/${id}/memory-tier`, {
      memory_tier: memoryTier,
    })
    return data
  },
  async listMemories() {
    const { data } = await client.get('/memories')
    return data
  },
  async listMemorySuggestions(limit = 20) {
    const { data } = await client.get('/memories/suggestions', { params: { limit } })
    return data
  },
  async listMemoryConflicts(limit = 20) {
    const { data } = await client.get('/memories/conflicts', { params: { limit } })
    return data
  },
  async listMemoryCleanupSuggestions(limit = 20) {
    const { data } = await client.get('/memories/cleanup-suggestions', { params: { limit } })
    return data
  },
  async resolveMemoryConflict(payload) {
    const { data } = await client.post('/memories/conflicts/resolve', payload)
    return data
  },
  async createMemory(payload) {
    const { data } = await client.post('/memories', payload)
    return data
  },
  async updateMemory(memoryId, payload) {
    const { data } = await client.post(`/memories/${memoryId}`, payload)
    return data
  },
  async updateMemoryStatus(memoryId, status) {
    const { data } = await client.post(`/memories/${memoryId}/status`, { status })
    return data
  },
  async updateMemoryPriority(memoryId, priority) {
    const { data } = await client.post(`/memories/${memoryId}/priority`, { priority })
    return data
  },
  async updateMemoryClientRules(memoryId, clientRules) {
    const { data } = await client.post(`/memories/${memoryId}/client-rules`, { client_rules: clientRules })
    return data
  },
  async mergeMemories(payload) {
    const { data } = await client.post('/memories/merge', payload)
    return data
  },
  async deleteMemory(memoryId) {
    const { data } = await client.delete(`/memories/${memoryId}`)
    return data
  },
  async extractMemoriesFromConversation(conversationId) {
    const { data } = await client.post(`/memories/extract/${conversationId}`, null, { timeout: 60000 })
    return data
  },
  async getConversationMemories(conversationId) {
    const { data } = await client.get(`/conversations/${conversationId}/memories`)
    return data
  },
  async search(query, limit = 10) {
    const { data } = await client.get('/search', { params: { query, limit } })
    return data
  },
  async getRelated(conversationId, limit = 5) {
    const { data } = await client.get(`/related/${conversationId}`, { params: { limit } })
    return data
  },
  async getAIStatus() {
    const { data } = await client.get('/ai/status')
    return data
  },
  async reloadAIConfig() {
    const { data } = await client.post('/ai/reload')
    return data
  },
  async analyzeConversation(conversationId) {
    const { data } = await client.post(`/analyze/${conversationId}`, null, { timeout: 60000 })
    return data
  },
  async resummarizeConversations(payload) {
    const { data } = await client.post('/conversations/resummarize', payload, { timeout: 120000 })
    return data
  },
  async resummarizeUglyConversations(payload) {
    const { data } = await client.post('/conversations/resummarize-ugly', payload, { timeout: 120000 })
    return data
  },
  async listExportClients() {
    const { data } = await client.get('/export/clients')
    return data
  },
  async simulateMemoryExport(payload) {
    const { data } = await client.post('/memories/export-simulate', payload)
    return data
  },
  async previewConversationExport(conversationId, clientId, selectedMemoryIds = []) {
    const { data } = await client.get(`/conversations/${conversationId}/export`, {
      params: {
        client: clientId,
        selected_memory_ids: selectedMemoryIds.length ? selectedMemoryIds.join(',') : undefined,
      }
    })
    return data
  },
  async applyConversationExport(conversationId, payload) {
    const { data } = await client.post(`/conversations/${conversationId}/export/apply`, payload)
    return data
  },
  async importLocalSessions(payload) {
    const { data } = await client.post('/import/local', payload)
    return data
  },
  async exportBackupBundle() {
    const { data } = await client.post('/backup/export')
    return data
  },
  async getBackupSettings() {
    const { data } = await client.get('/backup/settings')
    return data
  },
  async updateBackupSettings(payload) {
    const { data } = await client.post('/backup/settings', payload)
    return data
  },
  async restoreBackupBundle(payload) {
    const { data } = await client.post('/backup/restore', payload)
    return data
  },
  async previewBackupSource(sourcePath) {
    const { data } = await client.get('/backup/preview', { params: { source_path: sourcePath } })
    return data
  },
  async validateBackupSource(sourcePath) {
    const { data } = await client.get('/backup/validate', { params: { source_path: sourcePath } })
    return data
  },
  async switchPreview(params) {
    const { data } = await client.post('/v2/switch/preview', {
      to_cli: params.to_cli,
      workspace_path: params.workspace_path,
      token_budget: params.token_budget,
      conversation_ids: params.conversation_ids,
      custom_context: params.custom_context,
    }, { timeout: 60000 })
    return data
  },
  async executeSwitch(params) {
    const { data } = await client.post('/v2/switch', params, { timeout: 60000 })
    return data
  },
  async switchHistory() {
    const { data } = await client.get('/v2/switch/history')
    return data
  },
}
