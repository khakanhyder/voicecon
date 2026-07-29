import React, { useState, useCallback } from 'react'
import { ConfirmModal } from '@/components/ui/confirm-modal'

export interface ConfirmOptions {
  title: string
  description?: string
  confirmText?: string
  cancelText?: string
  isDestructive?: boolean
}

export function useConfirm() {
  const [isOpen, setIsOpen] = useState(false)
  const [config, setConfig] = useState<ConfirmOptions>({
    title: '',
    description: '',
    confirmText: 'Confirm',
    cancelText: 'Cancel',
    isDestructive: false,
  })

  const [resolver, setResolver] = useState<{ resolve: (value: boolean) => void } | null>(null)

  const confirm = useCallback((options: ConfirmOptions) => {
    setConfig({
      title: options.title,
      description: options.description || '',
      confirmText: options.confirmText || 'Confirm',
      cancelText: options.cancelText || 'Cancel',
      isDestructive: options.isDestructive ?? true, // Default to true since most confirmations are destructive (delete/revoke)
    })
    setIsOpen(true)

    return new Promise<boolean>((resolve) => {
      setResolver({ resolve })
    })
  }, [])

  const handleConfirm = useCallback(() => {
    setIsOpen(false)
    if (resolver) resolver.resolve(true)
  }, [resolver])

  const handleCancel = useCallback(() => {
    setIsOpen(false)
    if (resolver) resolver.resolve(false)
  }, [resolver])

  const ConfirmDialog = useCallback(() => (
    <ConfirmModal
      isOpen={isOpen}
      title={config.title}
      description={config.description || ''}
      confirmText={config.confirmText}
      cancelText={config.cancelText}
      isDestructive={config.isDestructive}
      onConfirm={handleConfirm}
      onCancel={handleCancel}
    />
  ), [isOpen, config, handleConfirm, handleCancel])

  return { confirm, ConfirmDialog }
}
