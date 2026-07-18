const API_BASE_URL =
  import.meta.env.VITE_API_URL?.replace(/\/$/, '') ?? 'http://127.0.0.1:8001'

export type HealthResponse = {
  status: string
  model_provider: string
}

export type ProviderHealth = {
  id: string;
  name: string;
  ready: boolean;
  mode: string;
  missing: string[];
  message: string;
  live_checked: boolean;
  live_ready: boolean | null;
  live_message: string | null;
};

export type ProvidersHealth = {
  active_provider: string;
  providers: ProviderHealth[];
};

export type LocalAgent = {
  id: string
  name: string
  description: string
  system_prompt: string
  tools: string[]
  source?: 'builtin' | 'connector' | 'custom'
}

export type CustomAgent = LocalAgent & {
  source: 'custom'
  created_at: string
  updated_at: string
}

export type LocalTeam = {
  id: string
  name: string
  description: string
  agent_ids: string[]
  source?: 'builtin' | 'connector' | 'custom'
}

export type AgentsResponse = {
  agents: LocalAgent[]
  teams: LocalTeam[]
  supervisor_agent_id: string
  supervisor_team_agent_ids: string[]
}

export type Conversation = {
  id: string
  title: string
  selected_agent_ids: string[]
  created_at: string
}

export type Message = {
  id: string
  conversation_id: string
  role: string
  content: string
  agent_name: string | null
  provider_id: string | null
  model_name: string | null
  created_at: string
}

export type ToolExample = {
  description: string
  arguments: Record<string, unknown>
}

export type LocalTool = {
  name: string
  description: string
  parameter_schema: Record<string, unknown>
  examples: ToolExample[]
}

export type ToolsResponse = {
  tools: LocalTool[]
}

export type DatasetColumn = {
  name: string
  column_type: 'string' | 'number'
}

export type ImportedDataset = {
  id: string
  name: string
  description: string
  original_filename: string
  columns: DatasetColumn[]
  tool_name: string
  created_at: string
  updated_at: string
}

export type ConnectorHealth = {
  id: string
  name: string
  purpose: string
  configuration_hint: string
  tool_name: string
  ready: boolean
  missing: string[]
  message: string
}

export type GroupChatEvent = {
  id: string
  conversation_id: string
  event_type: string
  agent_id: string | null
  content: string
  payload: Record<string, unknown>
  created_at: string
}

export type Artifact = {
  id: string
  conversation_id: string
  message_id: string | null
  artifact_type: string
  title: string
  payload: Record<string, unknown>
  created_at: string
}

export type ConversationDetail = Conversation & {
  messages: Message[]
  group_chat_events: GroupChatEvent[]
  artifacts: Artifact[]
}

export async function listCustomAgents(): Promise<CustomAgent[]> {
  return getJson('/custom-agents')
}

export async function createCustomAgent(body: {
  name: string
  description: string
  system_prompt: string
  tools: string[]
}): Promise<CustomAgent> {
  return postJson('/custom-agents', body)
}

export async function updateCustomAgent(
  agentId: string,
  body: {
    name: string
    description: string
    system_prompt: string
    tools: string[]
  },
): Promise<CustomAgent> {
  return putJson(`/custom-agents/${agentId}`, body)
}

export async function deleteCustomAgent(agentId: string): Promise<void> {
  await deleteRequest(`/custom-agents/${agentId}`)
}

export async function getHealth(): Promise<HealthResponse> {
  return getJson('/health')
}

export async function getProvidersHealth(live = false): Promise<ProvidersHealth> {
  return getJson(`/providers/health?live=${live}`)
}

export async function setActiveProvider(providerId: string): Promise<{ active_provider: string }> {
  return putJson('/providers/active', { provider_id: providerId })
}

export async function listAgents(): Promise<AgentsResponse> {
  return getJson('/agents')
}

export async function listTools(): Promise<ToolsResponse> {
  return getJson('/tools')
}

export async function listDatasets(): Promise<ImportedDataset[]> {
  const response = await getJson<{ datasets: ImportedDataset[] }>('/datasets')
  return response.datasets
}

export async function uploadDataset(
  name: string,
  file: File,
  description = '',
): Promise<ImportedDataset> {
  const body = new FormData()
  body.append('name', name)
  body.append('description', description)
  body.append('file', file)

  const response = await fetch(`${API_BASE_URL}/datasets`, {
    method: 'POST',
    body,
  })

  if (!response.ok) {
    throw await apiError(response)
  }

  return response.json()
}

export async function deleteDataset(datasetId: string): Promise<void> {
  await deleteRequest(`/datasets/${datasetId}`)
}

export async function getConnectorsHealth(): Promise<ConnectorHealth[]> {
  const response = await getJson<{ connectors: ConnectorHealth[] }>('/connectors')
  return response.connectors
}

export async function createConversation(
  selectedAgentIds: string[],
): Promise<Conversation> {
  return postJson('/conversations', {
    selected_agent_ids: selectedAgentIds,
  })
}

export async function getConversation(
  conversationId: string,
): Promise<ConversationDetail> {
  return getJson(`/conversations/${conversationId}`)
}


export async function listConversations(): Promise<Conversation[]> {
  return getJson('/conversations')
}

export async function renameConversation(
  conversationId: string,
  title: string,
): Promise<Conversation> {
  return patchJson(`/conversations/${conversationId}`, { title })
}

export async function deleteConversation(conversationId: string): Promise<void> {
  await deleteRequest(`/conversations/${conversationId}`)
}

export async function streamMessage(
  conversationId: string,
  content: string,
  onChunk: (chunk: string) => void,
): Promise<string> {
  const response = await fetch(
    `${API_BASE_URL}/conversations/${conversationId}/messages/stream`,
    {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({ content }),
    },
  )

  if (!response.ok) {
    throw await apiError(response)
  }

  if (!response.body) {
    const text = await response.text()
    onChunk(text)
    return text
  }

  const reader = response.body.getReader()
  const decoder = new TextDecoder()
  let fullText = ''

  while (true) {
    const { value, done } = await reader.read()
    if (done) {
      break
    }

    const chunk = decoder.decode(value, { stream: true })
    fullText += chunk
    onChunk(chunk)
  }

  const finalChunk = decoder.decode()
  if (finalChunk) {
    fullText += finalChunk
    onChunk(finalChunk)
  }

  return fullText
}

async function getJson<T>(path: string): Promise<T> {
  const response = await fetch(`${API_BASE_URL}${path}`)

  if (!response.ok) {
    throw await apiError(response)
  }

  return response.json()
}

async function putJson<T>(
  path: string,
  body: Record<string, unknown>,
): Promise<T> {
  const response = await fetch(`${API_BASE_URL}${path}`, {
    method: 'PUT',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify(body),
  })

  if (!response.ok) {
    throw await apiError(response)
  }

  return response.json()
}

async function patchJson<T>(
  path: string,
  body: Record<string, unknown>,
): Promise<T> {
  const response = await fetch(`${API_BASE_URL}${path}`, {
    method: 'PATCH',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify(body),
  })

  if (!response.ok) {
    throw await apiError(response)
  }

  return response.json()
}

async function deleteRequest(path: string): Promise<void> {
  const response = await fetch(`${API_BASE_URL}${path}`, {
    method: 'DELETE',
  })

  if (!response.ok) {
    throw await apiError(response)
  }
}

async function postJson<T>(
  path: string,
  body: Record<string, unknown>,
): Promise<T> {
  const response = await fetch(`${API_BASE_URL}${path}`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify(body),
  })

  if (!response.ok) {
    throw await apiError(response)
  }

  return response.json()
}

async function apiError(response: Response): Promise<Error> {
  try {
    const payload = await response.json()
    const message =
      payload?.error?.message ?? `Request failed with ${response.status}`
    return new Error(message)
  } catch {
    return new Error(`Request failed with ${response.status}`)
  }
}
