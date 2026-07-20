import { useEffect, useState } from 'react'

import {
  createConversation,
  createCustomAgent,
  deleteConversation,
  deleteCustomAgent,
  deleteDataset,
  getConversation,
  getConnectorsHealth,
  getHealth,
  getProvidersHealth,
  setActiveProvider,
  listConversations,
  listCustomAgents,
  listDatasets,
  listTools,
  streamMessage,
  updateCustomAgent,
  uploadDataset,
  type Artifact,
  type Conversation,
  type CustomAgent,
  type ConnectorHealth,
  type GroupChatEvent,
  type HealthResponse,
  type ImportedDataset,
  type LocalTool,
  type Message,
  type ProvidersHealth,
} from './api'

const emptyStudioForm = {
  name: '',
  description: '',
  system_prompt: '',
  tools: [] as string[],
}

const UI_PROVIDER_IDS = ['ollama', 'openai', 'bedrock'] as const
const HIDDEN_AGENT_TOOL_NAMES = new Set([
  'summarize_findings',
  'build_chart_spec',
  'query_sample_sales',
])

type InspectTab = 'trace' | 'artifacts' | 'tools'
type SettingsView = 'home' | 'agent' | 'knowledge'

const inspectTabs: Array<{ id: InspectTab; label: string }> = [
  { id: 'trace', label: 'Trace' },
  { id: 'artifacts', label: 'Artifacts' },
  { id: 'tools', label: 'Tools' },
]

function App() {
  const [sidebarOpen, setSidebarOpen] = useState(false)
  const [sidebarCollapsed, setSidebarCollapsed] = useState(false)
  const [health, setHealth] = useState<HealthResponse | null>(null)
  const [healthError, setHealthError] = useState<string | null>(null)
  const [activeConversation, setActiveConversation] = useState<Conversation | null>(null)
  const [conversationError, setConversationError] = useState<string | null>(null)
  const [isCreatingConversation, setIsCreatingConversation] = useState(false)
  const [conversations, setConversations] = useState<Conversation[]>([])
  const [conversationsError, setConversationsError] = useState<string | null>(null)
  const [messages, setMessages] = useState<Message[]>([])
  const [groupChatEvents, setGroupChatEvents] = useState<GroupChatEvent[]>([])
  const [artifacts, setArtifacts] = useState<Artifact[]>([])
  const [messageText, setMessageText] = useState('')
  const [isSendingMessage, setIsSendingMessage] = useState(false)
  const [messageError, setMessageError] = useState<string | null>(null)
  const [streamingResponse, setStreamingResponse] = useState('')
  const [isLoadingMessages, setIsLoadingMessages] = useState(false)
  const [messagesError, setMessagesError] = useState<string | null>(null)
  const [providerHealth, setProviderHealth] = useState<ProvidersHealth | null>(null)
  const [providerHealthError, setProviderHealthError] = useState<string | null>(null)
  const [providerSwitching, setProviderSwitching] = useState(false)
  const [providerMenuOpen, setProviderMenuOpen] = useState(false)
  const [tools, setTools] = useState<LocalTool[]>([])
  const [toolsError, setToolsError] = useState<string | null>(null)
  const [isDeletingConversation, setIsDeletingConversation] = useState(false)
  const [deleteError, setDeleteError] = useState<string | null>(null)
  const [customAgents, setCustomAgents] = useState<CustomAgent[]>([])
  const [customAgentsError, setCustomAgentsError] = useState<string | null>(null)
  const [editingAgentId, setEditingAgentId] = useState<string | null>(null)
  const [studioForm, setStudioForm] = useState(emptyStudioForm)
  const [studioError, setStudioError] = useState<string | null>(null)
  const [isSavingStudio, setIsSavingStudio] = useState(false)
  const [settingsView, setSettingsView] = useState<SettingsView>('home')
  const [settingsOpen, setSettingsOpen] = useState(false)
  const [inspectOpen, setInspectOpen] = useState(false)
  const [inspectTab, setInspectTab] = useState<InspectTab>('trace')
  const [datasets, setDatasets] = useState<ImportedDataset[]>([])
  const [datasetsError, setDatasetsError] = useState<string | null>(null)
  const [datasetName, setDatasetName] = useState('')
  const [datasetFile, setDatasetFile] = useState<File | null>(null)
  const [datasetError, setDatasetError] = useState<string | null>(null)
  const [isUploadingDataset, setIsUploadingDataset] = useState(false)
  const [connectors, setConnectors] = useState<ConnectorHealth[]>([])
  const [connectorsError, setConnectorsError] = useState<string | null>(null)

  useEffect(() => {
    let ignore = false

    getHealth()
      .then((response) => {
        if (!ignore) {
          setHealth(response)
          setHealthError(null)
        }
      })
      .catch((error: unknown) => {
        if (!ignore) {
          setHealth(null)
          setHealthError(error instanceof Error ? error.message : 'Backend unavailable')
        }
      })

    return () => {
      ignore = true
    }
  }, [])

  useEffect(() => {
    let ignore = false

    listCustomAgents()
      .then((response) => {
        if (!ignore) {
          setCustomAgents(response)
          setCustomAgentsError(null)
        }
      })
      .catch((error: unknown) => {
        if (!ignore) {
          setCustomAgents([])
          setCustomAgentsError(error instanceof Error ? error.message : 'Custom agents unavailable')
        }
      })

    return () => {
      ignore = true
    }
  }, [])

  useEffect(() => {
    getConnectorsHealth()
      .then((response) => {
        setConnectors(response)
        setConnectorsError(null)
      })
      .catch((error: unknown) => {
        setConnectors([])
        setConnectorsError(error instanceof Error ? error.message : 'Connectors unavailable')
      })
  }, [])

  useEffect(() => {
    let ignore = false

    listDatasets()
      .then((response) => {
        if (!ignore) {
          setDatasets(response)
          setDatasetsError(null)
        }
      })
      .catch((error: unknown) => {
        if (!ignore) {
          setDatasets([])
          setDatasetsError(error instanceof Error ? error.message : 'Datasets unavailable')
        }
      })

    return () => {
      ignore = true
    }
  }, [])

  useEffect(() => {
    let ignore = false

    listConversations()
      .then((response) => {
        if (!ignore) {
          setConversations(response)
          setConversationsError(null)
        }
      })
      .catch((error: unknown) => {
        if (!ignore) {
          setConversations([])
          setConversationsError(error instanceof Error ? error.message : 'Conversations unavailable')
        }
      })

    return () => {
      ignore = true
    }
  }, [])

  useEffect(() => {
    getProvidersHealth()
      .then((response) => {
        setProviderHealth(response)
        setProviderHealthError(null)
      })
      .catch((error: unknown) => {
        setProviderHealth(null)
        setProviderHealthError(error instanceof Error ? error.message : 'Providers unavailable')
      })
  }, [])

  useEffect(() => {
    let ignore = false

    listTools()
      .then((response) => {
        if (!ignore) {
          setTools(response.tools)
          setToolsError(null)
        }
      })
      .catch((error: unknown) => {
        if (!ignore) {
          setTools([])
          setToolsError(error instanceof Error ? error.message : 'Tools unavailable')
        }
      })

    return () => {
      ignore = true
    }
  }, [])

  const providerLabel = health?.model_provider ?? (healthError ? 'offline' : 'loading')
  const selectableProviders = (providerHealth?.providers ?? []).filter((provider) =>
    UI_PROVIDER_IDS.includes(provider.id as (typeof UI_PROVIDER_IDS)[number]),
  )
  const rawActiveProviderId =
    providerHealth?.active_provider ?? health?.model_provider ?? 'ollama'
  const activeProviderId = selectableProviders.some((provider) => provider.id === rawActiveProviderId)
    ? rawActiveProviderId
    : (selectableProviders.find((provider) => provider.id === 'ollama')?.id ??
      selectableProviders[0]?.id ??
      'ollama')
  const activeProvider = selectableProviders.find((provider) => provider.id === activeProviderId)
  const providerStatus = providerHealthError
    ? 'error'
    : !providerHealth
      ? 'loading'
      : activeProvider?.ready
        ? 'ready'
        : 'error'
  const connectorToolNames = new Set(
    connectors.filter((connector) => connector.ready).map((connector) => connector.tool_name),
  )
  const assignableTools = tools.filter(
    (tool) =>
      !connectorToolNames.has(tool.name) && !HIDDEN_AGENT_TOOL_NAMES.has(tool.name),
  )
  const managedCustomAgents = customAgents.filter((agent) => !isStaleCustomAgent(agent))
  const managedCustomAgentIds = managedCustomAgents.map((agent) => agent.id)

  function toolLabel(toolName: string) {
    return displayToolLabel(toolName, connectors, datasets)
  }

  function formatAgentTools(toolNames: string[]) {
    const visibleTools = toolNames.filter(
      (toolName) => !HIDDEN_AGENT_TOOL_NAMES.has(toolName),
    )
    if (visibleTools.length === 0) {
      return 'No tools configured'
    }
    return visibleTools.map((toolName) => toolLabel(toolName)).join(', ')
  }

  async function handleProviderChange(providerId: string) {
    if (providerId === activeProviderId) {
      return
    }

    setProviderSwitching(true)
    setProviderHealthError(null)

    try {
      await setActiveProvider(providerId)
      const [healthResponse, providersResponse] = await Promise.all([
        getHealth(),
        getProvidersHealth(),
      ])
      setHealth(healthResponse)
      setProviderHealth(providersResponse)
    } catch (error: unknown) {
      setProviderHealthError(
        error instanceof Error ? error.message : 'Could not switch model provider',
      )
    } finally {
      setProviderSwitching(false)
    }
  }

  async function handleCreateConversation(): Promise<Conversation | null> {
    setIsCreatingConversation(true)
    setConversationError(null)

    try {
      const conversation = await createConversation(managedCustomAgentIds)
      setActiveConversation(conversation)
      setMessages([])
      setGroupChatEvents([])
      setArtifacts([])
      setStreamingResponse('')
      setMessageError(null)
      setMessagesError(null)
      setConversations((current) => [conversation, ...current])
      return conversation
    } catch (error: unknown) {
      setConversationError(error instanceof Error ? error.message : 'Could not create conversation')
      return null
    } finally {
      setIsCreatingConversation(false)
    }
  }

  function handleNewChat() {
    setActiveConversation(null)
    setMessages([])
    setGroupChatEvents([])
    setArtifacts([])
    setStreamingResponse('')
    setMessageError(null)
    setMessagesError(null)
    setConversationError(null)
    setDeleteError(null)
  }

  async function ensureActiveConversation(): Promise<Conversation | null> {
    if (activeConversation) {
      return activeConversation
    }
    return handleCreateConversation()
  }

  async function handleSendMessage(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault()

    if (messageText.trim().length === 0 || isSendingMessage || isCreatingConversation) {
      return
    }

    const conversation = await ensureActiveConversation()
    if (!conversation) {
      return
    }

    const content = messageText.trim()
    const isFirstMessage =
      messages.length === 0 && conversation.title === 'New conversation'
    const autoTitle = isFirstMessage ? titleFromFirstMessage(content) : null

    setMessageText('')
    setIsSendingMessage(true)
    setMessageError(null)
    setStreamingResponse('')

    if (autoTitle) {
      const titledConversation = { ...conversation, title: autoTitle }
      setActiveConversation(titledConversation)
      setConversations((current) =>
        current.map((item) => (item.id === conversation.id ? titledConversation : item)),
      )
    }

    setMessages((current) => [
      ...current,
      {
        id: crypto.randomUUID(),
        conversation_id: conversation.id,
        role: 'user',
        content,
        agent_name: null,
        provider_id: null,
        model_name: null,
        created_at: new Date().toISOString(),
      },
    ])

    try {
      let assistantContent = ''

      await streamMessage(conversation.id, content, (chunk) => {
        assistantContent += chunk
        setStreamingResponse(assistantContent)
      })

      setMessages((current) => [
        ...current,
        {
          id: crypto.randomUUID(),
          conversation_id: conversation.id,
          role: 'assistant',
          content: assistantContent,
          agent_name: null,
          provider_id: null,
          model_name: null,
          created_at: new Date().toISOString(),
        },
      ])

      const conversationDetail = await getConversation(conversation.id)
      setMessages(conversationDetail.messages)
      setGroupChatEvents(conversationDetail.group_chat_events)
      setArtifacts(conversationDetail.artifacts)
      setActiveConversation({
        id: conversationDetail.id,
        title: conversationDetail.title,
        selected_agent_ids: conversationDetail.selected_agent_ids,
        created_at: conversationDetail.created_at,
      })
      setConversations((current) =>
        current.map((item) =>
          item.id === conversationDetail.id
            ? {
                id: conversationDetail.id,
                title: conversationDetail.title,
                selected_agent_ids: conversationDetail.selected_agent_ids,
                created_at: conversationDetail.created_at,
              }
            : item,
        ),
      )
      setInspectTab(
        conversationDetail.artifacts.length > 0
          ? 'artifacts'
          : conversationDetail.group_chat_events.length > 0
            ? 'trace'
            : inspectTab,
      )
      setStreamingResponse('')
    } catch (error: unknown) {
      setMessageError(error instanceof Error ? error.message : 'Could not send message')
    } finally {
      setIsSendingMessage(false)
    }
  }

  async function loadConversationMessages(conversation: Conversation) {
    setActiveConversation(conversation)
    setIsLoadingMessages(true)
    setMessagesError(null)
    setDeleteError(null)
    setGroupChatEvents([])
    setArtifacts([])
    setStreamingResponse('')
    setMessageError(null)

    try {
      const conversationDetail = await getConversation(conversation.id)
      setMessages(conversationDetail.messages)
      setGroupChatEvents(conversationDetail.group_chat_events)
      setArtifacts(conversationDetail.artifacts)
      setInspectTab(
        conversationDetail.artifacts.length > 0
          ? 'artifacts'
          : conversationDetail.group_chat_events.length > 0
            ? 'trace'
            : 'trace',
      )
    } catch (error: unknown) {
      setMessages([])
      setGroupChatEvents([])
      setArtifacts([])
      setMessagesError(error instanceof Error ? error.message : 'Could not load messages')
    } finally {
      setIsLoadingMessages(false)
    }
  }

  async function handleDeleteConversation() {
    if (!activeConversation) {
      return
    }

    const confirmed = window.confirm(
      `Delete "${activeConversation.title}" and all of its messages?`,
    )
    if (!confirmed) {
      return
    }

    setIsDeletingConversation(true)
    setDeleteError(null)

    try {
      await deleteConversation(activeConversation.id)
      setConversations((current) =>
        current.filter((conversation) => conversation.id !== activeConversation.id),
      )
      setActiveConversation(null)
      setMessages([])
      setGroupChatEvents([])
      setArtifacts([])
    } catch (error: unknown) {
      setDeleteError(error instanceof Error ? error.message : 'Could not delete conversation')
    } finally {
      setIsDeletingConversation(false)
    }
  }

  async function refreshAgentsCatalog() {
    const savedCustomAgents = await listCustomAgents()
    setCustomAgents(savedCustomAgents)
    setCustomAgentsError(null)
  }

  async function refreshToolsCatalog() {
    const [toolsResponse, datasetResponse] = await Promise.all([listTools(), listDatasets()])
    setTools(toolsResponse.tools)
    setToolsError(null)
    setDatasets(datasetResponse)
    setDatasetsError(null)
  }

  function resetStudioForm() {
    setEditingAgentId(null)
    setStudioForm(emptyStudioForm)
    setStudioError(null)
  }

  function openNewAgentForm() {
    setEditingAgentId(null)
    setStudioForm(emptyStudioForm)
    setStudioError(null)
    setSettingsView('agent')
    setSettingsOpen(true)
    setSidebarOpen(false)
  }

  function openAgents() {
    setSettingsView('home')
    setSettingsOpen(true)
    setSidebarOpen(false)
  }

  function startEditingCustomAgent(agent: CustomAgent) {
    setEditingAgentId(agent.id)
    setStudioForm({
      name: agent.name,
      description: agent.description,
      system_prompt: agent.system_prompt,
      tools: agent.tools,
    })
    setStudioError(null)
    setSettingsView('agent')
    setSettingsOpen(true)
  }

  function openKnowledgeStudio() {
    setDatasetError(null)
    setSettingsView('knowledge')
    setSettingsOpen(true)
    setSidebarOpen(false)
  }

  function closeSettings() {
    setSettingsOpen(false)
    setSettingsView('home')
    resetStudioForm()
  }

  function backToSettingsHome() {
    if (
      settingsView === 'knowledge' &&
      (editingAgentId !== null ||
        studioForm.name.trim().length > 0 ||
        studioForm.system_prompt.trim().length > 0 ||
        studioForm.tools.length > 0)
    ) {
      setSettingsView('agent')
      setDatasetError(null)
      return
    }

    setSettingsView('home')
    resetStudioForm()
    setDatasetError(null)
  }

  function toggleStudioTool(toolName: string) {
    setStudioForm((current) => ({
      ...current,
      tools: current.tools.includes(toolName)
        ? current.tools.filter((name) => name !== toolName)
        : [...current.tools, toolName],
    }))
  }

  async function handleSaveCustomAgent(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault()

    if (studioForm.name.trim().length === 0 || studioForm.system_prompt.trim().length === 0) {
      setStudioError('Name and instructions are required')
      return
    }

    const selectedTools = studioForm.tools.filter(
      (toolName) => !HIDDEN_AGENT_TOOL_NAMES.has(toolName),
    )
    if (selectedTools.length === 0) {
      setStudioError(
        'Select at least one tool — a backend connector (Sales pipeline / Account lookup) or a CSV knowledge tool.',
      )
      return
    }

    setIsSavingStudio(true)
    setStudioError(null)

    const instructions = studioForm.system_prompt.trim()
    const payload = {
      name: studioForm.name.trim(),
      description: studioForm.description.trim() || instructions.slice(0, 120),
      system_prompt: instructions,
      tools: selectedTools,
    }

    try {
      if (editingAgentId) {
        await updateCustomAgent(editingAgentId, payload)
      } else {
        await createCustomAgent(payload)
      }

      await refreshAgentsCatalog()
      setSettingsView('home')
      resetStudioForm()
    } catch (error: unknown) {
      setStudioError(error instanceof Error ? error.message : 'Could not save custom agent')
    } finally {
      setIsSavingStudio(false)
    }
  }

  async function handleDeleteCustomAgent(agentId: string) {
    const agent = customAgents.find((item) => item.id === agentId)
    if (!agent) {
      return
    }

    const confirmed = window.confirm(`Delete custom agent "${agent.name}"?`)
    if (!confirmed) {
      return
    }

    setIsSavingStudio(true)
    setStudioError(null)

    try {
      await deleteCustomAgent(agentId)
      if (editingAgentId === agentId) {
        resetStudioForm()
      }
      await refreshAgentsCatalog()
    } catch (error: unknown) {
      setStudioError(error instanceof Error ? error.message : 'Could not delete custom agent')
    } finally {
      setIsSavingStudio(false)
    }
  }

  async function handleUploadDataset(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault()

    if (datasetName.trim().length === 0 || datasetFile === null) {
      setDatasetError('Dataset name and CSV file are required')
      return
    }

    setIsUploadingDataset(true)
    setDatasetError(null)

    try {
      await uploadDataset(datasetName.trim(), datasetFile)
      setDatasetName('')
      setDatasetFile(null)
      await refreshToolsCatalog()
    } catch (error: unknown) {
      setDatasetError(error instanceof Error ? error.message : 'Could not import dataset')
    } finally {
      setIsUploadingDataset(false)
    }
  }

  async function handleDeleteDataset(datasetId: string) {
    const dataset = datasets.find((item) => item.id === datasetId)
    if (!dataset) {
      return
    }

    const confirmed = window.confirm(`Delete dataset "${dataset.name}" and its query tool?`)
    if (!confirmed) {
      return
    }

    setIsUploadingDataset(true)
    setDatasetError(null)

    try {
      await deleteDataset(datasetId)
      await refreshToolsCatalog()
    } catch (error: unknown) {
      setDatasetError(error instanceof Error ? error.message : 'Could not delete dataset')
    } finally {
      setIsUploadingDataset(false)
    }
  }

  return (
    <main
      className="app-shell gpt-layout"
      data-sidebar-open={sidebarOpen}
      data-sidebar-collapsed={sidebarCollapsed}
    >
      <button
        className="gpt-sidebar-scrim"
        type="button"
        aria-label="Close sidebar"
        onClick={() => setSidebarOpen(false)}
      />
      <aside className="gpt-sidebar" aria-label="Chats">
        <div className="gpt-sidebar-header">
          <button className="gpt-brand" type="button" onClick={handleNewChat}>
            <span className="gpt-brand-mark" aria-hidden="true">
              LA
            </span>
            <span>ChatRoom</span>
          </button>
          <button
            className="gpt-sidebar-control"
            type="button"
            onClick={() => {
              setSidebarOpen(false)
              setSidebarCollapsed(true)
            }}
            aria-label="Close sidebar"
            title="Close sidebar"
          >
            <Icon name="sidebar" />
          </button>
        </div>

        <nav className="gpt-primary-nav" aria-label="Main navigation">
          <button
            className="gpt-nav-item"
            type="button"
            onClick={() => {
              handleNewChat()
              setSidebarOpen(false)
            }}
          >
            <Icon name="compose" />
            <span>New chat</span>
          </button>
          <button
            className="gpt-nav-item"
            data-active={settingsOpen && settingsView !== 'knowledge'}
            type="button"
            onClick={openAgents}
          >
            <Icon name="agents" />
            <span>Agents</span>
          </button>
          <button
            className="gpt-nav-item"
            data-active={settingsOpen && settingsView === 'knowledge'}
            type="button"
            onClick={openKnowledgeStudio}
          >
            <Icon name="library" />
            <span>Knowledge</span>
          </button>
        </nav>

        <section className="gpt-history" aria-label="Chat history">
          <h2>Chats</h2>
          <nav className="gpt-conv-list">
            {conversationsError ? <p className="panel-message">{conversationsError}</p> : null}
            {conversations.length === 0 ? (
              <p className="gpt-conv-empty">Your chats will appear here.</p>
            ) : (
              conversations.map((conversation) => (
                <button
                  className="gpt-conv-item"
                  data-active={conversation.id === activeConversation?.id}
                  disabled={isSendingMessage || isLoadingMessages}
                  key={conversation.id}
                  onClick={() => {
                    void loadConversationMessages(conversation)
                    setSidebarOpen(false)
                  }}
                  type="button"
                >
                  {conversation.title}
                </button>
              ))
            )}
          </nav>
        </section>

        <footer className="gpt-sidebar-footer">
          <div
            className="gpt-model-select"
            data-status={providerStatus}
            onBlur={(event) => {
              if (!event.currentTarget.contains(event.relatedTarget)) {
                setProviderMenuOpen(false)
              }
            }}
          >
            <button
              className="gpt-model-trigger"
              type="button"
              aria-expanded={providerMenuOpen}
              aria-haspopup="listbox"
              aria-label={`LLM provider: ${activeProvider?.name ?? providerLabel}`}
              disabled={providerSwitching || selectableProviders.length === 0}
              onClick={() => setProviderMenuOpen((isOpen) => !isOpen)}
            >
              <span className="provider-dot" aria-hidden="true" />
              <span className="gpt-model-copy">
                <small>LLM provider</small>
                <strong>{activeProvider?.name ?? providerLabel}</strong>
              </span>
              <span className="gpt-model-chevron" aria-hidden="true">
                {providerMenuOpen ? '⌄' : '⌃'}
              </span>
            </button>
            {providerMenuOpen ? (
              <div
                className="gpt-model-menu"
                role="listbox"
                aria-label="Available LLM providers"
              >
                <p className="gpt-model-menu-title">LLM providers</p>
                {selectableProviders.map((provider) => {
                  const isActive = provider.id === activeProviderId
                  const status = isActive
                    ? 'Active · Configured'
                    : provider.ready
                      ? 'Configured'
                      : 'Not configured'

                  return (
                    <button
                      className="gpt-model-option"
                      type="button"
                      role="option"
                      aria-label={`${provider.name}: ${status}`}
                      aria-selected={isActive}
                      disabled={providerSwitching || !provider.ready}
                      key={provider.id}
                      onClick={() => {
                        setProviderMenuOpen(false)
                        void handleProviderChange(provider.id)
                      }}
                    >
                      <span>{provider.name}</span>
                      <small>{status}</small>
                    </button>
                  )
                })}
                <p className="gpt-model-menu-note">
                  Additional providers become selectable when configured in the backend.
                </p>
              </div>
            ) : null}
          </div>
          <button className="gpt-footer-btn" type="button" onClick={openAgents}>
            <Icon name="settings" />
            <span>Settings</span>
          </button>
        </footer>
      </aside>

      <div className="gpt-main">
        <header className="gpt-topbar">
          <div className="gpt-topbar-leading">
            <button
              className="gpt-mobile-menu"
              type="button"
              onClick={() => {
                setSidebarCollapsed(false)
                setSidebarOpen(true)
              }}
              aria-label="Open sidebar"
              title="Open sidebar"
            >
              <Icon name="sidebar" />
            </button>
            <h1 className="gpt-topbar-title">
              {activeProvider?.name ?? 'ChatRoom'}
              <span className="gpt-title-chevron" aria-hidden="true">⌄</span>
            </h1>
          </div>
          <div className="gpt-topbar-actions">
            {activeConversation ? (
              <button
                className="gpt-icon-btn danger-text"
                type="button"
                onClick={() => {
                  void handleDeleteConversation()
                }}
                disabled={isDeletingConversation || isSendingMessage}
                title="Delete chat"
              >
                Delete
              </button>
            ) : null}
            <button
              className="gpt-icon-btn"
              data-active={inspectOpen}
              type="button"
              onClick={() => setInspectOpen((open) => !open)}
              title="Inspect trace and tools"
            >
              Inspect
            </button>
          </div>
        </header>

        <div className="gpt-chat-scroll">
          <div className="gpt-chat-inner">
            {isLoadingMessages ? <p className="panel-message">Loading messages…</p> : null}
            {messagesError ? <p className="panel-message">{messagesError}</p> : null}
            {deleteError ? <p className="panel-message">{deleteError}</p> : null}

            {messages.length === 0 &&
            !streamingResponse &&
            !isSendingMessage &&
            !isLoadingMessages ? (
              <div className="gpt-welcome">
                <h2>How can I help you today?</h2>
                <p>Ask about sales pipeline, accounts, or your uploaded data.</p>
              </div>
            ) : null}

            {messages.map((message) => (
              <article className="gpt-message" data-role={message.role} key={message.id}>
                <div className="gpt-message-label">{messageDisplayName(message)}</div>
                <div className="gpt-message-body">{message.content}</div>
              </article>
            ))}

            {isSendingMessage && !streamingResponse ? (
              <article className="gpt-message" data-role="assistant" aria-live="polite">
                <div className="gpt-message-label">assistant</div>
                <div className="gpt-thinking" role="status">
                  <span className="gpt-thinking-dots" aria-hidden="true">
                    <span />
                    <span />
                    <span />
                  </span>
                  <span className="gpt-thinking-label">Thinking</span>
                </div>
              </article>
            ) : null}

            {streamingResponse ? (
              <article className="gpt-message" data-role="assistant">
                <div className="gpt-message-label">assistant</div>
                <div className="gpt-message-body">
                  {streamingResponse}
                  {isSendingMessage ? <span className="gpt-stream-cursor" aria-hidden="true" /> : null}
                </div>
              </article>
            ) : null}
          </div>
        </div>

        <div className="gpt-composer-wrap">
          <form className="gpt-composer" onSubmit={handleSendMessage}>
            <textarea
              value={messageText}
              onChange={(event) => setMessageText(event.target.value)}
              onKeyDown={(event) => {
                if (event.key === 'Enter' && !event.shiftKey) {
                  event.preventDefault()
                  event.currentTarget.form?.requestSubmit()
                }
              }}
              placeholder="Message ChatRoom…"
              disabled={isSendingMessage || isCreatingConversation}
              rows={1}
            />
            <button
              className="gpt-send-btn"
              type="submit"
              disabled={
                isSendingMessage || isCreatingConversation || messageText.trim().length === 0
              }
              aria-label="Send message"
            >
              {isSendingMessage ? '…' : '↑'}
            </button>
          </form>
          {messageError ? <p className="panel-message">{messageError}</p> : null}
          {conversationError ? <p className="panel-message">{conversationError}</p> : null}
          <p className="gpt-composer-hint">
            {activeProvider?.name ?? providerLabel}
            {managedCustomAgents.length > 0
              ? ` · ${managedCustomAgents.length} custom agent${managedCustomAgents.length === 1 ? '' : 's'}`
              : ''}
          </p>
        </div>
      </div>

      {inspectOpen ? (
        <aside className="gpt-inspect" aria-label="Inspect">
          <header className="gpt-inspect-header">
            <strong>Inspect</strong>
            <button className="gpt-icon-btn" type="button" onClick={() => setInspectOpen(false)}>
              Close
            </button>
          </header>
          <div className="tab-bar inspect-tabs" role="tablist">
            {inspectTabs.map((tab) => {
              const count =
                tab.id === 'trace'
                  ? groupChatEvents.length
                  : tab.id === 'artifacts'
                    ? artifacts.length
                    : tools.length

              return (
                <button
                  className="tab-button"
                  type="button"
                  role="tab"
                  aria-selected={inspectTab === tab.id}
                  data-active={inspectTab === tab.id}
                  key={tab.id}
                  onClick={() => setInspectTab(tab.id)}
                >
                  {tab.label}
                  {count > 0 ? ` (${count})` : ''}
                </button>
              )
            })}
          </div>
          <div className="inspect-body gpt-inspect-body">
            {inspectTab === 'trace' ? (
              groupChatEvents.length > 0 ? (
                <div className="event-list">
                  {groupChatEvents.map((event) => (
                    <article className="event-row" data-event-type={event.event_type} key={event.id}>
                      <div>
                        <strong>{formatEventType(event.event_type)}</strong>
                        {event.agent_id ? <small>{event.agent_id}</small> : null}
                      </div>
                      <p>{event.content}</p>
                      {event.event_type === 'tool_finished' &&
                      event.payload.output !== undefined ? (
                        <pre>{formatJson(event.payload.output)}</pre>
                      ) : null}
                    </article>
                  ))}
                </div>
              ) : (
                <p className="helper-text">Send a message to see routing and tool calls.</p>
              )
            ) : null}

            {inspectTab === 'artifacts' ? (
              artifacts.length > 0 ? (
                <div className="artifact-list">
                  {artifacts.map((artifact) => (
                    <article className="artifact-card" key={artifact.id}>
                      <div className="artifact-header">
                        <div>
                          <strong>{artifact.title}</strong>
                          <small>{artifact.artifact_type}</small>
                        </div>
                      </div>
                      <ChartArtifact artifact={artifact} />
                    </article>
                  ))}
                </div>
              ) : (
                <p className="helper-text">Charts and outputs appear here.</p>
              )
            ) : null}

            {inspectTab === 'tools' ? (
              toolsError ? (
                <p className="panel-message">{toolsError}</p>
              ) : tools.length > 0 ? (
                <div className="tool-list">
                  {tools.map((tool) => (
                    <details className="tool-card" key={tool.name}>
                      <summary>
                        <span>
                          <strong>{toolLabel(tool.name)}</strong>
                          <small className="tool-source">
                            {toolSourceLabel(tool.name, connectors, datasets)}
                          </small>
                          <small className="tool-id">Tool ID: {tool.name}</small>
                          <small>{tool.description}</small>
                        </span>
                      </summary>
                      <div className="tool-card-body">
                        <div>
                          <h3>Parameters</h3>
                          <pre>{formatJson(tool.parameter_schema)}</pre>
                        </div>
                        {tool.examples.length > 0 ? (
                          <div>
                            <h3>Examples</h3>
                            <div className="tool-example-list">
                              {tool.examples.map((example) => (
                                <div className="tool-example" key={example.description}>
                                  <p>{example.description}</p>
                                  <pre>{formatJson(example.arguments)}</pre>
                                </div>
                              ))}
                            </div>
                          </div>
                        ) : null}
                      </div>
                    </details>
                  ))}
                </div>
              ) : (
                <p className="helper-text">Loading tools…</p>
              )
            ) : null}
          </div>
        </aside>
      ) : null}

      {settingsOpen ? (
        <div className="gpt-modal-backdrop" onClick={closeSettings} role="presentation">
          <div
            className="gpt-modal"
            onClick={(event) => event.stopPropagation()}
            role="dialog"
            aria-label="Settings"
          >
            <header className="gpt-modal-header">
              <div className="gpt-modal-heading">
                {settingsView !== 'home' ? (
                  <button className="text-button" type="button" onClick={backToSettingsHome}>
                    ← Back
                  </button>
                ) : null}
                <h2>
                  {settingsView === 'agent'
                    ? editingAgentId
                      ? 'Edit agent'
                      : 'Agent Studio'
                    : settingsView === 'knowledge'
                      ? 'Knowledge Base Studio'
                      : 'Agents'}
                </h2>
              </div>
              <button className="gpt-icon-btn" type="button" onClick={closeSettings}>
                Close
              </button>
            </header>
            <div className="gpt-modal-body configure-panel">
              {settingsView === 'home' ? (
                <>
                  <section className="setup-section">
                    <h3 className="studio-heading">Studios</h3>
                    <p className="helper-text">
                      Create a specialist agent, or upload CSV knowledge tools.
                    </p>
                    <div className="available-card">
                      <p className="available-card-label">Available options</p>
                      <div className="available-list" role="list">
                        <button
                          className="available-row"
                          type="button"
                          role="listitem"
                          onClick={openNewAgentForm}
                        >
                          <span className="available-row-copy">
                            <strong>Create agent</strong>
                            <small>
                              Open Agent Studio and choose tools like Snowflake SQL, API lookup, or
                              CSV knowledge.
                            </small>
                          </span>
                          <span className="available-row-chevron" aria-hidden="true">
                            →
                          </span>
                        </button>
                        <button
                          className="available-row"
                          type="button"
                          role="listitem"
                          onClick={openKnowledgeStudio}
                        >
                          <span className="available-row-copy">
                            <strong>Create knowledge base</strong>
                            <small>
                              Open Knowledge Base Studio to upload a CSV as a query tool.
                            </small>
                          </span>
                          <span className="available-row-chevron" aria-hidden="true">
                            →
                          </span>
                        </button>
                      </div>
                    </div>
                  </section>

                  <section className="setup-section">
                    <p className="step-label">Your agents</p>
                    {customAgentsError ? <p className="panel-message">{customAgentsError}</p> : null}
                    {managedCustomAgents.length > 0 ? (
                      <div className="compact-item-list">
                        {managedCustomAgents.map((agent) => (
                          <div className="compact-item-row" key={agent.id}>
                            <div>
                              <strong>{agent.name}</strong>
                              <small>{formatAgentTools(agent.tools)}</small>
                            </div>
                            <div className="studio-inline-actions">
                              <button
                                className="text-button"
                                type="button"
                                onClick={() => startEditingCustomAgent(agent)}
                              >
                                Edit
                              </button>
                              <button
                                className="text-button danger-text"
                                type="button"
                                onClick={() => {
                                  void handleDeleteCustomAgent(agent.id)
                                }}
                                disabled={isSavingStudio}
                              >
                                Delete
                              </button>
                            </div>
                          </div>
                        ))}
                      </div>
                    ) : (
                      <p className="helper-text compact">No custom agents yet.</p>
                    )}
                  </section>
                </>
              ) : null}

              {settingsView === 'agent' ? (
                <section className="setup-section">
                  <h3 className="studio-heading">Tools</h3>
                  <p className="helper-text">Tools are used by the agent to perform tasks.</p>
                  {customAgentsError ? <p className="panel-message">{customAgentsError}</p> : null}
                  {connectorsError ? <p className="panel-message">{connectorsError}</p> : null}
                  <form className="studio-form" onSubmit={handleSaveCustomAgent}>
                    <input
                      className="studio-input"
                      value={studioForm.name}
                      onChange={(event) =>
                        setStudioForm((current) => ({ ...current, name: event.target.value }))
                      }
                      placeholder="Agent name"
                      disabled={isSavingStudio}
                    />
                    <textarea
                      className="studio-textarea"
                      value={studioForm.system_prompt}
                      onChange={(event) =>
                        setStudioForm((current) => ({
                          ...current,
                          system_prompt: event.target.value,
                        }))
                      }
                      placeholder="What should this agent do?"
                      disabled={isSavingStudio}
                    />

                    <div className="available-card">
                      <p className="available-card-label">Available tools</p>
                      <div className="available-list" role="list">
                        {connectors.map((connector) => {
                          const selected = studioForm.tools.includes(connector.tool_name)
                          return (
                            <button
                              className="available-row"
                              data-selected={selected}
                              data-ready={connector.ready}
                              key={connector.tool_name}
                              type="button"
                              role="listitem"
                              onClick={() => {
                                if (connector.ready) {
                                  toggleStudioTool(connector.tool_name)
                                }
                              }}
                              disabled={isSavingStudio || !connector.ready}
                              title={
                                connector.ready
                                  ? connector.purpose
                                  : connector.message || 'Not configured'
                              }
                            >
                              <span className="available-row-copy">
                                <strong>{connectorDisplayLabel(connector)}</strong>
                                <small className="tool-source">
                                  Pre-configured tool — Backend configuration
                                </small>
                                <small>
                                  {connector.ready
                                    ? connector.purpose
                                    : connector.message || 'Not configured in .env'}
                                </small>
                              </span>
                              <span className="available-row-check" aria-hidden="true">
                                {selected ? '✓' : ''}
                              </span>
                            </button>
                          )
                        })}
                        {assignableTools.map((tool) => {
                          const selected = studioForm.tools.includes(tool.name)
                          return (
                            <button
                              className="available-row"
                              data-selected={selected}
                              key={tool.name}
                              type="button"
                              role="listitem"
                              onClick={() => toggleStudioTool(tool.name)}
                              disabled={isSavingStudio}
                            >
                              <span className="available-row-copy">
                                <strong>{toolLabel(tool.name)}</strong>
                                <small className="tool-source">
                                  {toolSourceLabel(tool.name, connectors, datasets)}
                                </small>
                                <small>{tool.description}</small>
                              </span>
                              <span className="available-row-check" aria-hidden="true">
                                {selected ? '✓' : ''}
                              </span>
                            </button>
                          )
                        })}
                        <button
                          className="available-row available-row-action"
                          type="button"
                          role="listitem"
                          onClick={openKnowledgeStudio}
                          disabled={isSavingStudio}
                        >
                          <span className="available-row-copy">
                            <strong>Knowledge Base Studio</strong>
                            <small>Upload a CSV to add another knowledge tool.</small>
                          </span>
                          <span className="available-row-chevron" aria-hidden="true">
                            →
                          </span>
                        </button>
                      </div>
                    </div>

                    {connectors.length === 0 && assignableTools.length === 0 ? (
                      <p className="helper-text compact">
                        No connector tools yet. Upload a CSV via Knowledge Base Studio, or configure
                        Snowflake / External API in `.env`.
                      </p>
                    ) : null}

                    <div className="studio-actions">
                      <button
                        className="primary-action compact"
                        type="submit"
                        disabled={isSavingStudio}
                      >
                        {isSavingStudio ? 'Saving…' : editingAgentId ? 'Save' : 'Create'}
                      </button>
                      <button className="text-button" type="button" onClick={backToSettingsHome}>
                        Cancel
                      </button>
                    </div>
                    {studioError ? <p className="panel-message">{studioError}</p> : null}
                  </form>
                </section>
              ) : null}

              {settingsView === 'knowledge' ? (
                <section className="setup-section">
                  <h3 className="studio-heading">Knowledge</h3>
                  <p className="helper-text">
                    Upload CSV files. Each file becomes a query tool specialists can use.
                  </p>
                  {datasetsError ? <p className="panel-message">{datasetsError}</p> : null}
                  <div className="available-card">
                    <p className="available-card-label">Uploaded datasets</p>
                    {datasets.length > 0 ? (
                      <div className="available-list" role="list">
                        {datasets.map((dataset) => (
                          <div className="available-row static" key={dataset.id} role="listitem">
                            <span className="available-row-copy">
                              <strong>{dataset.name}</strong>
                              <small>
                                {dataset.columns.length} columns · {dataset.original_filename}
                              </small>
                            </span>
                            <button
                              className="text-button danger-text"
                              type="button"
                              onClick={() => {
                                void handleDeleteDataset(dataset.id)
                              }}
                              disabled={isUploadingDataset}
                            >
                              Delete
                            </button>
                          </div>
                        ))}
                      </div>
                    ) : (
                      <p className="helper-text compact available-empty">No CSV uploads yet.</p>
                    )}
                  </div>
                  <form className="studio-form compact-form" onSubmit={handleUploadDataset}>
                    <input
                      className="studio-input"
                      value={datasetName}
                      onChange={(event) => setDatasetName(event.target.value)}
                      placeholder="Name, e.g. Q4 Pipeline"
                      disabled={isUploadingDataset}
                    />
                    <input
                      className="dataset-file-input"
                      type="file"
                      accept=".csv,text/csv"
                      onChange={(event) => setDatasetFile(event.target.files?.[0] ?? null)}
                      disabled={isUploadingDataset}
                    />
                    <button
                      className="primary-action compact"
                      type="submit"
                      disabled={isUploadingDataset}
                    >
                      {isUploadingDataset ? 'Uploading…' : 'Upload CSV'}
                    </button>
                    {datasetError ? <p className="panel-message">{datasetError}</p> : null}
                  </form>
                </section>
              ) : null}
            </div>
          </div>
        </div>
      ) : null}
    </main>
  )
}

function formatEventType(eventType: string) {
  return eventType.replaceAll('_', ' ')
}

function displayToolLabel(
  toolName: string,
  connectors: ConnectorHealth[],
  datasets: ImportedDataset[],
) {
  const connector = connectors.find((item) => item.tool_name === toolName)
  if (connector) {
    return connectorDisplayLabel(connector)
  }

  const dataset = datasets.find((item) => item.tool_name === toolName)
  if (dataset) {
    return dataset.name
  }

  return toolName.replaceAll('_', ' ')
}

function connectorDisplayLabel(connector: ConnectorHealth) {
  if (connector.id === 'snowflake') {
    return 'Sales pipeline — Snowflake query'
  }
  if (connector.id === 'external_api') {
    return 'Account lookup — External API service'
  }
  return connector.name
}

function toolSourceLabel(
  toolName: string,
  connectors: ConnectorHealth[],
  datasets: ImportedDataset[],
) {
  if (connectors.some((connector) => connector.tool_name === toolName)) {
    return 'Pre-configured tool — Backend configuration'
  }
  if (datasets.some((dataset) => dataset.tool_name === toolName)) {
    return 'Dynamically generated tool — CSV upload'
  }
  return 'Built-in tool — Application code'
}

function isStaleCustomAgent(agent: { tools: string[] }) {
  // Hide agents that have no usable tools (only supervisor-only leftovers).
  const visibleTools = agent.tools.filter(
    (toolName) => !HIDDEN_AGENT_TOOL_NAMES.has(toolName),
  )
  return visibleTools.length === 0
}

function messageDisplayName(message: Message) {
  if (message.role === 'user') {
    return 'You'
  }
  if (message.agent_name && message.agent_name !== 'supervisor') {
    return message.agent_name
  }
  return 'assistant'
}

function titleFromFirstMessage(content: string, maxLength = 72): string {
  const cleaned = content.trim().replace(/\s+/g, ' ')
  if (!cleaned) {
    return 'New conversation'
  }
  if (cleaned.length <= maxLength) {
    return cleaned
  }

  let truncated = cleaned.slice(0, maxLength - 1).trimEnd()
  const lastSpace = truncated.lastIndexOf(' ')
  if (lastSpace > 0) {
    truncated = truncated.slice(0, lastSpace).trimEnd()
  }
  if (!truncated) {
    truncated = cleaned.slice(0, maxLength - 1).trimEnd()
  }
  return `${truncated}…`
}

function formatJson(value: unknown) {
  return JSON.stringify(value, null, 2)
}

function ChartArtifact({ artifact }: { artifact: Artifact }) {
  const spec = chartSpecFromArtifact(artifact)
  if (!spec) {
    return <p className="panel-message">This chart artifact cannot be rendered yet.</p>
  }

  const maxValue = Math.max(...spec.series.map((point) => point.value), 1)

  if (spec.chartType === 'line') {
    return <LineChart spec={spec} maxValue={maxValue} />
  }

  return <BarChart spec={spec} maxValue={maxValue} />
}

type ChartSpec = {
  title: string
  chartType: 'bar' | 'line'
  series: Array<{ label: string; value: number }>
}

function chartSpecFromArtifact(artifact: Artifact): ChartSpec | null {
  if (artifact.artifact_type !== 'chart') {
    return null
  }

  const spec = artifact.payload.spec
  if (!isRecord(spec)) {
    return null
  }

  const title = typeof spec.title === 'string' ? spec.title : artifact.title
  const chartType = spec.chart_type === 'line' ? 'line' : 'bar'
  const rawSeries = spec.series
  if (!Array.isArray(rawSeries)) {
    return null
  }

  const series = rawSeries.flatMap((point) => {
    if (!isRecord(point) || typeof point.label !== 'string' || typeof point.value !== 'number') {
      return []
    }

    return [{ label: point.label, value: point.value }]
  })

  if (series.length === 0) {
    return null
  }

  return { title, chartType, series }
}

function BarChart({ spec, maxValue }: { spec: ChartSpec; maxValue: number }) {
  return (
    <div className="bar-chart" aria-label={spec.title}>
      {spec.series.map((point) => (
        <div className="bar-row" key={point.label}>
          <span>{point.label}</span>
          <div className="bar-track">
            <div style={{ width: `${Math.max((point.value / maxValue) * 100, 3)}%` }} />
          </div>
          <strong>{formatNumber(point.value)}</strong>
        </div>
      ))}
    </div>
  )
}

function LineChart({ spec, maxValue }: { spec: ChartSpec; maxValue: number }) {
  const width = 640
  const height = 220
  const padding = 32
  const points = spec.series.map((point, index) => {
    const x =
      spec.series.length === 1
        ? width / 2
        : padding + (index * (width - padding * 2)) / (spec.series.length - 1)
    const y = height - padding - (point.value / maxValue) * (height - padding * 2)
    return { ...point, x, y }
  })
  const path = points.map((point, index) => `${index === 0 ? 'M' : 'L'} ${point.x} ${point.y}`).join(' ')

  return (
    <div className="line-chart" aria-label={spec.title}>
      <svg viewBox={`0 0 ${width} ${height}`} role="img">
        <path className="line-axis" d={`M ${padding} ${height - padding} H ${width - padding}`} />
        <path className="line-path" d={path} />
        {points.map((point) => (
          <g key={point.label}>
            <circle cx={point.x} cy={point.y} r="4" />
            <text x={point.x} y={height - 8} textAnchor="middle">
              {point.label}
            </text>
          </g>
        ))}
      </svg>
    </div>
  )
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === 'object' && value !== null && !Array.isArray(value)
}

function formatNumber(value: number) {
  return new Intl.NumberFormat('en-US', {
    maximumFractionDigits: 0,
  }).format(value)
}

export default App

type IconName = 'agents' | 'compose' | 'library' | 'settings' | 'sidebar'

function Icon({ name }: { name: IconName }) {
  const paths: Record<IconName, React.ReactNode> = {
    compose: (
      <>
        <path d="M12 20h9" />
        <path d="M16.5 3.5a2.12 2.12 0 0 1 3 3L8 18l-4 1 1-4Z" />
      </>
    ),
    agents: (
      <>
        <rect x="4" y="8" width="16" height="11" rx="4" />
        <path d="M9 12v3M15 12v3M9 19v2M15 19v2M12 8V5" />
        <circle cx="12" cy="3.5" r="1.5" />
      </>
    ),
    library: (
      <>
        <path d="M4 19.5A2.5 2.5 0 0 1 6.5 17H20" />
        <path d="M6.5 2H20v20H6.5A2.5 2.5 0 0 1 4 19.5v-15A2.5 2.5 0 0 1 6.5 2Z" />
      </>
    ),
    settings: (
      <>
        <circle cx="12" cy="12" r="3" />
        <path d="M19.4 15a1.7 1.7 0 0 0 .34 1.88l.06.06-2.83 2.83-.06-.06A1.7 1.7 0 0 0 15 19.4a1.7 1.7 0 0 0-1 .6 1.7 1.7 0 0 0-.4 1.1V21H9.6v-.09A1.7 1.7 0 0 0 8.5 19.4a1.7 1.7 0 0 0-1.88.34l-.06.06-2.83-2.83.06-.06A1.7 1.7 0 0 0 4.6 15a1.7 1.7 0 0 0-.6-1 1.7 1.7 0 0 0-1.1-.4H3V9.6h.09A1.7 1.7 0 0 0 4.6 8.5a1.7 1.7 0 0 0-.34-1.88l-.06-.06 2.83-2.83.06.06A1.7 1.7 0 0 0 9 4.6a1.7 1.7 0 0 0 1-.6 1.7 1.7 0 0 0 .4-1.1V3h4v.09A1.7 1.7 0 0 0 15.5 4.6a1.7 1.7 0 0 0 1.88-.34l.06-.06 2.83 2.83-.06.06A1.7 1.7 0 0 0 19.4 9c.15.38.36.72.6 1 .3.32.7.5 1.1.5h.09v4h-.09a1.7 1.7 0 0 0-1.7.5Z" />
      </>
    ),
    sidebar: (
      <>
        <rect x="3" y="4" width="18" height="16" rx="3" />
        <path d="M9 4v16" />
      </>
    ),
  }

  return (
    <svg className="gpt-icon" viewBox="0 0 24 24" aria-hidden="true">
      {paths[name]}
    </svg>
  )
}
