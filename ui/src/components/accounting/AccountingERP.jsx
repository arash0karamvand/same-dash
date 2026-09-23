import Icon from '../icons/Icon'
import { fromLegacy } from '../../styles/tw.js'

export function AccountingPageHeader({ title, description, eyebrow, actions, meta }) {
  return (
    <header className={fromLegacy("acct-erp-page-head acct-glass")}>
      <div className={fromLegacy("acct-erp-page-copy")}>
        {eyebrow && <span className={fromLegacy("acct-erp-eyebrow")}>{eyebrow}</span>}
        <h2>{title}</h2>
        {description && <p>{description}</p>}
        {meta && <div className={fromLegacy("acct-erp-meta")}>{meta}</div>}
      </div>
      {actions && <div className={fromLegacy("acct-erp-page-actions")}>{actions}</div>}
    </header>
  )
}

export function AccountingToolbar({ children, className = '' }) {
  return <div className={fromLegacy(`acct-erp-toolbar acct-glass ${className}`)}>{children}</div>
}

export function AccountingSummary({ items = [] }) {
  return (
    <div className={fromLegacy("acct-erp-summary acct-glass")} aria-label="خلاصه مالی">
      {items.map((item) => (
        <div key={item.label} className={fromLegacy(`acct-erp-summary-item${item.tone ? ` is-${item.tone}` : ''}`)}>
          <span>{item.label}</span>
          <strong className="acct-number">{item.value}</strong>
          {item.hint && <small>{item.hint}</small>}
        </div>
      ))}
    </div>
  )
}

export function AccountingDataPanel({ title, subtitle, actions, children, className = '' }) {
  return (
    <section className={fromLegacy(`acct-erp-data-panel acct-glass ${className}`)}>
      {(title || actions) && (
        <header className={fromLegacy("acct-erp-panel-head")}>
          <div>
            {title && <h3>{title}</h3>}
            {subtitle && <p>{subtitle}</p>}
          </div>
          {actions && <div className={fromLegacy("acct-erp-panel-actions")}>{actions}</div>}
        </header>
      )}
      <div className={fromLegacy("acct-erp-panel-body")}>{children}</div>
    </section>
  )
}

export function AccountingPagination({
  page,
  pageSize,
  total,
  onPageChange,
  disabled = false,
}) {
  const pageCount = Math.max(1, Math.ceil(total / pageSize))
  if (total <= pageSize) return null

  return (
    <div className={fromLegacy("acct-erp-pagination")}>
      <span>
        صفحه {page.toLocaleString('fa-IR')} از {pageCount.toLocaleString('fa-IR')}
        {' · '}
        {total.toLocaleString('fa-IR')} رکورد
      </span>
      <div>
        <button
          type="button"
          disabled={disabled || page <= 1}
          onClick={() => onPageChange(page - 1)}
          aria-label="صفحه قبل"
        >
          <Icon name="chevron-right" size={16} />
          قبلی
        </button>
        <button
          type="button"
          disabled={disabled || page >= pageCount}
          onClick={() => onPageChange(page + 1)}
          aria-label="صفحه بعد"
        >
          بعدی
          <Icon name="chevron-left" size={16} />
        </button>
      </div>
    </div>
  )
}
