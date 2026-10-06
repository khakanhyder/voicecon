'use client'

/**
 * The article body editor (Tiptap). Produces HTML limited to what the API's
 * sanitiser keeps (services/blog/content.py): h2–h4, paragraphs with text
 * alignment, bold/italic/underline/strike, inline code, code blocks, quotes,
 * lists, links, rules and images. Pasted content is reduced to the same set.
 */
import { useEffect, useRef, useState, type ReactNode } from 'react'
import { EditorContent, useEditor, type Editor } from '@tiptap/react'
import StarterKit from '@tiptap/starter-kit'
import Image from '@tiptap/extension-image'
import TextAlign from '@tiptap/extension-text-align'
import { Placeholder } from '@tiptap/extensions'
import { toast } from 'sonner'
import {
  AlignCenter,
  AlignLeft,
  AlignRight,
  Bold,
  Code,
  Heading2,
  Heading3,
  Heading4,
  ImagePlus,
  Italic,
  Link2,
  List,
  ListOrdered,
  Loader2,
  Minus,
  Pilcrow,
  Quote,
  Redo2,
  SquareCode,
  Strikethrough,
  Underline,
  Undo2,
  type LucideIcon,
} from 'lucide-react'
import { blogApi } from '@/lib/blog-admin'
import { errorText, inputClass } from '@/components/admin/ui'
import { cn } from '@/lib/utils'

export function RichTextEditor({
  value,
  onChange,
  readOnly = false,
  invalid = false,
}: {
  value: string
  onChange: (html: string) => void
  readOnly?: boolean
  invalid?: boolean
}) {
  const editor = useEditor({
    // Rendered client-side only; rendering on the server would mismatch.
    immediatelyRender: false,
    shouldRerenderOnTransaction: true,
    editable: !readOnly,
    extensions: [
      StarterKit.configure({
        heading: { levels: [2, 3, 4] },
        link: {
          openOnClick: false,
          autolink: true,
          defaultProtocol: 'https',
          protocols: ['http', 'https', 'mailto', 'tel'],
          HTMLAttributes: { rel: 'noopener noreferrer', target: '_blank' },
        },
      }),
      Image.configure({ inline: false, allowBase64: false }),
      TextAlign.configure({ types: ['heading', 'paragraph'], alignments: ['left', 'center', 'right'] }),
      Placeholder.configure({ placeholder: 'Write your article… Use the toolbar for headings, lists, links and images.' }),
    ],
    content: value,
    editorProps: {
      attributes: {
        class: cn(
          'blog-editor prose prose-slate max-w-none min-h-[420px] px-5 py-4 focus:outline-none',
          'prose-headings:font-semibold prose-a:text-brand-700 prose-img:rounded-lg prose-img:mx-auto'
        ),
        'aria-label': 'Article content',
      },
    },
    onUpdate: ({ editor }) => onChange(editor.isEmpty ? '' : editor.getHTML()),
  })

  // Loading a saved post replaces the content once it arrives.
  const loaded = useRef(false)
  useEffect(() => {
    if (!editor || loaded.current) return
    if (value && value !== editor.getHTML()) editor.commands.setContent(value, { emitUpdate: false })
    loaded.current = true
  }, [editor, value])

  useEffect(() => {
    editor?.setEditable(!readOnly)
  }, [editor, readOnly])

  const words = editor ? editor.getText().trim().split(/\s+/).filter(Boolean).length : 0

  return (
    <div
      className={cn(
        'overflow-hidden rounded-xl border bg-white',
        invalid ? 'border-rose-300 ring-2 ring-rose-100' : 'border-slate-200 focus-within:border-brand-400 focus-within:ring-2 focus-within:ring-brand-100'
      )}
    >
      {editor && !readOnly && <Toolbar editor={editor} />}
      <EditorContent editor={editor} />
      <div className="flex items-center justify-between border-t border-slate-100 bg-slate-50/60 px-4 py-2 text-xs text-slate-500">
        <span>
          {words.toLocaleString()} word{words === 1 ? '' : 's'} · about {Math.max(1, Math.ceil(words / 220))} min read
        </span>
        {!readOnly && <span className="hidden sm:inline">Tip: paste from Google Docs or Word keeps headings, lists and links.</span>}
      </div>
    </div>
  )
}

function Toolbar({ editor }: { editor: Editor }) {
  const [panel, setPanel] = useState<'link' | null>(null)
  const [href, setHref] = useState('')
  const [uploading, setUploading] = useState(false)
  const fileRef = useRef<HTMLInputElement>(null)
  const chain = () => editor.chain().focus()

  const openLink = () => {
    setHref((editor.getAttributes('link').href as string) || 'https://')
    setPanel(panel === 'link' ? null : 'link')
  }
  const applyLink = () => {
    const url = href.trim()
    if (!url || url === 'https://') {
      chain().extendMarkRange('link').unsetLink().run()
    } else {
      chain().extendMarkRange('link').setLink({ href: url }).run()
    }
    setPanel(null)
  }

  const uploadImage = async (file: File) => {
    setUploading(true)
    try {
      const image = await blogApi.uploadImage(file)
      chain().setImage({ src: image.url, alt: file.name.replace(/\.[^.]+$/, '').replace(/[-_]+/g, ' ') }).run()
    } catch (e) {
      toast.error(errorText(e))
    } finally {
      setUploading(false)
    }
  }

  const imageSelected = editor.isActive('image')
  const sep = <span className="mx-1 h-5 w-px bg-slate-200" aria-hidden="true" />

  return (
    <div className="sticky top-0 z-10 border-b border-slate-200 bg-white">
      <div role="toolbar" aria-label="Formatting" className="flex flex-wrap items-center gap-0.5 px-2 py-1.5">
        <Tool icon={Pilcrow} label="Paragraph" active={editor.isActive('paragraph')} onClick={() => chain().setParagraph().run()} />
        <Tool icon={Heading2} label="Heading 2" active={editor.isActive('heading', { level: 2 })} onClick={() => chain().toggleHeading({ level: 2 }).run()} />
        <Tool icon={Heading3} label="Heading 3" active={editor.isActive('heading', { level: 3 })} onClick={() => chain().toggleHeading({ level: 3 }).run()} />
        <Tool icon={Heading4} label="Heading 4" active={editor.isActive('heading', { level: 4 })} onClick={() => chain().toggleHeading({ level: 4 }).run()} />
        {sep}
        <Tool icon={Bold} label="Bold" active={editor.isActive('bold')} onClick={() => chain().toggleBold().run()} />
        <Tool icon={Italic} label="Italic" active={editor.isActive('italic')} onClick={() => chain().toggleItalic().run()} />
        <Tool icon={Underline} label="Underline" active={editor.isActive('underline')} onClick={() => chain().toggleUnderline().run()} />
        <Tool icon={Strikethrough} label="Strikethrough" active={editor.isActive('strike')} onClick={() => chain().toggleStrike().run()} />
        <Tool icon={Code} label="Inline code" active={editor.isActive('code')} onClick={() => chain().toggleCode().run()} />
        {sep}
        <Tool icon={List} label="Bulleted list" active={editor.isActive('bulletList')} onClick={() => chain().toggleBulletList().run()} />
        <Tool icon={ListOrdered} label="Numbered list" active={editor.isActive('orderedList')} onClick={() => chain().toggleOrderedList().run()} />
        <Tool icon={Quote} label="Quote" active={editor.isActive('blockquote')} onClick={() => chain().toggleBlockquote().run()} />
        <Tool icon={SquareCode} label="Code block" active={editor.isActive('codeBlock')} onClick={() => chain().toggleCodeBlock().run()} />
        <Tool icon={Minus} label="Divider" onClick={() => chain().setHorizontalRule().run()} />
        {sep}
        <Tool icon={AlignLeft} label="Align left" active={editor.isActive({ textAlign: 'left' })} onClick={() => chain().setTextAlign('left').run()} />
        <Tool icon={AlignCenter} label="Align centre" active={editor.isActive({ textAlign: 'center' })} onClick={() => chain().setTextAlign('center').run()} />
        <Tool icon={AlignRight} label="Align right" active={editor.isActive({ textAlign: 'right' })} onClick={() => chain().setTextAlign('right').run()} />
        {sep}
        <Tool icon={Link2} label="Link" active={editor.isActive('link') || panel === 'link'} onClick={openLink} />
        <Tool
          icon={uploading ? Loader2 : ImagePlus}
          label="Insert image"
          disabled={uploading}
          spin={uploading}
          onClick={() => fileRef.current?.click()}
        />
        <input
          ref={fileRef}
          type="file"
          accept="image/jpeg,image/png,image/webp"
          className="hidden"
          onChange={(e) => {
            const file = e.target.files?.[0]
            e.target.value = ''
            if (file) uploadImage(file)
          }}
        />
        <span className="ml-auto flex items-center gap-0.5">
          <Tool icon={Undo2} label="Undo" disabled={!editor.can().undo()} onClick={() => chain().undo().run()} />
          <Tool icon={Redo2} label="Redo" disabled={!editor.can().redo()} onClick={() => chain().redo().run()} />
        </span>
      </div>

      {panel === 'link' && (
        <ToolPanel>
          <input
            autoFocus
            value={href}
            onChange={(e) => setHref(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === 'Enter') {
                e.preventDefault()
                applyLink()
              }
              if (e.key === 'Escape') setPanel(null)
            }}
            placeholder="https://example.com"
            aria-label="Link address"
            className={cn(inputClass, 'h-8')}
          />
          <button type="button" onClick={applyLink} className="h-8 rounded-md bg-brand-600 px-3 text-xs font-medium text-white hover:bg-brand-700">
            Apply
          </button>
          {editor.isActive('link') && (
            <button
              type="button"
              onClick={() => {
                chain().extendMarkRange('link').unsetLink().run()
                setPanel(null)
              }}
              className="h-8 rounded-md px-3 text-xs font-medium text-rose-600 hover:bg-rose-50"
            >
              Remove link
            </button>
          )}
        </ToolPanel>
      )}

      {imageSelected && panel !== 'link' && (
        <ToolPanel>
          <span className="whitespace-nowrap text-xs font-medium text-slate-600">Image alt text</span>
          <input
            key={editor.getAttributes('image').src}
            defaultValue={(editor.getAttributes('image').alt as string) || ''}
            onChange={(e) => editor.chain().updateAttributes('image', { alt: e.target.value }).run()}
            placeholder="Describe the image for screen readers and search engines"
            aria-label="Image alt text"
            className={cn(inputClass, 'h-8')}
          />
        </ToolPanel>
      )}
    </div>
  )
}

function ToolPanel({ children }: { children: ReactNode }) {
  return <div className="flex items-center gap-2 border-t border-slate-100 bg-slate-50 px-3 py-2">{children}</div>
}

function Tool({
  icon: Icon,
  label,
  active,
  disabled,
  spin,
  onClick,
}: {
  icon: LucideIcon
  label: string
  active?: boolean
  disabled?: boolean
  spin?: boolean
  onClick: () => void
}) {
  return (
    <button
      type="button"
      title={label}
      aria-label={label}
      aria-pressed={active}
      disabled={disabled}
      // Keep the editor's selection: a mousedown on the toolbar would blur it.
      onMouseDown={(e) => e.preventDefault()}
      onClick={onClick}
      className={cn(
        'flex h-8 w-8 items-center justify-center rounded-md transition-colors disabled:opacity-40',
        active ? 'bg-brand-50 text-brand-700' : 'text-slate-600 hover:bg-slate-100 hover:text-slate-900'
      )}
    >
      <Icon className={cn('h-4 w-4', spin && 'animate-spin')} />
    </button>
  )
}
