// مجموعه کامپوننت‌های پایه و قابل‌استفاده مجدد رابط کاربری.

import { forwardRef, useEffect } from 'react'
import { createPortal } from 'react-dom'
import Icon from './icons/Icon'
import { useIsPhone } from '../hooks/breakpoints'
import { PAGE_SIZE } from '../config/pagination'
import { badgeStyle, badgeVariantFromColor } from '../config/statusColors'
import { toPersianDigits } from '../utils/jalali'
import {
  badgeClass,
  buttonClass,
  cardClass,
  cn,
  tw,
} from '../styles/tw'

const STAT_ACCENT_DEFAULT = 'var(--accent)'

export function StatCard({
  label,
  value,
  hint,
  accent = STAT_ACCENT_DEFAULT,
  className = '',
  active = false,
  onClick,
}) {
  const interactive = typeof onClick === 'function'
  const Tag = interactive ? 'button' : 'div'
  return (
    <Tag
      type={interactive ? 'button' : undefined}
      className={cn(
        'liquid-glass liquid-glass--panel liquid-glass--jelly',
        tw.statCard,
        interactive && tw.statCardInteractive,
        active && tw.statCardActive,
        className,
      )}
      onClick={onClick}
      aria-pressed={interactive ? active : undefined}
    >
      <div className={tw.statBar} style={{ background: accent }} />
      <div className={tw.statBody}>
        <span className={tw.statLabel}>{label}</span>
        <span className={cn(tw.statValue, tw.numDisplay)}>{value}</span>
        {hint && <span className={tw.statHint}>{hint}</span>}
      </div>
    </Tag>
  )
}

export function Badge({ children, color = STAT_ACCENT_DEFAULT, variant }) {
  const resolvedVariant = variant || badgeVariantFromColor(color)
  const style = badgeStyle(color)
  return (
    <span className={badgeClass(resolvedVariant)} style={style}>
      {children}
    </span>
  )
}

export const Button = forwardRef(function Button(
  { children, variant = 'primary', size, className = '', ...props },
  ref,
) {
  return (
    <button
      ref={ref}
      className={buttonClass({ variant, size, className })}
      {...props}
    >
      {children}
    </button>
  )
})

export const LinkAction = forwardRef(function LinkAction(
  { children, variant = 'default', className = '', ...props },
  ref,
) {
  const variantClass =
    variant === 'danger' ? tw.linkDanger : variant === 'success' ? tw.linkSuccess : variant === 'warning' ? tw.linkWarning : ''
  return (
    <button
      ref={ref}
      type="button"
      className={cn(tw.link, variantClass, className)}
      {...props}
    >
      {children}
    </button>
  )
})

export function Card({ title, actions, children, className = '', elevated = false, interactive = true }) {
  return (
    <div className={cardClass({ elevated, interactive, className })}>
      {(title || actions) && (
        <div className={tw.cardHead}>
          <h3>{title}</h3>
          <div className={tw.cardActions}>{actions}</div>
        </div>
      )}
      <div className={tw.cardBody}>{children}</div>
    </div>
  )
}

export function Modal({ title, open, onClose, children, wide = false, className = '', overlayClassName = '' }) {
  const isMobile = useIsPhone()

  useEffect(() => {
    if (!open) return undefined
    document.body.classList.add('modal-open')
    return () => document.body.classList.remove('modal-open')
  }, [open])

  if (!open) return null

  return createPortal(
    <div 
      className={cn(tw.modalOverlay, overlayClassName)} 
      onClick={onClose}
      style={{
        backdropFilter: 'blur(8px)',
        WebkitBackdropFilter: 'blur(8px)',
        background: 'rgba(0, 0, 0, 0.4)'
      }}
    >
      <div
        className={cn('acct-glass-modal', tw.modal, wide && tw.modalWide, isMobile && tw.modalSheet, className)}
        onClick={(e) => e.stopPropagation()}
        role="dialog"
        aria-modal="true"
        aria-label={title}
      >
        {isMobile && <div className={tw.modalSheetHandle} aria-hidden />}
        <div className={tw.modalHead}>
          <h3 style={{ 
            fontSize: '18px',
            fontWeight: '700',
            color: '#111827'
          }}>
            {title}
          </h3>
          <button 
            type="button" 
            className={tw.modalClose} 
            onClick={onClose} 
            aria-label="بستن"
            style={{
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              width: '36px',
              height: '36px',
              borderRadius: '6px',
              border: 'none',
              background: 'transparent',
              cursor: 'pointer',
              transition: 'background var(--transition-fast)'
            }}
            onMouseEnter={(e) => e.currentTarget.style.background = '#F3F4F6'}
            onMouseLeave={(e) => e.currentTarget.style.background = 'transparent'}
          >
            <Icon name="x" size={20} />
          </button>
        </div>
        <div className={tw.modalBody}>{children}</div>
      </div>
    </div>,
    document.body,
  )
}

export function Field({ label, children, caps = false }) {
  return (
    <label className={tw.field}>
      <span className={cn(tw.fieldLabel, caps && tw.fieldLabelCaps)}>{label}</span>
      {children}
    </label>
  )
}

export function FilterBar({ children, className = '' }) {
  return (
    <div className={cn(tw.pageFilters, className)}>
      {children}
    </div>
  )
}

export function LoadMoreButton({ hasMore, loading, onClick, pageSize = PAGE_SIZE }) {
  if (!hasMore) return null
  return (
    <div className={tw.loadMore}>
      <Button type="button" disabled={loading} onClick={onClick}>
        {loading ? 'در حال بارگذاری…' : `نمایش ${toPersianDigits(pageSize)} رکورد دیگر`}
      </Button>
    </div>
  )
}

export function EmptyState({ text = 'داده‌ای برای نمایش وجود ندارد.', children }) {
  return (
    <div className={tw.emptyState}>
      <div className={tw.emptyStateIcon}>
        <Icon name="info" size={32} />
      </div>
      <p>{text}</p>
      {children}
    </div>
  )
}
