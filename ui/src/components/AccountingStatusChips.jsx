// چیپ‌های وضعیت — جایگزین select برای لمس راحت‌تر

import { fromLegacy } from '../styles/tw.js'
export default function AccountingStatusChips({ value, onChange, options }) {
  return (
    <div className={fromLegacy("acct-status-chips")} role="tablist" aria-label="فیلتر وضعیت">
      {options.map((opt) => {
        const active = value === opt.value
        return (
          <button
            key={opt.value || '__all__'}
            type="button"
            role="tab"
            aria-selected={active}
            className={fromLegacy(`acct-status-chip${active ? ' active' : ''}`)}
            onClick={() => onChange(opt.value)}
          >
            {opt.label}
            {opt.count != null && <span className={fromLegacy("acct-status-chip-count")}>{opt.count}</span>}
          </button>
        )
      })}
    </div>
  )
}
