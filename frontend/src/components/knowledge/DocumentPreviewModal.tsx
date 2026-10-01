'use client'

import { useEffect, useRef, useState } from 'react'
import { createPortal } from 'react-dom'
import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'
import { Download, ExternalLink, Loader2, X } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { apiClient, getErrorMessage } from '@/lib/api'
import { API_ENDPOINTS } from '@/lib/constants'
import { fetchDocumentFile, type DocumentPreview, type SheetPreview } from '@/lib/knowledge-files'

export interface PreviewTarget {
  id: string
  title: string
  source_type: string
}

interface Props {
  doc: PreviewTarget | null
  onClose: () => void
  onDownload: (doc: PreviewTarget) => void
  isDownloading?: boolean
}

/**
 * Shows a knowledge-base document in its own format before it is downloaded:
 * PDFs in the browser's PDF viewer, Word files laid out as pages, spreadsheets
 * and CSVs as tables, Markdown rendered, JSON pretty-printed, text as text.
 */
export function DocumentPreviewModal({ doc, onClose, onDownload, isDownloading }: Props) {
  const [mounted, setMounted] = useState(false)
  const [preview, setPreview] = useState<DocumentPreview | null>(null)
  const [fileUrl, setFileUrl] = useState<string | null>(null)
  const [fileBlob, setFileBlob] = useState<Blob | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [loading, setLoading] = useState(false)

  useEffect(() => setMounted(true), [])

  useEffect(() => {
    if (!doc) return
    let cancelled = false
    let objectUrl: string | null = null
    setPreview(null)
    setFileUrl(null)
    setFileBlob(null)
    setError(null)
    setLoading(true)

    ;(async () => {
      try {
        const res = await apiClient.get<DocumentPreview>(API_ENDPOINTS.KNOWLEDGE_DOCUMENT_PREVIEW(doc.id))
        if (cancelled) return
        const p = res.data
        if (p.kind === 'pdf' || p.kind === 'docx') {
          const { blob } = await fetchDocumentFile(doc.id, doc.title)
          if (cancelled) return
          if (p.kind === 'pdf') {
            // Typed explicitly: an iframe only ever gets a PDF blob, never
            // something the browser might sniff and run as a page.
            objectUrl = URL.createObjectURL(new Blob([blob], { type: 'application/pdf' }))
            setFileUrl(objectUrl)
          } else {
            setFileBlob(blob)
          }
        }
        setPreview(p)
      } catch (err) {
        if (!cancelled) setError(getErrorMessage(err))
      } finally {
        if (!cancelled) setLoading(false)
      }
    })()

    return () => {
      cancelled = true
      if (objectUrl) URL.revokeObjectURL(objectUrl)
    }
  }, [doc])

  useEffect(() => {
    if (!doc) return
    const onKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape') onClose()
    }
    const overflow = document.body.style.overflow
    document.body.style.overflow = 'hidden'
    window.addEventListener('keydown', onKey)
    return () => {
      document.body.style.overflow = overflow
      window.removeEventListener('keydown', onKey)
    }
  }, [doc, onClose])

  if (!doc || !mounted) return null

  const title = preview?.filename ?? doc.title

  return createPortal(
    <div
      className="fixed inset-0 z-[9999] flex items-center justify-center p-2 sm:p-6 bg-black/50 backdrop-blur-sm"
      onClick={onClose}
    >
      <div
        role="dialog"
        aria-modal="true"
        aria-labelledby="doc-preview-title"
        className="flex h-full max-h-[92vh] w-full max-w-5xl flex-col overflow-hidden rounded-2xl border border-slate-200 bg-white shadow-xl"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="flex items-center gap-3 border-b border-slate-200 px-4 py-3 sm:px-6">
          <div className="min-w-0 flex-1">
            <h2 id="doc-preview-title" className="truncate font-poppins text-[16px] font-semibold text-black">
              {title}
            </h2>
            <p className="font-poppins text-[12px] text-slate-500">Preview</p>
          </div>
          {fileUrl && (
            <a
              href={fileUrl}
              target="_blank"
              rel="noopener noreferrer"
              className="hidden sm:inline-flex items-center gap-1.5 rounded-[8px] border border-slate-200 px-3 h-[40px] font-poppins text-sm font-medium text-black hover:bg-slate-50"
            >
              <ExternalLink className="h-4 w-4" />
              Open in new tab
            </a>
          )}
          <Button
            onClick={() => onDownload(doc)}
            disabled={isDownloading}
            className="bg-[#106959] hover:opacity-90 text-white rounded-[8px] font-poppins font-medium h-[40px] px-4"
          >
            <Download className="h-4 w-4 sm:mr-2" />
            <span className="hidden sm:inline">{isDownloading ? 'Downloading…' : 'Download'}</span>
          </Button>
          <button
            aria-label="Close preview"
            onClick={onClose}
            className="flex h-[40px] w-[40px] items-center justify-center rounded-[8px] text-slate-500 hover:bg-slate-100 hover:text-slate-800"
          >
            <X className="h-5 w-5" />
          </button>
        </div>

        {preview && !preview.original_available && (
          <p className="border-b border-amber-200 bg-amber-50 px-4 py-2 font-poppins text-[13px] text-amber-900 sm:px-6">
            {doc.source_type === 'text'
              ? 'This is pasted text, shown as your agent reads it.'
              : 'The original file wasn’t kept for documents uploaded before previews were added, so this shows the text your agent reads. Upload the file again to preview and download it in its original format.'}
          </p>
        )}

        <div className="min-h-0 flex-1 overflow-auto bg-slate-50">
          {loading && (
            <div className="flex h-full items-center justify-center gap-2 p-10 text-slate-500">
              <Loader2 className="h-5 w-5 animate-spin" />
              <span className="font-poppins text-sm">Loading preview…</span>
            </div>
          )}
          {error && !loading && (
            <div className="flex h-full items-center justify-center p-10">
              <p className="font-poppins text-sm text-red-600">{error}</p>
            </div>
          )}
          {preview && !loading && !error && (
            <PreviewBody preview={preview} fileUrl={fileUrl} fileBlob={fileBlob} title={title} />
          )}
        </div>
      </div>
    </div>,
    document.body,
  )
}

function PreviewBody({
  preview,
  fileUrl,
  fileBlob,
  title,
}: {
  preview: DocumentPreview
  fileUrl: string | null
  fileBlob: Blob | null
  title: string
}) {
  switch (preview.kind) {
    case 'pdf':
      return fileUrl ? <iframe src={fileUrl} title={title} className="h-full min-h-[70vh] w-full border-0 bg-white" /> : null
    case 'docx':
      return fileBlob ? <DocxView blob={fileBlob} /> : null
    case 'sheet':
      return <SheetView sheets={preview.sheets ?? []} />
    case 'markdown':
      return (
        <TextFrame truncated={preview.text_truncated}>
          <article className="prose prose-slate max-w-none rounded-xl bg-white p-6 font-poppins">
            <ReactMarkdown remarkPlugins={[remarkGfm]}>{preview.text ?? ''}</ReactMarkdown>
          </article>
        </TextFrame>
      )
    case 'json':
      return (
        <TextFrame truncated={preview.text_truncated}>
          <pre className="whitespace-pre-wrap break-words rounded-xl bg-white p-6 font-mono text-[13px] text-slate-800">
            {prettyJson(preview.text ?? '')}
          </pre>
        </TextFrame>
      )
    default:
      return (
        <TextFrame truncated={preview.text_truncated}>
          <pre className="whitespace-pre-wrap break-words rounded-xl bg-white p-6 font-mono text-[13px] leading-relaxed text-slate-800">
            {preview.text ?? ''}
          </pre>
        </TextFrame>
      )
  }
}

function TextFrame({ truncated, children }: { truncated: boolean; children: React.ReactNode }) {
  return (
    <div className="p-3 sm:p-6">
      {children}
      {truncated && (
        <p className="mt-3 font-poppins text-[12px] text-slate-500">
          The preview is cut short because the file is very long. Download it to see everything.
        </p>
      )}
    </div>
  )
}

function prettyJson(text: string) {
  try {
    return JSON.stringify(JSON.parse(text), null, 2)
  } catch {
    return text
  }
}

function DocxView({ blob }: { blob: Blob }) {
  const ref = useRef<HTMLDivElement>(null)
  const [failed, setFailed] = useState(false)

  useEffect(() => {
    const container = ref.current
    if (!container) return
    let cancelled = false
    setFailed(false)
    container.innerHTML = ''
    import('docx-preview')
      .then(({ renderAsync }) =>
        renderAsync(blob, container, undefined, {
          className: 'docx',
          inWrapper: true,
          breakPages: true,
          ignoreLastRenderedPageBreak: true,
          renderHeaders: true,
          renderFooters: true,
          renderFootnotes: true,
          // Embedded images and fonts as data: URLs — the CSP allows data:
          // for img-src and font-src, but not blob:.
          useBase64URL: true,
        }),
      )
      .then(() => {
        if (cancelled) return
        // The file is someone's upload: keep only links that go somewhere
        // ordinary, and open them away from the dashboard.
        container.querySelectorAll('a[href]').forEach((a) => {
          const href = a.getAttribute('href') ?? ''
          if (!/^(https?:|mailto:|#)/i.test(href)) a.removeAttribute('href')
          else if (!href.startsWith('#')) {
            a.setAttribute('target', '_blank')
            a.setAttribute('rel', 'noopener noreferrer')
          }
        })
      })
      .catch(() => {
        if (!cancelled) setFailed(true)
      })
    return () => {
      cancelled = true
    }
  }, [blob])

  if (failed) {
    return (
      <div className="flex h-full items-center justify-center p-10">
        <p className="font-poppins text-sm text-slate-600">
          This Word document can’t be previewed here. Download it to open it in Word.
        </p>
      </div>
    )
  }
  return <div ref={ref} className="docx-preview-host min-h-full [&_.docx-wrapper]:bg-slate-100" />
}

function SheetView({ sheets }: { sheets: SheetPreview[] }) {
  const [active, setActive] = useState(0)
  const sheet = sheets[active]

  if (!sheet) {
    return <p className="p-10 text-center font-poppins text-sm text-slate-600">This spreadsheet is empty.</p>
  }

  const [header, ...body] = sheet.rows

  return (
    <div className="flex h-full flex-col">
      {sheets.length > 1 && (
        <div role="tablist" className="flex gap-1 overflow-x-auto border-b border-slate-200 bg-white px-3 pt-2">
          {sheets.map((s, i) => (
            <button
              key={`${s.name}-${i}`}
              role="tab"
              aria-selected={i === active}
              onClick={() => setActive(i)}
              className={`whitespace-nowrap rounded-t-lg px-3 py-2 font-poppins text-[13px] ${
                i === active ? 'bg-slate-100 font-semibold text-black' : 'text-slate-500 hover:text-black'
              }`}
            >
              {s.name}
            </button>
          ))}
        </div>
      )}
      <div className="min-h-0 flex-1 overflow-auto p-3 sm:p-6">
        {sheet.rows.length === 0 ? (
          <p className="text-center font-poppins text-sm text-slate-600">This sheet is empty.</p>
        ) : (
          <table className="min-w-full border-collapse bg-white font-poppins text-[13px]">
            <thead>
              <tr>
                {header.map((cell, c) => (
                  <th
                    key={c}
                    className="sticky top-0 border border-slate-200 bg-slate-100 px-3 py-2 text-left font-semibold text-black"
                  >
                    {cell}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {body.map((row, r) => (
                <tr key={r} className="even:bg-slate-50">
                  {row.map((cell, c) => (
                    <td key={c} className="whitespace-pre-wrap border border-slate-200 px-3 py-1.5 align-top text-slate-800">
                      {cell}
                    </td>
                  ))}
                </tr>
              ))}
            </tbody>
          </table>
        )}
        {sheet.truncated && (
          <p className="mt-3 font-poppins text-[12px] text-slate-500">
            Showing the first 500 rows and 50 columns. Download the file to see everything.
          </p>
        )}
      </div>
    </div>
  )
}
