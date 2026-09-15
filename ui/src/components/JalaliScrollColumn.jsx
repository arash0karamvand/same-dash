// ستون اسکرولی تقویم شمسی — سال / ماه / روز

import { useEffect, useRef } from 'react'
import { fromLegacy } from '../styles/tw.js'

export const JCAL_CELL_H = 44

export default function JalaliScrollColumn({ label, items, value, onSelect }) {
  const scrollRef = useRef(null)
  const scrollEndRef = useRef(null)

  useEffect(() => {
    const el = scrollRef.current
    if (!el) return
    const idx = items.findIndex((it) => it.value === value)
    if (idx < 0) return
    el.scrollTop = idx * JCAL_CELL_H
  }, [items, value])

  const snapToNearest = () => {
    const el = scrollRef.current
    if (!el || !items.length) return
    const idx = Math.round(el.scrollTop / JCAL_CELL_H)
    const clamped = Math.max(0, Math.min(items.length - 1, idx))
    const item = items[clamped]
    if (item && item.value !== value) onSelect(item.value)
    el.scrollTo({ top: clamped * JCAL_CELL_H, behavior: 'smooth' })
  }

  const onScroll = () => {
    if (scrollEndRef.current) clearTimeout(scrollEndRef.current)
    scrollEndRef.current = setTimeout(snapToNearest, 120)
  }

  return (
    <div className={fromLegacy("jcal-column")}>
      <div className={fromLegacy("jcal-column-label")}>{label}</div>
      <div className={fromLegacy("jcal-column-viewport")}>
        <div className={fromLegacy("jcal-column-highlight")} aria-hidden />
        <div
          ref={scrollRef}
          className={fromLegacy("jcal-column-scroll")}
          onScroll={onScroll}
          role="listbox"
          aria-label={label}
        >
          <div className={fromLegacy("jcal-column-spacer")} />
          {items.map((it, idx) => (
            <button
              key={it.value}
              type="button"
              role="option"
              aria-selected={it.value === value}
              className={fromLegacy(`jcal-cell ${it.value === value ? 'selected' : ''}`)}
              onClick={() => {
                onSelect(it.value)
                scrollRef.current?.scrollTo({ top: idx * JCAL_CELL_H, behavior: 'smooth' })
              }}
            >
              {it.label}
            </button>
          ))}
          <div className={fromLegacy("jcal-column-spacer")} />
        </div>
      </div>
    </div>
  )
}
