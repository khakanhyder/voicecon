/**
 * The staff console's blog client (`/api/v1/admin/blog`, behind a console
 * session). Types are shared with the website in lib/blog.ts.
 */
import { apiClient } from '@/lib/api'
import type {
  BlogCategory,
  BlogOverview,
  BlogPostDetail,
  BlogPostInput,
  BlogPostRow,
  BlogTeamMember,
  ConsoleAuthor,
  Paged,
} from '@/lib/blog'

const BASE = '/api/v1/admin/blog'
const NO_WORKSPACE = { headers: { 'X-Skip-Workspace': '1' } }

type Params = Record<string, string | number | undefined | null>

function clean(params?: Params) {
  if (!params) return undefined
  return Object.fromEntries(Object.entries(params).filter(([, v]) => v !== undefined && v !== null && v !== ''))
}

async function get<T>(path: string, params?: Params): Promise<T> {
  const { data } = await apiClient.get<T>(`${BASE}${path}`, { ...NO_WORKSPACE, params: clean(params) })
  return data
}

async function send<T>(method: 'post' | 'put' | 'patch' | 'delete', path: string, body?: unknown): Promise<T> {
  const { data } = await apiClient.request<T>({ method, url: `${BASE}${path}`, data: body, ...NO_WORKSPACE })
  return data
}

export const blogApi = {
  overview: () => get<BlogOverview>('/overview'),
  posts: (params: Params) => get<Paged<BlogPostRow>>('/posts', params),
  post: (id: string) => get<BlogPostDetail>(`/posts/${id}`),
  createPost: (body: BlogPostInput) => send<BlogPostDetail>('post', '/posts', body),
  updatePost: (id: string, body: BlogPostInput) => send<BlogPostDetail>('put', `/posts/${id}`, body),
  publish: (id: string, publishedAt?: string | null) =>
    send<BlogPostDetail>('post', `/posts/${id}/publish`, publishedAt ? { published_at: publishedAt } : {}),
  unpublish: (id: string) => send<BlogPostDetail>('post', `/posts/${id}/unpublish`),
  deletePost: (id: string) => send<{ ok: true }>('delete', `/posts/${id}`),
  slugCheck: (slug: string, excludeId?: string) =>
    get<{ slug: string; available: boolean; suggestion: string | null }>('/slug-check', { slug, exclude_id: excludeId }),
  authors: () => get<ConsoleAuthor[]>('/authors'),
  categories: () => get<BlogCategory[]>('/categories'),
  createCategory: (body: { name: string; slug?: string; description?: string }) =>
    send<BlogCategory>('post', '/categories', body),
  updateCategory: (id: string, body: { name: string; slug?: string; description?: string }) =>
    send<BlogCategory>('put', `/categories/${id}`, body),
  deleteCategory: (id: string) => send<{ ok: true }>('delete', `/categories/${id}`),
  uploadImage: async (file: File) => {
    const form = new FormData()
    form.append('file', file)
    const { data } = await apiClient.post<{ url: string; width: number; height: number }>(`${BASE}/images`, form, {
      // undefined, as for avatars: the browser sets multipart with its boundary.
      headers: { 'X-Skip-Workspace': '1', 'Content-Type': undefined },
    })
    return data
  },
  team: () => get<BlogTeamMember[]>('/team'),
  addTeamMember: (body: { email: string; full_name?: string; role: 'editor' | 'viewer'; password?: string }) =>
    send<BlogTeamMember & { created: boolean }>('post', '/team', body),
  changeTeamRole: (id: string, role: 'editor' | 'viewer') => send<BlogTeamMember>('patch', `/team/${id}`, { role }),
  removeTeamMember: (id: string) => send<{ ok: true }>('delete', `/team/${id}`),
}
