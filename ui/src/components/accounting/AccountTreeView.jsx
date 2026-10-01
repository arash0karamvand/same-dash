import { useState } from 'react'
import { Badge } from '../ui'
import Icon from '../icons/Icon'
import AccountRecords from './AccountRecords'
import { formatRial } from '../../utils/format'

function nodeKey(level, id) {
  return `${level}:${id}`
}

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
  childLabel,
  onToggle,
  onEdit,
  onCreateChild,
  onDelete,
  postableAccounts,
  editLevel,
  children,
}) {
  const amount = nodeAmount(node)
  const depthClass = level === 'general' ? 'acct-hmap-node--l1' : level === 'subsidiary' ? 'acct-hmap-node--l2' : 'acct-hmap-node--l3'
  const isDebit = amount && amount.balance > 0.01
  const isCredit = amount && amount.balance < -0.01
  const emptyText = level === 'general'
    ? 'معینی برای این حساب ثبت نشده.'
    : 'تفصیلی برای این معین ثبت نشده.'
  const [recordsOpen, setRecordsOpen] = useState(false)
  const isLeaf = level === 'detailed'
  const opened = isLeaf ? recordsOpen : expanded

  const openHere = () => {
    if (isLeaf) setRecordsOpen((open) => !open)
    onToggle?.()
  }
  const toggleRecords = (event) => {
    event.stopPropagation()
    setRecordsOpen((open) => !open)
  }

  return (
    <div className={`acct-hmap-branch${opened || recordsOpen ? ' is-open' : ''}`}>
      <div
        className={`acct-hmap-node ${depthClass}${selected ? ' is-selected' : ''}`}
        role="treeitem"
        aria-expanded={opened}
        aria-selected={selected}
        tabIndex={0}
        onClick={openHere}
        onKeyDown={(event) => {
          if (event.key === 'Enter' || event.key === ' ') {
            event.preventDefault()
            openHere()
          }
          if (event.key === 'ArrowLeft' && !expanded) {
            event.preventDefault()
            openHere()
          }
          if (event.key === 'ArrowRight' && expanded) {
            event.preventDefault()
            openHere()
          }
        }}
      >
        <span className="acct-hmap-lead">
          <Icon name={opened ? 'chevron-up' : 'chevron-down'} size={14} />
          <span className="acct-hmap-code">{node.full_code || node.code || node.sort_order || '—'}</span>
          <span className="acct-hmap-name">{node.name}</span>
        </span>
        <span className="acct-hmap-tools">
          {childLabel ? <span className="acct-hmap-count">{childLabel}</span> : null}
          <button
            type="button"
            className={`acct-hmap-records-toggle${recordsOpen ? ' is-open' : ''}`}
            aria-expanded={recordsOpen}
            onClick={toggleRecords}
          >
            <Icon name={recordsOpen ? 'chevron-up' : 'chevron-down'} size={12} />
            رکوردها
          </button>
          {amount && (
            <span className={`acct-hmap-balance ${isDebit ? 'acct-debit' : isCredit ? 'acct-credit' : ''}`}>
              {formatRial(Math.abs(amount.balance))}
            </span>
          )}
          {node.is_active === false && <Badge color="var(--muted)">غیرفعال</Badge>}
          <span className="acct-hmap-actions">
            {level !== 'detailed' ? (
              <button
                type="button"
                className="acct-btn acct-btn--sm"
                aria-label={level === 'general' ? 'معین جدید' : 'تفصیلی جدید'}
                onClick={(event) => {
                  event.stopPropagation()
                  onCreateChild?.(node, editLevel)
                }}
              >
                <Icon name="plus" size={14} />
                <span className="acct-hmap-action-label">{level === 'general' ? 'معین' : 'تفصیلی'}</span>
              </button>
            ) : null}
            <button
              type="button"
              className="acct-btn acct-btn--sm"
              aria-label="ویرایش حساب"
              onClick={(event) => {
                event.stopPropagation()
                onEdit?.(node, editLevel)
              }}
            >
              <Icon name="pencil" size={14} />
              <span className="acct-hmap-action-label">ویرایش</span>
            </button>
            <button
              type="button"
              className="acct-btn acct-btn--sm"
              aria-label="حذف حساب"
              onClick={(event) => {
                event.stopPropagation()
                onDelete?.(node, editLevel)
              }}
            >
              <Icon name="trash" size={14} />
              <span className="acct-hmap-action-label">حذف</span>
            </button>
          </span>
        </span>
      </div>
      {recordsOpen ? (
        <div className="acct-hmap-children">
          <AccountRecords level={level} accountId={node.id} postableAccounts={postableAccounts} />
        </div>
      ) : null}
      {!isLeaf && expanded ? (
        <div className="acct-hmap-children">
          {hasChildren ? children : <p className="acct-hmap-empty">{emptyText}</p>}
        </div>
      ) : null}
    </div>
  )
}

export default function AccountTreeView({
  accountGroups = [],
  onEdit,
  onCreateChild,
  onDelete,
  postableAccounts = [],
  onSelect,
  selectedKey = '',
  expandAll = false,
}) {
  const [openNodes, setOpenNodes] = useState(() => new Set())

  const toggle = (key, payload) => {
    setOpenNodes((prev) => {
      const next = new Set(prev)
      if (next.has(key)) next.delete(key)
      else next.add(key)
      return next
    })
    onSelect?.(payload)
  }

  const isOpen = (key) => openNodes.has(key)

  if (!accountGroups || accountGroups.length === 0) {
    return (
      <p style={{ textAlign: 'center', padding: '2rem', color: 'var(--text-secondary)' }}>
        حسابی تعریف نشده است
      </p>
    )
  }

  return (
    <div className="acct-hmap min-w-0 max-w-full overflow-x-auto" role="tree" aria-label="نقشه سلسله‌مراتبی حساب‌ها">
      {accountGroups.map((group) => (
        <section key={group.class_label} className="acct-hmap-group">
          <h4 className="acct-hmap-group-title">{group.class_label}</h4>
          {(group.accounts || []).map((account) => {
            const accountKey = nodeKey('general', account.id)
            const subsidiaries = account.subsidiaries || []
            const accountOpen = expandAll || isOpen(accountKey)
            return (
              <HierarchyNode
                key={accountKey}
                node={account}
                level="general"
                selected={selectedKey === accountKey}
                expanded={accountOpen}
                hasChildren={subsidiaries.length > 0}
                childLabel={subsidiaries.length ? `${subsidiaries.length.toLocaleString('fa-IR')} معین` : 'بدون معین'}
                onToggle={() => toggle(accountKey, { account, level: 'general' })}
                onEdit={onEdit}
                onCreateChild={onCreateChild}
                onDelete={onDelete}
                postableAccounts={postableAccounts}
                editLevel="general"
              >
                {subsidiaries.map((subsidiary) => {
                  const subsidiaryKey = nodeKey('subsidiary', subsidiary.id)
                  const details = subsidiary.details || []
                  const subsidiaryOpen = expandAll || isOpen(subsidiaryKey)
                  return (
                    <HierarchyNode
                      key={subsidiaryKey}
                      node={subsidiary}
                      level="subsidiary"
                      selected={selectedKey === subsidiaryKey}
                      expanded={subsidiaryOpen}
                      hasChildren={details.length > 0}
                      childLabel={details.length ? `${details.length.toLocaleString('fa-IR')} تفصیلی` : 'بدون تفصیلی'}
                      onToggle={() => toggle(subsidiaryKey, { account: subsidiary, level: 'subsidiary' })}
                      onEdit={onEdit}
                      onCreateChild={onCreateChild}
                      onDelete={onDelete}
                      postableAccounts={postableAccounts}
                      editLevel="subsidiary"
                    >
                      {details.map((detail) => {
                        const detailKey = nodeKey('detailed', detail.id)
                        return (
                          <HierarchyNode
                            key={detailKey}
                            node={detail}
                            level="detailed"
                            selected={selectedKey === detailKey}
                            expanded={isOpen(detailKey)}
                            hasChildren={false}
                            onToggle={() => toggle(detailKey, { account: detail, level: 'detailed' })}
                            onEdit={onEdit}
                            onCreateChild={onCreateChild}
                            onDelete={onDelete}
                            postableAccounts={postableAccounts}
                            editLevel="detailed"
                          />
                        )
                      })}
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
