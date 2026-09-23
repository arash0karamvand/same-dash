// کاوشگر دفتر کل — Modern Tree + Detail Panel

import { useEffect, useMemo, useState } from 'react'
import Icon from '../icons/Icon'
import { Button, EmptyState } from '../ui'
import { TERMS } from '../../config/accountingTerms'
import { formatRial } from '../../utils/format'
import { useIsCompactTablet, useIsPhone } from '../../hooks/breakpoints'

/**
 * Professional Ledger Explorer
 * - Enhanced tree navigation with keyboard support
 * - High data density display
 * - Color-coded balances
 * - Responsive collapsible panels
 */

function balanceLabel(row) {
  if (!row) return null
  const debit = Number(row.balance_debit) || 0
  const credit = Number(row.balance_credit) || 0
  if (!debit && !credit) return null
  if (debit >= credit) return { amount: debit - credit, side: TERMS.debit, type: 'debit' }
  return { amount: credit - debit, side: TERMS.credit, type: 'credit' }
}

function TreeNode({ label, code, balance, depth = 0, active, expanded, hasChildren, onToggle, onSelect }) {
  return (
    <div className={`acct-ledger-account-row depth-${depth}${active ? ' is-active' : ''}`}>
      <div className="acct-ledger-account-line">
        {hasChildren ? (
          <button
            type="button"
            onClick={onToggle}
            aria-label={expanded ? 'بستن' : 'باز کردن'}
            className="acct-ledger-expand"
          >
            <Icon name={expanded ? 'minus' : 'plus'} size={12} />
          </button>
        ) : (
          <span className="acct-ledger-expand-spacer" />
        )}
        <button
          type="button"
          onClick={onSelect}
          className="acct-ledger-account-select"
        >
          <span className="acct-ledger-account-name">{label}</span>
          <span className="acct-ledger-account-meta">
            <span className="acct-ledger-account-code">{code || '—'}</span>
            {balance && (
              <span className={`acct-ledger-account-balance ${balance.type === 'debit' ? 'acct-debit' : 'acct-credit'}`}>
                {formatRial(balance.amount)} · {balance.side}
              </span>
            )}
          </span>
        </button>
      </div>
    </div>
  )
}

export default function LedgerExplorer({
  accountGroups = [],
  subsidiaries = [],
  details = [],
  ledgerGeneralRows = [],
  drillSubsidiaryRows = [],
  drillDetailedRows = [],
  drillGeneral,
  drillSubsidiary,
  drillDetailed,
  breadcrumb = '',
  detailHint = '',
  treeSearch = '',
  onTreeSearchChange,
  loadingGeneral = false,
  loadingSubsidiary = false,
  loadingDetailed = false,
  onSelectGeneral,
  onSelectSubsidiary,
  onSelectDetailed,
  ledgerPanel,
  sidePanel,
  canCreate,
  onQuickDoc,
  onManageAccount,
}) {
  const compact = useIsCompactTablet()
  const isPhone = useIsPhone()
  const [treeOpen, setTreeOpen] = useState(!compact)
  const [treeVisible, setTreeVisible] = useState(true)
  const [isFullscreen, setIsFullscreen] = useState(false)
  const [expandedGenerals, setExpandedGenerals] = useState(() => new Set())
  const [expandedSubs, setExpandedSubs] = useState(() => new Set())

  useEffect(() => {
    if (!isFullscreen) return undefined
    const previousOverflow = document.body.style.overflow
    document.body.style.overflow = 'hidden'
    const closeOnEscape = (event) => {
      if (event.key === 'Escape') setIsFullscreen(false)
    }
    window.addEventListener('keydown', closeOnEscape)
    return () => {
      document.body.style.overflow = previousOverflow
      window.removeEventListener('keydown', closeOnEscape)
    }
  }, [isFullscreen])

  const generalBalanceMap = useMemo(() => {
    const map = new Map()
    for (const row of ledgerGeneralRows) {
      map.set(row.account_id, row)
    }
    return map
  }, [ledgerGeneralRows])

  const q = treeSearch.trim().toLowerCase()

  const filteredGroups = useMemo(() => {
    if (!q) return accountGroups
    return accountGroups
      .map((group) => ({
        ...group,
        accounts: (group.accounts || []).filter((acc) => {
          const text = `${acc.code} ${acc.name}`.toLowerCase()
          if (text.includes(q)) return true
          const subs = subsidiaries.filter((s) => s.account_id === acc.id)
          return subs.some((sub) => {
            if (`${sub.full_code || sub.code} ${sub.name}`.toLowerCase().includes(q)) return true
            return details
              .filter((detail) => detail.subsidiary_id === sub.id)
              .some((detail) => `${detail.full_code || detail.code} ${detail.name}`.toLowerCase().includes(q))
          })
        }),
      }))
      .filter((g) => g.accounts?.length)
  }, [accountGroups, subsidiaries, details, q])

  const toggleGeneral = (id) => {
    setExpandedGenerals((prev) => {
      const next = new Set(prev)
      if (next.has(id)) next.delete(id)
      else next.add(id)
      return next
    })
  }

  const toggleSub = (id) => {
    setExpandedSubs((prev) => {
      const next = new Set(prev)
      if (next.has(id)) next.delete(id)
      else next.add(id)
      return next
    })
  }

  const handleGeneral = (acc) => {
    const row = generalBalanceMap.get(acc.id) || {
      account_id: acc.id,
      account_code: acc.code,
      account_name: acc.name,
    }
    setExpandedGenerals((prev) => new Set(prev).add(acc.id))
    onSelectGeneral?.(row)
    if (compact) setTreeOpen(false)
  }

  const handleSubsidiary = (sub) => {
    const row = drillSubsidiaryRows.find((r) => r.subsidiary_id === sub.id) || {
      subsidiary_id: sub.id,
      account_id: sub.account_id,
      account_code: sub.full_code,
      account_name: sub.name,
    }
    setExpandedSubs((prev) => new Set(prev).add(sub.id))
    onSelectSubsidiary?.(row)
    if (compact) setTreeOpen(false)
  }

  const handleDetailed = (det) => {
    const row = drillDetailedRows.find((r) => r.detailed_id === det.id) || {
      detailed_id: det.id,
      subsidiary_id: det.subsidiary_id,
      account_id: det.account_id,
      account_code: det.full_code,
      account_name: det.name,
    }
    onSelectDetailed?.(row)
    if (compact) setTreeOpen(false)
  }

  const treePanel = (
      <div className="acct-glass-panel" style={{ display: 'flex', flexDirection: 'column', height: '100%', overflow: 'hidden', padding: 0, zIndex: 101, background: 'var(--acct-glass-bg-strong)' }}>
      <div style={{ padding: 16, borderBottom: '1px solid var(--acct-glass-border)' }}>
        <h3 style={{ margin: '0 0 12px 0', fontSize: 16, fontWeight: 700 }}>
          حساب‌ها
        </h3>
        <input
          className="acct-input"
          value={treeSearch}
          onChange={(e) => onTreeSearchChange?.(e.target.value)}
          placeholder="جستجوی کد یا عنوان حساب..."
          style={{ width: '100%' }}
          tabIndex={0}
        />
      </div>
      <div style={{ 
        flex: 1, 
        overflowY: 'auto',
        padding: '8px'
      }}>
        {loadingGeneral && !filteredGroups.length ? (
          <div style={{ 
            textAlign: 'center', 
            padding: '2rem',
            color: '#6B7280'
          }}>
            <Icon name="hourglass" size={24} />
            <p style={{ marginTop: '8px', fontSize: '13px' }}>در حال بارگذاری...</p>
          </div>
        ) : !filteredGroups.length ? (
          <EmptyState text="حسابی یافت نشد. واژه‌ی دیگری جستجو کنید." />
        ) : (
          filteredGroups.map((group) => (
            <section key={group.class || group.class_label} className="acct-ledger-account-group">
              <p className="acct-ledger-account-group-title">
                {group.class_label}
              </p>
              {(group.accounts || []).map((acc) => {
                const balRow = generalBalanceMap.get(acc.id)
                const isActive = drillGeneral?.account_id === acc.id && !drillSubsidiary && !drillDetailed
                const expanded = Boolean(q) || expandedGenerals.has(acc.id) || drillGeneral?.account_id === acc.id
                const accSubs = subsidiaries.filter((s) => s.account_id === acc.id)
                return (
                  <div key={acc.id}>
                    <TreeNode
                      label={acc.name}
                      code={acc.code}
                      balance={balanceLabel(balRow)}
                      depth={0}
                      active={isActive}
                      expanded={expanded}
                      hasChildren={accSubs.length > 0}
                      onToggle={() => toggleGeneral(acc.id)}
                      onSelect={() => handleGeneral(acc)}
                    />
                    {expanded && accSubs.map((sub) => {
                      const subBal = drillSubsidiaryRows.find((r) => r.subsidiary_id === sub.id)
                      const subActive = drillSubsidiary?.subsidiary_id === sub.id && !drillDetailed
                      const subExpanded = Boolean(q) || expandedSubs.has(sub.id) || drillSubsidiary?.subsidiary_id === sub.id
                      const subDetails = details.filter((d) => d.subsidiary_id === sub.id)
                      return (
                        <div key={sub.id}>
                          <TreeNode
                            label={sub.name}
                            code={sub.full_code || sub.code}
                            balance={balanceLabel(subBal)}
                            depth={1}
                            active={subActive}
                            expanded={subExpanded}
                            hasChildren={subDetails.length > 0}
                            onToggle={() => toggleSub(sub.id)}
                            onSelect={() => handleSubsidiary(sub)}
                          />
                          {subExpanded && subDetails.map((det) => {
                            const detBal = drillDetailedRows.find((r) => r.detailed_id === det.id)
                            const detActive = drillDetailed?.detailed_id === det.id
                            return (
                              <TreeNode
                                key={det.id}
                                label={det.name}
                                code={det.full_code || det.code}
                                balance={balanceLabel(detBal)}
                                depth={2}
                                active={detActive}
                                expanded={false}
                                hasChildren={false}
                                onToggle={() => {}}
                                onSelect={() => handleDetailed(det)}
                              />
                            )
                          })}
                          {subExpanded && loadingDetailed && !subDetails.length && (
                            <p style={{ 
                              padding: '8px 16px 8px 64px',
                              color: '#9CA3AF',
                              fontSize: '12px'
                            }}>
                              در حال بارگذاری تفصیلی...
                            </p>
                          )}
                        </div>
                      )
                    })}
                    {expanded && loadingSubsidiary && !accSubs.length && (
                      <p style={{ 
                        padding: '8px 16px 8px 48px',
                        color: '#9CA3AF',
                        fontSize: '12px'
                      }}>
                        در حال بارگذاری معین...
                      </p>
                    )}
                  </div>
                )
              })}
            </section>
          ))
        )}
      </div>
    </div>
  )

  const showDesktopTree = !compact && treeVisible
  const gridColumns = !showDesktopTree
    ? (sidePanel && !isFullscreen ? 'minmax(0, 1fr) minmax(280px, 360px)' : 'minmax(0, 1fr)')
    : (sidePanel
      ? 'minmax(240px, 280px) minmax(0, 1fr) minmax(280px, 360px)'
      : 'minmax(240px, 280px) minmax(0, 1fr)')

  return (
    <div
      className={`acct-ledger-workspace${isFullscreen ? ' is-fullscreen' : ''}`}
      style={{
        display: 'grid',
        gridTemplateColumns: gridColumns,
        gap: 'var(--acct-space-md)',
        minHeight: isFullscreen ? 0 : 560,
      }}
    >
      {compact && !isFullscreen && (
        <div className="acct-ledger-mobile-bar" style={{
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          gridColumn: '1 / -1'
        }}>
          <Button type="button" variant="ghost" onClick={() => setTreeOpen((v) => !v)}>
            <Icon name="menu" size={16} />
            {treeOpen ? 'بستن حساب‌ها' : 'انتخاب حساب'}
          </Button>
          {breadcrumb && <span className="acct-ledger-crumb">{breadcrumb}</span>}
        </div>
      )}

      {(showDesktopTree || (compact && treeOpen && !isFullscreen)) && (
        <aside style={{
          ...(compact ? {
            position: 'fixed',
            top: '80px',
            right: 0,
            bottom: 0,
            width: '320px',
            zIndex: 100,
            boxShadow: 'var(--shadow-lg)',
          } : {
            height: isFullscreen ? 'calc(100dvh - 28px)' : 'calc(100vh - 220px)',
          })
        }}>
          {treePanel}
        </aside>
      )}

      <section className="acct-glass-panel" style={{ 
        padding: isPhone ? 12 : 16,
        display: 'flex',
        flexDirection: 'column',
        minWidth: 0,
        overflow: 'hidden',
      }}>
        <header className="acct-ledger-focus-head">
          <div style={{ 
            display: 'flex',
            justifyContent: 'space-between',
            alignItems: 'flex-start',
            marginBottom: '8px'
          }}>
            <div>
              <h2 style={{ 
                margin: 0,
                fontSize: '20px',
                fontWeight: '700',
              }}>
                {TERMS.ledger}
              </h2>
              {detailHint ? (
                <p style={{ 
                  margin: '4px 0 0',
                  fontSize: '14px',
                  color: 'var(--text-secondary)'
                }}>
                  {detailHint}
                </p>
              ) : (
                <p style={{ 
                  margin: '4px 0 0',
                  fontSize: '13px',
                  color: 'var(--text-secondary)'
                }}>
                  از بخش حساب‌ها یک حساب انتخاب کنید.
                </p>
              )}
              {breadcrumb && !compact && (
                <p style={{ 
                  margin: '8px 0 0',
                  fontSize: '12px',
                  fontFamily: 'var(--font-mono)',
                  color: 'var(--text-secondary)'
                }}>
                  {breadcrumb}
                </p>
              )}
            </div>
            <div className="acct-ledger-actions">
              {!compact && (
                <button
                  type="button"
                  onClick={() => setTreeVisible((visible) => !visible)}
                  className="acct-btn acct-btn--secondary acct-btn--sm"
                  title={treeVisible ? 'مخفی کردن حساب‌ها' : 'نمایش حساب‌ها'}
                >
                  <Icon name="menu" size={14} />
                  <span>{treeVisible ? 'بستن حساب‌ها' : 'حساب‌ها'}</span>
                </button>
              )}
              {canCreate && (
                <>
                <button 
                  type="button" 
                  onClick={onQuickDoc}
                  className="acct-btn acct-btn--primary acct-btn--sm"
                  tabIndex={0}
                >
                  <Icon name="plus" size={14} />
                  <span>سند سریع</span>
                </button>
                <button 
                  type="button" 
                  onClick={onManageAccount}
                  className="acct-btn acct-btn--secondary acct-btn--sm"
                  tabIndex={0}
                >
                  <Icon name="gear" size={14} />
                  <span>مدیریت</span>
                </button>
                </>
              )}
              <button 
                type="button" 
                onClick={() => setIsFullscreen((fullscreen) => !fullscreen)}
                className="acct-btn acct-btn--primary acct-btn--sm"
                title={isFullscreen ? 'بازگشت به نمای عادی (Esc)' : 'نمایش تمام‌صفحه'}
              >
                <Icon name={isFullscreen ? 'minus' : 'plus'} size={14} />
                <span>{isFullscreen ? 'نمای عادی' : 'تمام‌صفحه'}</span>
              </button>
            </div>
          </div>
        </header>
        <div className="acct-ledger-results">
          {ledgerPanel || (
            <EmptyState text="حسابی انتخاب نشده — از درخت یک حساب را برگزینید." />
          )}
        </div>
      </section>

      {sidePanel && !isFullscreen && (
        <aside className="acct-glass-panel" style={{ 
          padding: '16px',
          overflowY: 'auto',
          background: 'var(--acct-glass-bg-strong)'
        }}>
          {sidePanel}
        </aside>
      )}
    </div>
  )
}
