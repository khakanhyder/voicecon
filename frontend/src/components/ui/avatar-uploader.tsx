'use client'

import { useEffect, useRef, useState } from 'react'
import { Camera, Loader2, Trash2, Upload } from 'lucide-react'

import { Button } from '@/components/ui/button'
import { FieldError } from '@/components/ui/field-error'

/** Mirrors ALLOWED_AVATAR_TYPES in backend/app/services/storage.py. */
const ACCEPTED = ['image/jpeg', 'image/png', 'image/webp', 'image/gif']
const MAX_BYTES = 5 * 1024 * 1024

export interface AvatarUploaderProps {
  /** Current picture, or null for the initials placeholder. */
  src: string | null
  /** Seeds the placeholder when there is no picture. */
  name: string
  onUpload: (file: File) => Promise<void>
  onRemove: () => Promise<void>
  disabled?: boolean
}

/**
 * Profile picture control: click or drop a file to replace it.
 *
 * Checks type and size before sending. The server checks both again — and is
 * the only one that can be trusted, since it also verifies the bytes really
 * decode as an image — but a local check turns a round-trip and an error toast
 * into an instant, specific message.
 *
 * The preview is an object URL shown only while the request is in flight. The
 * server re-encodes what it stores, so the authoritative image is whatever URL
 * comes back, never the local file.
 */
export function AvatarUploader({
  src,
  name,
  onUpload,
  onRemove,
  disabled,
}: AvatarUploaderProps) {
  const inputRef = useRef<HTMLInputElement>(null)
  const [busy, setBusy] = useState(false)
  const [dragging, setDragging] = useState(false)
  const [error, setError] = useState<string>()
  const [preview, setPreview] = useState<string | null>(null)

  // Revoke on unmount as well as after each upload: an object URL pins the
  // whole file in memory until it is released.
  useEffect(() => () => {
    if (preview) URL.revokeObjectURL(preview)
  }, [preview])

  const handleFile = async (file: File) => {
    setError(undefined)

    if (!ACCEPTED.includes(file.type)) {
      setError('Use a JPEG, PNG, WebP or GIF image.')
      return
    }
    if (file.size > MAX_BYTES) {
      setError(`That image is ${(file.size / 1024 / 1024).toFixed(1)}MB. The limit is 5MB.`)
      return
    }

    const objectUrl = URL.createObjectURL(file)
    setPreview(objectUrl)
    setBusy(true)
    try {
      await onUpload(file)
    } catch {
      // The caller surfaces the reason; just drop the optimistic preview so the
      // UI does not claim a picture that was never stored.
    } finally {
      setBusy(false)
      setPreview(null)
      URL.revokeObjectURL(objectUrl)
      // Reset the input so picking the *same* file again still fires onChange.
      if (inputRef.current) inputRef.current.value = ''
    }
  }

  const handleRemove = async () => {
    setError(undefined)
    setBusy(true)
    try {
      await onRemove()
    } finally {
      setBusy(false)
    }
  }

  const shown = preview ?? src
  const initial = name.trim().charAt(0).toUpperCase() || 'U'
  const interactive = !disabled && !busy

  return (
    <div className="space-y-3">
      <div className="flex flex-wrap items-center gap-5">
        <button
          type="button"
          onClick={() => interactive && inputRef.current?.click()}
          disabled={!interactive}
          aria-label={src ? 'Change profile picture' : 'Upload profile picture'}
          onDragOver={(e) => {
            if (!interactive) return
            e.preventDefault()
            setDragging(true)
          }}
          onDragLeave={() => setDragging(false)}
          onDrop={(e) => {
            if (!interactive) return
            e.preventDefault()
            setDragging(false)
            const file = e.dataTransfer.files?.[0]
            if (file) handleFile(file)
          }}
          className={`group relative h-20 w-20 shrink-0 overflow-hidden rounded-full outline-none transition-all focus-visible:ring-2 focus-visible:ring-[#0F6A59]/40 ${
            dragging ? 'ring-2 ring-[#0F6A59] ring-offset-2' : ''
          } ${interactive ? 'cursor-pointer' : 'cursor-not-allowed opacity-60'}`}
        >
          {shown ? (
            // eslint-disable-next-line @next/next/no-img-element
            <img src={shown} alt="" className="h-full w-full object-cover" />
          ) : (
            <span className="flex h-full w-full items-center justify-center bg-[#0F6A59]/10 text-2xl font-semibold text-[#106959]">
              {initial}
            </span>
          )}

          <span
            aria-hidden="true"
            className={`absolute inset-0 flex items-center justify-center bg-black/45 text-white transition-opacity ${
              busy ? 'opacity-100' : 'opacity-0 group-hover:opacity-100'
            }`}
          >
            {busy ? (
              <Loader2 className="h-5 w-5 animate-spin" />
            ) : (
              <Camera className="h-5 w-5" />
            )}
          </span>
        </button>

        <div className="space-y-2">
          <div className="flex flex-wrap gap-2">
            <Button
              type="button"
              variant="outline"
              onClick={() => inputRef.current?.click()}
              disabled={!interactive}
            >
              <Upload className="mr-2 h-4 w-4" />
              {src ? 'Change Picture' : 'Upload Picture'}
            </Button>
            {src && (
              <Button
                type="button"
                variant="outline"
                onClick={handleRemove}
                disabled={!interactive}
                className="text-red-600 hover:bg-red-50 hover:text-red-700"
              >
                <Trash2 className="mr-2 h-4 w-4" />
                Remove
              </Button>
            )}
          </div>
          <p className="text-xs text-muted-foreground">
            JPEG, PNG, WebP or GIF, up to 5MB. Drag one onto the circle if you prefer.
          </p>
        </div>
      </div>

      <FieldError id="avatar-error" message={error} />

      <input
        ref={inputRef}
        type="file"
        accept={ACCEPTED.join(',')}
        className="hidden"
        onChange={(e) => {
          const file = e.target.files?.[0]
          if (file) handleFile(file)
        }}
      />
    </div>
  )
}
