// صفحه حسابداری — مطابق ساختار اکسل (تراز / دفتر کل / ثبت سند / ایجاد حساب)

import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { accountingApi } from '../api/client'
import AccountDetailPanel from '../components/AccountDetailPanel'
import LedgerSidePanelContent from '../components/LedgerSidePanelContent'
import {
  DEFAULT_DRILL_PANEL_LAYOUT,
  LedgerDrillCard,
  LedgerDrillStage,
  LedgerSidePanel,
  LedgerStageDivider,
  LedgerTrialColumn,
  LedgerWorkspace,
  rowSelectionLabel,
} from '../components/LedgerDrillPanels'
import MoneyInput from '../components/MoneyInput'
import TrialBalanceFilterPanel, {
  applyTrialBalanceFilter,
  EMPTY_TRIAL_BALANCE_FILTER,
  sumTrialBalanceTotals,
  trialBalanceFilterActive,
} from '../components/TrialBalanceFilterPanel'
import { TRIAL_BALANCE_FILTERS, LEDGER_DRILL_FILTER } from '../config/recordFilterSections'
import Select from '../components/Select'
import PersianDateInput from '../components/PersianDateInput'
import { Button, Card, EmptyState, Field, FilterBar, Modal } from '../components/ui'
import {
  ACCOUNTING_TABS,
  ACCOUNTING_MENU,
  ACCOUNT_CLASS_OPTIONS,
  TERMS,
  TRIAL_BALANCE_LEVEL,
} from '../config/accountingTerms'
import { PAGE_GUIDE_DEFAULTS } from '../config/pageGuideDefaults'
import { useAuth } from '../context/AuthContext'
import { useRegisterPageGuide } from '../context/PageGuideContext'
import { usePersistedState } from '../hooks/usePersistedState'
import {
  buildAccountEditForm,
  clampHeight,
  clampWidth,
  computeDrillColumnWidths,
  DEFAULT_DRILL_ROW_HEIGHT,
  DEFAULT_DRILL_WEIGHTS,
  DRILL_HEIGHT_LIMITS,
  migrateDrillWidthsToWeights,
  resizeDrillPanelPair,
  drillRowToAccountRecord,
  drillSelectionToDocLine,
  EMPTY_CHART_CHILD,
  saveAccountChild,
  saveAccountEdit,
} from '../utils/accountHelpers'
import { formatDate, formatNumber, formatRial } from '../utils/format'
import { hasPermission } from '../utils/permissions'

const TRIAL_TABS = ['trial-balance', 'subsidiary-trial', 'detailed-trial']

const EMPTY_DOC_LINE = {
  detailed_id: '',
  subsidiary_id: '',
  account_id: '',
  debit: '',
  credit: '',
}

function buildAccountOptions(groups) {
  const opts = []
  for (const group of groups || []) {
    for (const acc of group.accounts || []) {
      opts.push({
        value: String(acc.id),
        label: `${acc.code || acc.sort_order} — ${acc.name}`,
      })
    }
  }
  return opts
}

function chartSearchText(parts) {
  return parts.filter(Boolean).join(' ').toLowerCase()
}

function matchesChartSearch(parts, query) {
  if (!query) return true
  return chartSearchText(parts).includes(query)
}

function chartRowSelected(selected, level, id) {
  return selected?.level === level && selected?.id === id
}

function detailedOptionLabel(d) {
  return `${d.full_code} — ${d.name}`
}

function renderAmount(value) {
  return value ? formatRial(value) : '—'
}

function TrialBalanceAmountGrid({ row }) {
  return (
    <div className="accounting-amount-sections">
      <div className="accounting-amount-section">
        <span className="accounting-amount-section-label">{TERMS.openingBalance}</span>
        <div className="m-card-grid">
          <div><span className="muted">{TERMS.debit}</span><strong>{renderAmount(row.opening_debit)}</strong></div>
          <div><span className="muted">{TERMS.credit}</span><strong>{renderAmount(row.opening_credit)}</strong></div>
        </div>
      </div>
      <div className="accounting-amount-section">
        <span className="accounting-amount-section-label">{TERMS.turnover}</span>
        <div className="m-card-grid">
          <div><span className="muted">{TERMS.debit}</span><strong>{renderAmount(row.turnover_debit)}</strong></div>
          <div><span className="muted">{TERMS.credit}</span><strong>{renderAmount(row.turnover_credit)}</strong></div>
        </div>
      </div>
      <div className="accounting-amount-section">
        <span className="accounting-amount-section-label">{TERMS.balance}</span>
        <div className="m-card-grid">
          <div><span className="muted">{TERMS.debit}</span><strong>{renderAmount(row.balance_debit)}</strong></div>
          <div><span className="muted">{TERMS.credit}</span><strong>{renderAmount(row.balance_credit)}</strong></div>
        </div>
      </div>
    </div>
  )
}

function TrialBalanceTable({ rows, totals, loading, onRowClick, selectedKey, getRowKey }) {
  if (loading) return <div className="loading">در حال بارگذاری…</div>
  if (!rows.length) return <EmptyState text="ردیفی یافت نشد." />

  const balanced = totals.turnover_balanced !== false

  return (
    <>
      <div className="table-wrap accounting-ledger-wrap accounting-table-desktop">
        <table className="table accounting-ledger-table">
          <thead>
            <tr>
              <th rowSpan={2}>{TERMS.accountCode}</th>
              <th rowSpan={2}>{TERMS.accountTitle}</th>
              <th colSpan={2} className="ledger-group-head">{TERMS.openingBalance}</th>
              <th colSpan={2} className="ledger-group-head">{TERMS.turnover}</th>
              <th colSpan={2} className="ledger-group-head">{TERMS.balance}</th>
            </tr>
            <tr>
              <th>{TERMS.debit}</th>
              <th>{TERMS.credit}</th>
              <th>{TERMS.debit}</th>
              <th>{TERMS.credit}</th>
              <th>{TERMS.debit}</th>
              <th>{TERMS.credit}</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((row) => {
              const key = getRowKey ? getRowKey(row) : `${row.account_code}-${row.account_name}`
              const selected = selectedKey != null && selectedKey === key
              return (
                <tr
                  key={key}
                  className={onRowClick ? `entry-row-clickable${selected ? ' drill-row-selected' : ''}` : undefined}
                  onClick={() => onRowClick?.(row)}
                >
                  <td><strong>{row.account_code}</strong></td>
                  <td className="text-cell">{row.account_name}</td>
                  <td>{renderAmount(row.opening_debit)}</td>
                  <td>{renderAmount(row.opening_credit)}</td>
                  <td>{renderAmount(row.turnover_debit)}</td>
                  <td>{renderAmount(row.turnover_credit)}</td>
                  <td>{renderAmount(row.balance_debit)}</td>
                  <td>{renderAmount(row.balance_credit)}</td>
                </tr>
              )
            })}
          </tbody>
          {totals && Object.keys(totals).length > 0 && (
            <tfoot>
              <tr className="ledger-totals-row">
                <td colSpan={2}><strong>{TERMS.total}</strong></td>
                <td>{renderAmount(totals.opening_debit)}</td>
                <td>{renderAmount(totals.opening_credit)}</td>
                <td>{renderAmount(totals.turnover_debit)}</td>
                <td>{renderAmount(totals.turnover_credit)}</td>
                <td>{renderAmount(totals.balance_debit)}</td>
                <td>{renderAmount(totals.balance_credit)}</td>
              </tr>
            </tfoot>
          )}
        </table>
      </div>

      <div className="accounting-cards-mobile">
        {rows.map((row) => {
          const key = getRowKey ? getRowKey(row) : `${row.account_code}-${row.account_name}`
          const selected = selectedKey != null && selectedKey === key
          return (
            <div
              key={key}
              className={`m-card accounting-trial-card${onRowClick ? ' entry-row-clickable' : ''}${selected ? ' drill-row-selected' : ''}`}
              onClick={() => onRowClick?.(row)}
              onKeyDown={onRowClick ? (e) => { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); onRowClick(row) } } : undefined}
              role={onRowClick ? 'button' : undefined}
              tabIndex={onRowClick ? 0 : undefined}
            >
              <div className="m-card-head accounting-entry-card-head">
                <div>
                  <strong>{row.account_code}</strong>
                  <p className="accounting-entry-desc">{row.account_name}</p>
                </div>
              </div>
              <TrialBalanceAmountGrid row={row} />
            </div>
          )
        })}
        {totals && Object.keys(totals).length > 0 && (
          <div className="m-card accounting-trial-card accounting-totals-card">
            <div className="m-card-head">
              <strong>{TERMS.total}</strong>
            </div>
            <TrialBalanceAmountGrid row={totals} />
          </div>
        )}
      </div>

      {totals?.turnover_balanced != null && (
        <p className={`accounting-footer-summary ${balanced ? 'doc-balanced' : 'doc-unbalanced'}`}>
          گردش دوره: {TERMS.debit} {formatRial(totals.raw_turnover_debit || totals.turnover_debit)}
          {' / '}
          {TERMS.credit} {formatRial(totals.raw_turnover_credit || totals.turnover_credit)}
          {balanced ? ` — ✓ ${TERMS.balanced}` : ` — ⚠ ${TERMS.unbalanced}`}
        </p>
      )}
    </>
  )
}

function parseLedgerMoney(value) {
  if (value === '' || value == null) return null
  const n = Number(String(value).replace(/,/g, ''))
  return Number.isFinite(n) ? n : null
}

function ledgerLineMatchesFilters(line, col) {
  const dateText = line.entry_date ? formatDate(line.entry_date) : ''
  if (col.date && !dateText.includes(col.date) && !(line.entry_date || '').includes(col.date)) return false

  const docNum = line.document_number != null ? String(line.document_number) : ''
  if (col.document_number && !docNum.includes(col.document_number)) return false

  const attach = (line.attach_code || '').toLowerCase()
  if (col.attach_code && !attach.includes(col.attach_code.trim().toLowerCase())) return false

  const desc = (line.description || '').toLowerCase()
  if (col.description && !desc.includes(col.description.trim().toLowerCase())) return false

  const debit = Number(line.debit) || 0
  const credit = Number(line.credit) || 0
  const balance = Number(line.balance) || 0

  const debitMin = parseLedgerMoney(col.debit_min)
  const debitMax = parseLedgerMoney(col.debit_max)
  if (debitMin != null && debit < debitMin) return false
  if (debitMax != null && debit > debitMax) return false

  const creditMin = parseLedgerMoney(col.credit_min)
  const creditMax = parseLedgerMoney(col.credit_max)
  if (creditMin != null && credit < creditMin) return false
  if (creditMax != null && credit > creditMax) return false

  const balanceMin = parseLedgerMoney(col.balance_min)
  const balanceMax = parseLedgerMoney(col.balance_max)
  if (balanceMin != null && balance < balanceMin) return false
  if (balanceMax != null && balance > balanceMax) return false

  return true
}

const EMPTY_LEDGER_COL_FILTERS = {
  date: '',
  document_number: '',
  attach_code: '',
  description: '',
  debit_min: '',
  debit_max: '',
  credit_min: '',
  credit_max: '',
  balance_min: '',
  balance_max: '',
}

function DetailLedgerTable({ ledger, loading, compact = false, onEditEntry, onDeleteEntry, canApprove }) {
  const [colFilters, setColFilters] = useState(EMPTY_LEDGER_COL_FILTERS)

  useEffect(() => {
    setColFilters(EMPTY_LEDGER_COL_FILTERS)
  }, [ledger?.header?.detailed_code, ledger?.header?.detailed_name])

  const filteredLines = useMemo(() => {
    if (!ledger?.lines?.length) return []
    return ledger.lines.filter((line) => ledgerLineMatchesFilters(line, colFilters))
  }, [ledger, colFilters])

  const setCol = (key) => (e) => setColFilters({ ...colFilters, [key]: e.target.value })

  if (loading) return <div className="loading">در حال بارگذاری…</div>
  if (!ledger) return <EmptyState text="حساب تفصیلی را انتخاب کنید." />

  const total = ledger.lines.length
  const shown = filteredLines.length

  return (
    <>
      <div className={`detail-ledger-header${compact ? ' detail-ledger-header-compact' : ''}`}>
        {compact ? (
          <p className="detail-ledger-header-inline">
            <span className="muted">{TERMS.generalAccount}:</span> {ledger.header.general_name}
            {' · '}
            <span className="muted">{TERMS.subsidiaryAccount}:</span> {ledger.header.subsidiary_name}
            {' · '}
            <span className="muted">{TERMS.detailedAccount}:</span> {ledger.header.detailed_code} — {ledger.header.detailed_name}
            {' · '}
            <strong>{formatNumber(shown)}</strong> از {formatNumber(total)} ردیف
          </p>
        ) : (
          <>
            <p><span className="muted">{TERMS.generalAccount}:</span> {ledger.header.general_name}</p>
            <p><span className="muted">{TERMS.subsidiaryAccount}:</span> {ledger.header.subsidiary_name}</p>
            <p><span className="muted">{TERMS.detailedAccount}:</span> {ledger.header.detailed_code} — {ledger.header.detailed_name}</p>
            <p className="record-filter-count muted">
              <strong>{formatNumber(shown)}</strong> از {formatNumber(total)} ردیف
            </p>
          </>
        )}
      </div>
      <div className={`table-wrap accounting-ledger-wrap accounting-table-desktop${compact ? ' ledger-table-compact' : ''}`}>
        <table className="table accounting-ledger-table">
          <thead>
            <tr>
              <th>تاریخ</th>
              <th>{TERMS.documentNumber}</th>
              <th>{TERMS.attachCode}</th>
              <th>{TERMS.description}</th>
              <th>{TERMS.debit}</th>
              <th>{TERMS.credit}</th>
              <th>{TERMS.balance}</th>
              <th>{TERMS.side}</th>
              {(onEditEntry || onDeleteEntry) && <th>عملیات</th>}
            </tr>
            <tr className="ledger-search-row">
              <th>
                <input className="ledger-col-search" value={colFilters.date} onChange={setCol('date')} placeholder="فیلتر…" />
              </th>
              <th>
                <input className="ledger-col-search" value={colFilters.document_number} onChange={setCol('document_number')} placeholder="فیلتر…" />
              </th>
              <th>
                <input className="ledger-col-search" value={colFilters.attach_code} onChange={setCol('attach_code')} placeholder="فیلتر…" />
              </th>
              <th>
                <input className="ledger-col-search" value={colFilters.description} onChange={setCol('description')} placeholder="فیلتر…" />
              </th>
              <th>
                <div className="ledger-col-search-range">
                  <input className="ledger-col-search" value={colFilters.debit_min} onChange={setCol('debit_min')} placeholder="از" inputMode="numeric" />
                  <input className="ledger-col-search" value={colFilters.debit_max} onChange={setCol('debit_max')} placeholder="تا" inputMode="numeric" />
                </div>
              </th>
              <th>
                <div className="ledger-col-search-range">
                  <input className="ledger-col-search" value={colFilters.credit_min} onChange={setCol('credit_min')} placeholder="از" inputMode="numeric" />
                  <input className="ledger-col-search" value={colFilters.credit_max} onChange={setCol('credit_max')} placeholder="تا" inputMode="numeric" />
                </div>
              </th>
              <th>
                <div className="ledger-col-search-range">
                  <input className="ledger-col-search" value={colFilters.balance_min} onChange={setCol('balance_min')} placeholder="از" inputMode="numeric" />
                  <input className="ledger-col-search" value={colFilters.balance_max} onChange={setCol('balance_max')} placeholder="تا" inputMode="numeric" />
                </div>
              </th>
              <th />
              {(onEditEntry || onDeleteEntry) && <th />}
            </tr>
          </thead>
          <tbody>
            {filteredLines.length === 0 ? (
              <tr>
                <td colSpan={(onEditEntry || onDeleteEntry) ? 9 : 8} className="muted text-center">ردیفی با این فیلتر یافت نشد.</td>
              </tr>
            ) : (
              filteredLines.map((line, idx) => (
                <tr key={line.id || `opening-${idx}`}>
                  <td>{formatDate(line.entry_date)}</td>
                  <td>{line.document_number ? formatNumber(line.document_number) : '—'}</td>
                  <td>{line.attach_code || '—'}</td>
                  <td className="text-cell">
                    {line.description}
                    {line.transferred_to_office_at && (
                      <span className="accounting-transfer-badge" title={line.office_document_code || ''}>
                        {' '}منتقل‌شده به اداری
                      </span>
                    )}
                  </td>
                  <td>{renderAmount(line.debit)}</td>
                  <td>{renderAmount(line.credit)}</td>
                  <td>{formatRial(line.balance)}</td>
                  <td>{line.balance_side_label}</td>
                  {(onEditEntry || onDeleteEntry) && (
                    <td className="ledger-entry-actions">
                      {!line.is_opening && line.id && (
                        <>
                          {line.can_edit && onEditEntry && (
                            <button type="button" className="link" onClick={() => onEditEntry(line)} title="ویرایش">✎</button>
                          )}
                          {line.can_delete && onDeleteEntry && (
                            <button type="button" className="link danger" onClick={() => onDeleteEntry(line)} title="حذف">×</button>
                          )}
                          {canApprove && line.is_approved === false && (
                            <span className="muted small" title="تایید نشده">○</span>
                          )}
                        </>
                      )}
                    </td>
                  )}
                </tr>
              ))
            )}
          </tbody>
        </table>
      </div>
      <div className="accounting-cards-mobile">
        {filteredLines.map((line, idx) => (
          <div key={line.id || `opening-${idx}`} className="m-card">
            <div className="m-card-head accounting-entry-card-head">
              <div>
                <strong>{formatDate(line.entry_date)}</strong>
                <p className="accounting-entry-meta muted">
                  {TERMS.documentNumber}: {line.document_number ? formatNumber(line.document_number) : '—'}
                  {line.attach_code ? ` · ${TERMS.attachCode}: ${line.attach_code}` : ''}
                </p>
              </div>
              <span className="accounting-entry-amount">{line.balance_side_label}</span>
            </div>
            {line.description && <p className="accounting-entry-desc">{line.description}</p>}
            {line.transferred_to_office_at && (
              <p className="accounting-transfer-badge muted small">
                منتقل‌شده به اداری{line.office_document_code ? ` (${line.office_document_code})` : ''}
              </p>
            )}
            <div className="m-card-grid">
              <div><span className="muted">{TERMS.debit}</span><strong>{renderAmount(line.debit)}</strong></div>
              <div><span className="muted">{TERMS.credit}</span><strong>{renderAmount(line.credit)}</strong></div>
              <div><span className="muted">{TERMS.balance}</span><strong>{formatRial(line.balance)}</strong></div>
            </div>
            {(onEditEntry || onDeleteEntry) && !line.is_opening && line.id && (
              <div className="accounting-doc-list-actions ledger-entry-actions">
                {line.can_edit && onEditEntry && (
                  <button type="button" className="btn btn-ghost btn-sm" onClick={() => onEditEntry(line)} title="ویرایش">✎ ویرایش</button>
                )}
                {line.can_delete && onDeleteEntry && (
                  <button type="button" className="btn btn-ghost btn-sm danger" onClick={() => onDeleteEntry(line)} title="حذف">× حذف</button>
                )}
                {canApprove && line.is_approved === false && (
                  <span className="muted small accounting-doc-list-pending" title="تایید نشده">○ در انتظار تایید</span>
                )}
              </div>
            )}
          </div>
        ))}
      </div>
    </>
  )
}

export default function Accounting({
  api = accountingApi,
  pageTitle = 'حسابداری',
  createPermission = 'create_accounting',
  editPermission = 'edit_accounting',
  deletePermission = 'delete_accounting',
  approvePermission = 'approve_accounting',
  guidePrefix = 'accounting',
  ledgerKind = 'office',
  transferPermission = '',
}) {
  const { user } = useAuth()
  const canCreate = hasPermission(user, createPermission)
  const canEdit = hasPermission(user, editPermission) || canCreate
  const canDelete = hasPermission(user, deletePermission)
  const canApprove = hasPermission(user, approvePermission)
  const canEditChart = canEdit
  const canTransfer = Boolean(transferPermission) && hasPermission(user, transferPermission)
  const visibleTabs = useMemo(() => {
    const tabs = [...ACCOUNTING_TABS]
    if (canTransfer) {
      tabs.push({ id: 'transfer-to-office', label: 'انتقال به اداری' })
    }
    return tabs
  }, [canTransfer])
  const [activeTab, setActiveTab] = useState('trial-balance')
  const accountingGuideKey = `${guidePrefix}__${activeTab}`
  useRegisterPageGuide(accountingGuideKey, PAGE_GUIDE_DEFAULTS[accountingGuideKey] || '')
  const [classFilter, setClassFilter] = useState('')
  const [trialDateFrom, setTrialDateFrom] = useState('')
  const [trialDateTo, setTrialDateTo] = useState('')
  const [error, setError] = useState('')

  const [accountGroups, setAccountGroups] = useState([])
  const [subsidiaries, setSubsidiaries] = useState([])
  const [details, setDetails] = useState([])

  const [trialRows, setTrialRows] = useState([])
  const [trialTotals, setTrialTotals] = useState({})
  const [trialLoading, setTrialLoading] = useState(false)
  const [trialTextFilter, setTrialTextFilter] = useState(EMPTY_TRIAL_BALANCE_FILTER)
  const [ledgerTextFilter, setLedgerTextFilter] = useState(EMPTY_TRIAL_BALANCE_FILTER)

  const [detailLedger, setDetailLedger] = useState(null)
  const [detailLoading, setDetailLoading] = useState(false)

  const [drillGeneral, setDrillGeneral] = useState(null)
  const [drillSubsidiary, setDrillSubsidiary] = useState(null)
  const [drillDetailed, setDrillDetailed] = useState(null)
  const [drillSubsidiaryRows, setDrillSubsidiaryRows] = useState([])
  const [drillDetailedRows, setDrillDetailedRows] = useState([])
  const [drillSubsidiaryLoading, setDrillSubsidiaryLoading] = useState(false)
  const [drillDetailedLoading, setDrillDetailedLoading] = useState(false)
  const [ledgerGeneralRows, setLedgerGeneralRows] = useState([])
  const [ledgerGeneralLoading, setLedgerGeneralLoading] = useState(false)
  const [drillPanelLayout, setDrillPanelLayout] = useState(DEFAULT_DRILL_PANEL_LAYOUT)
  const storageKey = `accounting-ledger-panels-${ledgerKind}`
  const [drillWeights, setDrillWeights] = usePersistedState(`${storageKey}-weights`, DEFAULT_DRILL_WEIGHTS)
  const [drillRowHeight, setDrillRowHeight] = usePersistedState(`${storageKey}-row-height`, DEFAULT_DRILL_ROW_HEIGHT)
  const [ledgerAccountPanelOpen, setLedgerAccountPanelOpen] = useState(false)
  const [ledgerAccountPanelMinimized, setLedgerAccountPanelMinimized] = useState(false)
  const [ledgerAccountPanelWidth, setLedgerAccountPanelWidth] = usePersistedState(`${storageKey}-account-panel-w`, 340)
  const [ledgerAccountSelected, setLedgerAccountSelected] = useState(null)
  const [ledgerAccountEditForm, setLedgerAccountEditForm] = useState(null)
  const [ledgerAccountChildForm, setLedgerAccountChildForm] = useState(EMPTY_CHART_CHILD)
  const [ledgerAccountEditSaving, setLedgerAccountEditSaving] = useState(false)
  const [ledgerAccountChildSaving, setLedgerAccountChildSaving] = useState(false)
  const [ledgerAccountPanelTab, setLedgerAccountPanelTab] = useState('edit')
  const [activeLedgerCard, setActiveLedgerCard] = useState('general')
  const [ledgerSidePanelTab, setLedgerSidePanelTab] = useState('account')
  const [quickDocForm, setQuickDocForm] = useState({
    description: '',
    entry_date: '',
    attach_code: '',
    debit: '',
    credit: '',
    account_id: '',
    subsidiary_id: '',
    detailed_id: '',
  })
  const [quickDocSaving, setQuickDocSaving] = useState(false)
  const [quickDocError, setQuickDocError] = useState('')
  const [quickDocSuccess, setQuickDocSuccess] = useState('')
  const ledgerAccountPanelRef = useRef(null)
  const ledgerLayoutRef = useRef(null)
  const drillStageWrapRef = useRef(null)
  const drillStageRef = useRef(null)
  const [drillStageWidth, setDrillStageWidth] = useState(0)
  const [drillStageMaxHeight, setDrillStageMaxHeight] = useState(DRILL_HEIGHT_LIMITS.ledger.max)
  const drillSavedSizesRef = useRef({ weights: {}, rowHeight: null })
  const ledgerQueryRef = useRef('')

  const [docHeader, setDocHeader] = useState({ attach_code: '', description: '', entry_date: '', document_number: '' })
  const [docLines, setDocLines] = useState([{ ...EMPTY_DOC_LINE }, { ...EMPTY_DOC_LINE }])
  const [docSaving, setDocSaving] = useState(false)
  const [docError, setDocError] = useState('')
  const [docSuccess, setDocSuccess] = useState('')
  const [docEditCode, setDocEditCode] = useState('')
  const [docCanEdit, setDocCanEdit] = useState(true)
  const [docView, setDocView] = useState('list')

  const [docListRows, setDocListRows] = useState([])
  const [docListTotal, setDocListTotal] = useState(0)
  const [docListOffset, setDocListOffset] = useState(0)
  const [docListLoading, setDocListLoading] = useState(false)
  const [docListSearch, setDocListSearch] = useState('')
  const [docListApproved, setDocListApproved] = useState('')
  const DOC_LIST_LIMIT = 30

  const [entryEdit, setEntryEdit] = useState(null)
  const [entryEditSaving, setEntryEditSaving] = useState(false)

  const [chartSearch, setChartSearch] = useState('')
  const [chartSelected, setChartSelected] = useState(null)
  const [chartEditForm, setChartEditForm] = useState(null)
  const [chartEditSaving, setChartEditSaving] = useState(false)
  const [chartChildForm, setChartChildForm] = useState(EMPTY_CHART_CHILD)
  const [chartChildSaving, setChartChildSaving] = useState(false)
  const [chartPanelTab, setChartPanelTab] = useState('edit')
  const chartDetailRef = useRef(null)

  const [lineAccountPick, setLineAccountPick] = useState(null)
  const lineAccountPickRef = useRef(null)

  const [importFile, setImportFile] = useState(null)
  const [importDryRun, setImportDryRun] = useState(false)

  const [transferDocCode, setTransferDocCode] = useState('')
  const [transferDocNumber, setTransferDocNumber] = useState('')
  const [transferPreview, setTransferPreview] = useState(null)
  const [transferLoading, setTransferLoading] = useState(false)
  const [transferSaving, setTransferSaving] = useState(false)
  const [transferError, setTransferError] = useState('')
  const [transferSuccess, setTransferSuccess] = useState('')
  const [importLoading, setImportLoading] = useState(false)
  const [importResult, setImportResult] = useState(null)
  const [importError, setImportError] = useState('')
  const [importSuccess, setImportSuccess] = useState('')

  const dateRange = useMemo(() => {
    const dateFrom = (trialDateFrom || '').trim()
    const dateTo = (trialDateTo || '').trim()
    if (!dateFrom && !dateTo) return {}
    return {
      ...(dateFrom ? { dateFrom } : {}),
      ...(dateTo ? { dateTo } : {}),
    }
  }, [trialDateFrom, trialDateTo])

  const accountOptions = useMemo(() => buildAccountOptions(accountGroups), [accountGroups])
  const detailOptions = useMemo(
    () => details.map((d) => ({ value: String(d.id), label: `${d.full_code} — ${d.name}` })),
    [details],
  )
  const subsidiaryOptions = useMemo(
    () => subsidiaries.map((s) => ({ value: String(s.id), label: `${s.full_code} — ${s.name}` })),
    [subsidiaries],
  )

  const chartQuery = chartSearch.trim().toLowerCase()

  const filteredChartGroups = useMemo(() => {
    if (!chartQuery) {
      return accountGroups.map((group) => ({
        ...group,
        accounts: (group.accounts || []).map((acc) => ({
          acc,
          subs: subsidiaries
            .filter((s) => s.account_id === acc.id)
            .map((sub) => ({
              sub,
              dets: details.filter((d) => d.subsidiary_id === sub.id),
            })),
        })),
      }))
    }

    return accountGroups
      .map((group) => {
        const accounts = (group.accounts || [])
          .map((acc) => {
            const accMatch = matchesChartSearch([acc.code, acc.name, group.class_label], chartQuery)
            const subsAll = subsidiaries.filter((s) => s.account_id === acc.id)
            const subs = subsAll
              .map((sub) => {
                const subMatch = matchesChartSearch([sub.code, sub.full_code, sub.name], chartQuery)
                const detsAll = details.filter((d) => d.subsidiary_id === sub.id)
                const dets = detsAll.filter((det) =>
                  matchesChartSearch([det.code, det.full_code, det.name], chartQuery),
                )
                if (subMatch || dets.length) {
                  return { sub, dets: subMatch ? detsAll : dets }
                }
                return null
              })
              .filter(Boolean)
            if (accMatch || subs.length) {
              return {
                acc,
                subs: accMatch
                  ? subsAll.map((sub) => ({
                      sub,
                      dets: details.filter((d) => d.subsidiary_id === sub.id),
                    }))
                  : subs,
              }
            }
            return null
          })
          .filter(Boolean)
        if (!accounts.length) return null
        return { ...group, accounts }
      })
      .filter(Boolean)
  }, [accountGroups, subsidiaries, details, chartQuery])

  const chartListEmpty = filteredChartGroups.every((g) => !(g.accounts || []).length)

  const askLineAccountPick = useCallback((title, message, options) => new Promise((resolve) => {
    lineAccountPickRef.current = resolve
    setLineAccountPick({ title, message, options })
  }), [])

  const finishLineAccountPick = (choice) => {
    lineAccountPickRef.current?.(choice)
    lineAccountPickRef.current = null
    setLineAccountPick(null)
  }

  const generalAccountLabel = useCallback((accountId) => {
    for (const group of accountGroups) {
      for (const acc of group.accounts || []) {
        if (String(acc.id) === String(accountId)) {
          return `${acc.code} — ${acc.name}`
        }
      }
    }
    return String(accountId)
  }, [accountGroups])

  const applyDetailedToLine = (index, det) => {
    setDocLines((prev) => prev.map((line, i) => (i === index ? {
      ...line,
      detailed_id: String(det.id),
      subsidiary_id: String(det.subsidiary_id),
      account_id: String(det.account_id),
    } : line)))
  }

  const changeDocLineDetailed = async (index, value) => {
    if (!value) {
      setDocLines((prev) => prev.map((line, i) => (i === index ? { ...line, detailed_id: '' } : line)))
      return
    }
    const selected = details.find((d) => String(d.id) === String(value))
    if (!selected) return

    const label = detailedOptionLabel(selected)
    const duplicates = details.filter((d) => detailedOptionLabel(d) === label)
    if (duplicates.length > 1) {
      const choice = await askLineAccountPick(
        `انتخاب ${TERMS.detailedAccount}`,
        'چند حساب تفصیلی با این عنوان وجود دارد. کدام را می‌خواهید؟',
        duplicates.map((d) => ({
          key: String(d.id),
          label: detailedOptionLabel(d),
          detailed: d,
        })),
      )
      if (!choice?.detailed) return
      applyDetailedToLine(index, choice.detailed)
      return
    }
    applyDetailedToLine(index, selected)
  }

  const changeDocLineSubsidiary = (index, value) => {
    setDocLines((prev) => prev.map((line, i) => {
      if (i !== index) return line
      if (!value) return { ...line, subsidiary_id: '' }
      const sub = subsidiaries.find((s) => String(s.id) === String(value))
      if (!sub) return { ...line, subsidiary_id: value }
      const next = {
        ...line,
        subsidiary_id: value,
        account_id: String(sub.account_id),
      }
      if (line.detailed_id) {
        const det = details.find((d) => String(d.id) === String(line.detailed_id))
        if (det && String(det.subsidiary_id) !== String(value)) {
          next.detailed_id = ''
        }
      }
      return next
    }))
  }

  const changeDocLineGeneral = (index, value) => {
    setDocLines((prev) => prev.map((line, i) => {
      if (i !== index) return line
      if (!value) return { ...line, account_id: '' }
      const next = { ...line, account_id: value }
      if (line.subsidiary_id) {
        const sub = subsidiaries.find((s) => String(s.id) === String(line.subsidiary_id))
        if (sub && String(sub.account_id) !== String(value)) {
          next.subsidiary_id = ''
          next.detailed_id = ''
        }
      } else if (line.detailed_id) {
        const det = details.find((d) => String(d.id) === String(line.detailed_id))
        if (det && String(det.account_id) !== String(value)) {
          next.detailed_id = ''
        }
      }
      return next
    }))
  }

  const resolveLinePosting = async (line, rowNumber, options = {}) => {
    const description = options.description ?? docHeader.description
    const attachCode = options.attach_code ?? docHeader.attach_code
    const base = {
      description: description.trim(),
      debit: Number(line.debit) || 0,
      credit: Number(line.credit) || 0,
      attach_code: attachCode.trim(),
    }

    const det = line.detailed_id ? details.find((d) => String(d.id) === String(line.detailed_id)) : null
    const sub = line.subsidiary_id ? subsidiaries.find((s) => String(s.id) === String(line.subsidiary_id)) : null
    const accId = line.account_id ? Number(line.account_id) : null

    const choices = []

    if (det) {
      const parentsMatch = (!line.subsidiary_id || String(det.subsidiary_id) === String(line.subsidiary_id))
        && (!line.account_id || String(det.account_id) === String(line.account_id))
      if (parentsMatch) {
        return { ...base, detailed_id: det.id }
      }
      choices.push({
        key: 'detailed',
        label: `${TERMS.detailedAccount}: ${detailedOptionLabel(det)}`,
        payload: { detailed_id: det.id },
      })
    }

    if (sub && line.subsidiary_id) {
      choices.push({
        key: 'subsidiary',
        label: `${TERMS.subsidiaryAccount}: ${sub.full_code} — ${sub.name}`,
        payload: { subsidiary_id: sub.id },
      })
    }

    if (accId && line.account_id && (!sub || sub.account_id !== accId)) {
      choices.push({
        key: 'general',
        label: `${TERMS.generalAccount}: ${generalAccountLabel(accId)}`,
        payload: { account_id: accId },
      })
    }

    const uniqueChoices = choices.filter(
      (choice, idx, arr) => arr.findIndex((c) => c.key === choice.key) === idx,
    )

    if (!uniqueChoices.length) {
      throw new Error(`ردیف ${formatNumber(rowNumber)}: حداقل یک سطح حساب (کل، معین یا تفصیلی) انتخاب کنید.`)
    }

    if (uniqueChoices.length === 1) {
      return { ...base, ...uniqueChoices[0].payload }
    }

    const pick = await askLineAccountPick(
      'سطح ثبت حساب',
      `ردیف ${formatNumber(rowNumber)} — چند سطح حساب پر شده است. ثبت روی کدام انجام شود؟`,
      uniqueChoices,
    )
    if (!pick?.payload) {
      throw new Error('ثبت سند لغو شد.')
    }
    return { ...base, ...pick.payload }
  }

  const loadAccounts = useCallback(async () => {
    try {
      const [accData, subData, detData] = await Promise.all([
        api.accounts(),
        api.subsidiaries(),
        api.details(),
      ])
      setAccountGroups(accData.accounts || [])
      setSubsidiaries(subData.results || [])
      setDetails(detData.results || [])
    } catch {
      /* optional */
    }
  }, [api])

  const loadTrialBalance = useCallback(async () => {
    const level = TRIAL_BALANCE_LEVEL[activeTab]
    if (!level) return
    setTrialLoading(true)
    try {
      const data = await api.trialBalance({
        level,
        accountClass: classFilter,
        ...dateRange,
      })
      setTrialRows(data.results || [])
      setTrialTotals(data.totals || {})
      setError('')
    } catch (e) {
      setError(e.message)
    } finally {
      setTrialLoading(false)
    }
  }, [activeTab, classFilter, dateRange])

  const loadLedgerGeneral = useCallback(async () => {
    setLedgerGeneralLoading(true)
    try {
      const data = await api.trialBalance({
        level: 'general',
        accountClass: classFilter,
        ...dateRange,
      })
      setLedgerGeneralRows(data.results || [])
      setError('')
    } catch (e) {
      setError(e.message)
    } finally {
      setLedgerGeneralLoading(false)
    }
  }, [classFilter, dateRange])

  const fetchDetailLedger = useCallback(async (target) => {
    setDetailLoading(true)
    try {
      const data = await api.detailLedger({
        detailedId: target.detailedId,
        subsidiaryId: target.subsidiaryId,
        accountId: target.accountId,
        ...dateRange,
      })
      setDetailLedger(data)
      setError('')
    } catch (e) {
      setError(e.message)
      setDetailLedger(null)
    } finally {
      setDetailLoading(false)
    }
  }, [dateRange])

  const loadDrillSubsidiary = useCallback(async (accountId) => {
    if (!accountId) {
      setDrillSubsidiaryRows([])
      return []
    }
    setDrillSubsidiaryLoading(true)
    try {
      const data = await api.trialBalance({
        level: 'subsidiary',
        accountId,
        accountClass: classFilter,
        ...dateRange,
      })
      const rows = data.results || []
      setDrillSubsidiaryRows(rows)
      setError('')
      return rows
    } catch (e) {
      setError(e.message)
      setDrillSubsidiaryRows([])
      return []
    } finally {
      setDrillSubsidiaryLoading(false)
    }
  }, [classFilter, dateRange])

  const loadDrillDetailed = useCallback(async (subsidiaryId) => {
    if (!subsidiaryId) {
      setDrillDetailedRows([])
      return []
    }
    setDrillDetailedLoading(true)
    try {
      const data = await api.trialBalance({
        level: 'detailed',
        subsidiaryId,
        accountClass: classFilter,
        ...dateRange,
      })
      const rows = data.results || []
      setDrillDetailedRows(rows)
      setError('')
      return rows
    } catch (e) {
      setError(e.message)
      setDrillDetailedRows([])
      return []
    } finally {
      setDrillDetailedLoading(false)
    }
  }, [classFilter, dateRange])

  const loadDocumentList = useCallback(async (offset = 0) => {
    setDocListLoading(true)
    try {
      const data = await api.listDocuments({
        search: docListSearch.trim() || undefined,
        approved: docListApproved || undefined,
        accountClass: classFilter || undefined,
        dateFrom: trialDateFrom || undefined,
        dateTo: trialDateTo || undefined,
        offset,
        limit: DOC_LIST_LIMIT,
      })
      setDocListRows(data.results || [])
      setDocListTotal(data.total || 0)
      setDocListOffset(data.offset || 0)
      setError('')
    } catch (e) {
      setError(e.message)
    } finally {
      setDocListLoading(false)
    }
  }, [api, docListSearch, docListApproved, classFilter, trialDateFrom, trialDateTo])

  const refreshAll = useCallback(async () => {
    await Promise.all([loadAccounts(), loadTrialBalance()])
    if (activeTab === 'ledger') await loadLedgerGeneral()
    if (activeTab === 'documents' && docView === 'list') await loadDocumentList(docListOffset)
  }, [loadAccounts, loadTrialBalance, loadLedgerGeneral, loadDocumentList, activeTab, docView, docListOffset])

  const resetDocForm = () => {
    setDocEditCode('')
    setDocCanEdit(true)
    setDocHeader({ attach_code: '', description: '', entry_date: '', document_number: '' })
    setDocLines([{ ...EMPTY_DOC_LINE }, { ...EMPTY_DOC_LINE }])
    setDocError('')
    setDocSuccess('')
  }

  const openNewDocument = () => {
    resetDocForm()
    setDocView('form')
  }

  const openEditDocument = async (docCode) => {
    setDocError('')
    setDocSuccess('')
    setDocSaving(true)
    try {
      const doc = await api.getDocument(docCode)
      setDocEditCode(doc.document_code)
      setDocCanEdit(doc.can_edit !== false)
      setDocHeader({
        attach_code: doc.attach_code || '',
        description: doc.description || '',
        entry_date: doc.entry_date ? doc.entry_date.slice(0, 10) : '',
        document_number: doc.document_number != null ? String(doc.document_number) : '',
      })
      setDocLines(
        doc.lines.map((line) => ({
          id: line.id,
          account_id: line.account_id ? String(line.account_id) : '',
          subsidiary_id: line.subsidiary_id ? String(line.subsidiary_id) : '',
          detailed_id: line.detailed_id ? String(line.detailed_id) : '',
          debit: line.debit ? String(line.debit) : '',
          credit: line.credit ? String(line.credit) : '',
          description: line.description || '',
        })),
      )
      setDocView('form')
    } catch (err) {
      setError(err.message)
    } finally {
      setDocSaving(false)
    }
  }

  const deleteDocumentByCode = async (docCode) => {
    if (!window.confirm(`سند ${docCode} حذف شود؟`)) return
    try {
      await api.deleteDocument(docCode)
      await loadDocumentList(docListOffset)
      await refreshAll()
    } catch (err) {
      setError(err.message)
    }
  }

  const toggleDocumentApproval = async (doc, approve) => {
    try {
      await api.approveDocument(doc.document_code, approve)
      await loadDocumentList(docListOffset)
    } catch (err) {
      setError(err.message)
    }
  }

  const refreshDetailLedger = useCallback(async () => {
    if (drillDetailed?.detailed_id) {
      await fetchDetailLedger({ detailedId: String(drillDetailed.detailed_id) })
    } else if (drillSubsidiary?.subsidiary_id) {
      await fetchDetailLedger({ subsidiaryId: String(drillSubsidiary.subsidiary_id) })
    } else if (drillGeneral?.account_id) {
      await fetchDetailLedger({ accountId: String(drillGeneral.account_id) })
    }
  }, [drillDetailed, drillSubsidiary, drillGeneral, fetchDetailLedger])

  const deleteLedgerEntry = async (line) => {
    if (!line.id || !window.confirm('این ردیف حذف شود؟')) return
    try {
      await api.remove(line.id)
      await refreshDetailLedger()
      await refreshAll()
    } catch (err) {
      setError(err.message)
    }
  }

  const saveEntryEdit = async (e) => {
    e.preventDefault()
    if (!entryEdit?.id) return
    setEntryEditSaving(true)
    try {
      await api.update(entryEdit.id, {
        description: entryEdit.description,
        debit: Number(entryEdit.debit) || 0,
        credit: Number(entryEdit.credit) || 0,
        entry_date: entryEdit.entry_date || undefined,
      })
      setEntryEdit(null)
      await refreshDetailLedger()
      await refreshAll()
    } catch (err) {
      setError(err.message)
    } finally {
      setEntryEditSaving(false)
    }
  }

  useEffect(() => { loadAccounts() }, [loadAccounts])
  useEffect(() => { loadTrialBalance() }, [loadTrialBalance])
  useEffect(() => {
    if (activeTab === 'ledger') {
      loadLedgerGeneral()
    }
  }, [activeTab, loadLedgerGeneral])

  useEffect(() => {
    if (activeTab !== 'ledger') return

    const queryKey = `${classFilter}|${trialDateFrom}|${trialDateTo}`
    if (ledgerQueryRef.current === queryKey) return
    ledgerQueryRef.current = queryKey

    if (drillGeneral?.account_id) {
      loadDrillSubsidiary(drillGeneral.account_id)
    }
    if (drillSubsidiary?.subsidiary_id) {
      loadDrillDetailed(drillSubsidiary.subsidiary_id)
    }
    if (drillDetailed?.detailed_id) {
      fetchDetailLedger({ detailedId: String(drillDetailed.detailed_id) })
    } else if (drillSubsidiary?.subsidiary_id) {
      fetchDetailLedger({ subsidiaryId: String(drillSubsidiary.subsidiary_id) })
    } else if (drillGeneral?.account_id) {
      fetchDetailLedger({ accountId: String(drillGeneral.account_id) })
    }
  }, [
    activeTab,
    classFilter,
    trialDateFrom,
    trialDateTo,
    drillGeneral,
    drillSubsidiary,
    drillDetailed,
    loadDrillSubsidiary,
    loadDrillDetailed,
    fetchDetailLedger,
  ])

  useEffect(() => {
    try {
      const weightsKey = `${storageKey}-weights`
      const widthsKey = `${storageKey}-widths`
      if (!localStorage.getItem(weightsKey) && localStorage.getItem(widthsKey)) {
        const migrated = migrateDrillWidthsToWeights(JSON.parse(localStorage.getItem(widthsKey)))
        setDrillWeights(migrated)
        localStorage.removeItem(widthsKey)
      }
      const rowHeightKey = `${storageKey}-row-height`
      const heightsKey = `${storageKey}-heights`
      if (!localStorage.getItem(rowHeightKey) && localStorage.getItem(heightsKey)) {
        const heights = JSON.parse(localStorage.getItem(heightsKey))
        const nextHeight = heights?.general ?? heights?.ledger ?? DEFAULT_DRILL_ROW_HEIGHT
        setDrillRowHeight(nextHeight)
        localStorage.removeItem(heightsKey)
      }
    } catch {
      /* ignore migration errors */
    }
  }, [storageKey, setDrillWeights, setDrillRowHeight])

  useEffect(() => {
    if (activeTab === 'documents' && docView === 'list') {
      loadDocumentList(0)
    }
  }, [activeTab, docView, docListSearch, docListApproved, classFilter, trialDateFrom, trialDateTo])

  const selectDrillGeneral = useCallback(async (row) => {
    setActiveLedgerCard('general')
    setDrillGeneral(row)
    setDrillSubsidiary(null)
    setDrillDetailed(null)
    setDrillDetailedRows([])
    setDetailLedger(null)
    const rows = await loadDrillSubsidiary(row.account_id)
    if (!rows?.length) {
      await fetchDetailLedger({ accountId: String(row.account_id) })
    }
  }, [loadDrillSubsidiary, fetchDetailLedger])

  const selectDrillSubsidiary = useCallback(async (row) => {
    setActiveLedgerCard('subsidiary')
    setDrillSubsidiary(row)
    setDrillDetailed(null)
    setDetailLedger(null)
    const rows = await loadDrillDetailed(row.subsidiary_id)
    if (!rows.length) {
      await fetchDetailLedger({ subsidiaryId: String(row.subsidiary_id) })
    }
  }, [loadDrillDetailed, fetchDetailLedger])

  const selectDrillDetailed = useCallback(async (row) => {
    setActiveLedgerCard('detailed')
    setDrillDetailed(row)
    await fetchDetailLedger({ detailedId: String(row.detailed_id) })
  }, [fetchDetailLedger])

  const drillLayoutHasMaximized = useMemo(
    () => Object.values(drillPanelLayout).some((mode) => mode === 'maximized'),
    [drillPanelLayout],
  )

  useEffect(() => {
    if (activeTab !== 'ledger') return undefined

    const updateStageMetrics = () => {
      const wrap = drillStageWrapRef.current
      if (!wrap) return
      setDrillStageWidth(wrap.clientWidth)
      const rect = wrap.getBoundingClientRect()
      const available = window.innerHeight - rect.top - 24
      setDrillStageMaxHeight(Math.max(DRILL_HEIGHT_LIMITS.general.min, available))
    }

    updateStageMetrics()
    const wrap = drillStageWrapRef.current
    if (!wrap) return undefined

    const observer = new ResizeObserver(updateStageMetrics)
    observer.observe(wrap)
    window.addEventListener('resize', updateStageMetrics)
    return () => {
      observer.disconnect()
      window.removeEventListener('resize', updateStageMetrics)
    }
  }, [activeTab, drillLayoutHasMaximized, ledgerAccountPanelOpen, ledgerAccountPanelMinimized])

  useEffect(() => {
    setDrillRowHeight((prev) => clampHeight(
      prev ?? DEFAULT_DRILL_ROW_HEIGHT,
      DRILL_HEIGHT_LIMITS.general.min,
      drillStageMaxHeight,
    ))
  }, [drillStageMaxHeight, setDrillRowHeight])

  const maximizedPanelId = useMemo(
    () => Object.entries(drillPanelLayout).find(([, mode]) => mode === 'maximized')?.[0] || null,
    [drillPanelLayout],
  )

  const ledgerAccountSelection = useMemo(() => {
    switch (activeLedgerCard) {
      case 'general':
        return drillGeneral ? { level: 'general', row: drillGeneral } : null
      case 'subsidiary':
        return drillSubsidiary ? { level: 'subsidiary', row: drillSubsidiary } : null
      case 'detailed':
        return drillDetailed ? { level: 'detailed', row: drillDetailed } : null
      case 'ledger':
        if (drillDetailed) return { level: 'detailed', row: drillDetailed }
        if (drillSubsidiary) return { level: 'subsidiary', row: drillSubsidiary }
        if (drillGeneral) return { level: 'general', row: drillGeneral }
        return null
      default:
        return null
    }
  }, [activeLedgerCard, drillGeneral, drillSubsidiary, drillDetailed])

  const syncQuickDocForm = useCallback((selection) => {
    const line = drillSelectionToDocLine(selection)
    setQuickDocForm((prev) => ({
      ...prev,
      description: prev.description,
      entry_date: prev.entry_date,
      attach_code: prev.attach_code,
      debit: prev.debit,
      credit: prev.credit,
      account_id: line.account_id,
      subsidiary_id: line.subsidiary_id,
      detailed_id: line.detailed_id,
    }))
    setQuickDocError('')
    setQuickDocSuccess('')
  }, [])

  const selectLedgerCard = useCallback((panelId) => {
    setActiveLedgerCard(panelId)
  }, [])

  const syncLedgerAccountContext = useCallback((selection, tab = 'edit') => {
    if (!selection) {
      setLedgerAccountSelected(null)
      setLedgerAccountEditForm(null)
      setLedgerAccountChildForm(EMPTY_CHART_CHILD)
      return
    }
    const record = drillRowToAccountRecord(selection.level, selection.row, {
      accountGroups,
      subsidiaries,
      details,
    })
    if (!record?.id) return
    setLedgerAccountSelected({ level: selection.level, id: record.id })
    setLedgerAccountEditForm(buildAccountEditForm(selection.level, record))
    setLedgerAccountChildForm(EMPTY_CHART_CHILD)
    setLedgerAccountPanelTab(tab === 'add' && selection.level !== 'detailed' ? 'add' : 'edit')
  }, [accountGroups, subsidiaries, details])

  useEffect(() => {
    if (!ledgerAccountPanelOpen) return
    syncLedgerAccountContext(ledgerAccountSelection)
    syncQuickDocForm(ledgerAccountSelection)
  }, [ledgerAccountPanelOpen, ledgerAccountSelection, syncLedgerAccountContext, syncQuickDocForm])

  const openLedgerAccountPanel = useCallback((tab = 'edit') => {
    setLedgerAccountPanelOpen(true)
    setLedgerAccountPanelMinimized(false)
    if (activeLedgerCard === 'ledger' || tab === 'document') {
      setLedgerSidePanelTab('document')
    } else {
      setLedgerSidePanelTab('account')
    }
    syncLedgerAccountContext(ledgerAccountSelection, tab === 'add' ? 'add' : 'edit')
    syncQuickDocForm(ledgerAccountSelection)
    requestAnimationFrame(() => {
      ledgerAccountPanelRef.current?.scrollIntoView({ block: 'nearest', behavior: 'smooth' })
    })
  }, [activeLedgerCard, ledgerAccountSelection, syncLedgerAccountContext, syncQuickDocForm])

  const closeLedgerAccountPanel = useCallback(() => {
    setLedgerAccountPanelOpen(false)
    setLedgerAccountPanelMinimized(false)
    setLedgerAccountSelected(null)
    setLedgerAccountEditForm(null)
    setLedgerAccountChildForm(EMPTY_CHART_CHILD)
    setLedgerAccountPanelTab('edit')
    setLedgerSidePanelTab('account')
    setQuickDocError('')
    setQuickDocSuccess('')
  }, [])

  const restoreDrillPanelSize = useCallback((panelKey) => {
    const savedWeight = drillSavedSizesRef.current.weights[panelKey]
    const savedRowHeight = drillSavedSizesRef.current.rowHeight
    if (savedWeight != null) {
      setDrillWeights((prev) => ({ ...prev, [panelKey]: savedWeight }))
    }
    if (savedRowHeight) {
      setDrillRowHeight(savedRowHeight)
    }
  }, [setDrillWeights, setDrillRowHeight])

  const resizeDrillPanel = useCallback((panelKey, delta) => {
    if (!drillStageWidth) return
    setDrillWeights((prev) => resizeDrillPanelPair(
      prev,
      drillPanelLayout,
      panelKey,
      delta,
      drillStageWidth,
    ))
  }, [drillStageWidth, drillPanelLayout, setDrillWeights])

  const resizeDrillRowHeight = useCallback((delta) => {
    setDrillRowHeight((prev) => clampHeight(
      (prev ?? DEFAULT_DRILL_ROW_HEIGHT) + delta,
      DRILL_HEIGHT_LIMITS.general.min,
      drillStageMaxHeight,
    ))
  }, [setDrillRowHeight, drillStageMaxHeight])

  const resizeLedgerAccountPanel = useCallback((delta) => {
    const layoutWidth = ledgerLayoutRef.current?.clientWidth ?? window.innerWidth
    const maxSide = Math.max(260, Math.min(560, layoutWidth * 0.55))
    setLedgerAccountPanelWidth((prev) => clampWidth(prev + delta, 260, maxSide))
  }, [setLedgerAccountPanelWidth])

  const ledgerBreadcrumb = useMemo(() => {
    const parts = []
    if (drillGeneral) parts.push(`${drillGeneral.account_code || ''} ${drillGeneral.account_name || ''}`.trim())
    if (drillSubsidiary) parts.push(`${drillSubsidiary.account_code || ''} ${drillSubsidiary.account_name || ''}`.trim())
    if (drillDetailed) parts.push(`${drillDetailed.account_code || ''} ${drillDetailed.account_name || ''}`.trim())
    return parts.filter(Boolean).join(' › ')
  }, [drillGeneral, drillSubsidiary, drillDetailed])

  const ledgerDetailHint = drillDetailed
    ? `${drillDetailed.account_code} — ${drillDetailed.account_name}`
    : drillSubsidiary
      ? `${drillSubsidiary.account_code} — ${drillSubsidiary.account_name}`
      : drillGeneral
        ? `${drillGeneral.account_code} — ${drillGeneral.account_name}`
        : ''

  const filteredLedgerGeneralRows = useMemo(
    () => applyTrialBalanceFilter(ledgerGeneralRows, ledgerTextFilter),
    [ledgerGeneralRows, ledgerTextFilter],
  )

  const filteredDrillSubsidiaryRows = useMemo(
    () => applyTrialBalanceFilter(drillSubsidiaryRows, ledgerTextFilter),
    [drillSubsidiaryRows, ledgerTextFilter],
  )

  const filteredDrillDetailedRows = useMemo(
    () => applyTrialBalanceFilter(drillDetailedRows, ledgerTextFilter),
    [drillDetailedRows, ledgerTextFilter],
  )

  const ledgerFilterOn = trialBalanceFilterActive(ledgerTextFilter)

  const ledgerFilterCounts = useMemo(() => ({
    general: {
      shown: filteredLedgerGeneralRows.length,
      total: ledgerGeneralRows.length,
    },
    subsidiary: {
      shown: filteredDrillSubsidiaryRows.length,
      total: drillSubsidiaryRows.length,
    },
    detailed: {
      shown: filteredDrillDetailedRows.length,
      total: drillDetailedRows.length,
    },
  }), [
    filteredLedgerGeneralRows.length,
    ledgerGeneralRows.length,
    filteredDrillSubsidiaryRows.length,
    drillSubsidiaryRows.length,
    filteredDrillDetailedRows.length,
    drillDetailedRows.length,
  ])

  const toggleDrillPanelMinimize = useCallback((panelId) => {
    setDrillPanelLayout((prev) => {
      const hasMaximized = Object.values(prev).some((mode) => mode === 'maximized')
      if (hasMaximized && prev[panelId] === 'minimized') {
        restoreDrillPanelSize(panelId)
        const next = { ...DEFAULT_DRILL_PANEL_LAYOUT }
        for (const key of Object.keys(next)) {
          next[key] = key === panelId ? 'maximized' : 'minimized'
        }
        return next
      }
      if (prev[panelId] === 'maximized') return prev
      if (prev[panelId] === 'minimized') {
        restoreDrillPanelSize(panelId)
        return { ...prev, [panelId]: 'normal' }
      }
      drillSavedSizesRef.current.weights[panelId] = drillWeights[panelId] ?? DEFAULT_DRILL_WEIGHTS[panelId]
      drillSavedSizesRef.current.rowHeight = drillRowHeight ?? DEFAULT_DRILL_ROW_HEIGHT
      return { ...prev, [panelId]: 'minimized' }
    })
  }, [restoreDrillPanelSize, drillWeights, drillRowHeight])

  const focusDrillPanel = useCallback((panelId) => {
    setDrillPanelLayout((prev) => {
      const hasMaximized = Object.values(prev).some((mode) => mode === 'maximized')
      if (!hasMaximized) {
        if (prev[panelId] === 'minimized') restoreDrillPanelSize(panelId)
        return { ...prev, [panelId]: 'normal' }
      }
      restoreDrillPanelSize(panelId)
      const next = { ...DEFAULT_DRILL_PANEL_LAYOUT }
      for (const key of Object.keys(next)) {
        next[key] = key === panelId ? 'maximized' : 'minimized'
      }
      return next
    })
  }, [restoreDrillPanelSize])

  const toggleDrillPanelMaximize = useCallback((panelId) => {
    setDrillPanelLayout((prev) => {
      if (prev[panelId] === 'maximized') {
        return { ...DEFAULT_DRILL_PANEL_LAYOUT }
      }
      drillSavedSizesRef.current.weights[panelId] = drillWeights[panelId] ?? DEFAULT_DRILL_WEIGHTS[panelId]
      drillSavedSizesRef.current.rowHeight = drillRowHeight ?? DEFAULT_DRILL_ROW_HEIGHT
      const next = { ...DEFAULT_DRILL_PANEL_LAYOUT }
      for (const key of Object.keys(next)) {
        next[key] = key === panelId ? 'maximized' : 'minimized'
      }
      return next
    })
  }, [drillWeights, drillRowHeight])

  const renderGeneralPanel = (compact = false) => (
    <LedgerTrialColumn
      panelId="general"
      layoutMode={drillPanelLayout.general}
      onToggleMinimize={toggleDrillPanelMinimize}
      onToggleMaximize={toggleDrillPanelMaximize}
      onFocus={focusDrillPanel}
      title={ACCOUNTING_MENU['trial-balance']}
      selectionLabel={rowSelectionLabel(drillGeneral)}
      rows={filteredLedgerGeneralRows}
      loading={ledgerGeneralLoading}
      selectedId={drillGeneral?.account_id}
      idKey="account_id"
      onSelect={selectDrillGeneral}
      compact={compact}
      emptyText={ledgerFilterOn ? 'با این فیلتر حسابی یافت نشد.' : 'حسابی یافت نشد.'}
      resizable={!compact}
      panelHeight={drillRowHeight ?? DEFAULT_DRILL_ROW_HEIGHT}
      onResizeHeight={resizeDrillRowHeight}
      cardSelected={activeLedgerCard === 'general'}
      onSelectCard={selectLedgerCard}
    />
  )

  const renderSubsidiaryPanel = (compact = false) => (
    <LedgerTrialColumn
      panelId="subsidiary"
      layoutMode={drillPanelLayout.subsidiary}
      onToggleMinimize={toggleDrillPanelMinimize}
      onToggleMaximize={toggleDrillPanelMaximize}
      onFocus={focusDrillPanel}
      title={ACCOUNTING_MENU['subsidiary-trial']}
      subtitle={drillGeneral?.account_name || 'ابتدا حساب کل را انتخاب کنید'}
      selectionLabel={rowSelectionLabel(drillSubsidiary)}
      rows={drillGeneral ? filteredDrillSubsidiaryRows : []}
      loading={drillGeneral ? drillSubsidiaryLoading : false}
      selectedId={drillSubsidiary?.subsidiary_id}
      idKey="subsidiary_id"
      onSelect={selectDrillSubsidiary}
      compact={compact}
      emptyText={drillGeneral ? (ledgerFilterOn ? 'با این فیلتر حساب معینی یافت نشد.' : 'حساب معینی یافت نشد.') : 'ابتدا حساب کل را انتخاب کنید.'}
      resizable={!compact}
      panelHeight={drillRowHeight ?? DEFAULT_DRILL_ROW_HEIGHT}
      onResizeHeight={resizeDrillRowHeight}
      cardSelected={activeLedgerCard === 'subsidiary'}
      onSelectCard={selectLedgerCard}
    />
  )

  const renderDetailedPanel = (compact = false) => (
    <LedgerTrialColumn
      panelId="detailed"
      layoutMode={drillPanelLayout.detailed}
      onToggleMinimize={toggleDrillPanelMinimize}
      onToggleMaximize={toggleDrillPanelMaximize}
      onFocus={focusDrillPanel}
      title={ACCOUNTING_MENU['detailed-trial']}
      subtitle={drillSubsidiary?.account_name || 'ابتدا حساب معین را انتخاب کنید'}
      selectionLabel={rowSelectionLabel(drillDetailed)}
      rows={drillSubsidiary ? filteredDrillDetailedRows : []}
      loading={drillSubsidiary ? drillDetailedLoading : false}
      selectedId={drillDetailed?.detailed_id}
      idKey="detailed_id"
      onSelect={selectDrillDetailed}
      compact={compact}
      emptyText={drillSubsidiary ? (ledgerFilterOn ? 'با این فیلتر حساب تفصیلی یافت نشد.' : 'حساب تفصیلی یافت نشد.') : 'ابتدا حساب معین را انتخاب کنید.'}
      resizable={!compact}
      panelHeight={drillRowHeight ?? DEFAULT_DRILL_ROW_HEIGHT}
      onResizeHeight={resizeDrillRowHeight}
      cardSelected={activeLedgerCard === 'detailed'}
      onSelectCard={selectLedgerCard}
    />
  )

  const renderLedgerPanel = (compact = false) => (
    <LedgerDrillCard
      panelId="ledger"
      variant="ledger"
      layoutMode={drillPanelLayout.ledger}
      onToggleMinimize={toggleDrillPanelMinimize}
      onToggleMaximize={toggleDrillPanelMaximize}
      onFocus={focusDrillPanel}
      cardSelected={activeLedgerCard === 'ledger'}
      onSelectCard={selectLedgerCard}
      title={TERMS.ledger}
      subtitle={ledgerDetailHint || 'حساب را از مراحل قبل انتخاب کنید'}
      selectionLabel={ledgerDetailHint}
      compact={compact}
      resizable={!compact}
      panelHeight={drillRowHeight ?? DEFAULT_DRILL_ROW_HEIGHT}
      onResizeHeight={resizeDrillRowHeight}
    >
      {detailLoading ? (
        <div className="loading">در حال بارگذاری…</div>
      ) : detailLedger ? (
        <DetailLedgerTable
          ledger={detailLedger}
          loading={false}
          compact={compact || drillLayoutHasMaximized}
          onEditEntry={canEdit ? (line) => setEntryEdit({
            id: line.id,
            description: line.description || '',
            debit: String(line.debit || ''),
            credit: String(line.credit || ''),
            entry_date: line.entry_date || '',
          }) : undefined}
          onDeleteEntry={canDelete ? deleteLedgerEntry : undefined}
          canApprove={canApprove}
        />
      ) : (
        <EmptyState text="حساب تفصیلی، معین یا کل را انتخاب کنید." />
      )}
    </LedgerDrillCard>
  )

  const drillColumnWidths = useMemo(() => computeDrillColumnWidths(
    drillWeights,
    drillPanelLayout,
    drillStageWidth || 1200,
  ), [drillWeights, drillPanelLayout, drillStageWidth])

  const drillStageStyle = useMemo(() => ({
    '--ld-w-general': `${drillColumnWidths.general}px`,
    '--ld-w-subsidiary': `${drillColumnWidths.subsidiary}px`,
    '--ld-w-detailed': `${drillColumnWidths.detailed}px`,
    '--ld-w-ledger': `${drillColumnWidths.ledger}px`,
  }), [drillColumnWidths])

  const renderDrillStageResizable = () => (
    <LedgerDrillStage ref={drillStageRef} style={drillStageStyle}>
      {renderGeneralPanel()}
      <LedgerStageDivider label="تغییر عرض ستون حساب کل" onDrag={(d) => resizeDrillPanel('general', d)} />
      {renderSubsidiaryPanel()}
      <LedgerStageDivider label="تغییر عرض ستون حساب معین" onDrag={(d) => resizeDrillPanel('subsidiary', d)} />
      {renderDetailedPanel()}
      <LedgerStageDivider label="تغییر عرض ستون حساب تفصیلی" onDrag={(d) => resizeDrillPanel('detailed', d)} />
      {renderLedgerPanel()}
    </LedgerDrillStage>
  )

  const docTotals = useMemo(() => {
    let debit = 0
    let credit = 0
    for (const line of docLines) {
      debit += Number(line.debit) || 0
      credit += Number(line.credit) || 0
    }
    const hasAmounts = debit > 0 || credit > 0
    return {
      debit,
      credit,
      hasAmounts,
      balanced: hasAmounts && debit === credit,
    }
  }, [docLines])

  const updateDocLine = (index, key, value) => {
    setDocLines((prev) => prev.map((line, i) => (i === index ? { ...line, [key]: value } : line)))
  }

  const addDocLine = () => setDocLines((prev) => [...prev, { ...EMPTY_DOC_LINE }])
  const removeDocLine = (index) => {
    setDocLines((prev) => (prev.length <= 2 ? prev : prev.filter((_, i) => i !== index)))
  }

  const saveDocument = async (e) => {
    e?.preventDefault?.()
    setDocError('')
    setDocSuccess('')
    const docDescription = docHeader.description.trim()
    if (!docDescription) {
      setDocError(`${TERMS.description} ${TERMS.document} الزامی است.`)
      return
    }

    const activeRows = docLines
      .map((line, index) => ({ line, rowNumber: index + 1 }))
      .filter(({ line }) => (Number(line.debit) || 0) > 0 || (Number(line.credit) || 0) > 0)

    if (!activeRows.length) {
      setDocError('حداقل یک ردیف با مبلغ لازم است.')
      return
    }

    setDocSaving(true)
    try {
      const lines = []
      for (const { line, rowNumber } of activeRows) {
        const resolved = await resolveLinePosting(line, rowNumber)
        if (line.id) resolved.id = line.id
        if (line.description?.trim()) resolved.description = line.description.trim()
        if (docHeader.attach_code.trim() && rowNumber === activeRows[0].rowNumber) {
          resolved.attach_code = docHeader.attach_code.trim()
        }
        lines.push(resolved)
      }
      const payload = {
        description: docDescription,
        lines,
        attach_code: docHeader.attach_code.trim() || undefined,
      }
      if (docHeader.entry_date) payload.entry_date = docHeader.entry_date
      if (docHeader.document_number.trim()) payload.document_number = Number(docHeader.document_number)

      let result
      const wasEdit = Boolean(docEditCode)
      if (docEditCode) {
        result = await api.updateDocument(docEditCode, payload)
      } else {
        result = await api.createDocument(payload)
      }

      const savedCode = result.document_code
      const savedNumber = result.document_number
      resetDocForm()
      const unbalancedNote =
        docTotals.debit !== docTotals.credit ? ` (${TERMS.unbalanced} — ${TERMS.debit} و ${TERMS.credit} برابر نیست.)` : ''
      setDocSuccess(
        wasEdit
          ? `${TERMS.document} ${savedCode} ویرایش شد.${unbalancedNote}`
          : `${TERMS.document} شماره ${formatNumber(savedNumber)} ثبت شد.${unbalancedNote}`,
      )
      setDocView('list')
      await loadDocumentList(0)
      await refreshAll()
    } catch (err) {
      setDocError(err.message)
    } finally {
      setDocSaving(false)
    }
  }

  const saveQuickLedgerDocument = async (e) => {
    e?.preventDefault?.()
    setQuickDocError('')
    setQuickDocSuccess('')
    if (!ledgerAccountSelection) {
      setQuickDocError('ابتدا یک حساب در کارت فعال انتخاب کنید.')
      return
    }
    const description = quickDocForm.description.trim()
    if (!description) {
      setQuickDocError(`${TERMS.description} ${TERMS.document} الزامی است.`)
      return
    }
    const debit = Number(quickDocForm.debit) || 0
    const credit = Number(quickDocForm.credit) || 0
    if (debit <= 0 && credit <= 0) {
      setQuickDocError('مبلغ بدهکار یا بستانکار را وارد کنید.')
      return
    }

    setQuickDocSaving(true)
    try {
      const line = {
        account_id: quickDocForm.account_id,
        subsidiary_id: quickDocForm.subsidiary_id,
        detailed_id: quickDocForm.detailed_id,
        debit: quickDocForm.debit,
        credit: quickDocForm.credit,
      }
      const resolved = await resolveLinePosting(line, 1, {
        description,
        attach_code: quickDocForm.attach_code,
      })
      const payload = {
        description,
        lines: [resolved],
        attach_code: quickDocForm.attach_code.trim() || undefined,
      }
      if (quickDocForm.entry_date) payload.entry_date = quickDocForm.entry_date

      const result = await api.createDocument(payload)
      setQuickDocSuccess(`${TERMS.document} شماره ${formatNumber(result.document_number)} ثبت شد.`)
      setQuickDocForm((prev) => ({
        ...prev,
        description: '',
        debit: '',
        credit: '',
      }))
      await refreshAll()
      if (drillDetailed?.detailed_id) {
        await fetchDetailLedger({ detailedId: String(drillDetailed.detailed_id) })
      } else if (drillSubsidiary?.subsidiary_id) {
        await fetchDetailLedger({ subsidiaryId: String(drillSubsidiary.subsidiary_id) })
      } else if (drillGeneral?.account_id) {
        await fetchDetailLedger({ accountId: String(drillGeneral.account_id) })
      }
    } catch (err) {
      setQuickDocError(err.message)
    } finally {
      setQuickDocSaving(false)
    }
  }

  const selectChartAccount = (level, record, options = {}) => {
    setChartSelected({ level, id: record.id })
    setChartChildForm(EMPTY_CHART_CHILD)
    setChartPanelTab(options.tab === 'add' && level !== 'detailed' ? 'add' : 'edit')
    setChartEditForm(buildAccountEditForm(level, record))
    requestAnimationFrame(() => {
      chartDetailRef.current?.scrollIntoView({ block: 'nearest', behavior: 'smooth' })
    })
  }

  const saveChartEdit = async (e) => {
    e.preventDefault()
    if (!chartSelected || !chartEditForm || !canEditChart) return
    setChartEditSaving(true)
    try {
      const updated = await saveAccountEdit(api, chartSelected, chartEditForm)
      selectChartAccount(chartSelected.level, { ...updated, id: chartSelected.id })
      await loadAccounts()
      setError('')
    } catch (err) {
      setError(err.message)
    } finally {
      setChartEditSaving(false)
    }
  }

  const saveChartChild = async (e) => {
    e.preventDefault()
    if (!canCreate || !chartSelected || chartSelected.level === 'detailed') return
    const code = chartChildForm.code.trim()
    const name = chartChildForm.name.trim()
    if (!code || !name) return

    setChartChildSaving(true)
    try {
      const created = await saveAccountChild(api, chartSelected, chartChildForm)
      await loadAccounts()
      if (chartSelected.level === 'general') {
        selectChartAccount('subsidiary', created)
      } else {
        selectChartAccount('detailed', created)
      }
      setError('')
    } catch (err) {
      setError(err.message)
    } finally {
      setChartChildSaving(false)
    }
  }

  const refreshLedgerAfterAccountChange = useCallback(async (level, created) => {
    await loadAccounts()
    await loadLedgerGeneral()
    if (level === 'subsidiary' && drillGeneral) {
      const rows = await loadDrillSubsidiary(drillGeneral.account_id)
      const newRow = rows.find((r) => r.subsidiary_id === created.id) || {
        subsidiary_id: created.id,
        account_id: created.account_id || drillGeneral.account_id,
        account_code: created.full_code,
        account_name: created.name,
      }
      await selectDrillSubsidiary(newRow)
      syncLedgerAccountContext({ level: 'subsidiary', row: newRow })
      return
    }
    if (level === 'detailed' && drillSubsidiary) {
      const rows = await loadDrillDetailed(drillSubsidiary.subsidiary_id)
      const newRow = rows.find((r) => r.detailed_id === created.id) || {
        detailed_id: created.id,
        subsidiary_id: created.subsidiary_id || drillSubsidiary.subsidiary_id,
        account_id: drillSubsidiary.account_id,
        account_code: created.full_code,
        account_name: created.name,
      }
      await selectDrillDetailed(newRow)
      syncLedgerAccountContext({ level: 'detailed', row: newRow })
    }
  }, [
    drillGeneral,
    drillSubsidiary,
    loadAccounts,
    loadDrillDetailed,
    loadDrillSubsidiary,
    loadLedgerGeneral,
    selectDrillDetailed,
    selectDrillSubsidiary,
    syncLedgerAccountContext,
  ])

  const saveLedgerAccountEdit = async (e) => {
    e.preventDefault()
    if (!ledgerAccountSelected || !ledgerAccountEditForm || !canEditChart) return
    setLedgerAccountEditSaving(true)
    try {
      const updated = await saveAccountEdit(api, ledgerAccountSelected, ledgerAccountEditForm)
      await loadAccounts()
      syncLedgerAccountContext({
        level: ledgerAccountSelected.level,
        row: { ...updated, id: ledgerAccountSelected.id },
      })
      setError('')
    } catch (err) {
      setError(err.message)
    } finally {
      setLedgerAccountEditSaving(false)
    }
  }

  const saveLedgerAccountChild = async (e) => {
    e.preventDefault()
    if (!canCreate || !ledgerAccountSelected || ledgerAccountSelected.level === 'detailed') return
    const code = ledgerAccountChildForm.code.trim()
    const name = ledgerAccountChildForm.name.trim()
    if (!code || !name) return

    setLedgerAccountChildSaving(true)
    try {
      const created = await saveAccountChild(api, ledgerAccountSelected, ledgerAccountChildForm)
      const childLevel = ledgerAccountSelected.level === 'general' ? 'subsidiary' : 'detailed'
      await refreshLedgerAfterAccountChange(childLevel, created)
      setLedgerAccountChildForm(EMPTY_CHART_CHILD)
      setLedgerAccountPanelTab('edit')
      setError('')
    } catch (err) {
      setError(err.message)
    } finally {
      setLedgerAccountChildSaving(false)
    }
  }

  const closeChartDetail = () => {
    setChartSelected(null)
    setChartEditForm(null)
    setChartChildForm(EMPTY_CHART_CHILD)
    setChartPanelTab('edit')
  }

  const openDetailFromTrial = async (row) => {
    const fromTab = activeTab
    setActiveTab('ledger')
    setDrillGeneral(null)
    setDrillSubsidiary(null)
    setDrillDetailed(null)
    setDetailLedger(null)

    if (fromTab === 'detailed-trial' && row.detailed_id) {
      const generalRow = ledgerGeneralRows.find((g) => g.account_id === row.account_id) || {
        account_id: row.account_id,
        account_code: String(row.account_code || '').split('-')[0] || '',
        account_name: '',
      }
      setDrillGeneral(generalRow)
      const subRows = await loadDrillSubsidiary(row.account_id)
      const subRow = subRows.find((s) => s.subsidiary_id === row.subsidiary_id) || {
        subsidiary_id: row.subsidiary_id,
        account_code: row.account_code,
        account_name: row.account_name,
      }
      setDrillSubsidiary(subRow)
      await loadDrillDetailed(row.subsidiary_id)
      setDrillDetailed(row)
      await fetchDetailLedger({ detailedId: String(row.detailed_id) })
    } else if (fromTab === 'subsidiary-trial' && row.subsidiary_id) {
      const generalRow = ledgerGeneralRows.find((g) => g.account_id === row.account_id) || {
        account_id: row.account_id,
        account_code: '',
        account_name: '',
      }
      setDrillGeneral(generalRow)
      await loadDrillSubsidiary(row.account_id)
      await selectDrillSubsidiary(row)
    } else if (row.account_id) {
      await selectDrillGeneral(row)
    }
  }

  const runTransferPreview = async (e) => {
    e?.preventDefault?.()
    const code = transferDocCode.trim()
    const num = transferDocNumber.trim()
    if (!code && !num) {
      setTransferError('کد یا شماره سند کارخانه را وارد کنید.')
      return
    }
    setTransferLoading(true)
    setTransferError('')
    setTransferSuccess('')
    setTransferPreview(null)
    try {
      const preview = await api.transferPreview({
        documentCode: code,
        documentNumber: num || undefined,
      })
      setTransferPreview(preview)
    } catch (err) {
      setTransferError(err.message)
    } finally {
      setTransferLoading(false)
    }
  }

  const runTransferDocument = async () => {
    if (!transferPreview?.can_transfer) return
    setTransferSaving(true)
    setTransferError('')
    setTransferSuccess('')
    try {
      const result = await api.transferDocument({
        document_code: transferPreview.factory_document_code,
      })
      setTransferSuccess(
        `سند ${result.factory_document_code} به اداری منتقل شد — سند اداری شماره ${formatNumber(result.office_document_number)} (${result.office_document_code})`,
      )
      setTransferPreview(null)
      setTransferDocCode('')
      setTransferDocNumber('')
    } catch (err) {
      setTransferError(err.message)
    } finally {
      setTransferSaving(false)
    }
  }

  const runExcelImport = async (e) => {
    e?.preventDefault?.()
    if (!importFile) {
      setImportError('فایل اکسل را انتخاب کنید.')
      return
    }
    setImportLoading(true)
    setImportError('')
    setImportSuccess('')
    setImportResult(null)
    try {
      const result = await api.importExcel(importFile, {
        dryRun: importDryRun,
        approve: true,
      })
      setImportResult(result)
      if (result.committed) {
        const stats = result.stats || {}
        setImportSuccess(
          `بارگذاری انجام شد: ${formatNumber(stats.subsidiaries_created || 0)} ${TERMS.subsidiaryAccount}، `
          + `${formatNumber(stats.details_created || 0)} ${TERMS.detailedAccount}، `
          + `${formatNumber(stats.entries_created || 0)} ${TERMS.entry}`,
        )
        setActiveTab('trial-balance')
        await refreshAll()
      } else if (result.dry_run) {
        setImportSuccess('اعتبارسنجی انجام شد — برای ذخیره، تیک «فقط اعتبارسنجی» را بردارید.')
      }
    } catch (err) {
      const report = err.data?.data || err.data
      if (report?.counts || report?.stats) setImportResult(report)
      setImportError(err.message || 'خطا در آپلود فایل')
    } finally {
      setImportLoading(false)
    }
  }

  const reportMeta = useMemo(() => {
    const from = (trialDateFrom || '').trim()
    const to = (trialDateTo || '').trim()
    if (!from && !to) return 'همه تاریخ‌ها'
    if (from && to) return `${TERMS.dateFrom} ${formatDate(from)} — ${TERMS.dateTo} ${formatDate(to)}`
    if (from) return `${TERMS.dateFrom} ${formatDate(from)}`
    return `${TERMS.dateTo} ${formatDate(to)}`
  }, [trialDateFrom, trialDateTo])

  useEffect(() => {
    if (TRIAL_TABS.includes(activeTab)) {
      setTrialTextFilter(EMPTY_TRIAL_BALANCE_FILTER)
    }
    if (activeTab !== 'ledger') {
      ledgerQueryRef.current = ''
    }
  }, [activeTab])

  const trialFilterConfig = TRIAL_BALANCE_FILTERS[activeTab]

  const filteredTrialRows = useMemo(
    () => (TRIAL_TABS.includes(activeTab) ? applyTrialBalanceFilter(trialRows, trialTextFilter) : trialRows),
    [activeTab, trialRows, trialTextFilter],
  )

  const trialFilterOn = trialBalanceFilterActive(trialTextFilter)

  const displayTrialTotals = useMemo(() => {
    if (!TRIAL_TABS.includes(activeTab) || !trialFilterOn) return trialTotals
    return sumTrialBalanceTotals(filteredTrialRows)
  }, [activeTab, trialFilterOn, filteredTrialRows, trialTotals])

  return (
    <div className="page accounting-page">
      <div className="accounting-toolbar">
        {canCreate && activeTab === 'documents' && docView === 'form' && docCanEdit && (
          <Button type="button" onClick={saveDocument} disabled={docSaving || !docTotals.hasAmounts}>
            {docSaving ? 'در حال ثبت…' : docEditCode ? 'ذخیره تغییرات' : `ثبت ${TERMS.document}`}
          </Button>
        )}
        {canCreate && activeTab === 'documents' && docView === 'list' && (
          <Button type="button" onClick={openNewDocument}>+ سند جدید</Button>
        )}
        {activeTab === 'documents' && docView === 'form' && (
          <Button type="button" variant="ghost" onClick={() => { resetDocForm(); setDocView('list') }}>
            بازگشت به فهرست
          </Button>
        )}
        {canCreate && activeTab === 'upload-excel' && (
          <Button type="button" onClick={runExcelImport} disabled={importLoading || !importFile}>
            {importLoading ? 'در حال پردازش…' : importDryRun ? 'اعتبارسنجی فایل' : 'بارگذاری و ثبت'}
          </Button>
        )}
        {(canCreate || canEditChart) && activeTab === 'ledger' && (
          <Button
            type="button"
            onClick={() => {
              if (activeLedgerCard === 'ledger') {
                openLedgerAccountPanel('document')
              } else if (ledgerAccountSelection && ledgerAccountSelection.level !== 'detailed') {
                openLedgerAccountPanel('add')
              } else {
                openLedgerAccountPanel('edit')
              }
            }}
          >
            {ledgerAccountPanelOpen ? 'پنل ساخت' : '+ ساخت حساب / سند'}
          </Button>
        )}
      </div>

      <div className="accounting-tabs">
        {visibleTabs.map((tab) => (
          <button
            key={tab.id}
            type="button"
            className={`accounting-tab ${activeTab === tab.id ? 'active' : ''}`}
            onClick={() => setActiveTab(tab.id)}
          >
            {tab.label}
          </button>
        ))}
      </div>

      {TRIAL_TABS.includes(activeTab) && trialFilterConfig && (
        <Card title={trialFilterConfig.title} className="section-record-filter accounting-section-filter">
          <TrialBalanceFilterPanel
            codeLabel={trialFilterConfig.codeLabel}
            nameLabel={trialFilterConfig.nameLabel}
            value={trialTextFilter}
            onChange={setTrialTextFilter}
            onReset={() => setTrialTextFilter(EMPTY_TRIAL_BALANCE_FILTER)}
            shownCount={filteredTrialRows.length}
            totalCount={trialRows.length}
          />
        </Card>
      )}

      {activeTab === 'ledger' && (
        <Card title={LEDGER_DRILL_FILTER.title} className="section-record-filter accounting-section-filter">
          <TrialBalanceFilterPanel
            codeLabel={LEDGER_DRILL_FILTER.codeLabel}
            nameLabel={LEDGER_DRILL_FILTER.nameLabel}
            value={ledgerTextFilter}
            onChange={setLedgerTextFilter}
            onReset={() => setLedgerTextFilter(EMPTY_TRIAL_BALANCE_FILTER)}
            shownCount={filteredLedgerGeneralRows.length}
            totalCount={ledgerGeneralRows.length}
          />
          {ledgerFilterOn && (ledgerFilterCounts.subsidiary.shown !== ledgerFilterCounts.subsidiary.total
            || ledgerFilterCounts.detailed.shown !== ledgerFilterCounts.detailed.total) && (
            <p className="record-filter-count muted ledger-drill-filter-meta">
              {drillGeneral && ledgerFilterCounts.subsidiary.total > 0 && (
                <span>
                  معین: <strong>{formatNumber(ledgerFilterCounts.subsidiary.shown)}</strong>
                  {' '}از {formatNumber(ledgerFilterCounts.subsidiary.total)}
                  {' · '}
                </span>
              )}
              {drillSubsidiary && ledgerFilterCounts.detailed.total > 0 && (
                <span>
                  تفصیلی: <strong>{formatNumber(ledgerFilterCounts.detailed.shown)}</strong>
                  {' '}از {formatNumber(ledgerFilterCounts.detailed.total)}
                </span>
              )}
            </p>
          )}
        </Card>
      )}

      {[...TRIAL_TABS, 'ledger', 'documents'].includes(activeTab) && (
        <FilterBar>
          <Field label={TERMS.accountGroup}>
            <Select value={classFilter} onChange={setClassFilter} options={ACCOUNT_CLASS_OPTIONS} placeholder="همه" />
          </Field>
          {(TRIAL_TABS.includes(activeTab) || activeTab === 'ledger') && (
            <>
              <Field label={TERMS.dateFrom}>
                <PersianDateInput
                  value={trialDateFrom}
                  onChange={setTrialDateFrom}
                  placeholder={TERMS.dateFrom}
                  maxIso={trialDateTo || undefined}
                  onClear={() => setTrialDateFrom('')}
                  clearLabel="پاک کردن"
                />
              </Field>
              <Field label={TERMS.dateTo}>
                <PersianDateInput
                  value={trialDateTo}
                  onChange={setTrialDateTo}
                  placeholder={TERMS.dateTo}
                  minIso={trialDateFrom || undefined}
                  onClear={() => setTrialDateTo('')}
                  clearLabel="پاک کردن"
                />
              </Field>
            </>
          )}
        </FilterBar>
      )}

      {error && <div className="alert-error">{error}</div>}

      {TRIAL_TABS.includes(activeTab) && (
        <Card title={`${ACCOUNTING_TABS.find((t) => t.id === activeTab)?.label} — ${reportMeta}`}>
          <TrialBalanceTable
            rows={filteredTrialRows}
            totals={displayTrialTotals}
            loading={trialLoading}
            onRowClick={openDetailFromTrial}
          />
          <p className="accounting-footer-summary muted">
            {formatNumber(filteredTrialRows.length)} حساب
            {trialFilterOn && filteredTrialRows.length !== trialRows.length
              ? ` (از ${formatNumber(trialRows.length)})`
              : ''}
          </p>
        </Card>
      )}

      {activeTab === 'documents' && docView === 'list' && (
        <Card title={ACCOUNTING_MENU.documents}>
          <FilterBar>
            <Field label="جستجو">
              <input
                className="search-input"
                value={docListSearch}
                onChange={(e) => setDocListSearch(e.target.value)}
                placeholder="شرح، کد یا شماره سند…"
              />
            </Field>
            <Field label="وضعیت تایید">
              <Select
                value={docListApproved}
                onChange={setDocListApproved}
                options={[
                  { value: '', label: 'همه' },
                  { value: 'true', label: 'تایید شده' },
                  { value: 'false', label: 'در انتظار' },
                ]}
                placeholder="همه"
              />
            </Field>
          </FilterBar>
          {docListLoading ? (
            <div className="loading">در حال بارگذاری…</div>
          ) : !docListRows.length ? (
            <EmptyState text="سندی یافت نشد." />
          ) : (
            <>
              <div className="table-wrap accounting-ledger-wrap accounting-doc-list-table-desktop">
                <table className="table accounting-ledger-table">
                  <thead>
                    <tr>
                      <th>{TERMS.documentNumber}</th>
                      <th>تاریخ</th>
                      <th>کد سند</th>
                      <th>{TERMS.description}</th>
                      <th>{TERMS.debit}</th>
                      <th>{TERMS.credit}</th>
                      <th>ردیف</th>
                      <th>وضعیت</th>
                      <th>عملیات</th>
                    </tr>
                  </thead>
                  <tbody>
                    {docListRows.map((doc) => (
                      <tr key={doc.document_code}>
                        <td>{doc.document_number ? formatNumber(doc.document_number) : '—'}</td>
                        <td>{doc.entry_date ? formatDate(doc.entry_date) : '—'}</td>
                        <td><strong>{doc.document_code}</strong></td>
                        <td className="text-cell">
                          {doc.description}
                          {doc.is_transferred && (
                            <span className="accounting-transfer-badge" title={doc.office_document_code || ''}>
                              {' '}منتقل‌شده
                            </span>
                          )}
                          {doc.has_system_entries && (
                            <span className="muted small"> (سیستمی)</span>
                          )}
                        </td>
                        <td>{formatRial(doc.total_debit)}</td>
                        <td>{formatRial(doc.total_credit)}</td>
                        <td>{formatNumber(doc.line_count)}</td>
                        <td>
                          {doc.is_approved ? '✓ تایید' : '○ در انتظار'}
                          {!doc.balanced && <span className="doc-unbalanced"> · {TERMS.unbalanced}</span>}
                        </td>
                        <td className="ledger-entry-actions">
                          <button type="button" className="link" onClick={() => openEditDocument(doc.document_code)} title="مشاهده/ویرایش">✎</button>
                          {canDelete && !doc.is_transferred && !doc.has_system_entries && (
                            <button type="button" className="link danger" onClick={() => deleteDocumentByCode(doc.document_code)} title="حذف">×</button>
                          )}
                          {canApprove && !doc.is_transferred && (
                            doc.is_approved ? (
                              <button type="button" className="link" onClick={() => toggleDocumentApproval(doc, false)} title="لغو تایید">↩</button>
                            ) : (
                              <button type="button" className="link" onClick={() => toggleDocumentApproval(doc, true)} title="تایید">✓</button>
                            )
                          )}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
              <div className="accounting-doc-list-cards-mobile">
                {docListRows.map((doc) => (
                  <div key={doc.document_code} className="m-card accounting-doc-list-card">
                    <div className="m-card-head accounting-entry-card-head">
                      <div>
                        <strong>{doc.document_code}</strong>
                        <p className="accounting-entry-meta muted">
                          {TERMS.documentNumber}: {doc.document_number ? formatNumber(doc.document_number) : '—'}
                          {' · '}
                          {doc.entry_date ? formatDate(doc.entry_date) : '—'}
                        </p>
                      </div>
                      <span className={`accounting-doc-list-status${doc.is_approved ? '' : ' muted'}`}>
                        {doc.is_approved ? '✓ تایید' : '○ در انتظار'}
                      </span>
                    </div>
                    <p className="accounting-entry-desc">{doc.description}</p>
                    {(doc.is_transferred || doc.has_system_entries || !doc.balanced) && (
                      <p className="accounting-entry-meta muted">
                        {doc.is_transferred && (
                          <span className="accounting-transfer-badge" title={doc.office_document_code || ''}>
                            منتقل‌شده
                          </span>
                        )}
                        {doc.has_system_entries && <span> (سیستمی)</span>}
                        {!doc.balanced && <span className="doc-unbalanced"> · {TERMS.unbalanced}</span>}
                      </p>
                    )}
                    <div className="m-card-grid">
                      <div><span className="muted">{TERMS.debit}</span><strong>{formatRial(doc.total_debit)}</strong></div>
                      <div><span className="muted">{TERMS.credit}</span><strong>{formatRial(doc.total_credit)}</strong></div>
                      <div><span className="muted">ردیف</span><strong>{formatNumber(doc.line_count)}</strong></div>
                    </div>
                    <div className="accounting-doc-list-actions ledger-entry-actions">
                      <button type="button" className="btn btn-ghost btn-sm" onClick={() => openEditDocument(doc.document_code)} title="مشاهده/ویرایش">✎ ویرایش</button>
                      {canDelete && !doc.is_transferred && !doc.has_system_entries && (
                        <button type="button" className="btn btn-ghost btn-sm danger" onClick={() => deleteDocumentByCode(doc.document_code)} title="حذف">× حذف</button>
                      )}
                      {canApprove && !doc.is_transferred && (
                        doc.is_approved ? (
                          <button type="button" className="btn btn-ghost btn-sm" onClick={() => toggleDocumentApproval(doc, false)} title="لغو تایید">↩ لغو تایید</button>
                        ) : (
                          <button type="button" className="btn btn-ghost btn-sm" onClick={() => toggleDocumentApproval(doc, true)} title="تایید">✓ تایید</button>
                        )
                      )}
                    </div>
                  </div>
                ))}
              </div>
              <div className="accounting-pagination">
                <Button type="button" variant="ghost" disabled={docListOffset <= 0} onClick={() => loadDocumentList(Math.max(0, docListOffset - DOC_LIST_LIMIT))}>
                  قبلی
                </Button>
                <span className="muted">
                  {formatNumber(docListOffset + 1)}–{formatNumber(Math.min(docListOffset + DOC_LIST_LIMIT, docListTotal))} از {formatNumber(docListTotal)}
                </span>
                <Button type="button" variant="ghost" disabled={docListOffset + DOC_LIST_LIMIT >= docListTotal} onClick={() => loadDocumentList(docListOffset + DOC_LIST_LIMIT)}>
                  بعدی
                </Button>
              </div>
            </>
          )}
        </Card>
      )}

      {activeTab === 'documents' && docView === 'form' && (
        <Card title={docEditCode ? (docCanEdit ? `ویرایش ${TERMS.document}` : `مشاهده ${TERMS.document}`) : ACCOUNTING_MENU.documents}>
          {!docCanEdit && docEditCode && (
            <div className="alert-error">این سند قابل ویرایش نیست (سیستمی یا منتقل‌شده).</div>
          )}
          {docSuccess && <div className="alert-success">{docSuccess}</div>}
          {docError && <div className="alert-error">{docError}</div>}
          <form onSubmit={saveDocument} className="form accounting-doc-form">
            <div className="accounting-doc-header form-grid-2">
              <Field label={TERMS.attachCode}>
                <input
                  className="attach-code-input"
                  value={docHeader.attach_code}
                  onChange={(e) => setDocHeader({ ...docHeader, attach_code: e.target.value })}
                  placeholder="اختیاری"
                />
              </Field>
              <Field label={TERMS.description}>
                <input
                  value={docHeader.description}
                  onChange={(e) => setDocHeader({ ...docHeader, description: e.target.value })}
                  placeholder={`${TERMS.description} ${TERMS.document}…`}
                  required
                />
              </Field>
              <Field label="تاریخ سند">
                <PersianDateInput
                  value={docHeader.entry_date}
                  onChange={(v) => setDocHeader({ ...docHeader, entry_date: v })}
                  placeholder="اختیاری — پیش‌فرض امروز"
                  onClear={() => setDocHeader({ ...docHeader, entry_date: '' })}
                  clearLabel="پاک کردن"
                />
              </Field>
              <Field label={TERMS.documentNumber}>
                <input
                  value={docHeader.document_number}
                  onChange={(e) => setDocHeader({ ...docHeader, document_number: e.target.value })}
                  placeholder="اختیاری — خودکار"
                  inputMode="numeric"
                />
              </Field>
            </div>
            <div className="table-wrap accounting-ledger-wrap accounting-doc-table-desktop">
              <table className="table accounting-ledger-table accounting-doc-table">
                <thead>
                  <tr>
                    <th>{TERMS.generalAccount}</th>
                    <th>{TERMS.subsidiaryAccount}</th>
                    <th>{TERMS.detailedAccount}</th>
                    <th>{TERMS.debit}</th>
                    <th>{TERMS.credit}</th>
                    <th />
                  </tr>
                </thead>
                <tbody>
                  {docLines.map((line, index) => (
                    <tr key={index}>
                      <td>
                        <Select
                          value={line.account_id}
                          onChange={(v) => changeDocLineGeneral(index, v)}
                          options={[{ value: '', label: '—' }, ...accountOptions]}
                          placeholder={TERMS.generalAccount}
                        />
                      </td>
                      <td>
                        <Select
                          value={line.subsidiary_id}
                          onChange={(v) => changeDocLineSubsidiary(index, v)}
                          options={[{ value: '', label: '—' }, ...subsidiaryOptions]}
                          placeholder={TERMS.subsidiaryAccount}
                        />
                      </td>
                      <td>
                        <Select
                          value={line.detailed_id}
                          onChange={(v) => changeDocLineDetailed(index, v)}
                          options={[{ value: '', label: '—' }, ...detailOptions]}
                          placeholder={TERMS.detailedAccount}
                        />
                      </td>
                      <td>
                        <MoneyInput min="0" value={line.debit} onChange={(e) => updateDocLine(index, 'debit', e.target.value)} unit={TERMS.currency} />
                      </td>
                      <td>
                        <MoneyInput min="0" value={line.credit} onChange={(e) => updateDocLine(index, 'credit', e.target.value)} unit={TERMS.currency} />
                      </td>
                      <td>
                        <button type="button" className="link danger" onClick={() => removeDocLine(index)}>×</button>
                      </td>
                    </tr>
                  ))}
                </tbody>
                <tfoot>
                  <tr className="ledger-totals-row">
                    <td colSpan={3}><strong>{TERMS.total}</strong></td>
                    <td>{formatRial(docTotals.debit)}</td>
                    <td>{formatRial(docTotals.credit)}</td>
                    <td>{docTotals.balanced ? <span className="doc-balanced">✓ {TERMS.balanced}</span> : <span className="doc-unbalanced">{TERMS.unbalanced}</span>}</td>
                  </tr>
                </tfoot>
              </table>
            </div>

            <div className="accounting-doc-cards-mobile">
              <div className="accounting-doc-header-mobile form">
                <Field label={TERMS.attachCode}>
                  <input
                    className="attach-code-input"
                    value={docHeader.attach_code}
                    onChange={(e) => setDocHeader({ ...docHeader, attach_code: e.target.value })}
                    placeholder="اختیاری"
                  />
                </Field>
                <Field label={TERMS.description}>
                  <input
                    value={docHeader.description}
                    onChange={(e) => setDocHeader({ ...docHeader, description: e.target.value })}
                    placeholder={`${TERMS.description} ${TERMS.document}…`}
                    required
                  />
                </Field>
              </div>
              {docLines.map((line, index) => (
                <div key={index} className="m-card accounting-doc-line-card">
                  <div className="m-card-head accounting-entry-card-head">
                    <strong>ردیف {formatNumber(index + 1)}</strong>
                    <button type="button" className="link danger" onClick={() => removeDocLine(index)}>حذف</button>
                  </div>
                  <div className="form accounting-doc-line-fields">
                    <Field label={TERMS.generalAccount}>
                      <Select
                        value={line.account_id}
                        onChange={(v) => changeDocLineGeneral(index, v)}
                        options={[{ value: '', label: '—' }, ...accountOptions]}
                        placeholder={TERMS.generalAccount}
                      />
                    </Field>
                    <Field label={TERMS.subsidiaryAccount}>
                      <Select
                        value={line.subsidiary_id}
                        onChange={(v) => changeDocLineSubsidiary(index, v)}
                        options={[{ value: '', label: '—' }, ...subsidiaryOptions]}
                        placeholder={TERMS.subsidiaryAccount}
                      />
                    </Field>
                    <Field label={TERMS.detailedAccount}>
                      <Select
                        value={line.detailed_id}
                        onChange={(v) => changeDocLineDetailed(index, v)}
                        options={[{ value: '', label: '—' }, ...detailOptions]}
                        placeholder={TERMS.detailedAccount}
                      />
                    </Field>
                    <div className="form-grid-2 entry-amount-grid">
                      <Field label={TERMS.debit}>
                        <MoneyInput min="0" value={line.debit} onChange={(e) => updateDocLine(index, 'debit', e.target.value)} unit={TERMS.currency} />
                      </Field>
                      <Field label={TERMS.credit}>
                        <MoneyInput min="0" value={line.credit} onChange={(e) => updateDocLine(index, 'credit', e.target.value)} unit={TERMS.currency} />
                      </Field>
                    </div>
                  </div>
                </div>
              ))}
              <div className={`m-card accounting-doc-mobile-totals ${docTotals.balanced ? 'doc-balanced' : 'doc-unbalanced'}`}>
                <div className="m-card-grid">
                  <div><span className="muted">{TERMS.debit}</span><strong>{formatRial(docTotals.debit)}</strong></div>
                  <div><span className="muted">{TERMS.credit}</span><strong>{formatRial(docTotals.credit)}</strong></div>
                </div>
                <p className="accounting-footer-summary">
                  {docTotals.balanced ? `✓ ${TERMS.balanced}` : TERMS.unbalanced}
                </p>
              </div>
            </div>

            <div className="form-actions-row">
              <Button type="button" variant="ghost" onClick={addDocLine}>+ ردیف</Button>
              <Button type="submit" disabled={docSaving || !docTotals.hasAmounts || !canCreate || (docEditCode && !docCanEdit)}>
                {docSaving ? 'در حال ثبت…' : docEditCode ? 'ذخیره تغییرات' : `ثبت ${TERMS.document}`}
              </Button>
            </div>
          </form>
        </Card>
      )}

      {activeTab === 'ledger' && (
        <LedgerWorkspace
          title={`${ACCOUNTING_MENU.ledger} — ${reportMeta}`}
          breadcrumb={ledgerBreadcrumb || null}
        >
          <div
            ref={ledgerLayoutRef}
            className={`ld-layout${ledgerAccountPanelOpen ? ' ld-layout--with-side' : ''}${drillLayoutHasMaximized ? ' ld-layout--maximized' : ''}`}
          >
            <div className="ld-main">
              {drillLayoutHasMaximized && (
                <div className="ld-rail">
                  {maximizedPanelId !== 'general' && renderGeneralPanel(true)}
                  {maximizedPanelId !== 'subsidiary' && renderSubsidiaryPanel(true)}
                  {maximizedPanelId !== 'detailed' && renderDetailedPanel(true)}
                  {maximizedPanelId !== 'ledger' && renderLedgerPanel(true)}
                </div>
              )}
              <div ref={drillStageWrapRef} className="ld-stage-wrap">
                {drillLayoutHasMaximized ? (
                  <div className="ld-stage ld-stage--single">
                    {maximizedPanelId === 'general' && renderGeneralPanel()}
                    {maximizedPanelId === 'subsidiary' && renderSubsidiaryPanel()}
                    {maximizedPanelId === 'detailed' && renderDetailedPanel()}
                    {maximizedPanelId === 'ledger' && renderLedgerPanel()}
                  </div>
                ) : (
                  renderDrillStageResizable()
                )}
              </div>
            </div>

            <LedgerSidePanel
              open={ledgerAccountPanelOpen}
              minimized={ledgerAccountPanelMinimized}
              width={ledgerAccountPanelWidth}
              title="ساخت / ویرایش"
              panelRef={ledgerAccountPanelRef}
              onToggleMinimize={() => setLedgerAccountPanelMinimized((v) => !v)}
              onClose={closeLedgerAccountPanel}
              onResize={resizeLedgerAccountPanel}
            >
              <LedgerSidePanelContent
                activeCard={activeLedgerCard}
                selection={ledgerAccountSelection}
                sideTab={ledgerSidePanelTab}
                onSideTabChange={setLedgerSidePanelTab}
                canCreate={canCreate}
                quickDocForm={quickDocForm}
                onQuickDocFormChange={setQuickDocForm}
                onSaveQuickDoc={saveQuickLedgerDocument}
                quickDocSaving={quickDocSaving}
                quickDocError={quickDocError}
                quickDocSuccess={quickDocSuccess}
                accountProps={{
                  selected: ledgerAccountSelected,
                  editForm: ledgerAccountEditForm,
                  onEditFormChange: setLedgerAccountEditForm,
                  childForm: ledgerAccountChildForm,
                  onChildFormChange: setLedgerAccountChildForm,
                  panelTab: ledgerAccountPanelTab,
                  onPanelTabChange: setLedgerAccountPanelTab,
                  onSaveEdit: saveLedgerAccountEdit,
                  onSaveChild: saveLedgerAccountChild,
                  editSaving: ledgerAccountEditSaving,
                  childSaving: ledgerAccountChildSaving,
                  canCreate,
                  canEdit: canEditChart,
                }}
              />
            </LedgerSidePanel>
          </div>
        </LedgerWorkspace>
      )}

      {activeTab === 'chart-of-accounts' && (
        <Card title={ACCOUNTING_MENU['chart-of-accounts']} className="chart-of-accounts-card">
          <div className="chart-of-accounts-layout">
            <div className="chart-of-accounts-main">
              <FilterBar>
                <Field label="جستجو">
                  <input
                    className="search-input"
                    value={chartSearch}
                    onChange={(e) => setChartSearch(e.target.value)}
                    placeholder="کد یا عنوان حساب کل، معین یا تفصیلی…"
                  />
                </Field>
              </FilterBar>

              {chartListEmpty ? (
                <EmptyState text="حسابی با این عبارت یافت نشد." />
              ) : (
                <div className="account-model-list">
                  {filteredChartGroups.map((group) => (
                    <div key={group.class} className="account-model-class">
                      <h3 className="account-model-class-title">{group.class_label}</h3>
                      {group.accounts.map(({ acc, subs }) => (
                        <section key={acc.id} className="account-model-panel">
                          <div
                            role="button"
                            tabIndex={0}
                            className={`account-model-head chart-account-head entry-row-clickable${chartRowSelected(chartSelected, 'general', acc.id) ? ' drill-row-selected' : ''}`}
                            onClick={() => selectChartAccount('general', acc)}
                            onKeyDown={(e) => {
                              if (e.key === 'Enter' || e.key === ' ') {
                                e.preventDefault()
                                selectChartAccount('general', acc)
                              }
                            }}
                          >
                            <strong>{acc.code} — {acc.name}</strong>
                            <span className="chart-account-head-actions">
                              <span className="muted small">{formatNumber(subs.length)} {TERMS.subsidiaryAccount}</span>
                              {canCreate && (
                                <button
                                  type="button"
                                  className="chart-quick-add"
                                  title={`افزودن ${TERMS.subsidiaryAccount}`}
                                  onClick={(e) => {
                                    e.stopPropagation()
                                    selectChartAccount('general', acc, { tab: 'add' })
                                  }}
                                >
                                  +
                                </button>
                              )}
                            </span>
                          </div>
                          {subs.map(({ sub, dets }) => (
                            <div key={sub.id} className="chart-subsidiary-block">
                              <div
                                role="button"
                                tabIndex={0}
                                className={`chart-subsidiary-title entry-row-clickable${chartRowSelected(chartSelected, 'subsidiary', sub.id) ? ' drill-row-selected' : ''}`}
                                onClick={() => selectChartAccount('subsidiary', sub)}
                                onKeyDown={(e) => {
                                  if (e.key === 'Enter' || e.key === ' ') {
                                    e.preventDefault()
                                    selectChartAccount('subsidiary', sub)
                                  }
                                }}
                              >
                                <strong>{sub.full_code} — {sub.name}</strong>
                                <span className="chart-account-head-actions">
                                  <span className="muted small">{formatNumber(dets.length)} {TERMS.detailedAccount}</span>
                                  {canCreate && (
                                    <button
                                      type="button"
                                      className="chart-quick-add"
                                      title={`افزودن ${TERMS.detailedAccount}`}
                                      onClick={(e) => {
                                        e.stopPropagation()
                                        selectChartAccount('subsidiary', sub, { tab: 'add' })
                                      }}
                                    >
                                      +
                                    </button>
                                  )}
                                </span>
                              </div>
                              {dets.length > 0 && (
                                <ul className="chart-detail-list">
                                  {dets.map((det) => (
                                    <li key={det.id}>
                                      <button
                                        type="button"
                                        className={`chart-detail-row${chartRowSelected(chartSelected, 'detailed', det.id) ? ' drill-row-selected' : ''}`}
                                        onClick={() => selectChartAccount('detailed', det)}
                                      >
                                        {det.full_code} — {det.name}
                                      </button>
                                    </li>
                                  ))}
                                </ul>
                              )}
                            </div>
                          ))}
                        </section>
                      ))}
                    </div>
                  ))}
                </div>
              )}
            </div>

            <aside ref={chartDetailRef} className="chart-account-detail">
              <AccountDetailPanel
                selected={chartSelected}
                editForm={chartEditForm}
                onEditFormChange={setChartEditForm}
                childForm={chartChildForm}
                onChildFormChange={setChartChildForm}
                panelTab={chartPanelTab}
                onPanelTabChange={setChartPanelTab}
                onSaveEdit={saveChartEdit}
                onSaveChild={saveChartChild}
                editSaving={chartEditSaving}
                childSaving={chartChildSaving}
                canCreate={canCreate}
                canEdit={canEditChart}
                showClose
                onClose={closeChartDetail}
                emptyHint={canCreate ? ' دکمه «+» کنار هر ردیف، مستقیم فرم افزودن را باز می‌کند.' : ''}
              />
            </aside>
          </div>
        </Card>
      )}

      {activeTab === 'upload-excel' && !canCreate && (
        <Card title={ACCOUNTING_MENU['upload-excel']}>
          <div className="alert-error">مجوز ثبت {TERMS.entry} برای بارگذاری فایل لازم است.</div>
        </Card>
      )}

      {activeTab === 'upload-excel' && canCreate && (
        <Card title={ACCOUNTING_MENU['upload-excel']}>
          {importSuccess && <div className="alert-success">{importSuccess}</div>}
          {importError && <div className="alert-error">{importError}</div>}
          <form onSubmit={runExcelImport} className="form accounting-import-form">
            <Field label="فایل اکسل (.xlsx)">
              <input
                type="file"
                accept=".xlsx,.xlsm"
                onChange={(e) => {
                  setImportFile(e.target.files?.[0] || null)
                  setImportResult(null)
                  setImportError('')
                  setImportSuccess('')
                }}
              />
              {importFile && <p className="muted small">{importFile.name}</p>}
            </Field>
            <label className="checkbox-field accounting-import-options">
              <input
                type="checkbox"
                checked={importDryRun}
                onChange={(e) => setImportDryRun(e.target.checked)}
              />
              فقط اعتبارسنجی (بدون ثبت)
            </label>
            <Button type="submit" disabled={importLoading || !importFile}>
              {importLoading ? 'در حال پردازش…' : importDryRun ? 'اعتبارسنجی فایل' : 'بارگذاری و ثبت'}
            </Button>
          </form>

          {importResult && (
            <div className="accounting-import-report">
              <h3 className="accounting-import-report-title">
                {importResult.committed
                  ? '✓ بارگذاری با موفقیت انجام شد'
                  : importResult.dry_run
                    ? 'گزارش اعتبارسنجی'
                    : 'بارگذاری انجام نشد'}
              </h3>
              <div className="accounting-import-meta">
                {importResult.metadata?.date_from && (
                  <span>{TERMS.dateFrom} {importResult.metadata.date_from}</span>
                )}
                {importResult.metadata?.date_to && (
                  <span>{TERMS.dateTo} {importResult.metadata.date_to}</span>
                )}
                {importResult.metadata?.doc_from != null && (
                  <span>{TERMS.docFrom} {formatNumber(importResult.metadata.doc_from)}</span>
                )}
                {importResult.metadata?.doc_to != null && (
                  <span>{TERMS.docTo} {formatNumber(importResult.metadata.doc_to)}</span>
                )}
              </div>
              <ul className="accounting-import-stats-list">
                <li>{TERMS.generalAccount}: {formatNumber(importResult.counts?.general_rows || 0)}</li>
                <li>{TERMS.subsidiaryAccount}: {formatNumber(importResult.counts?.subsidiary_rows || 0)}</li>
                <li>{TERMS.detailedAccount}: {formatNumber(importResult.counts?.detailed_rows || 0)}</li>
                <li>{TERMS.ledger}: {formatNumber(importResult.counts?.detail_ledger_rows || 0)} ردیف</li>
              </ul>
              {importResult.stats && Object.keys(importResult.stats).length > 0 && (
                <ul className="accounting-import-stats-list">
                  {importResult.stats.subsidiaries_created > 0 && <li>{formatNumber(importResult.stats.subsidiaries_created)} {TERMS.subsidiaryAccount} جدید</li>}
                  {importResult.stats.details_created > 0 && <li>{formatNumber(importResult.stats.details_created)} {TERMS.detailedAccount} جدید</li>}
                  {importResult.stats.entries_created > 0 && <li>{formatNumber(importResult.stats.entries_created)} {TERMS.entry} ثبت شد</li>}
                  {importResult.stats.entries_skipped > 0 && <li>{formatNumber(importResult.stats.entries_skipped)} {TERMS.entry} تکراری</li>}
                </ul>
              )}
              {importResult.trial_totals && (
                <p className={`accounting-footer-summary ${importResult.trial_totals.turnover_balanced ? 'doc-balanced' : 'doc-unbalanced'}`}>
                  {TERMS.turnover} {TERMS.trialBalance}: {TERMS.debit} {formatRial(importResult.trial_totals.turnover_debit)}
                  {' / '}
                  {TERMS.credit} {formatRial(importResult.trial_totals.turnover_credit)}
                  {importResult.trial_totals.turnover_balanced ? ` — ✓ ${TERMS.balanced}` : ` — ⚠ ${TERMS.unbalanced}`}
                </p>
              )}
              {importResult.detail_ledger_account && (
                <p className="muted">{TERMS.ledger}: {importResult.detail_ledger_account}</p>
              )}
              {importResult.warnings?.length > 0 && (
                <div className="accounting-import-warnings">
                  <strong>هشدارها</strong>
                  <ul>{importResult.warnings.map((w) => <li key={w}>{w}</li>)}</ul>
                </div>
              )}
              {importResult.errors?.length > 0 && (
                <div className="alert-error">
                  <ul>{importResult.errors.map((err) => <li key={err}>{err}</li>)}</ul>
                </div>
              )}
            </div>
          )}
        </Card>
      )}

      {activeTab === 'transfer-to-office' && canTransfer && (
        <Card title="انتقال سند به حسابداری اداری">
          <p className="muted small">
            سند کارخانه را با کد (F-*) یا شماره سند وارد کنید. انتقال فقط وقتی ممکن است که همه حساب‌های سند در هر دو دفتر مشترک باشند.
          </p>
          {transferSuccess && <div className="alert-success">{transferSuccess}</div>}
          {transferError && <div className="alert-error">{transferError}</div>}
          <form onSubmit={runTransferPreview} className="form accounting-transfer-form">
            <div className="form-grid-2">
              <Field label="کد سند کارخانه">
                <input
                  value={transferDocCode}
                  onChange={(e) => setTransferDocCode(e.target.value)}
                  placeholder="F-1404-001"
                />
              </Field>
              <Field label={TERMS.documentNumber}>
                <input
                  value={transferDocNumber}
                  onChange={(e) => setTransferDocNumber(e.target.value)}
                  placeholder="شماره سند"
                  inputMode="numeric"
                />
              </Field>
            </div>
            <div className="form-actions-row">
              <Button type="submit" disabled={transferLoading}>
                {transferLoading ? 'در حال بررسی…' : 'بررسی امکان انتقال'}
              </Button>
              {transferPreview?.can_transfer && (
                <Button type="button" onClick={runTransferDocument} disabled={transferSaving}>
                  {transferSaving ? 'در حال انتقال…' : 'انتقال به اداری'}
                </Button>
              )}
            </div>
          </form>

          {transferPreview && (
            <div className="accounting-transfer-preview">
              <p className="accounting-footer-summary">
                سند {transferPreview.factory_document_code}
                {transferPreview.document_number != null ? ` — شماره ${formatNumber(transferPreview.document_number)}` : ''}
                {' · '}
                {formatNumber(transferPreview.lines?.length || 0)} ردیف
              </p>
              {transferPreview.already_transferred && (
                <div className="alert-error">
                  این سند قبلاً منتقل شده است
                  {transferPreview.office_document_code ? ` (${transferPreview.office_document_code})` : ''}.
                </div>
              )}
              {transferPreview.unmappable_count > 0 && (
                <div className="alert-error">
                  حساب‌های غیرمشترک: {transferPreview.unmappable_accounts.join('، ')}
                </div>
              )}
              {transferPreview.can_transfer && (
                <p className="alert-success">همه ردیف‌ها قابل انتقال هستند.</p>
              )}
              {transferPreview.lines?.length > 0 && (
                <>
                  <div className="table-wrap accounting-transfer-table-desktop">
                    <table className="data-table">
                      <thead>
                        <tr>
                          <th>حساب</th>
                          <th>{TERMS.debit}</th>
                          <th>{TERMS.credit}</th>
                          <th>وضعیت</th>
                        </tr>
                      </thead>
                      <tbody>
                        {transferPreview.lines.map((line) => (
                          <tr key={line.entry_id}>
                            <td>{line.account_label}</td>
                            <td>{renderAmount(line.debit)}</td>
                            <td>{renderAmount(line.credit)}</td>
                            <td>{line.mappable ? '✓ مشترک' : line.error}</td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                  <div className="accounting-transfer-cards-mobile">
                    {transferPreview.lines.map((line) => (
                      <div key={line.entry_id} className="m-card accounting-transfer-line-card">
                        <p className="accounting-entry-desc"><strong>{line.account_label}</strong></p>
                        <div className="m-card-grid">
                          <div><span className="muted">{TERMS.debit}</span><strong>{renderAmount(line.debit)}</strong></div>
                          <div><span className="muted">{TERMS.credit}</span><strong>{renderAmount(line.credit)}</strong></div>
                          <div><span className="muted">وضعیت</span><strong>{line.mappable ? '✓ مشترک' : line.error}</strong></div>
                        </div>
                      </div>
                    ))}
                  </div>
                </>
              )}
            </div>
          )}
        </Card>
      )}

      <Modal title="ویرایش ردیف" open={Boolean(entryEdit)} onClose={() => setEntryEdit(null)}>
        {entryEdit && (
          <form onSubmit={saveEntryEdit} className="form">
            <Field label={TERMS.description}>
              <input
                value={entryEdit.description}
                onChange={(e) => setEntryEdit({ ...entryEdit, description: e.target.value })}
                required
              />
            </Field>
            <Field label="تاریخ">
              <PersianDateInput
                value={entryEdit.entry_date}
                onChange={(v) => setEntryEdit({ ...entryEdit, entry_date: v })}
                onClear={() => setEntryEdit({ ...entryEdit, entry_date: '' })}
                clearLabel="پاک کردن"
              />
            </Field>
            <div className="form-grid-2">
              <Field label={TERMS.debit}>
                <MoneyInput min="0" value={entryEdit.debit} onChange={(e) => setEntryEdit({ ...entryEdit, debit: e.target.value })} unit={TERMS.currency} />
              </Field>
              <Field label={TERMS.credit}>
                <MoneyInput min="0" value={entryEdit.credit} onChange={(e) => setEntryEdit({ ...entryEdit, credit: e.target.value })} unit={TERMS.currency} />
              </Field>
            </div>
            <Button type="submit" disabled={entryEditSaving}>{entryEditSaving ? '…' : 'ذخیره'}</Button>
          </form>
        )}
      </Modal>

      <Modal
        title={lineAccountPick?.title || 'انتخاب حساب'}
        open={Boolean(lineAccountPick)}
        onClose={() => finishLineAccountPick(null)}
      >
        {lineAccountPick?.message && <p className="accounting-line-pick-message">{lineAccountPick.message}</p>}
        <div className="accounting-line-pick-actions">
          {lineAccountPick?.options?.map((opt) => (
            <Button key={opt.key} type="button" variant="ghost" onClick={() => finishLineAccountPick(opt)}>
              {opt.label}
            </Button>
          ))}
        </div>
      </Modal>

    </div>
  )
}
