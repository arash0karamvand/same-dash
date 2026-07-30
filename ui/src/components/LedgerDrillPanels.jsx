import { forwardRef } from 'react'
import ResizeHandle from './ResizeHandle'
import { EmptyState } from './ui'
import { TERMS } from '../config/accountingTerms'
import { formatRial } from '../utils/format'

export const DEFAULT_DRILL_PANEL_LAYOUT = {
  general: 'normal',
  subsidiary: 'normal',
  detailed: 'normal',
  ledger: 'normal',
}

const PANEL_STEP = {
  general: 1,
  subsidiary: 2,
  detailed: 3,
  ledger: 4,
}

export function rowSelectionLabel(row) {
  if (!row) return ''
  const code = row.account_code || row.detailed_code || ''
  const name = row.account_name || row.detailed_name || ''
  return [code, name].filter(Boolean).join(' · ')
}

function formatBalance(row) {
  const balance = row.balance_debit || row.balance_credit
  if (!balance) return null
  const side = row.balance_debit ? TERMS.debit : TERMS.credit
  return { amount: Number(balance), side, text: `${formatRial(balance)} (${side})` }
}

export function LedgerDrillCard({
  panelId,
  title,
  subtitle = '',
  selectionLabel = '',
  layoutMode = 'normal',
  onToggleMinimize,
  onToggleMaximize,
  onFocus,
  compact = false,
  variant = 'trial',
  panelHeight,
  onResizeHeight,
  resizable = false,
  cardSelected = false,
  onSelectCard,
  children,
}) {
  const minimized = layoutMode === 'minimized'
  const maximized = layoutMode === 'maximized'
  const collapsed = minimized && !compact
  const canFocus = collapsed && onFocus
  const canResizeBody = resizable && !minimized && !compact
  const step = PANEL_STEP[panelId] || 1

  const cardStyle = canResizeBody && panelHeight
    ? { height: `${panelHeight}px` }
    : undefined

  const headSubtitle = collapsed
    ? (selectionLabel || subtitle)
    : subtitle

  return (
    <article
      style={cardStyle}
      data-panel={panelId}
      className={[
        'ld-card',
        `ld-card--${panelId}`,
        collapsed ? 'ld-card--collapsed' : '',
        maximized ? 'ld-card--maximized' : '',
        compact ? 'ld-card--compact' : '',
        canFocus ? 'ld-card--focusable' : '',
        canResizeBody ? 'ld-card--resizable' : '',
        variant === 'ledger' ? 'ld-card--ledger' : '',
        cardSelected ? 'ld-card--selected' : '',
      ].filter(Boolean).join(' ')}
    >
      <header
        className="ld-card__head"
        onClick={(e) => {
          if (e.target.closest('.ld-card__btn')) return
          if (canFocus) {
            onFocus(panelId)
            return
          }
          onSelectCard?.(panelId)
        }}
        onKeyDown={canFocus ? (e) => {
          if (e.key === 'Enter' || e.key === ' ') {
            e.preventDefault()
            onFocus(panelId)
          }
        } : undefined}
        role={canFocus ? 'button' : undefined}
        tabIndex={canFocus ? 0 : undefined}
      >
        <span className="ld-card__step" aria-hidden="true">{step}</span>
        <div className="ld-card__meta">
          <h3 className="ld-card__title">{title}</h3>
          {headSubtitle && (
            <p className="ld-card__subtitle">{headSubtitle}</p>
          )}
        </div>
        {!compact && (
          <div className="ld-card__actions">
            <button
              type="button"
              className="ld-card__btn"
              onClick={(e) => { e.stopPropagation(); onToggleMinimize(panelId) }}
              title={minimized ? 'باز کردن' : 'جمع کردن'}
              aria-label={minimized ? 'باز کردن' : 'جمع کردن'}
            >
              {minimized ? '+' : '−'}
            </button>
            <button
              type="button"
              className="ld-card__btn"
              onClick={(e) => { e.stopPropagation(); onToggleMaximize(panelId) }}
              title={maximized ? 'بازگشت' : 'تمام‌صفحه'}
              aria-label={maximized ? 'بازگشت' : 'تمام‌صفحه'}
            >
              {maximized ? '⤡' : '⛶'}
            </button>
          </div>
        )}
      </header>

      {!minimized && (
        <div className="ld-card__body">
          {children}
          {canResizeBody && onResizeHeight && (
            <ResizeHandle
              direction="row"
              className="ld-card__resize-h"
              ariaLabel={`تغییر ارتفاع ${title}`}
              onDrag={onResizeHeight}
            />
          )}
        </div>
      )}
    </article>
  )
}

export function LedgerTrialColumn({
  panelId,
  title,
  subtitle,
  selectionLabel,
  layoutMode,
  onToggleMinimize,
  onToggleMaximize,
  onFocus,
  rows,
  loading,
  selectedId,
  idKey,
  onSelect,
  compact = false,
  emptyText = 'حسابی یافت نشد.',
  resizable = false,
  panelHeight,
  onResizeHeight,
  cardSelected = false,
  onSelectCard,
}) {
  return (
    <LedgerDrillCard
      panelId={panelId}
      title={title}
      subtitle={subtitle}
      selectionLabel={selectionLabel}
      layoutMode={layoutMode}
      onToggleMinimize={onToggleMinimize}
      onToggleMaximize={onToggleMaximize}
      onFocus={onFocus}
      compact={compact}
      resizable={resizable}
      panelHeight={panelHeight}
      onResizeHeight={onResizeHeight}
      cardSelected={cardSelected}
      onSelectCard={onSelectCard}
    >
      {loading ? (
        <div className="ld-card__loading">در حال بارگذاری…</div>
      ) : !rows.length ? (
        <div className="ld-card__empty">
          <EmptyState text={emptyText} />
        </div>
      ) : (
        <ul className="ld-list" role="listbox" aria-label={title}>
          {rows.map((row) => {
            const rowId = row[idKey]
            const selected = selectedId != null && String(selectedId) === String(rowId)
            const balance = formatBalance(row)
            return (
              <li key={rowId || row.account_code} role="none">
                <button
                  type="button"
                  role="option"
                  aria-selected={selected}
                  className={`ld-list__row${selected ? ' ld-list__row--active' : ''}`}
                  onClick={() => {
                    onSelectCard?.(panelId)
                    onSelect(row)
                  }}
                >
                  <span className="ld-list__code">{row.account_code}</span>
                  <span className="ld-list__name">{row.account_name}</span>
                  <span className="ld-list__balance">
                    {balance ? balance.text : '—'}
                  </span>
                </button>
              </li>
            )
          })}
        </ul>
      )}
    </LedgerDrillCard>
  )
}

export const LedgerDrillStage = forwardRef(function LedgerDrillStage({ style, children }, ref) {
  return (
    <div ref={ref} className="ld-stage" style={style}>
      {children}
    </div>
  )
})

export function LedgerStageDivider({ label, onDrag, invert = false }) {
  return (
    <ResizeHandle
      className="ld-stage__divider"
      ariaLabel={label}
      invert={invert}
      onDrag={onDrag}
    />
  )
}

export function LedgerWorkspace({ title, breadcrumb, toolbar, children }) {
  return (
    <section className="ld-workspace">
      <header className="ld-workspace__bar">
        <div className="ld-workspace__heading">
          <h2 className="ld-workspace__title">{title}</h2>
          {breadcrumb && (
            <p className="ld-workspace__path">{breadcrumb}</p>
          )}
        </div>
        {toolbar && <div className="ld-workspace__toolbar">{toolbar}</div>}
      </header>
      <div className="ld-workspace__content">
        {children}
      </div>
    </section>
  )
}

export function LedgerSidePanel({
  open,
  minimized,
  width,
  title,
  onToggleMinimize,
  onClose,
  onResize,
  children,
  panelRef,
}) {
  if (!open) return null

  return (
    <aside
      ref={panelRef}
      className={`ld-side${minimized ? ' ld-side--collapsed' : ''}`}
      style={minimized ? undefined : { width: `${width}px` }}
    >
      {!minimized && (
        <ResizeHandle
          className="ld-side__resize"
          edge="inline-start"
          ariaLabel="تغییر عرض پنل"
          onDrag={onResize}
        />
      )}
      <header className="ld-side__head">
        <h3 className="ld-side__title">{title}</h3>
        <div className="ld-side__actions">
          <button
            type="button"
            className="ld-card__btn"
            onClick={onToggleMinimize}
            title={minimized ? 'باز کردن' : 'جمع کردن'}
            aria-label={minimized ? 'باز کردن' : 'جمع کردن'}
          >
            {minimized ? '+' : '−'}
          </button>
          <button
            type="button"
            className="ld-card__btn"
            onClick={onClose}
            title="بستن"
            aria-label="بستن"
          >
            ×
          </button>
        </div>
      </header>
      {!minimized && (
        <div className="ld-side__body">{children}</div>
      )}
    </aside>
  )
}
