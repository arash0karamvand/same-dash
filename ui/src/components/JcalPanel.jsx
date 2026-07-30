// پنل شناور — portal برای نمایش جلوی/زیر المان ماشه (بدون clip شدن داخل card)

import { createPortal } from 'react-dom'
import { useEffect, useLayoutEffect, useRef, useState } from 'react'

const PANEL_WIDTH = { date: 380, month: 320, select: 220, menu: 280 }
const PANEL_HEIGHT = { date: 300, month: 300, select: 320, menu: 240 }
const POPOVER_Z = 6000

function isMobileViewport() {
  return window.matchMedia('(max-width: 767px)').matches
}

function computePosition(anchorRect, panelRect, variant) {
  const margin = 8
  const gap = 6
  const minWidth = PANEL_WIDTH[variant] || PANEL_WIDTH.date
  const width = variant === 'select' || variant === 'menu'
    ? Math.max(anchorRect.width, minWidth)
    : minWidth
  const height = panelRect?.height || PANEL_HEIGHT[variant] || PANEL_HEIGHT.date

  let top = anchorRect.bottom + gap
  if (top + height > window.innerHeight - margin) {
    const above = anchorRect.top - height - gap
    if (above >= margin) {
      top = above
    } else {
      top = Math.max(margin, window.innerHeight - height - margin)
    }
  }

  let left = anchorRect.right - width
  left = Math.max(margin, Math.min(left, window.innerWidth - width - margin))

  return {
    position: 'fixed',
    top,
    left,
    width: variant === 'select' || variant === 'menu' ? width : undefined,
    minWidth: variant === 'date' || variant === 'month' ? minWidth : undefined,
    maxHeight: Math.max(120, window.innerHeight - margin * 2),
    right: 'auto',
    zIndex: POPOVER_Z,
  }
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
  const [mobileSheet, setMobileSheet] = useState(false)

  useLayoutEffect(() => {
    if (!open) {
      setStyle(null)
      setMobileSheet(false)
      return undefined
    }

    const update = () => {
      const anchor = anchorRef.current
      if (!anchor) return

      if (isMobileViewport()) {
        setMobileSheet(true)
        setStyle(null)
        return
      }

      setMobileSheet(false)
      const anchorRect = anchor.getBoundingClientRect()
      const panelRect = panelRef.current?.getBoundingClientRect()
      setStyle(computePosition(anchorRect, panelRect, variant))
    }

    update()
    const raf = requestAnimationFrame(update)

    window.addEventListener('scroll', update, true)
    window.addEventListener('resize', update)

    let ro
    if (typeof ResizeObserver !== 'undefined') {
      ro = new ResizeObserver(update)
      if (anchorRef.current) ro.observe(anchorRef.current)
      if (panelRef.current) ro.observe(panelRef.current)
    }

    return () => {
      cancelAnimationFrame(raf)
      window.removeEventListener('scroll', update, true)
      window.removeEventListener('resize', update)
      ro?.disconnect()
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
      className={[
        'jcal-panel',
        mobileSheet ? 'jcal-panel--sheet' : 'jcal-panel--floating',
        !mobileSheet && !style ? 'jcal-panel--pending' : '',
      ].filter(Boolean).join(' ')}
      style={style || undefined}
      role="dialog"
      aria-label={ariaLabel}
    >
      {children}
    </div>
  )

  return createPortal(panel, document.body)
}
