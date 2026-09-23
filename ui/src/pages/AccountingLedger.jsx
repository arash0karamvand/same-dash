// صفحه دفتر کل — Workspace کاوش حساب و ریز گردش

import { useCallback, useEffect, useMemo, useState } from 'react'
import LedgerExplorer from '../components/accounting/LedgerExplorer'
import ReportFilters from '../components/accounting/ReportFilters'
import { AccountingPageHeader, AccountingSummary } from '../components/accounting/AccountingERP'
import LiveTBalance from '../components/accounting/LiveTBalance'
import { accountingApi } from '../api/client'
import { resultList } from '../api/accounting'
import { EmptyState } from '../components/ui'
import { formatDate, formatRial } from '../utils/format'
import { fromLegacy } from '../styles/tw'

const INITIAL_FILTERS = {
  accountClass: '',
  accountId: '',
  subsidiaryId: '',
  detailedId: '',
  dateFrom: '',
  dateTo: '',
  approvedOnly: true,
}

function LedgerLinesTable({ payload, loading }) {
  if (loading) return <div className={fromLegacy("loading")}>در حال بارگذاری گردش حساب…</div>
  const lines = payload?.lines || []
  if (!lines.length) return <EmptyState text="برای حساب انتخاب‌شده گردش ثبت نشده است." />

  const totals = lines.reduce((acc, line) => ({
    debit: acc.debit + Number(line.debit || 0),
    credit: acc.credit + Number(line.credit || 0),
  }), { debit: 0, credit: 0 })

  return (
    <div className="acct-card-stack is-compact">
      <div className="acct-ledger-column-head" aria-hidden="true">
        <span>سند و شرح</span>
        <span>تاریخ</span>
        <span className="is-number">بدهکار</span>
        <span className="is-number">بستانکار</span>
        <span className="is-number">مانده</span>
      </div>
      {lines.map((line) => (
        <div key={line.id} className="acct-line-card">
          <div>
            <strong className="acct-number">{line.document_number || line.document_code || '—'}</strong>
            <div className="acct-ledger-description">{line.description || '—'}</div>
          </div>
          <div>{formatDate(line.entry_date)}</div>
          <strong className={`acct-number${line.debit ? ' acct-debit' : ''}`}>{formatRial(line.debit || 0)}</strong>
          <strong className={`acct-number${line.credit ? ' acct-credit' : ''}`}>{formatRial(line.credit || 0)}</strong>
          <span>
            <strong className="acct-number">{formatRial(line.balance || 0)}</strong>
            <small style={{ display: 'block', color: 'var(--text-secondary)' }}>{line.balance_side_label || '—'}</small>
          </span>
        </div>
      ))}
      <LiveTBalance debit={totals.debit} credit={totals.credit} label="تراز آزمایشی لحظه‌ای گردش" compact />
    </div>
  )
}

export default function AccountingLedger() {
  const api = accountingApi
  const [filters, setFilters] = useState(INITIAL_FILTERS)
  const [accountGroups, setAccountGroups] = useState([])
  const [subsidiaries, setSubsidiaries] = useState([])
  const [details, setDetails] = useState([])
  const [generalRows, setGeneralRows] = useState([])
  const [subsidiaryRows, setSubsidiaryRows] = useState([])
  const [detailedRows, setDetailedRows] = useState([])
  const [selectedGeneral, setSelectedGeneral] = useState(null)
  const [selectedSubsidiary, setSelectedSubsidiary] = useState(null)
  const [selectedDetailed, setSelectedDetailed] = useState(null)
  const [ledgerPayload, setLedgerPayload] = useState(null)
  const [treeSearch, setTreeSearch] = useState('')
  const [loading, setLoading] = useState(false)
  const [loadingDetail, setLoadingDetail] = useState(false)

  const accountOptions = useMemo(() => accountGroups.flatMap((group) =>
    (group.accounts || []).map((account) => ({
      value: String(account.id),
      label: `${account.code} — ${account.name}`,
    }))), [accountGroups])

  const loadWorkspace = useCallback(async () => {
    setLoading(true)
    try {
      const [accounts, subs, dets, ledger] = await Promise.all([
        api.accounts(),
        api.subsidiaries(),
        api.details(),
        api.ledger({ ...filters, limit: 500 }),
      ])
      setAccountGroups(resultList(accounts))
      setSubsidiaries(resultList(subs))
      setDetails(resultList(dets))
      setGeneralRows(resultList(ledger))
    } finally {
      setLoading(false)
    }
  }, [api, filters])

  useEffect(() => {
    const timeoutId = setTimeout(loadWorkspace, 0)
    return () => clearTimeout(timeoutId)
  }, [loadWorkspace])

  const loadLedger = useCallback(async (selection) => {
    setLoadingDetail(true)
    try {
      setLedgerPayload(await api.detailLedger({
        accountId: selection.accountId,
        subsidiaryId: selection.subsidiaryId,
        detailedId: selection.detailedId,
        dateFrom: filters.dateFrom,
        dateTo: filters.dateTo,
        approvedOnly: filters.approvedOnly,
      }))
    } finally {
      setLoadingDetail(false)
    }
  }, [api, filters])

  const selectGeneral = async (row) => {
    setSelectedGeneral(row)
    setSelectedSubsidiary(null)
    setSelectedDetailed(null)
    const result = await api.trialBalance({ ...filters, level: 'subsidiary', accountId: row.account_id })
    setSubsidiaryRows(resultList(result))
    setDetailedRows([])
    await loadLedger({ accountId: row.account_id })
  }

  const selectSubsidiary = async (row) => {
    setSelectedSubsidiary(row)
    setSelectedDetailed(null)
    const result = await api.trialBalance({
      ...filters,
      level: 'detailed',
      accountId: row.account_id,
      subsidiaryId: row.subsidiary_id,
    })
    setDetailedRows(resultList(result))
    await loadLedger({ subsidiaryId: row.subsidiary_id })
  }

  const selectDetailed = async (row) => {
    setSelectedDetailed(row)
    await loadLedger({ detailedId: row.detailed_id })
  }

  const selectedLabel = selectedDetailed?.account_name
    || selectedSubsidiary?.account_name
    || selectedGeneral?.account_name
    || ''
  const lines = ledgerPayload?.lines || []
  const summary = lines.reduce((acc, line) => ({
    debit: acc.debit + Number(line.debit || 0),
    credit: acc.credit + Number(line.credit || 0),
  }), { debit: 0, credit: 0 })

  return (
    <div className={fromLegacy('accounting-ledger-page')} style={{ position: 'relative', zIndex: 1 }}>
      <AccountingPageHeader
        eyebrow="دفتر اداری"
        title="دفتر کل و گردش حساب"
        description="حساب را از درخت انتخاب کنید تا گردش، مانده و اسناد مرتبط نمایش داده شود."
      />

      <ReportFilters
        filters={filters}
        onChange={setFilters}
        accountOptions={accountOptions}
        showSubsidiary={false}
        onReset={() => setFilters(INITIAL_FILTERS)}
      />

      {selectedLabel && (
        <AccountingSummary items={[
          { label: 'حساب انتخابی', value: selectedLabel },
          { label: 'گردش بدهکار', value: formatRial(summary.debit) },
          { label: 'گردش بستانکار', value: formatRial(summary.credit) },
          { label: 'تعداد آرتیکل', value: lines.length.toLocaleString('fa-IR') },
        ]} />
      )}

      <LedgerExplorer
        accountGroups={accountGroups}
        subsidiaries={subsidiaries}
        details={details}
        ledgerGeneralRows={generalRows}
        drillSubsidiaryRows={subsidiaryRows}
        drillDetailedRows={detailedRows}
        drillGeneral={selectedGeneral}
        drillSubsidiary={selectedSubsidiary}
        drillDetailed={selectedDetailed}
        breadcrumb={selectedLabel}
        detailHint={selectedLabel ? `گردش حساب ${selectedLabel}` : ''}
        treeSearch={treeSearch}
        onTreeSearchChange={setTreeSearch}
        loadingGeneral={loading}
        loadingSubsidiary={loadingDetail}
        loadingDetailed={loadingDetail}
        onSelectGeneral={selectGeneral}
        onSelectSubsidiary={selectSubsidiary}
        onSelectDetailed={selectDetailed}
        ledgerPanel={<LedgerLinesTable payload={ledgerPayload} loading={loadingDetail} />}
      />
    </div>
  )
}
