// ورودی مبلغ با نمایش حروف فارسی زیر فیلد

import { useLayoutEffect, useRef } from 'react'
import { CURRENCY_UNIT } from '../config/money'
import { digitsOnly, formatGroupedDigits, getAmountWords } from '../utils/format'

export default function MoneyInput({
  value,
  onChange,
  unit = CURRENCY_UNIT,
  className = 'ltr',
  min,
  max,
  step,
  required,
  placeholder,
  disabled,
  name,
  id,
}) {
  const words = getAmountWords(value, unit)
  const inputRef = useRef(null)
  const caretDigitsRef = useRef(null)
  const display = formatGroupedDigits(value)

  const emit = (event, raw) => {
    onChange({
      ...event,
      target: { value: raw, name, id },
    })
  }

  const handleChange = (event) => {
    const rawDisplay = event.target.value
    const caret = event.target.selectionStart ?? rawDisplay.length
    caretDigitsRef.current = digitsOnly(rawDisplay.slice(0, caret)).length
    let raw = digitsOnly(rawDisplay)
    if (max != null && max !== '' && raw && Number(raw) > Number(max)) {
      raw = String(Math.trunc(Number(max)))
    }
    emit(event, raw)
  }

  useLayoutEffect(() => {
    const input = inputRef.current
    const digitsWanted = caretDigitsRef.current
    if (!input || digitsWanted == null || document.activeElement !== input) return
    const formatted = input.value
    let pos = 0
    let seen = 0
    while (pos < formatted.length && seen < digitsWanted) {
      if (/\d/.test(formatted[pos])) seen += 1
      pos += 1
    }
    input.setSelectionRange(pos, pos)
    caretDigitsRef.current = null
  }, [display])

  return (
    <div className="money-input-wrap">
      <input
        ref={inputRef}
        className={className}
        type="text"
        inputMode="numeric"
        autoComplete="off"
        name={name}
        id={id}
        min={min}
        max={max}
        step={step}
        required={required}
        placeholder={placeholder}
        disabled={disabled}
        value={display}
        onChange={handleChange}
        onWheel={(event) => event.currentTarget.blur()}
      />
      {words ? <span className="money-input-hint" aria-live="polite">{words}</span> : null}
    </div>
  )
}

export function MoneyWordsHint({ value, unit = CURRENCY_UNIT, className = 'money-input-hint' }) {
  const words = getAmountWords(value, unit)
  if (!words) return null
  return <span className={className} aria-live="polite">{words}</span>
}
