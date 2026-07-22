'use client'

import { useMemo } from 'react'
import CodeMirror from '@uiw/react-codemirror'
import { javascript } from '@codemirror/lang-javascript'
import { python } from '@codemirror/lang-python'
import { oneDark } from '@codemirror/theme-one-dark'
import { EditorView } from '@codemirror/view'

/**
 * Syntax-highlighted code editor for the Code node.
 *
 * Picks the language grammar from the node's `language` config so Python and
 * JavaScript both highlight correctly. Uses the One Dark theme for a familiar,
 * modern look. Replaces the plain black monospace textarea.
 */
export function CodeEditor({
  value,
  language,
  onChange,
}: {
  value: string
  language: string
  onChange: (value: string) => void
}) {
  const extensions = useMemo(() => {
    const lang =
      language === 'javascript' || language === 'js'
        ? javascript()
        : python()
    // Soft-wrap long lines so a wide API URL doesn't force horizontal scroll.
    return [lang, EditorView.lineWrapping]
  }, [language])

  return (
    <div className="overflow-hidden rounded-md border">
      <CodeMirror
        value={value ?? ''}
        height="240px"
        theme={oneDark}
        extensions={extensions}
        onChange={onChange}
        basicSetup={{
          lineNumbers: true,
          foldGutter: false,
          highlightActiveLine: true,
          autocompletion: true,
          tabSize: 2,
        }}
        style={{ fontSize: '12px' }}
      />
    </div>
  )
}
