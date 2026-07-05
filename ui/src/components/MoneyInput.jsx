// ورودی مبلغ با نمایش حروف فارسی زیر فیلد

import { getAmountWords } from '../utils/format'

export default function MoneyInput({
  value,
  onChange,
  unit = 'تومان',
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

  return (
    <div className="money-input-wrap">
      <input
        className={className}
        type="number"
        name={name}
        id={id}
        min={min}
        max={max}
        step={step}
        required={required}
        placeholder={placeholder}
        disabled={disabled}
        value={value}
        onChange={onChange}
        inputMode="numeric"
      />
      {words ? <span className="money-input-hint" aria-live="polite">{words}</span> : null}
    </div>
  )
}

export function MoneyWordsHint({ value, unit = 'تومان', className = 'money-input-hint' }) {
  const words = getAmountWords(value, unit)
  if (!words) return null
  return <span className={className} aria-live="polite">{words}</span>
}
