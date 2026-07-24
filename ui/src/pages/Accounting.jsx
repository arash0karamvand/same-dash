// صفحه حسابداری — مطابق ساختار اکسل (تراز / دفتر کل / ثبت سند / طرح حساب)

import { useCallback, useEffect, useMemo, useState } from 'react'
import { accountingApi } from '../api/client'
import PersianDateInput from '../components/PersianDateInput'
import PersianMonthPicker from '../components/PersianMonthPicker'
import MoneyInput from '../components/MoneyInput'
import Select from '../components/Select'
import { Button, Card, EmptyState, Field, FilterBar, Modal } from '../components/ui'
import {
  ACCOUNTING_TABS,
  ACCOUNTING_MENU,
  ACCOUNT_CLASS_OPTIONS,
  TERMS,
  TRIAL_BALANCE_LEVEL,
} from '../config/accountingTerms'
import { useAuth } from '../context/AuthContext'
import { formatDate, formatNumber, formatRial } from '../utils/format'
import { hasPermission } from '../utils/permissions'
import { currentJalali, jalaliMonthToGregorian } from '../utils/jalali'

const TRIAL_TABS = ['trial-balance', 'subsidiary-trial', 'detailed-trial']

const EMPTY_DOC_LINE = {
  detailed_id: '',
  subsidiary_id: '',
  account_id: '',
  description: '',
  debit: '',
  credit: '',
  attach_code: '',
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

function renderAmount(value) {
  return value ? formatRial(value) : '—'
}

function TrialBalanceTable({ rows, totals, loading, onRowClick, selectedKey, getRowKey }) {
  if (loading) return <div className="loading">در حال بارگذاری…</div>
  if (!rows.length) return <EmptyState text="ردیفی یافت نشد." />

  const balanced = totals.turnover_balanced !== false

  return (
    <>
      <div className="table-wrap accounting-ledger-wrap">
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
        <div className="table-wrap ledger-drill-table-wrap">
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
      )}
    </DrillPanelShell>
  )
}

function DetailLedgerTable({ ledger, loading }) {
  if (loading) return <div className="loading">در حال بارگذاری…</div>
  if (!ledger) return <EmptyState text="حساب تفصیلی را انتخاب کنید." />

  return (
    <>
      <div className="detail-ledger-header">
        <p><span className="muted">{TERMS.generalAccount}:</span> {ledger.header.general_name}</p>
        <p><span className="muted">{TERMS.subsidiaryAccount}:</span> {ledger.header.subsidiary_name}</p>
        <p><span className="muted">{TERMS.detailedAccount}:</span> {ledger.header.detailed_code} — {ledger.header.detailed_name}</p>
      </div>
      <div className="table-wrap accounting-ledger-wrap">
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
          </thead>
          <tbody>
            {ledger.lines.map((line, idx) => (
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
            ))}
          </tbody>
        </table>
      </div>
    </>
  )
}

export default function Accounting() {
  const { user } = useAuth()
  const canCreate = hasPermission(user, 'create_accounting')
  const init = currentJalali()

  const [activeTab, setActiveTab] = useState('trial-balance')
  const [classFilter, setClassFilter] = useState('')
  const [monthMode, setMonthMode] = useState(false)
  const [jYear, setJYear] = useState(init.year)
  const [jMonth, setJMonth] = useState(init.month)
  const [error, setError] = useState('')

  const [accountGroups, setAccountGroups] = useState([])
  const [subsidiaries, setSubsidiaries] = useState([])
  const [details, setDetails] = useState([])

  const [trialRows, setTrialRows] = useState([])
  const [trialTotals, setTrialTotals] = useState({})
  const [trialLoading, setTrialLoading] = useState(false)

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

  const [docHeader, setDocHeader] = useState({ entry_date: '', document_number: '', description: '' })
  const [docLines, setDocLines] = useState([{ ...EMPTY_DOC_LINE }, { ...EMPTY_DOC_LINE }])
  const [docSaving, setDocSaving] = useState(false)
  const [docError, setDocError] = useState('')
  const [docSuccess, setDocSuccess] = useState('')

  const [chartModal, setChartModal] = useState(null)
  const [chartForm, setChartForm] = useState({ code: '', name: '', account_id: '', subsidiary_id: '' })
  const [chartSaving, setChartSaving] = useState(false)

  const [importFile, setImportFile] = useState(null)
  const [importDryRun, setImportDryRun] = useState(false)
  const [importLoading, setImportLoading] = useState(false)
  const [importResult, setImportResult] = useState(null)
  const [importError, setImportError] = useState('')
  const [importSuccess, setImportSuccess] = useState('')

  const dateRange = useMemo(() => {
    if (!monthMode) return {}
    const range = jalaliMonthToGregorian(jYear, jMonth)
    return { dateFrom: range.dateFrom, dateTo: range.dateTo }
  }, [monthMode, jYear, jMonth])

  const accountOptions = useMemo(() => buildAccountOptions(accountGroups), [accountGroups])
  const detailOptions = useMemo(
    () => details.map((d) => ({ value: String(d.id), label: `${d.full_code} — ${d.name}` })),
    [details],
  )
  const subsidiaryOptions = useMemo(
    () => subsidiaries.map((s) => ({ value: String(s.id), label: `${s.full_code} — ${s.name}` })),
    [subsidiaries],
  )


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
    return { debit, credit, balanced: debit === credit && debit > 0 }
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
    if (!docTotals.balanced) {
      setDocError(`${TERMS.entry} ${TERMS.unbalanced} — مجموع ${TERMS.debit} و ${TERMS.credit} باید برابر باشد.`)
      return
    }
    const lines = docLines
      .filter((line) => (Number(line.debit) || 0) > 0 || (Number(line.credit) || 0) > 0)
      .map((line) => ({
        detailed_id: line.detailed_id ? Number(line.detailed_id) : undefined,
        subsidiary_id: !line.detailed_id && line.subsidiary_id ? Number(line.subsidiary_id) : undefined,
        account_id: !line.detailed_id && !line.subsidiary_id && line.account_id
          ? Number(line.account_id)
          : undefined,
        description: line.description || docHeader.description,
        debit: Number(line.debit) || 0,
        credit: Number(line.credit) || 0,
        attach_code: line.attach_code,
      }))

    if (!lines.length) {
      setDocError('حداقل یک ردیف با مبلغ لازم است.')
      return
    }

    setDocSaving(true)
    try {
      const result = await accountingApi.createDocument({
        entry_date: docHeader.entry_date || undefined,
        document_number: docHeader.document_number ? Number(docHeader.document_number) : undefined,
        description: docHeader.description,
        lines,
      })
      setDocHeader({ entry_date: '', document_number: '', description: '' })
      setDocLines([{ ...EMPTY_DOC_LINE }, { ...EMPTY_DOC_LINE }])
      setDocSuccess(`${TERMS.document} شماره ${formatNumber(result.document_number)} ثبت شد.`)
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

  const reportMeta = monthMode
    ? `${TERMS.dateFrom} ${jYear}/${String(jMonth).padStart(2, '0')}/01`
    : 'همه تاریخ‌ها'

  return (
    <div className="page accounting-page">
      <div className="accounting-toolbar">
        {canCreate && activeTab === 'entry' && (
          <Button type="button" onClick={saveDocument} disabled={docSaving || !docTotals.balanced}>
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

      {[...TRIAL_TABS, 'ledger'].includes(activeTab) && (
        <FilterBar>
          <Field label={TERMS.accountGroup}>
            <Select value={classFilter} onChange={setClassFilter} options={ACCOUNT_CLASS_OPTIONS} placeholder="همه" />
          </Field>
          <Field label="بازه زمانی (شمسی)">
            <PersianMonthPicker
              year={monthMode ? jYear : null}
              month={monthMode ? jMonth : null}
              onChange={(y, m) => { setMonthMode(true); setJYear(y); setJMonth(m) }}
              onClear={() => setMonthMode(false)}
              placeholder="همه تاریخ‌ها"
            />
          </Field>
        </FilterBar>
      )}

      {error && <div className="alert-error">{error}</div>}

      {TRIAL_TABS.includes(activeTab) && (
        <Card title={`${ACCOUNTING_TABS.find((t) => t.id === activeTab)?.label} — ${reportMeta}`}>
          <p className="muted accounting-models-intro">
            {TERMS.accountCode} | {TERMS.accountTitle} | {TERMS.openingBalance} | {TERMS.turnover} | {TERMS.balance}
            {' — '}کلیک روی ردیف برای {TERMS.ledger}
          </p>
          <TrialBalanceTable
            rows={trialRows}
            totals={trialTotals}
            loading={trialLoading}
            onRowClick={openDetailFromTrial}
          />
          <p className="accounting-footer-summary muted">{formatNumber(trialRows.length)} حساب</p>
        </Card>
      )}

      {activeTab === 'entry' && (
        <Card title={ACCOUNTING_MENU.entry}>
          <p className="muted accounting-models-intro">
            {TERMS.entry} چندردیفی متوازن — اولویت: {TERMS.detailedAccount} → {TERMS.subsidiaryAccount} → {TERMS.generalAccount}
          </p>
          {docSuccess && <div className="alert-success">{docSuccess}</div>}
          {docError && <div className="alert-error">{docError}</div>}
          <form onSubmit={saveDocument} className="form">
            <div className="form-grid-3">
              <Field label={`${TERMS.dateFrom} (شمسی)`}>
                <PersianDateInput
                  value={docHeader.entry_date}
                  onChange={(v) => setDocHeader({ ...docHeader, entry_date: v })}
                  onClear={() => setDocHeader({ ...docHeader, entry_date: '' })}
                  placeholder="امروز"
                />
              </Field>
              <Field label={TERMS.documentNumber}>
                <input
                  value={docHeader.document_number}
                  onChange={(e) => setDocHeader({ ...docHeader, document_number: e.target.value })}
                  placeholder="خالی = خودکار"
                />
              </Field>
              <Field label={`${TERMS.description} کلی`}>
                <input
                  value={docHeader.description}
                  onChange={(e) => setDocHeader({ ...docHeader, description: e.target.value })}
                  placeholder={`${TERMS.description} ${TERMS.document}…`}
                />
              </Field>
            </div>
            <div className="table-wrap accounting-ledger-wrap">
              <table className="table accounting-ledger-table accounting-doc-table">
                <thead>
                  <tr>
                    <th>{TERMS.detailedAccount}</th>
                    <th>{TERMS.subsidiaryAccount}</th>
                    <th>{TERMS.generalAccount}</th>
                    <th>{TERMS.description}</th>
                    <th>{TERMS.attachCode}</th>
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
                          value={line.detailed_id}
                          onChange={(v) => updateDocLine(index, 'detailed_id', v)}
                          options={[{ value: '', label: '—' }, ...detailOptions]}
                          placeholder={TERMS.detailedAccount}
                        />
                      </td>
                      <td>
                        <Select
                          value={line.subsidiary_id}
                          onChange={(v) => updateDocLine(index, 'subsidiary_id', v)}
                          options={[{ value: '', label: '—' }, ...subsidiaryOptions]}
                          placeholder={TERMS.subsidiaryAccount}
                          disabled={Boolean(line.detailed_id)}
                        />
                      </td>
                      <td>
                        <Select
                          value={line.account_id}
                          onChange={(v) => updateDocLine(index, 'account_id', v)}
                          options={[{ value: '', label: '—' }, ...accountOptions]}
                          placeholder={TERMS.generalAccount}
                          disabled={Boolean(line.detailed_id || line.subsidiary_id)}
                        />
                      </td>
                      <td>
                        <input
                          value={line.description}
                          onChange={(e) => updateDocLine(index, 'description', e.target.value)}
                          placeholder="شرح…"
                        />
                      </td>
                      <td>
                        <input
                          className="attach-code-input"
                          value={line.attach_code}
                          onChange={(e) => updateDocLine(index, 'attach_code', e.target.value)}
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
                    <td colSpan={5}><strong>{TERMS.total}</strong></td>
                    <td>{formatRial(docTotals.debit)}</td>
                    <td>{formatRial(docTotals.credit)}</td>
                    <td>{docTotals.balanced ? <span className="doc-balanced">✓ {TERMS.balanced}</span> : <span className="doc-unbalanced">{TERMS.unbalanced}</span>}</td>
                  </tr>
                </tfoot>
              </table>
            </div>
            <div className="form-actions-row">
              <Button type="button" variant="ghost" onClick={addDocLine}>+ ردیف</Button>
              <Button type="submit" disabled={docSaving || !docTotals.balanced || !canCreate}>
                {docSaving ? 'در حال ثبت…' : `ثبت ${TERMS.document}`}
              </Button>
            </div>
          </form>
        </Card>
      )}

      {activeTab === 'ledger' && (
        <Card title={`${ACCOUNTING_MENU.ledger} — ${reportMeta}`}>
          <p className="muted accounting-models-intro">
            {TERMS.generalAccount} → {TERMS.subsidiaryAccount} → {TERMS.detailedAccount} → {TERMS.ledger}
            {' — '}روی هر سطح کلیک کنید؛ با دکمه‌های − و ⛶ هر پنجره را جمع یا بزرگ کنید.
          </p>
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
          <div className="account-model-list">
            {accountGroups.map((group) => (
              <div key={group.class} className="account-model-class">
                <h3 className="account-model-class-title">{group.class_label}</h3>
                {group.accounts.map((acc) => {
                  const subs = subsidiaries.filter((s) => s.account_id === acc.id)
                  return (
                    <section key={acc.id} className="account-model-panel">
                      <div className="account-model-head chart-account-head">
                        <strong>{acc.code} — {acc.name}</strong>
                        <span className="muted small">{formatNumber(subs.length)} {TERMS.subsidiaryAccount}</span>
                      </div>
                      {subs.map((sub) => {
                        const dets = details.filter((d) => d.subsidiary_id === sub.id)
                        return (
                          <div key={sub.id} className="chart-subsidiary-block">
                            <div className="chart-subsidiary-title">
                              <strong>{sub.full_code} — {sub.name}</strong>
                              <span className="muted small">{formatNumber(dets.length)} {TERMS.detailedAccount}</span>
                            </div>
                            {dets.length > 0 && (
                              <ul className="chart-detail-list">
                                {dets.map((det) => (
                                  <li key={det.id}>{det.full_code} — {det.name}</li>
                                ))}
                              </ul>
                            )}
                          </div>
                        )
                      })}
                    </section>
                  )
                })}
              </div>
            ))}
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
          <p className="muted accounting-models-intro">
            فایل اکسل باید شیت‌های «تراز کل»، «تراز معین»، «تراز تفصیلی» و «ریز نمونه» (اختیاری) داشته باشد.
          </p>
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
