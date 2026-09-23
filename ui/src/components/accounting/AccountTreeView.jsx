import { useState } from 'react'
import { Badge } from '../ui'
import Icon from '../icons/Icon'
import { formatRial } from '../../utils/format'

function nodeAmount(node) {
  const debit = Number(node?.balance_debit ?? node?.total_debit ?? 0)
  const credit = Number(node?.balance_credit ?? node?.total_credit ?? 0)
  const raw = node?.balance
  const balance = raw == null ? debit - credit : Number(raw)
  if (!debit && !credit && !balance) return null
  return { debit, credit, balance }
}

function HierarchyNode({
  node,
  level,
  selected,
  expanded,
  hasChildren,
  onToggle,
  onSelect,
  onEdit,
  editLevel,
  children,
}) {
  const amount = nodeAmount(node)
  const depthClass = level === 'general' ? 'acct-hmap-node--l1' : level === 'subsidiary' ? 'acct-hmap-node--l2' : 'acct-hmap-node--l3'
  const isDebit = amount && amount.balance > 0.01
  const isCredit = amount && amount.balance < -0.01

  return (
    <div>
      <div
        className={`acct-hmap-node ${depthClass}${selected ? ' is-selected' : ''}`}
        role="treeitem"
        aria-expanded={hasChildren ? expanded : undefined}
        aria-selected={selected}
        tabIndex={0}
        onClick={() => {
          onSelect?.()
          if (hasChildren) onToggle?.()
        }}
        onKeyDown={(event) => {
          if (event.key === 'Enter' || event.key === ' ') {
            event.preventDefault()
            onSelect?.()
            if (hasChildren) onToggle?.()
          }
          if (event.key === 'ArrowLeft' && hasChildren && !expanded) {
            event.preventDefault()
            onToggle?.()
          }
          if (event.key === 'ArrowRight' && hasChildren && expanded) {
            event.preventDefault()
            onToggle?.()
          }
        }}
      >
        {hasChildren ? (
          <Icon name={expanded ? 'chevron-down' : 'chevron-up'} size={14} />
        ) : (
          <span style={{ width: 14 }} />
        )}
        <span className="acct-hmap-code">{node.full_code || node.code || node.sort_order || '—'}</span>
        <span className="acct-hmap-name">{node.name}</span>
        {amount && (
          <span className={`acct-hmap-balance ${isDebit ? 'acct-debit' : isCredit ? 'acct-credit' : ''}`}>
            {formatRial(Math.abs(amount.balance))}
          </span>
        )}
        {node.is_active === false && <Badge color="var(--muted)">غیرفعال</Badge>}
        <button
          type="button"
          className="acct-btn acct-btn--sm"
          tabIndex={0}
          aria-label="ویرایش حساب"
          onClick={(event) => {
            event.stopPropagation()
            onEdit?.(node, editLevel)
          }}
        >
          <Icon name="pencil" size={14} />
        </button>
      </div>
      {expanded && children ? <div className="acct-hmap-children">{children}</div> : null}
    </div>
  )
}

export default function AccountTreeView({ accountGroups = [], onEdit, onSelect, selectedId }) {
  const [expandedAccounts, setExpandedAccounts] = useState(new Set())
  const [expandedSubsidiaries, setExpandedSubsidiaries] = useState(new Set())

  const toggleAccount = (accountId) => {
    setExpandedAccounts((prev) => {
      const next = new Set(prev)
      if (next.has(accountId)) next.delete(accountId)
      else next.add(accountId)
      return next
    })
  }

  const toggleSubsidiary = (subsidiaryId) => {
    setExpandedSubsidiaries((prev) => {
      const next = new Set(prev)
      if (next.has(subsidiaryId)) next.delete(subsidiaryId)
      else next.add(subsidiaryId)
      return next
    })
  }

  if (!accountGroups || accountGroups.length === 0) {
    return (
      <p style={{ textAlign: 'center', padding: '2rem', color: 'var(--text-secondary)' }}>
        حسابی تعریف نشده است
      </p>
    )
  }

  return (
    <div className="acct-hmap" role="tree" aria-label="نقشه سلسله‌مراتبی حساب‌ها">
      {accountGroups.map((group) => (
        <section key={group.class_label} className="acct-hmap-group">
          <h4 className="acct-hmap-group-title">{group.class_label}</h4>
          {(group.accounts || []).map((account) => {
            const isExpanded = expandedAccounts.has(account.id)
            const hasSubsidiaries = account.subsidiaries && account.subsidiaries.length > 0
            return (
              <HierarchyNode
                key={account.id}
                node={account}
                level="general"
                selected={selectedId === account.id}
                expanded={isExpanded}
                hasChildren={hasSubsidiaries}
                onToggle={() => toggleAccount(account.id)}
                onSelect={() => onSelect?.({ account, level: 'general' })}
                onEdit={onEdit}
                editLevel="general"
              >
                {hasSubsidiaries && account.subsidiaries.map((subsidiary) => {
                  const isSubExpanded = expandedSubsidiaries.has(subsidiary.id)
                  const hasDetails = subsidiary.details && subsidiary.details.length > 0
                  return (
                    <HierarchyNode
                      key={subsidiary.id}
                      node={subsidiary}
                      level="subsidiary"
                      selected={selectedId === subsidiary.id}
                      expanded={isSubExpanded}
                      hasChildren={hasDetails}
                      onToggle={() => toggleSubsidiary(subsidiary.id)}
                      onSelect={() => onSelect?.({ account: subsidiary, level: 'subsidiary' })}
                      onEdit={onEdit}
                      editLevel="subsidiary"
                    >
                      {hasDetails && subsidiary.details.map((detail) => (
                        <HierarchyNode
                          key={detail.id}
                          node={detail}
                          level="detailed"
                          selected={selectedId === detail.id}
                          expanded={false}
                          hasChildren={false}
                          onSelect={() => onSelect?.({ account: detail, level: 'detailed' })}
                          onEdit={onEdit}
                          editLevel="detailed"
                        />
                      ))}
                    </HierarchyNode>
                  )
                })}
              </HierarchyNode>
            )
          })}
        </section>
      ))}
    </div>
  )
}
