'use client'

import React from 'react'
import { createPortal } from 'react-dom'
import { Button } from '@/components/ui/button'
import { AlertCircle, X } from 'lucide-react'

interface ConfirmModalProps {
  isOpen: boolean
  title: string
  description: string
  confirmText?: string
  cancelText?: string
  onConfirm: () => void
  onCancel: () => void
  isDestructive?: boolean
  isLoading?: boolean
}

export function ConfirmModal({
  isOpen,
  title,
  description,
  confirmText = 'Confirm',
  cancelText = 'Cancel',
  onConfirm,
  onCancel,
  isDestructive = false,
  isLoading = false,
}: ConfirmModalProps) {
  const [mounted, setMounted] = React.useState(false)

  React.useEffect(() => {
    setMounted(true)
  }, [])

  if (!isOpen || !mounted) return null

  return createPortal(
    <div
      className="fixed inset-0 z-[9999] flex items-center justify-center p-4 bg-black/40 backdrop-blur-sm"
      onClick={() => { if (!isLoading) onCancel() }}
    >
      <div
        role="dialog"
        aria-modal="true"
        aria-labelledby="confirm-modal-title"
        aria-describedby="confirm-modal-description"
        className="w-full max-w-md rounded-[10px] border border-[#000000] bg-white p-6 shadow-xl relative animate-in fade-in zoom-in-95 duration-200"
        onClick={(e) => e.stopPropagation()}
      >
        <button
          aria-label="Close"
          onClick={onCancel}
          className="absolute right-4 top-4 text-gray-400 hover:text-gray-600 transition-colors"
          disabled={isLoading}
        >
          <X className="w-5 h-5" />
        </button>
        <div className="flex flex-col items-center text-center space-y-4 pt-2">
          <div className={`p-4 rounded-full ${isDestructive ? 'bg-red-50 text-red-600' : 'bg-blue-50 text-blue-600'}`}>
            <AlertCircle className="w-8 h-8" />
          </div>
          <h3 id="confirm-modal-title" className="text-xl font-bold text-gray-900 font-poppins">{title}</h3>
          <p id="confirm-modal-description" className="text-sm text-gray-600">{description}</p>
        </div>
        <div className="flex items-center gap-3 mt-8">
          <Button
            variant="outline"
            className="flex-1 rounded-[8px] h-[45px] text-[14px] font-medium border border-[#000000]"
            onClick={onCancel}
            disabled={isLoading}
          >
            {cancelText}
          </Button>
          <Button
            variant={isDestructive ? 'destructive' : 'default'}
            className="flex-1 rounded-[8px] h-[45px] text-[14px] font-medium border border-[#000000]"
            onClick={onConfirm}
            disabled={isLoading}
          >
            {isLoading ? 'Processing...' : confirmText}
          </Button>
        </div>
      </div>
    </div>,
    document.body
  )
}
