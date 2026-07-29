// صفحه حسابداری — مطابق ساختار اکسل (تراز / دفتر کل / ثبت سند / ایجاد حساب)

import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { accountingApi } from '../api/client'
import MoneyInput from '../components/MoneyInput'
import TrialBalanceFilterPanel, {
  applyTrialBalanceFilter,
  EMPTY_TRIAL_BALANCE_FILTER,
  sumTrialBalanceTotals,
  trialBalanceFilterActive,
} from '../components/TrialBalanceFilterPanel'
import { TRIAL_BALANCE_FILTERS } from '../config/recordFilterSections'
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

const EMPTY_CHART_CHILD = { code: '', name: '' }

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

const DEFAULT_DRILL_PANEL_LAYOUT = {
  general: 'normal',
  subsidiary: 'normal',
  detailed: 'normal',
  ledger: 'normal',
}

function DrillPanelShell({
  panelId,
  layoutMode = 'normal',
  onToggleMinimize,
  onToggleMaximize,
  title,
  hint,
  children,
  className = '',
}) {
  const minimized = layoutMode === 'minimized'
  const maximized = layoutMode === 'maximized'

  return (
    <section
      className={[
        'ledger-drill-panel',
        className,
        minimized ? 'ledger-drill-panel-minimized' : '',
        maximized ? 'ledger-drill-panel-maximized' : '',
      ].filter(Boolean).join(' ')}
    >
      <header className="ledger-drill-panel-head">
        <div className="ledger-drill-panel-title">
          <h3>{title}</h3>
          {hint && !minimized && <p className="muted small">{hint}</p>}
        </div>
        <div className="ledger-drill-panel-actions">
          <button
            type="button"
            className="ledger-drill-panel-btn"
            onClick={() => onToggleMinimize(panelId)}
            title={minimized ? 'باز کردن پنجره' : 'جمع کردن پنجره'}
            aria-label={minimized ? 'باز کردن پنجره' : 'جمع کردن پنجره'}
          >
            {minimized ? '+' : '−'}
          </button>
          <button
            type="button"
            className="ledger-drill-panel-btn"
            onClick={() => onToggleMaximize(panelId)}
            title={maximized ? 'بازگشت به نمای عادی' : 'بزرگ‌نمایی پنجره'}
            aria-label={maximized ? 'بازگشت به نمای عادی' : 'بزرگ‌نمایی پنجره'}
          >
            {maximized ? '⤡' : '⛶'}
          </button>
        </div>
      </header>
      {!minimized && <div className="ledger-drill-panel-body">{children}</div>}
    </section>
  )
}

function DrillTrialPanel({
  panelId,
  layoutMode,
  onToggleMinimize,
  onToggleMaximize,
  title,
  hint,
  rows,
  loading,
  selectedId,
  idKey,
  onSelect,
}) {
  return (
    <DrillPanelShell
      panelId={panelId}
      layoutMode={layoutMode}
      onToggleMinimize={onToggleMinimize}
      onToggleMaximize={onToggleMaximize}
      title={title}
      hint={hint}
    >
      {loading ? (
        <div className="loading">در حال بارگذاری…</div>
      ) : !rows.length ? (
        <EmptyState text="حسابی یافت نشد." />
      ) : (
        <>
          <div className="table-wrap ledger-drill-table-wrap accounting-drill-table-desktop">
            <table className="table ledger-drill-table">
              <thead>
                <tr>
                  <th>{TERMS.accountCode}</th>
                  <th>{TERMS.accountTitle}</th>
                  <th>{TERMS.balance}</th>
                </tr>
              </thead>
              <tbody>
                {rows.map((row) => {
                  const rowId = row[idKey]
                  const selected = selectedId != null && String(selectedId) === String(rowId)
                  const balance = row.balance_debit || row.balance_credit
                  const side = row.balance_debit ? TERMS.debit : TERMS.credit
                  return (
                    <tr
                      key={rowId || row.account_code}
                      className={`entry-row-clickable${selected ? ' drill-row-selected' : ''}`}
                      onClick={() => onSelect(row)}
                    >
                      <td><strong>{row.account_code}</strong></td>
                      <td className="text-cell">{row.account_name}</td>
                      <td>{balance ? `${renderAmount(balance)} (${side})` : '—'}</td>
                    </tr>
                  )
                })}
              </tbody>
            </table>
          </div>
          <div className="accounting-drill-cards-mobile">
            {rows.map((row) => {
              const rowId = row[idKey]
              const selected = selectedId != null && String(selectedId) === String(rowId)
              const balance = row.balance_debit || row.balance_credit
              const side = row.balance_debit ? TERMS.debit : TERMS.credit
              return (
                <button
                  key={rowId || row.account_code}
                  type="button"
                  className={`accounting-drill-card${selected ? ' drill-row-selected' : ''}`}
                  onClick={() => onSelect(row)}
                >
                  <strong>{row.account_code}</strong>
                  <span className="accounting-drill-card-name">{row.account_name}</span>
                  <span className="accounting-drill-card-balance">
                    {balance ? `${renderAmount(balance)} (${side})` : '—'}
                  </span>
                </button>
              )
            })}
          </div>
        </>
      )}
    </DrillPanelShell>
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

function DetailLedgerTable({ ledger, loading }) {
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
      <div className="detail-ledger-header">
        <p><span className="muted">{TERMS.generalAccount}:</span> {ledger.header.general_name}</p>
        <p><span className="muted">{TERMS.subsidiaryAccount}:</span> {ledger.header.subsidiary_name}</p>
        <p><span className="muted">{TERMS.detailedAccount}:</span> {ledger.header.detailed_code} — {ledger.header.detailed_name}</p>
        <p className="record-filter-count muted">
          <strong>{formatNumber(shown)}</strong> از {formatNumber(total)} ردیف
        </p>
      </div>
      <div className="table-wrap accounting-ledger-wrap accounting-table-desktop">
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
            </tr>
          </thead>
          <tbody>
            {filteredLines.length === 0 ? (
              <tr>
                <td colSpan={8} className="muted text-center">ردیفی با این فیلتر یافت نشد.</td>
              </tr>
            ) : (
              filteredLines.map((line, idx) => (
                <tr key={line.id || `opening-${idx}`}>
                  <td>{formatDate(line.entry_date)}</td>
                  <td>{line.document_number ? formatNumber(line.document_number) : '—'}</td>
                  <td>{line.attach_code || '—'}</td>
                  <td className="text-cell">{line.description}</td>
                  <td>{renderAmount(line.debit)}</td>
                  <td>{renderAmount(line.credit)}</td>
                  <td>{formatRial(line.balance)}</td>
                  <td>{line.balance_side_label}</td>
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
            <div className="m-card-grid">
              <div><span className="muted">{TERMS.debit}</span><strong>{renderAmount(line.debit)}</strong></div>
              <div><span className="muted">{TERMS.credit}</span><strong>{renderAmount(line.credit)}</strong></div>
              <div><span className="muted">{TERMS.balance}</span><strong>{formatRial(line.balance)}</strong></div>
            </div>
          </div>
        ))}
      </div>
    </>
  )
}

export default function Accounting() {
  const { user } = useAuth()
  const canCreate = hasPermission(user, 'create_accounting')
  const canEditChart = hasPermission(user, 'edit_accounting') || canCreate
  const [activeTab, setActiveTab] = useState('trial-balance')
  const accountingGuideKey = `accounting__${activeTab}`
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

  const [docHeader, setDocHeader] = useState({ attach_code: '', description: '' })
  const [docLines, setDocLines] = useState([{ ...EMPTY_DOC_LINE }, { ...EMPTY_DOC_LINE }])
  const [docSaving, setDocSaving] = useState(false)
  const [docError, setDocError] = useState('')
  const [docSuccess, setDocSuccess] = useState('')

  const [chartModal, setChartModal] = useState(null)
  const [chartForm, setChartForm] = useState({ code: '', name: '', account_id: '', subsidiary_id: '' })
  const [chartSaving, setChartSaving] = useState(false)
  const [chartSearch, setChartSearch] = useState('')
  const [chartSelected, setChartSelected] = useState(null)
  const [chartEditForm, setChartEditForm] = useState(null)
  const [chartEditSaving, setChartEditSaving] = useState(false)
  const [chartChildForm, setChartChildForm] = useState(EMPTY_CHART_CHILD)
  const [chartChildSaving, setChartChildSaving] = useState(false)

  const [lineAccountPick, setLineAccountPick] = useState(null)
  const lineAccountPickRef = useRef(null)

  const [importFile, setImportFile] = useState(null)
  const [importDryRun, setImportDryRun] = useState(false)
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

  const resolveLinePosting = async (line, rowNumber) => {
    const base = {
      description: docHeader.description.trim(),
      debit: Number(line.debit) || 0,
      credit: Number(line.credit) || 0,
      attach_code: docHeader.attach_code.trim(),
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
        accountingApi.accounts(),
        accountingApi.subsidiaries(),
        accountingApi.details(),
      ])
      setAccountGroups(accData.accounts || [])
      setSubsidiaries(subData.results || [])
      setDetails(detData.results || [])
    } catch {
      /* optional */
    }
  }, [])

  const loadTrialBalance = useCallback(async () => {
    const level = TRIAL_BALANCE_LEVEL[activeTab]
    if (!level) return
    setTrialLoading(true)
    try {
      const data = await accountingApi.trialBalance({
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
      const data = await accountingApi.trialBalance({
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
      const data = await accountingApi.detailLedger({
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
      const data = await accountingApi.trialBalance({
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
      const data = await accountingApi.trialBalance({
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

  const refreshAll = useCallback(async () => {
    await Promise.all([loadAccounts(), loadTrialBalance()])
    if (activeTab === 'ledger') await loadLedgerGeneral()
  }, [loadAccounts, loadTrialBalance, loadLedgerGeneral, activeTab])

  useEffect(() => { loadAccounts() }, [loadAccounts])
  useEffect(() => { loadTrialBalance() }, [loadTrialBalance])
  useEffect(() => {
    if (activeTab === 'ledger') {
      loadLedgerGeneral()
    }
  }, [activeTab, loadLedgerGeneral])

  const selectDrillGeneral = useCallback(async (row) => {
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
    setDrillSubsidiary(row)
    setDrillDetailed(null)
    setDetailLedger(null)
    const rows = await loadDrillDetailed(row.subsidiary_id)
    if (!rows.length) {
      await fetchDetailLedger({ subsidiaryId: String(row.subsidiary_id) })
    }
  }, [loadDrillDetailed, fetchDetailLedger])

  const selectDrillDetailed = useCallback(async (row) => {
    setDrillDetailed(row)
    await fetchDetailLedger({ detailedId: String(row.detailed_id) })
  }, [fetchDetailLedger])

  const drillLayoutHasMaximized = useMemo(
    () => Object.values(drillPanelLayout).some((mode) => mode === 'maximized'),
    [drillPanelLayout],
  )

  const toggleDrillPanelMinimize = useCallback((panelId) => {
    setDrillPanelLayout((prev) => {
      if (prev[panelId] === 'maximized') return prev
      return {
        ...prev,
        [panelId]: prev[panelId] === 'minimized' ? 'normal' : 'minimized',
      }
    })
  }, [])

  const toggleDrillPanelMaximize = useCallback((panelId) => {
    setDrillPanelLayout((prev) => {
      if (prev[panelId] === 'maximized') {
        return { ...DEFAULT_DRILL_PANEL_LAYOUT }
      }
      const next = { ...DEFAULT_DRILL_PANEL_LAYOUT }
      for (const key of Object.keys(next)) {
        next[key] = key === panelId ? 'maximized' : 'minimized'
      }
      return next
    })
  }, [])

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
        lines.push(await resolveLinePosting(line, rowNumber))
      }
      const result = await accountingApi.createDocument({
        description: docDescription,
        lines,
      })
      setDocHeader({ attach_code: '', description: '' })
      setDocLines([{ ...EMPTY_DOC_LINE }, { ...EMPTY_DOC_LINE }])
      const unbalancedNote =
        docTotals.debit !== docTotals.credit ? ` (${TERMS.unbalanced} — ${TERMS.debit} و ${TERMS.credit} برابر نیست.)` : ''
      setDocSuccess(`${TERMS.document} شماره ${formatNumber(result.document_number)} ثبت شد.${unbalancedNote}`)
      await refreshAll()
    } catch (err) {
      setDocError(err.message)
    } finally {
      setDocSaving(false)
    }
  }

  const saveChartAccount = async (e) => {
    e.preventDefault()
    setChartSaving(true)
    try {
      if (chartModal === 'subsidiary') {
        await accountingApi.createSubsidiary({
          account_id: Number(chartForm.account_id),
          code: chartForm.code.trim(),
          name: chartForm.name.trim(),
        })
      } else {
        await accountingApi.createDetailed({
          subsidiary_id: Number(chartForm.subsidiary_id),
          code: chartForm.code.trim(),
          name: chartForm.name.trim(),
        })
      }
      setChartModal(null)
      setChartForm({ code: '', name: '', account_id: '', subsidiary_id: '' })
      await loadAccounts()
    } catch (err) {
      setError(err.message)
    } finally {
      setChartSaving(false)
    }
  }

  const selectChartAccount = (level, record) => {
    setChartSelected({ level, id: record.id })
    setChartChildForm(EMPTY_CHART_CHILD)
    if (level === 'general') {
      setChartEditForm({
        code: record.code || '',
        name: record.name || '',
        is_active: record.is_active !== false,
        class_label: record.account_class_label || '',
        normal_balance: record.normal_balance,
      })
      return
    }
    if (level === 'subsidiary') {
      setChartEditForm({
        code: record.code || '',
        name: record.name || '',
        is_active: record.is_active !== false,
        full_code: record.full_code,
        general_name: record.general_name,
      })
      return
    }
    setChartEditForm({
      code: record.code || '',
      name: record.name || '',
      is_active: record.is_active !== false,
      full_code: record.full_code,
      subsidiary_name: record.subsidiary_name,
      general_name: record.general_name,
    })
  }

  const saveChartEdit = async (e) => {
    e.preventDefault()
    if (!chartSelected || !chartEditForm || !canEditChart) return
    setChartEditSaving(true)
    try {
      const payload = {
        name: chartEditForm.name.trim(),
        is_active: chartEditForm.is_active,
      }
      let updated
      if (chartSelected.level === 'general') {
        updated = await accountingApi.updateGeneralAccount(chartSelected.id, payload)
      } else {
        payload.code = chartEditForm.code.trim()
        if (chartSelected.level === 'subsidiary') {
          updated = await accountingApi.updateSubsidiary(chartSelected.id, payload)
        } else {
          updated = await accountingApi.updateDetailed(chartSelected.id, payload)
        }
      }
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
      let created
      if (chartSelected.level === 'general') {
        created = await accountingApi.createSubsidiary({
          account_id: chartSelected.id,
          code,
          name,
        })
        await loadAccounts()
        selectChartAccount('subsidiary', created)
      } else {
        created = await accountingApi.createDetailed({
          subsidiary_id: chartSelected.id,
          code,
          name,
        })
        await loadAccounts()
        selectChartAccount('detailed', created)
      }
      setError('')
    } catch (err) {
      setError(err.message)
    } finally {
      setChartChildSaving(false)
    }
  }

  const closeChartDetail = () => {
    setChartSelected(null)
    setChartEditForm(null)
    setChartChildForm(EMPTY_CHART_CHILD)
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
      const result = await accountingApi.importExcel(importFile, {
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
        {canCreate && activeTab === 'entry' && (
          <Button type="button" onClick={saveDocument} disabled={docSaving || !docTotals.hasAmounts}>
            {docSaving ? 'در حال ثبت…' : `ثبت ${TERMS.document}`}
          </Button>
        )}
        {canCreate && activeTab === 'chart-of-accounts' && (
          <>
            <Button type="button" onClick={() => setChartModal('subsidiary')}>+ {TERMS.subsidiaryAccount}</Button>
            <Button type="button" variant="ghost" onClick={() => setChartModal('detailed')}>+ {TERMS.detailedAccount}</Button>
          </>
        )}
        {canCreate && activeTab === 'upload-excel' && (
          <Button type="button" onClick={runExcelImport} disabled={importLoading || !importFile}>
            {importLoading ? 'در حال پردازش…' : importDryRun ? 'اعتبارسنجی فایل' : 'بارگذاری و ثبت'}
          </Button>
        )}
      </div>

      <div className="accounting-tabs">
        {ACCOUNTING_TABS.map((tab) => (
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

      {[...TRIAL_TABS, 'ledger'].includes(activeTab) && (
        <FilterBar>
          <Field label={TERMS.accountGroup}>
            <Select value={classFilter} onChange={setClassFilter} options={ACCOUNT_CLASS_OPTIONS} placeholder="همه" />
          </Field>
          {TRIAL_TABS.includes(activeTab) && (
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

      {activeTab === 'entry' && (
        <Card title={ACCOUNTING_MENU.entry}>
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
            </div>
            <p className="muted small accounting-doc-header-hint">
              تاریخ و {TERMS.documentNumber} به‌صورت خودکار ثبت می‌شود؛ ردیف‌ها فقط حساب و مبلغ دارند.
            </p>
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
              <Button type="submit" disabled={docSaving || !docTotals.hasAmounts || !canCreate}>
                {docSaving ? 'در حال ثبت…' : `ثبت ${TERMS.document}`}
              </Button>
            </div>
          </form>
        </Card>
      )}

      {activeTab === 'ledger' && (
        <Card title={`${ACCOUNTING_MENU.ledger} — ${reportMeta}`}>
          <div className={`ledger-drill-layout${drillLayoutHasMaximized ? ' ledger-drill-layout-has-maximized' : ''}`}>
            <DrillTrialPanel
              panelId="general"
              layoutMode={drillPanelLayout.general}
              onToggleMinimize={toggleDrillPanelMinimize}
              onToggleMaximize={toggleDrillPanelMaximize}
              title={ACCOUNTING_MENU['trial-balance']}
              hint="حساب کل را انتخاب کنید"
              rows={ledgerGeneralRows}
              loading={ledgerGeneralLoading}
              selectedId={drillGeneral?.account_id}
              idKey="account_id"
              onSelect={selectDrillGeneral}
            />
            {drillGeneral && (
              <DrillTrialPanel
                panelId="subsidiary"
                layoutMode={drillPanelLayout.subsidiary}
                onToggleMinimize={toggleDrillPanelMinimize}
                onToggleMaximize={toggleDrillPanelMaximize}
                title={ACCOUNTING_MENU['subsidiary-trial']}
                hint={drillGeneral.account_name}
                rows={drillSubsidiaryRows}
                loading={drillSubsidiaryLoading}
                selectedId={drillSubsidiary?.subsidiary_id}
                idKey="subsidiary_id"
                onSelect={selectDrillSubsidiary}
              />
            )}
            {drillSubsidiary && drillDetailedRows.length > 0 && (
              <DrillTrialPanel
                panelId="detailed"
                layoutMode={drillPanelLayout.detailed}
                onToggleMinimize={toggleDrillPanelMinimize}
                onToggleMaximize={toggleDrillPanelMaximize}
                title={ACCOUNTING_MENU['detailed-trial']}
                hint={drillSubsidiary.account_name}
                rows={drillDetailedRows}
                loading={drillDetailedLoading}
                selectedId={drillDetailed?.detailed_id}
                idKey="detailed_id"
                onSelect={selectDrillDetailed}
              />
            )}
            {(detailLedger || detailLoading) && (
              <DrillPanelShell
                panelId="ledger"
                layoutMode={drillPanelLayout.ledger}
                onToggleMinimize={toggleDrillPanelMinimize}
                onToggleMaximize={toggleDrillPanelMaximize}
                title={TERMS.ledger}
                hint={
                  drillDetailed
                    ? `${drillDetailed.account_code} — ${drillDetailed.account_name}`
                    : drillSubsidiary
                      ? `${drillSubsidiary.account_code} — ${drillSubsidiary.account_name}`
                      : drillGeneral
                        ? `${drillGeneral.account_code} — ${drillGeneral.account_name}`
                        : ''
                }
                className="ledger-drill-panel-ledger"
              >
                <DetailLedgerTable ledger={detailLedger} loading={detailLoading} />
              </DrillPanelShell>
            )}
          </div>
        </Card>
      )}

      {activeTab === 'chart-of-accounts' && (
        <Card title={ACCOUNTING_MENU['chart-of-accounts']}>
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
                            <span className="muted small">{formatNumber(subs.length)} {TERMS.subsidiaryAccount}</span>
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
                                <span className="muted small">{formatNumber(dets.length)} {TERMS.detailedAccount}</span>
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

            {chartSelected && chartEditForm && (
              <aside className="chart-account-detail">
                <h3 className="chart-account-detail-title">
                  {chartSelected.level === 'general' && TERMS.generalAccount}
                  {chartSelected.level === 'subsidiary' && TERMS.subsidiaryAccount}
                  {chartSelected.level === 'detailed' && TERMS.detailedAccount}
                </h3>
                <dl className="chart-account-detail-meta">
                  {chartEditForm.full_code && (
                    <>
                      <dt>کد کامل</dt>
                      <dd>{chartEditForm.full_code}</dd>
                    </>
                  )}
                  {chartEditForm.general_name && chartSelected.level !== 'general' && (
                    <>
                      <dt>{TERMS.generalAccount}</dt>
                      <dd>{chartEditForm.general_name}</dd>
                    </>
                  )}
                  {chartEditForm.subsidiary_name && (
                    <>
                      <dt>{TERMS.subsidiaryAccount}</dt>
                      <dd>{chartEditForm.subsidiary_name}</dd>
                    </>
                  )}
                  {chartEditForm.class_label && (
                    <>
                      <dt>طبقه</dt>
                      <dd>{chartEditForm.class_label}</dd>
                    </>
                  )}
                </dl>
                <form onSubmit={saveChartEdit} className="form chart-account-detail-form">
                  {chartSelected.level === 'general' ? (
                    <Field label={TERMS.accountCode}>
                      <input value={chartEditForm.code} readOnly disabled />
                    </Field>
                  ) : (
                    <Field label={TERMS.accountCode}>
                      <input
                        value={chartEditForm.code}
                        onChange={(e) => setChartEditForm({ ...chartEditForm, code: e.target.value })}
                        required
                        disabled={!canEditChart}
                      />
                    </Field>
                  )}
                  <Field label={TERMS.accountTitle}>
                    <input
                      value={chartEditForm.name}
                      onChange={(e) => setChartEditForm({ ...chartEditForm, name: e.target.value })}
                      required
                      disabled={!canEditChart}
                    />
                  </Field>
                  <label className="checkbox-field">
                    <input
                      type="checkbox"
                      checked={chartEditForm.is_active}
                      onChange={(e) => setChartEditForm({ ...chartEditForm, is_active: e.target.checked })}
                      disabled={!canEditChart}
                    />
                    فعال
                  </label>
                  {canEditChart ? (
                    <Button type="submit" disabled={chartEditSaving}>
                      {chartEditSaving ? 'در حال ذخیره…' : 'ذخیره تغییرات'}
                    </Button>
                  ) : (
                    <p className="muted small">برای ویرایش، مجوز «ویرایش حسابداری» لازم است.</p>
                  )}
                  <Button type="button" variant="ghost" onClick={closeChartDetail}>
                    بستن
                  </Button>
                </form>

                {canCreate && chartSelected.level !== 'detailed' && (
                  <div className="chart-account-detail-add">
                    <h4 className="chart-account-detail-add-title">
                      {chartSelected.level === 'general'
                        ? `افزودن ${TERMS.subsidiaryAccount}`
                        : `افزودن ${TERMS.detailedAccount}`}
                    </h4>
                    <form onSubmit={saveChartChild} className="form chart-account-detail-form">
                      <Field label={TERMS.accountCode}>
                        <input
                          value={chartChildForm.code}
                          onChange={(e) => setChartChildForm({ ...chartChildForm, code: e.target.value })}
                          required
                        />
                      </Field>
                      <Field label={TERMS.accountTitle}>
                        <input
                          value={chartChildForm.name}
                          onChange={(e) => setChartChildForm({ ...chartChildForm, name: e.target.value })}
                          required
                        />
                      </Field>
                      <Button type="submit" disabled={chartChildSaving}>
                        {chartChildSaving ? 'در حال ثبت…' : 'ثبت زیرمجموعه'}
                      </Button>
                    </form>
                  </div>
                )}
              </aside>
            )}
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

      <Modal title={chartModal === 'subsidiary' ? `افزودن ${TERMS.subsidiaryAccount}` : `افزودن ${TERMS.detailedAccount}`} open={Boolean(chartModal)} onClose={() => setChartModal(null)}>
        <form onSubmit={saveChartAccount} className="form">
          {chartModal === 'subsidiary' ? (
            <Field label={TERMS.generalAccount}>
              <Select value={chartForm.account_id} onChange={(v) => setChartForm({ ...chartForm, account_id: v })} options={accountOptions} required />
            </Field>
          ) : (
            <Field label={TERMS.subsidiaryAccount}>
              <Select value={chartForm.subsidiary_id} onChange={(v) => setChartForm({ ...chartForm, subsidiary_id: v })} options={subsidiaryOptions} required />
            </Field>
          )}
          <Field label={TERMS.accountCode}><input value={chartForm.code} onChange={(e) => setChartForm({ ...chartForm, code: e.target.value })} required /></Field>
          <Field label={TERMS.accountTitle}><input value={chartForm.name} onChange={(e) => setChartForm({ ...chartForm, name: e.target.value })} required /></Field>
          <Button type="submit" disabled={chartSaving}>{chartSaving ? '…' : 'ثبت'}</Button>
        </form>
      </Modal>
    </div>
  )
}
