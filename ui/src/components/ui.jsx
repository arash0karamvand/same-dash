// مجموعه کامپوننت‌های پایه و قابل‌استفاده مجدد رابط کاربری.

import { forwardRef } from 'react'
import Icon from './icons/Icon'
import { badgeStyle, badgeVariantFromColor } from '../config/statusColors'

const STAT_ACCENT_DEFAULT = 'var(--accent)'

const LIQUID = 'liquid-glass liquid-glass--panel liquid-glass--jelly'

// کارت آماری داشبورد
export function StatCard({ label, value, hint, accent = STAT_ACCENT_DEFAULT }) {
  return (
    <div className={`stat-card ${LIQUID}`}>
      <div className="stat-bar" style={{ background: accent }} />
      <div className="stat-body">
        <span className="stat-label">{label}</span>
        <span className="stat-value num-display">{value}</span>
        {hint && <span className="stat-hint">{hint}</span>}
      </div>
    </div>
  )
}

// نشان (badge) رنگی برای سطح مشتری یا وضعیت
export function Badge({ children, color = STAT_ACCENT_DEFAULT, variant }) {
  const resolvedVariant = variant || badgeVariantFromColor(color)
  const style = badgeStyle(color)
  return (
    <span className={`badge badge--${resolvedVariant}`} style={style}>
      {children}
    </span>
  )
}

// دکمه با انواع مختلف
export const Button = forwardRef(function Button(
  { children, variant = 'primary', size, className = '', ...props },
  ref,
) {
  const sizeClass = size === 'sm' ? ' btn-sm' : ''
  return (
    <button
      ref={ref}
      className={`btn btn-${variant}${sizeClass}${className ? ` ${className}` : ''}`}
      {...props}
    >
      {children}
    </button>
  )
})

// دکمه لینکی جدول — variant: default | success | danger | warning
export const LinkAction = forwardRef(function LinkAction(
  { children, variant = 'default', className = '', ...props },
  ref,
) {
  const variantClass = variant === 'danger' ? ' danger' : variant !== 'default' ? ` link-${variant}` : ''
  return (
    <button
      ref={ref}
      type="button"
      className={`link${variantClass}${className ? ` ${className}` : ''}`}
      {...props}
    >
      {children}
    </button>
  )
})

// کارت ساده با عنوان
export function Card({ title, actions, children, className = '', elevated = false, interactive = true }) {
  const liquid = interactive ? LIQUID : 'liquid-glass liquid-glass--panel'
  return (
    <div className={`card ${liquid}${elevated ? ' card--elevated' : ''}${className ? ` ${className}` : ''}`.trim()}>
      {(title || actions) && (
        <div className="card-head">
          <h3>{title}</h3>
          <div className="card-actions">{actions}</div>
        </div>
      )}
      <div className="card-body">{children}</div>
    </div>
  )
}

// پنجره مودال ساده
export function Modal({ title, open, onClose, children, wide = false, className = '' }) {
  if (!open) return null
  return (
    <div className="modal-overlay" onClick={onClose}>
      <div
        className={`modal liquid-glass liquid-glass--strong liquid-glass--panel ${wide ? 'modal-wide' : ''}${className ? ` ${className}` : ''}`}
        onClick={(e) => e.stopPropagation()}
      >
        <div className="modal-head">
          <h3>{title}</h3>
          <button type="button" className="modal-close" onClick={onClose} aria-label="بستن">
            <Icon name="x" size={18} />
          </button>
        </div>
        <div className="modal-body">{children}</div>
      </div>
    </div>
  )
}

// فیلد فرم (label + input/children)
export function Field({ label, children, caps = false }) {
  return (
    <label className="field">
      <span className={`field-label${caps ? ' field-label--caps' : ''}`}>{label}</span>
      {children}
    </label>
  )
}

// نوار فیلتر یکدست صفحات (جستجو، select، تاریخ)
export function FilterBar({ children, className = '' }) {
  return (
    <div className={`page-filters liquid-glass liquid-glass--panel liquid-glass--jelly${className ? ` ${className}` : ''}`}>
      {children}
    </div>
  )
}

// نمایش پیام خالی بودن داده
export function EmptyState({ text = 'داده‌ای برای نمایش وجود ندارد.', children }) {
  return (
    <div className="empty-state liquid-glass liquid-glass--panel liquid-glass--jelly">
      <div className="empty-state-icon">
        <Icon name="info" size={32} />
      </div>
      <p>{text}</p>
      {children}
    </div>
  )
}
