import { useCallback, useRef } from 'react'
import { fromLegacy } from '../styles/tw.js'

/** @typedef {'inline-start' | 'inline-end'} ResizeEdge */

function isDocumentRtl() {
  if (typeof document === 'undefined') return false
  return document.documentElement.dir === 'rtl'
    || getComputedStyle(document.documentElement).direction === 'rtl'
}

function columnResizeDelta(movementX, edge, invert) {
  const rtl = isDocumentRtl()
  let sign = 1
  if (edge === 'inline-start') {
    sign = rtl ? 1 : -1
  } else {
    sign = rtl ? -1 : 1
  }
  const delta = sign * movementX
  return invert ? -delta : delta
}

export default function ResizeHandle({
  onDrag,
  onDragEnd,
  direction = 'column',
  edge = 'inline-end',
  invert = false,
  className = '',
  disabled = false,
  ariaLabel = 'تغییر اندازه',
  grip = true,
}) {
  const dragging = useRef(false)

  const onPointerDown = useCallback((e) => {
    if (disabled) return
    e.preventDefault()
    dragging.current = true
    e.currentTarget.setPointerCapture(e.pointerId)
    document.body.classList.add('is-resizing')
    document.body.dataset.resizeDir = direction === 'row' ? 'row' : 'col'
  }, [disabled, direction])

  const onPointerMove = useCallback((e) => {
    if (!dragging.current || disabled) return
    const delta = direction === 'row'
      ? (invert ? -e.movementY : e.movementY)
      : columnResizeDelta(e.movementX, edge, invert)
    if (delta !== 0) onDrag(delta)
  }, [direction, edge, invert, disabled, onDrag])

  const finishDrag = useCallback((e) => {
    if (!dragging.current) return
    dragging.current = false
    document.body.classList.remove('is-resizing')
    delete document.body.dataset.resizeDir
    if (e.currentTarget.hasPointerCapture(e.pointerId)) {
      e.currentTarget.releasePointerCapture(e.pointerId)
    }
    onDragEnd?.()
  }, [onDragEnd])

  return (
    <div
      role="separator"
      aria-orientation={direction === 'row' ? 'horizontal' : 'vertical'}
      aria-label={ariaLabel}
      className={fromLegacy(
        'resize-handle',
        direction === 'row' ? 'resize-handle-row' : 'resize-handle-col',
        grip ? 'resize-handle-grip' : '',
        disabled ? 'resize-handle-disabled' : '',
        className,
      )}
      onPointerDown={onPointerDown}
      onPointerMove={onPointerMove}
      onPointerUp={finishDrag}
      onPointerCancel={finishDrag}
    />
  )
}
