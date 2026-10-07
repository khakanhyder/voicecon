/**
 * Chatbots — the website chat channel, as its own section (Dashboard → Chatbot).
 *
 * A chatbot is linked to the agent that answers it; the link can change (or
 * be empty) without touching the embed code already installed on a site,
 * because the embed is keyed by the chatbot's `public_key`, which never
 * changes.
 */
import { apiClient } from '@/lib/api'
import { API_ENDPOINTS } from '@/lib/constants'

export interface ChatbotConfig {
  title: string
  subtitle: string
  greeting: string
  accent_color: string
  position: 'bottom-right' | 'bottom-left'
  launcher_text: string
}

export interface Chatbot {
  id: string
  name: string
  enabled: boolean
  agent_id: string | null
  agent: { id: string; name: string; is_active: boolean } | null
  /** Enabled and answered by an active agent — i.e. showing on sites. */
  live: boolean
  public_key: string
  config: ChatbotConfig
  embed_snippet: string
  session_count: number
  /** Unread visitor messages across this chatbot's conversations. */
  unread_count: number
  unread_sessions: number
  last_activity_at: string | null
  created_at: string | null
  updated_at: string | null
}

export interface ChatSessionSummary {
  id: string
  chatbot_id: string
  chatbot_name: string
  agent_id: string | null
  visitor_id: string | null
  visitor_label: string
  status: string
  /** 'human' while a team member has taken the conversation over. */
  mode: 'ai' | 'human'
  unread_count: number
  message_count: number
  last_message_preview: string | null
  last_message_role: string | null
  source_url: string | null
  started_at: string
  last_activity_at: string
}

export interface ChatTranscriptMessage {
  id: string
  /** user = visitor, assistant = the agent, human = a team member. */
  role: 'user' | 'assistant' | 'human'
  content: string
  tool_name: string | null
  sender: { id: string; name: string } | null
  created_at: string
}

export const DEFAULT_CHATBOT_CONFIG: ChatbotConfig = {
  title: 'Chat with us',
  subtitle: 'We usually reply in a few seconds',
  greeting: 'Hi! How can I help you today?',
  accent_color: '#0F6A59',
  position: 'bottom-right',
  launcher_text: 'Chat',
}

export const chatbotService = {
  async list(): Promise<Chatbot[]> {
    const { data } = await apiClient.get<{ chatbots: Chatbot[] }>(API_ENDPOINTS.CHATBOTS)
    return data.chatbots ?? []
  },
  async get(id: string): Promise<Chatbot> {
    const { data } = await apiClient.get<Chatbot>(API_ENDPOINTS.CHATBOT(id))
    return data
  },
  async create(payload: { name: string; agent_id: string | null; enabled?: boolean; config?: Partial<ChatbotConfig> }): Promise<Chatbot> {
    const { data } = await apiClient.post<Chatbot>(API_ENDPOINTS.CHATBOTS, payload)
    return data
  },
  /** Partial update; `agent_id: null` unlinks the agent. */
  async update(
    id: string,
    payload: Partial<{ name: string; agent_id: string | null; enabled: boolean; config: Partial<ChatbotConfig> }>
  ): Promise<Chatbot> {
    const { data } = await apiClient.patch<Chatbot>(API_ENDPOINTS.CHATBOT(id), payload)
    return data
  },
  async remove(id: string): Promise<void> {
    await apiClient.delete(API_ENDPOINTS.CHATBOT(id))
  },
  async sessions(id: string, page = 1): Promise<{ sessions: ChatSessionSummary[]; total: number }> {
    const { data } = await apiClient.get(`${API_ENDPOINTS.CHATBOT_SESSIONS(id)}?page=${page}&page_size=20`)
    return data
  },
  /** Clear a conversation's unread count (also clears it in the mobile app). */
  async markRead(sessionId: string): Promise<void> {
    await apiClient.post(API_ENDPOINTS.CHAT_SESSION_READ(sessionId))
  },
  async transcript(sessionId: string): Promise<ChatTranscriptMessage[]> {
    const { data } = await apiClient.get<{ messages: ChatTranscriptMessage[] }>(API_ENDPOINTS.CHAT_SESSION_MESSAGES(sessionId))
    return data.messages ?? []
  },
}
