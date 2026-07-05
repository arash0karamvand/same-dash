// پنل تقویم شمسی — portal برای نمایش کامل روی دسکتاپ (بدون clip شدن داخل card)

import { createPortal } from 'react-dom'
import { useEffect, useLayoutEffect, useRef, useState } from 'react'

const PANEL_WIDTH = { date: 380, month: 320, select: 220 }
const PANEL_HEIGHT = { date: 300, month: 300, select: 320 }

function isMobileViewport() {
  return window.matchMedia('(max-width: 767px)').matches
}

export default function JcalPanel({
  open,
  onClose,
  anchorRef,
  variant = 'date',
  ariaLabel,
  children,
}) {
  const panelRef = useRef(null)
  const [style, setStyle] = useState(null)

  useLayoutEffect(() => {
    if (!open || !anchorRef.current) return undefined

    const update = () => {
      if (isMobileViewport()) {
        setStyle(null)
        return
      }

      const rect = anchorRef.current.getBoundingClientRect()
      const width = variant === 'select'
        ? Math.max(rect.width, PANEL_WIDTH.select)
        : (PANEL_WIDTH[variant] || PANEL_WIDTH.date)
      const height = PANEL_HEIGHT[variant] || PANEL_HEIGHT.date
      const margin = 12

      let top = rect.bottom + 6
      if (top + height > window.innerHeight - margin) {
        top = Math.max(margin, rect.top - height - 6)
      }

      let left = rect.right - width
      left = Math.max(margin, Math.min(left, window.innerWidth - width - margin))

      setStyle({
        position: 'fixed',
        top,
        left,
        width,
        right: 'auto',
        zIndex: 5000,
      })
    }

    update()
    window.addEventListener('scroll', update, true)
    window.addEventListener('resize', update)
    return () => {
      window.removeEventListener('scroll', update, true)
      window.removeEventListener('resize', update)
    }
  }, [open, anchorRef, variant])

  useEffect(() => {
    if (!open) return undefined
    const onDoc = (e) => {
      if (anchorRef.current?.contains(e.target)) return
      if (panelRef.current?.contains(e.target)) return
      onClose()
    }
    document.addEventListener('mousedown', onDoc)
    return () => document.removeEventListener('mousedown', onDoc)
  }, [open, onClose, anchorRef])

  if (!open) return null

  const panel = (
    <div
      ref={panelRef}
      className={`jcal-panel${style ? ' jcal-panel--floating' : ''}`}
      style={style || undefined}
      role="dialog"
      aria-label={ariaLabel}
    >
      {children}
    </div>
  )

  return createPortal(panel, document.body)
}
