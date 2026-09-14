// کاوشگر دفتر کل — درخت حساب + پنل تراکنش (جایگزین ۴ پنل موازی)

import { useMemo, useState } from 'react'
import Icon from '../icons/Icon'
import { Button, EmptyState } from '../ui'
import { TERMS } from '../../config/accountingTerms'
import { formatNumber, formatRial } from '../../utils/format'
import { useMediaQuery } from '../../hooks/useMediaQuery'

function balanceLabel(row) {
  if (!row) return null
  const debit = Number(row.balance_debit) || 0
  const credit = Number(row.balance_credit) || 0
  if (!debit && !credit) return null
  if (debit >= credit) return { amount: debit - credit, side: TERMS.debit }
  return { amount: credit - debit, side: TERMS.credit }
}

function TreeNode({ label, code, balance, depth = 0, active, expanded, hasChildren, onToggle, onSelect }) {
  return (
    <div className={`acct-tree-node acct-tree-node--depth-${depth}${active ? ' is-active' : ''}`}>
      <div className="acct-tree-node-row">
        {hasChildren ? (
          <button type="button" className="acct-tree-toggle" onClick={onToggle} aria-label={expanded ? 'بستن' : 'باز کردن'}>
            <Icon name={expanded ? 'chevron-up' : 'chevron-down'} size={14} />
          </button>
        ) : (
          <span className="acct-tree-toggle acct-tree-toggle--spacer" />
        )}
        <button type="button" className="acct-tree-select" onClick={onSelect}>
          <span className="acct-tree-code">{code}</span>
          <span className="acct-tree-name">{label}</span>
          {balance && (
            <span className="acct-tree-balance">
              {formatRial(balance.amount)}
              <small>{balance.side}</small>
            </span>
          )}
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
  const compact = useMediaQuery('(max-width: 1024px)')
  const [treeOpen, setTreeOpen] = useState(!compact)
  const [expandedGenerals, setExpandedGenerals] = useState(() => new Set())
  const [expandedSubs, setExpandedSubs] = useState(() => new Set())

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
          return subs.some((s) => `${s.full_code} ${s.name}`.toLowerCase().includes(q))
        }),
      }))
      .filter((g) => g.accounts?.length)
  }, [accountGroups, subsidiaries, q])

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
    <div className="acct-ledger-tree">
      <div className="acct-ledger-tree-head">
        <h3>درخت حساب‌ها</h3>
        <input
          className="search-input"
          value={treeSearch}
          onChange={(e) => onTreeSearchChange?.(e.target.value)}
          placeholder="جستجوی کد یا عنوان…"
        />
      </div>
      <div className="acct-ledger-tree-body">
        {loadingGeneral && !filteredGroups.length ? (
          <div className="loading">در حال بارگذاری…</div>
        ) : !filteredGroups.length ? (
          <EmptyState text="حسابی یافت نشد." />
        ) : (
          filteredGroups.map((group) => (
            <section key={group.class} className="acct-tree-group">
              <p className="acct-tree-group-label">{group.class_label}</p>
              {(group.accounts || []).map((acc) => {
                const balRow = generalBalanceMap.get(acc.id)
                const isActive = drillGeneral?.account_id === acc.id && !drillSubsidiary && !drillDetailed
                const expanded = expandedGenerals.has(acc.id) || drillGeneral?.account_id === acc.id
                const accSubs = subsidiaries.filter((s) => s.account_id === acc.id)
                return (
                  <div key={acc.id} className="acct-tree-branch">
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
                      const subExpanded = expandedSubs.has(sub.id) || drillSubsidiary?.subsidiary_id === sub.id
                      const subDetails = details.filter((d) => d.subsidiary_id === sub.id)
                      return (
                        <div key={sub.id} className="acct-tree-branch">
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
                            <p className="muted small acct-tree-loading">در حال بارگذاری تفصیلی…</p>
                          )}
                        </div>
                      )
                    })}
                    {expanded && loadingSubsidiary && !accSubs.length && (
                      <p className="muted small acct-tree-loading">در حال بارگذاری معین…</p>
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

  return (
    <div className={`acct-ledger-explorer${sidePanel ? ' has-side-panel' : ''}`}>
      {compact && (
        <div className="acct-ledger-mobile-bar">
          <Button type="button" variant="ghost" onClick={() => setTreeOpen((v) => !v)}>
            {treeOpen ? 'بستن درخت' : 'انتخاب حساب'}
          </Button>
          {breadcrumb && <span className="acct-ledger-crumb muted">{breadcrumb}</span>}
        </div>
      )}

      <div className="acct-ledger-layout">
        {(!compact || treeOpen) && (
          <aside className={`acct-ledger-tree-panel${compact ? ' acct-ledger-tree-panel--sheet' : ''}`}>
            {treePanel}
          </aside>
        )}

        <section className="acct-ledger-detail-panel liquid-glass liquid-glass--panel">
          <header className="acct-ledger-detail-head">
            <div>
              <h2>{TERMS.ledger}</h2>
              {detailHint ? <p className="acct-ledger-detail-sub">{detailHint}</p> : (
                <p className="muted">از درخت سمت راست یک حساب انتخاب کنید.</p>
              )}
              {breadcrumb && !compact && <p className="acct-ledger-crumb muted">{breadcrumb}</p>}
            </div>
            <div className="acct-ledger-detail-actions">
              {canCreate && (
                <>
                  <Button type="button" size="sm" onClick={onQuickDoc}>+ سند سریع</Button>
                  <Button type="button" size="sm" variant="ghost" onClick={onManageAccount}>مدیریت حساب</Button>
                </>
              )}
            </div>
          </header>
          <div className="acct-ledger-detail-body">
            {ledgerPanel || <EmptyState text="حسابی انتخاب نشده — از درخت یک حساب را برگزینید." />}
          </div>
        </section>

        {sidePanel && (
          <aside className="acct-ledger-side-panel">{sidePanel}</aside>
        )}
      </div>
    </div>
  )
}
