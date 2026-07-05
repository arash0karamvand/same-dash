// دراپ‌داون سفارشی — جایگزین select بومی، هم‌استایل تقویم شمسی

import { useEffect, useId, useRef, useState } from 'react'
import JcalPanel from './JcalPanel'

export default function Select({
  value,
  onChange,
  options = [],
  placeholder = 'انتخاب کنید',
  required = false,
  disabled = false,
  label,
}) {
  const uid = useId()
  const wrapRef = useRef(null)
  const listRef = useRef(null)
  const [open, setOpen] = useState(false)

  const strValue = value == null ? '' : String(value)
  const selected = options.find((o) => String(o.value) === strValue)
  const display = selected ? selected.label : placeholder

  useEffect(() => {
    if (!open || !listRef.current) return
    const el = listRef.current.querySelector('.select-option.selected')
    el?.scrollIntoView({ block: 'nearest' })
  }, [open])

  const pick = (opt) => {
    onChange(opt.value)
    setOpen(false)
  }

  return (
    <div className="jcal-wrap" ref={wrapRef}>
      <input type="hidden" name={uid} value={strValue} required={required && !strValue} readOnly />
      <button
        type="button"
        className={`jcal-trigger select-trigger ${!selected || selected.value === '' ? 'placeholder' : ''}`}
        onClick={() => setOpen((o) => !o)}
        disabled={disabled}
        aria-expanded={open}
        aria-haspopup="listbox"
        aria-label={label}
      >
        <span className="select-trigger-text">{display}</span>
        <span className="jcal-trigger-chevron" aria-hidden>{open ? '▲' : '▼'}</span>
      </button>

      <JcalPanel
        open={open}
        onClose={() => setOpen(false)}
        anchorRef={wrapRef}
        variant="select"
        ariaLabel={label || placeholder}
      >
        <div className="select-options" role="listbox" ref={listRef}>
          {options.map((opt) => {
            const isSel = String(opt.value) === strValue
            return (
              <button
                key={String(opt.value)}
                type="button"
                role="option"
                aria-selected={isSel}
                className={`select-option ${isSel ? 'selected' : ''}`}
                onClick={() => pick(opt)}
              >
                <span>{opt.label}</span>
                {isSel && <span className="select-check" aria-hidden>✓</span>}
              </button>
            )
          })}
        </div>
      </JcalPanel>
    </div>
  )
}
