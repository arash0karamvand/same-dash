// کامپوننت Slide-over Panel برای نمایش جزئیات

import { useEffect } from 'react'
import { createPortal } from 'react-dom'
import Icon from './icons/Icon'
import { cn, tw } from '../styles/tw'

export default function SlideOver({
  open,
  onClose,
  title,
  children,
  size = 'default',
  className = '',
}) {
  useEffect(() => {
    if (!open) return undefined
    document.body.classList.add('slideover-open')
    return () => document.body.classList.remove('slideover-open')
  }, [open])

  if (!open) return null

  const sizeClasses = {
    default: 'max-w-[480px]',
    wide: 'max-w-[640px]',
    wider: 'max-w-[820px]',
  }

  return createPortal(
    <>
      {/* Backdrop */}
      <div
        className="fixed inset-0 z-[90] animate-[fade-in_0.2s_ease] cursor-pointer bg-black/50 backdrop-blur-[6px]"
        onClick={onClose}
        aria-hidden="true"
      />

      {/* Panel */}
      <div
        className={cn(
          'fixed top-0 left-0 z-[100] h-full w-full animate-[slide-in-from-left_0.3s_cubic-bezier(0.4,0,0.2,1)]',
          sizeClasses[size],
          'liquid-glass liquid-glass--strong liquid-glass--panel',
          'shadow-[-12px_0_48px_rgba(0,0,0,0.3)]',
          'flex flex-col',
          className
        )}
        onClick={(e) => e.stopPropagation()}
        role="dialog"
        aria-modal="true"
        aria-label={title}
      >
        {/* Header */}
        <div className="flex shrink-0 items-center justify-between border-b border-border-subtle px-7 py-5 max-md:px-5 max-md:py-4">
          <h3 className="m-0 font-display text-xl font-bold text-text max-md:text-lg">
            {title}
          </h3>
          <button
            onClick={onClose}
            className={cn(
              tw.modalClose,
              'flex h-10 w-10 items-center justify-center'
            )}
            aria-label="بستن"
          >
            <Icon name="x" size={20} />
          </button>
        </div>

        {/* Body */}
        <div className="min-h-0 flex-1 overflow-y-auto px-7 py-6 [-webkit-overflow-scrolling:touch] max-md:px-5 max-md:py-4">
          {children}
        </div>
      </div>
    </>,
    document.body
  )
}
