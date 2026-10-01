import { apiClient } from '@/lib/api'
import { API_ENDPOINTS } from '@/lib/constants'

/** What /knowledge/documents/{id}/preview returns. */
export interface SheetPreview {
  name: string
  rows: string[][]
  truncated: boolean
}

export interface DocumentPreview {
  kind: 'pdf' | 'docx' | 'sheet' | 'markdown' | 'json' | 'text'
  filename: string
  content_type: string
  original_available: boolean
  text: string | null
  text_truncated: boolean
  sheets: SheetPreview[] | null
}

/** The name from a Content-Disposition header, preferring the UTF-8 form. */
export function filenameFromDisposition(header: string | null | undefined): string | null {
  if (!header) return null
  const star = /filename\*=UTF-8''([^;]+)/i.exec(header)
  if (star) {
    try {
      return decodeURIComponent(star[1].trim())
    } catch {
      // fall through to the plain form
    }
  }
  const plain = /filename="?([^";]+)"?/i.exec(header)
  return plain ? plain[1].trim() : null
}

/**
 * The document's file exactly as the server sends it — the original upload,
 * or the extracted text as .txt for pasted text and older uploads. Goes
 * through apiClient so the workspace header and token refresh apply.
 */
export async function fetchDocumentFile(docId: string, fallbackTitle: string) {
  const res = await apiClient.get<Blob>(API_ENDPOINTS.KNOWLEDGE_DOCUMENT_DOWNLOAD(docId), {
    responseType: 'blob',
  })
  const filename =
    filenameFromDisposition(res.headers['content-disposition']) ??
    (fallbackTitle.toLowerCase().endsWith('.txt') ? fallbackTitle : `${fallbackTitle}.txt`)
  return { blob: res.data, filename }
}

export function saveBlob(blob: Blob, filename: string) {
  const url = window.URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = filename
  document.body.appendChild(a)
  a.click()
  a.remove()
  window.URL.revokeObjectURL(url)
}
