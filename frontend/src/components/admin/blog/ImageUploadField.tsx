'use client'

import { useRef, useState } from 'react'
import { toast } from 'sonner'
import { AlertTriangle, ImagePlus, Link2, Loader2, RefreshCw, Trash2, UploadCloud } from 'lucide-react'
import { blogApi } from '@/lib/blog-admin'
import { FEATURED_IMAGE } from '@/lib/blog'
import { errorText, inputClass } from '@/components/admin/ui'
import { cn } from '@/lib/utils'

const RATIO = FEATURED_IMAGE.width / FEATURED_IMAGE.height

/**
 * Upload (or link) a 16:9 image: the featured image and the social share image.
 *
 * Nothing is cropped on upload. The site shows these in a 16:9 frame and crops
 * from the centre, so the field measures the image and says when it is a
 * different shape or smaller than the recommended size.
 */
export function ImageUploadField({
  label,
  value,
  onChange,
  disabled,
  hint,
}: {
  label: string
  value: string | null
  onChange: (url: string | null) => void
  disabled?: boolean
  hint?: string
}) {
  const fileRef = useRef<HTMLInputElement>(null)
  const [uploading, setUploading] = useState(false)
  const [dragging, setDragging] = useState(false)
  const [urlMode, setUrlMode] = useState(false)
  const [urlDraft, setUrlDraft] = useState('')
  const [size, setSize] = useState<{ w: number; h: number } | null>(null)
  const [broken, setBroken] = useState(false)

  const upload = async (file: File) => {
    if (!/^image\/(jpeg|png|webp)$/.test(file.type)) {
      toast.error('Use a JPG, PNG or WebP image.')
      return
    }
    setUploading(true)
    try {
      const image = await blogApi.uploadImage(file)
      setSize(null)
      setBroken(false)
      onChange(image.url)
    } catch (e) {
      toast.error(errorText(e))
    } finally {
      setUploading(false)
    }
  }

  const ratioOff = size ? Math.abs(size.w / size.h - RATIO) / RATIO > 0.03 : false
  const tooSmall = size ? size.w < FEATURED_IMAGE.width || size.h < FEATURED_IMAGE.height : false

  return (
    <div>
      <div className="mb-1.5 flex items-baseline justify-between gap-2">
        <span className="text-xs font-medium text-slate-700">{label}</span>
        {value && !disabled && (
          <button type="button" onClick={() => setUrlMode((v) => !v)} className="text-xs font-medium text-brand-700 hover:underline">
            {urlMode ? 'Cancel' : 'Use a link'}
          </button>
        )}
      </div>

      {value ? (
        <div className="group relative aspect-video overflow-hidden rounded-xl border border-slate-200 bg-slate-100">
          {/* eslint-disable-next-line @next/next/no-img-element */}
          <img
            src={value}
            alt=""
            className="h-full w-full object-cover"
            onLoad={(e) => {
              setBroken(false)
              setSize({ w: e.currentTarget.naturalWidth, h: e.currentTarget.naturalHeight })
            }}
            onError={() => setBroken(true)}
          />
          {broken && (
            <div className="absolute inset-0 flex items-center justify-center bg-slate-100 text-xs text-rose-600">
              This image could not be loaded.
            </div>
          )}
          {!disabled && (
            <div className="absolute inset-x-0 bottom-0 flex justify-end gap-1.5 bg-gradient-to-t from-black/60 to-transparent p-2 opacity-100 transition-opacity sm:opacity-0 sm:group-hover:opacity-100 sm:group-focus-within:opacity-100">
              <button
                type="button"
                onClick={() => fileRef.current?.click()}
                disabled={uploading}
                className="inline-flex h-8 items-center gap-1.5 rounded-md bg-white/95 px-2.5 text-xs font-medium text-slate-800 hover:bg-white"
              >
                {uploading ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <RefreshCw className="h-3.5 w-3.5" />}
                Replace
              </button>
              <button
                type="button"
                onClick={() => {
                  onChange(null)
                  setSize(null)
                }}
                className="inline-flex h-8 items-center gap-1.5 rounded-md bg-white/95 px-2.5 text-xs font-medium text-rose-600 hover:bg-white"
              >
                <Trash2 className="h-3.5 w-3.5" />
                Remove
              </button>
            </div>
          )}
        </div>
      ) : (
        <button
          type="button"
          disabled={disabled || uploading}
          onClick={() => fileRef.current?.click()}
          onDragOver={(e) => {
            e.preventDefault()
            setDragging(true)
          }}
          onDragLeave={() => setDragging(false)}
          onDrop={(e) => {
            e.preventDefault()
            setDragging(false)
            const file = e.dataTransfer.files?.[0]
            if (file && !disabled) upload(file)
          }}
          className={cn(
            'flex aspect-video w-full flex-col items-center justify-center gap-2 rounded-xl border-2 border-dashed text-center transition-colors disabled:cursor-not-allowed disabled:opacity-60',
            dragging ? 'border-brand-400 bg-brand-50' : 'border-slate-200 bg-slate-50 hover:border-brand-300 hover:bg-brand-50/40'
          )}
        >
          {uploading ? (
            <Loader2 className="h-6 w-6 animate-spin text-brand-600" />
          ) : (
            <UploadCloud className="h-6 w-6 text-slate-400" />
          )}
          <span className="text-sm font-medium text-slate-700">{uploading ? 'Uploading…' : 'Click or drop an image'}</span>
          <span className="px-4 text-xs text-slate-500">Recommended size: {FEATURED_IMAGE.label}</span>
        </button>
      )}

      <input
        ref={fileRef}
        type="file"
        accept="image/jpeg,image/png,image/webp"
        className="hidden"
        onChange={(e) => {
          const file = e.target.files?.[0]
          e.target.value = ''
          if (file) upload(file)
        }}
      />

      {(urlMode || (!value && !disabled)) && (
        <div className="mt-2 flex gap-2">
          {!urlMode && !value ? (
            <button
              type="button"
              onClick={() => setUrlMode(true)}
              className="inline-flex items-center gap-1.5 text-xs font-medium text-slate-500 hover:text-brand-700"
            >
              <Link2 className="h-3.5 w-3.5" />
              Or paste an image link
            </button>
          ) : (
            <>
              <input
                autoFocus
                value={urlDraft}
                onChange={(e) => setUrlDraft(e.target.value)}
                placeholder="https://…/image.webp"
                aria-label={`${label} link`}
                className={cn(inputClass, 'h-8 text-xs')}
              />
              <button
                type="button"
                onClick={() => {
                  const url = urlDraft.trim()
                  if (!/^https?:\/\//i.test(url)) return toast.error('Paste a full http(s) link to an image.')
                  setSize(null)
                  onChange(url)
                  setUrlMode(false)
                  setUrlDraft('')
                }}
                className="inline-flex h-8 items-center gap-1 rounded-md bg-slate-800 px-3 text-xs font-medium text-white hover:bg-slate-900"
              >
                <ImagePlus className="h-3.5 w-3.5" />
                Use
              </button>
            </>
          )}
        </div>
      )}

      <p className="mt-2 text-xs text-slate-500">
        {hint ?? `Recommended size: ${FEATURED_IMAGE.label}. Shown in a 16:9 frame on cards, the article page and link previews.`}
      </p>
      {size && (ratioOff || tooSmall) && (
        <p className="mt-1.5 flex items-start gap-1.5 text-xs text-amber-700">
          <AlertTriangle className="mt-0.5 h-3.5 w-3.5 flex-shrink-0" />
          <span>
            This image is {size.w} × {size.h} px.
            {ratioOff && ' It is not 16:9, so the edges will be cropped on cards.'}
            {tooSmall && ` It is smaller than ${FEATURED_IMAGE.width} × ${FEATURED_IMAGE.height} and may look soft on large screens.`}
          </span>
        </p>
      )}
    </div>
  )
}
