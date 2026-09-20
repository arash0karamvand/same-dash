import { fromLegacy } from '../styles/tw.js'

/**
 * Primary segmented navigation for beta workshop pages.
 * items: { key, label, count?, hint? }
 */
export function BetaSegmentNav({ items, value, onChange, label, className = '' }) {
  if (!items?.length) return null
  return (
    <div className={fromLegacy(`beta-segment-nav ${className}`.trim())} role="tablist" aria-label={label || 'ناوبری'}>
      {label && <span className={fromLegacy('beta-segment-nav-label')}>{label}</span>}
      <div className={fromLegacy('beta-segment-nav-track')}>
        {items.map((item) => (
          <button
            key={item.key}
            type="button"
            role="tab"
            aria-selected={value === item.key}
            className={fromLegacy(`beta-segment-btn ${value === item.key ? 'active' : ''}`)}
            onClick={() => onChange(item.key)}
          >
            <span className={fromLegacy('beta-segment-btn-label')}>{item.label}</span>
            {item.count != null && (
              <span className={fromLegacy('beta-segment-btn-count')}>{item.count}</span>
            )}
            {item.hint && <span className={fromLegacy('beta-segment-btn-hint')}>{item.hint}</span>}
          </button>
        ))}
      </div>
    </div>
  )
}

/**
 * Secondary chip navigation — stage/status filters with optional accent dot.
 */
export function BetaChipNav({ items, value, onChange, label, className = '' }) {
  if (!items?.length) return null
  return (
    <div className={fromLegacy(`beta-chip-nav ${className}`.trim())}>
      {label && <span className={fromLegacy('beta-chip-nav-label')}>{label}</span>}
      <div className={fromLegacy('beta-chip-nav-track')} role="tablist" aria-label={label || 'فیلتر'}>
        {items.map((item) => (
          <button
            key={item.key}
            type="button"
            role="tab"
            aria-selected={value === item.key}
            className={fromLegacy(`beta-chip-btn ${value === item.key ? 'active' : ''}`)}
            onClick={() => onChange(item.key)}
          >
            {item.accent && (
              <span className={fromLegacy('beta-chip-dot')} style={{ background: item.accent }} aria-hidden />
            )}
            <span>{item.label}</span>
            {item.count != null && <span className={fromLegacy('beta-chip-count')}>{item.count}</span>}
          </button>
        ))}
      </div>
    </div>
  )
}
