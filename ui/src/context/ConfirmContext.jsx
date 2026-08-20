import { createContext, useCallback, useContext, useEffect, useRef, useState } from 'react'
import { Button } from '../components/ui'
import Icon from '../components/icons/Icon'

const ConfirmContext = createContext(null)

const DEFAULTS = {
  title: 'تایید عملیات',
  confirmText: 'بله، مطمئنم',
  cancelText: 'انصراف',
  variant: 'default',
}

function ConfirmDialog({ state, onConfirm, onCancel }) {
  const confirmRef = useRef(null)

  useEffect(() => {
    if (!state) return undefined
    const prev = document.activeElement
    const timer = window.setTimeout(() => confirmRef.current?.focus(), 0)

    const onKey = (e) => {
      if (e.key === 'Escape') onCancel()
    }
    window.addEventListener('keydown', onKey)

    return () => {
      window.clearTimeout(timer)
      window.removeEventListener('keydown', onKey)
      if (prev && typeof prev.focus === 'function') prev.focus()
    }
  }, [state, onCancel])

  if (!state) return null

  const { title, message, confirmText, cancelText, variant } = state

  return (
    <div
      className="confirm-overlay"
      role="presentation"
      onClick={onCancel}
    >
      <div
        className={`confirm-dialog liquid-glass liquid-glass--strong liquid-glass--panel confirm-dialog-${variant}`}
        role="alertdialog"
        aria-modal="true"
        aria-labelledby="confirm-dialog-title"
        aria-describedby="confirm-dialog-message"
        onClick={(e) => e.stopPropagation()}
      >
        <div className={`confirm-icon confirm-icon-${variant}`} aria-hidden="true">
          <Icon
            name={variant === 'danger' ? 'warning' : variant === 'warning' ? 'warning' : 'info'}
            size={24}
          />
        </div>
        <h3 id="confirm-dialog-title" className="confirm-title">{title}</h3>
        <p id="confirm-dialog-message" className="confirm-message">{message}</p>
        <div className="confirm-actions">
          <Button type="button" variant="ghost" onClick={onCancel}>
            {cancelText}
          </Button>
          <Button
            ref={confirmRef}
            type="button"
            variant={variant === 'danger' ? 'danger' : variant === 'warning' ? 'primary' : 'success'}
            onClick={onConfirm}
          >
            {confirmText}
          </Button>
        </div>
      </div>
    </div>
  )
}

export function ConfirmProvider({ children }) {
  const [state, setState] = useState(null)
  const resolverRef = useRef(null)

  const confirm = useCallback((options = {}) => {
    const merged = { ...DEFAULTS, ...options }
    if (!merged.message) {
      return Promise.resolve(false)
    }
    return new Promise((resolve) => {
      resolverRef.current = resolve
      setState(merged)
    })
  }, [])

  const finish = (result) => {
    resolverRef.current?.(result)
    resolverRef.current = null
    setState(null)
  }

  return (
    <ConfirmContext.Provider value={confirm}>
      {children}
      <ConfirmDialog
        state={state}
        onConfirm={() => finish(true)}
        onCancel={() => finish(false)}
      />
    </ConfirmContext.Provider>
  )
}

export function useConfirm() {
  const confirm = useContext(ConfirmContext)
  if (!confirm) {
    throw new Error('useConfirm must be used within ConfirmProvider')
  }
  return confirm
}
