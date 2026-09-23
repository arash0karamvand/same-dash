import { useMemo, useState } from 'react'
import { accountingApi } from '../api/client'
import {
  AccountingDataPanel,
  AccountingPageHeader,
  AccountingPagination,
  AccountingSummary,
} from '../components/accounting/AccountingERP'
import LiveTBalance from '../components/accounting/LiveTBalance'
import PersianDateInput from '../components/PersianDateInput'
import Select from '../components/Select'
import Icon from '../components/icons/Icon'
import { Button, EmptyState, Field, FilterBar, Modal } from '../components/ui'
import { formatDate, formatRial } from '../utils/format'
import { fromLegacy } from '../styles/tw'

const PAGE_SIZE = 50

const DOMAIN_OPTIONS = [
  { id: 'journal', label: 'اسناد', icon: 'receipt' },
  { id: 'event', label: 'سندزنی خودکار', icon: 'gear' },
  { id: 'inventory', label: 'موجودی', icon: 'package' },
  { id: 'receivable', label: 'دریافتنی', icon: 'users' },
  { id: 'payable', label: 'پرداختنی', icon: 'coins' },
]

const DOMAIN_LABELS = Object.fromEntries(DOMAIN_OPTIONS.map((item) => [item.id, item.label]))
const SEVERITY_LABELS = { critical: 'بحرانی', warning: 'هشدار', info: 'اطلاعاتی' }
const SEVERITY_TONES = { critical: 'danger', warning: 'warning', info: 'neutral' }

const INITIAL_FILTERS = {
  dateFrom: '',
  dateTo: '',
  domains: DOMAIN_OPTIONS.map((item) => item.id),
  severity: [],
  status: '',
  sourceModule: '',
  minDifference: '',
  search: '',
  blockingOnly: false,
}

function toggleValue(values, value) {
  return values.includes(value)
    ? values.filter((item) => item !== value)
    : [...values, value]
}

function referenceLabel(item) {
  const refs = item.refs || {}
  if (refs.document_code) return `سند ${refs.document_code}`
  if (refs.invoice_number) return `فاکتور ${refs.invoice_number}`
  if (refs.source_key) return `مرجع ${refs.source_key}`
  if (refs.supplier_id) return `تأمین‌کننده #${refs.supplier_id}`
  if (refs.material_id) return `متریال #${refs.material_id}`
  if (refs.sale_id) return `فروش #${refs.sale_id}`
  return 'کنترل سیستمی'
}

function amountRows(item) {
  const amounts = item.amounts || {}
  return [
    ['بدهکار', amounts.debit],
    ['بستانکار', amounts.credit],
    ['مانده دفتر', amounts.book],
    ['مانده زیرسیستم', amounts.subledger],
    ['اختلاف', amounts.difference],
  ].filter(([, value]) => value !== null && value !== undefined)
}

export default function AccountingControlCenter() {
  const [filters, setFilters] = useState(INITIAL_FILTERS)
  const [appliedFilters, setAppliedFilters] = useState(null)
  const [report, setReport] = useState(null)
  const [selectedItem, setSelectedItem] = useState(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')
  const [notice, setNotice] = useState('')

  const runScan = async (page = 1, nextFilters = filters) => {
    if (!nextFilters.dateFrom || !nextFilters.dateTo) {
      setError('برای اسکن کامل، تاریخ شروع و پایان را انتخاب کنید.')
      return
    }
    if (!nextFilters.domains.length) {
      setError('حداقل یک حوزه برای بررسی انتخاب کنید.')
      return
    }
    setLoading(true)
    setError('')
    setNotice('')
    try {
      const payload = await accountingApi.scanDiscrepancies({
        ...nextFilters,
        offset: (page - 1) * PAGE_SIZE,
        limit: PAGE_SIZE,
      })
      setReport(payload)
      setAppliedFilters({ ...nextFilters })
    } catch (err) {
      setError(err?.message || 'اسکن ناترازی انجام نشد.')
    } finally {
      setLoading(false)
    }
  }

  const currentPage = report
    ? Math.floor((report.pagination?.offset || 0) / (report.pagination?.limit || PAGE_SIZE)) + 1
    : 1

  const resetFilters = () => {
    setFilters(INITIAL_FILTERS)
    setAppliedFilters(null)
    setReport(null)
    setError('')
    setNotice('')
  }

  const exportReport = () => {
    if (!appliedFilters) return
    window.location.assign(accountingApi.discrepancyScanExportPath(appliedFilters))
  }

  const closePeriod = async () => {
    if (!report || report.summary?.blocking_count > 0) {
      setError('تا رفع موارد مسدودکننده امکان بستن دوره وجود ندارد.')
      return
    }
    const reason = window.prompt('شرح بستن دوره', 'کنترل ناترازی انجام شد و دوره تأیید است')
    if (!reason) return
    setLoading(true)
    setError('')
    try {
      await accountingApi.closePeriod({
        date_from: appliedFilters.dateFrom,
        date_to: appliedFilters.dateTo,
        reason,
      })
      setNotice('دوره با موفقیت بسته شد.')
    } catch (err) {
      setError(err?.message || 'بستن دوره انجام نشد.')
    } finally {
      setLoading(false)
    }
  }

  const summaryItems = useMemo(() => {
    if (!report) return []
    const summary = report.summary || {}
    return [
      { label: 'کل موارد', value: Number(summary.issue_count || 0).toLocaleString('fa-IR'), tone: summary.issue_count ? 'warning' : 'success' },
      { label: 'بحرانی', value: Number(summary.by_severity?.critical || 0).toLocaleString('fa-IR'), tone: summary.by_severity?.critical ? 'danger' : 'success' },
      { label: 'مسدودکننده', value: Number(summary.blocking_count || 0).toLocaleString('fa-IR'), tone: summary.blocking_count ? 'danger' : 'success' },
      { label: 'اختلاف گردش', value: formatRial(Math.abs(summary.difference || 0)), tone: summary.balanced ? 'success' : 'danger' },
    ]
  }, [report])

  return (
    <div className={fromLegacy('acct-control-center')}>
      <AccountingPageHeader
        eyebrow="کنترل داخلی و حسابرسی"
        title="اسکنر ناترازی حسابداری"
        description="اسناد، سندزنی خودکار، موجودی، دریافتنی‌ها و پرداختنی‌ها را در بازه انتخابی بررسی کنید. اسکن فقط گزارش می‌دهد و هیچ عددی را تغییر نمی‌دهد."
        meta={report?.meta && (
          <span>
            آخرین اسکن: {formatDate(report.meta.scanned_at)} · زمان اجرا {Number(report.meta.duration_ms || 0).toLocaleString('fa-IR')} میلی‌ثانیه
          </span>
        )}
      />

      <AccountingDataPanel
        title="تنظیمات اسکن"
        subtitle="حوزه و فیلترها را انتخاب کنید، سپس اسکن را اجرا کنید."
      >
        <FilterBar>
          <Field label="از تاریخ">
            <PersianDateInput
              value={filters.dateFrom}
              onChange={(value) => setFilters((current) => ({ ...current, dateFrom: value }))}
            />
          </Field>
          <Field label="تا تاریخ">
            <PersianDateInput
              value={filters.dateTo}
              minIso={filters.dateFrom || undefined}
              onChange={(value) => setFilters((current) => ({ ...current, dateTo: value }))}
            />
          </Field>
          <Field label="شدت">
            <Select
              value={filters.severity.join(',')}
              onChange={(value) => setFilters((current) => ({
                ...current,
                severity: value ? String(value).split(',') : [],
              }))}
              options={[
                { value: '', label: 'همه شدت‌ها' },
                { value: 'critical', label: 'فقط بحرانی' },
                { value: 'warning', label: 'فقط هشدار' },
                { value: 'critical,warning', label: 'بحرانی و هشدار' },
              ]}
            />
          </Field>
          <Field label="وضعیت">
            <Select
              value={filters.status}
              onChange={(value) => setFilters((current) => ({ ...current, status: value }))}
              options={[
                { value: '', label: 'همه وضعیت‌ها' },
                { value: 'draft', label: 'پیش‌نویس' },
                { value: 'pending_review', label: 'در انتظار بررسی سند' },
                { value: 'pending', label: 'رویداد در انتظار' },
                { value: 'failed', label: 'رویداد خطادار' },
                { value: 'posted', label: 'ثبت قطعی' },
              ]}
            />
          </Field>
          <Field label="مبدأ">
            <Select
              value={filters.sourceModule}
              onChange={(value) => setFilters((current) => ({ ...current, sourceModule: value }))}
              options={[
                { value: '', label: 'همه مبدأها' },
                { value: 'sales', label: 'فروش' },
                { value: 'factory', label: 'کارخانه' },
                { value: 'warehouse', label: 'انبار' },
                { value: 'manual', label: 'دستی' },
              ]}
            />
          </Field>
          <Field label="حداقل اختلاف (ریال)">
            <input
              className={fromLegacy('input')}
              type="number"
              min="0"
              value={filters.minDifference}
              onChange={(event) => setFilters((current) => ({ ...current, minDifference: event.target.value }))}
              placeholder="بدون حداقل"
            />
          </Field>
          <Field label="جستجو">
            <input
              className={fromLegacy('input')}
              value={filters.search}
              onChange={(event) => setFilters((current) => ({ ...current, search: event.target.value }))}
              placeholder="سند، مشتری، تأمین‌کننده…"
            />
          </Field>
        </FilterBar>

        <div className="acct-control-domain-picker">
          <span className="muted">حوزه‌های بررسی</span>
          <div className="acct-control-domain-list">
            {DOMAIN_OPTIONS.map((domain) => {
              const active = filters.domains.includes(domain.id)
              return (
                <button
                  key={domain.id}
                  type="button"
                  className={`acct-control-domain${active ? ' is-active' : ''}`}
                  onClick={() => setFilters((current) => ({
                    ...current,
                    domains: toggleValue(current.domains, domain.id),
                  }))}
                  aria-pressed={active}
                >
                  <Icon name={domain.icon} size={16} />
                  <span>{domain.label}</span>
                  {active && <Icon name="check" size={14} />}
                </button>
              )
            })}
          </div>
          <label className="acct-control-blocking-toggle">
            <input
              type="checkbox"
              checked={filters.blockingOnly}
              onChange={(event) => setFilters((current) => ({ ...current, blockingOnly: event.target.checked }))}
            />
            فقط موارد مسدودکننده بستن دوره
          </label>
        </div>

        <div className="acct-ledger-actions" style={{ justifyContent: 'flex-start', paddingTop: 12 }}>
          <Button variant="primary" onClick={() => runScan(1)} disabled={loading}>
            <Icon name="search" size={16} />
            {loading ? 'در حال اسکن…' : 'اجرای اسکن ناترازی'}
          </Button>
          <Button variant="secondary" onClick={resetFilters} disabled={loading}>
            <Icon name="x" size={16} />
            پاک کردن
          </Button>
          {report && (
            <>
              <Button variant="secondary" onClick={exportReport}>
                <Icon name="scroll" size={16} />
                خروجی CSV
              </Button>
              <Button
                variant="secondary"
                onClick={closePeriod}
                disabled={loading || report.summary?.blocking_count > 0}
              >
                <Icon name="lock" size={16} />
                بستن دوره
              </Button>
            </>
          )}
        </div>
      </AccountingDataPanel>

      {error && <div className="acct-inline-error">{error}</div>}
      {notice && <div className="acct-control-note">{notice}</div>}

      {!report && !loading && (
        <AccountingDataPanel>
          <EmptyState text="هنوز اسکنی اجرا نشده است. بازه و حوزه‌ها را انتخاب و «اجرای اسکن ناترازی» را بزنید." />
        </AccountingDataPanel>
      )}

      {report && (
        <>
          <AccountingSummary items={summaryItems} />

          <LiveTBalance
            debit={report.summary?.debit || 0}
            credit={report.summary?.credit || 0}
            label="کنترل گردش اسناد قطعی در بازه"
          />

          <AccountingDataPanel
            title="نتیجه کنترل‌های اصلی"
            subtitle="اختلاف‌های کل قطعی هستند؛ موارد تفصیلی بعضی حوزه‌ها به‌عنوان سرنخ رسیدگی نمایش داده می‌شوند."
          >
            <div className="acct-control-grid">
              {(report.controls || []).map((control) => (
                <article key={control.key} className={`acct-control-check${control.ok ? ' is-ok' : ' is-error'}`}>
                  <Icon name={control.ok ? 'check' : 'warning'} size={17} />
                  <div>
                    <strong>{control.label}</strong>
                    <p>
                      {control.ok
                        ? 'بدون مغایرت'
                        : `اختلاف ${formatRial(Math.abs(control.difference || 0))}`}
                    </p>
                    {!control.ok && control.book != null && (
                      <small>
                        دفتر {formatRial(control.book)} · زیرسیستم {formatRial(control.subledger)}
                      </small>
                    )}
                  </div>
                </article>
              ))}
            </div>
          </AccountingDataPanel>

          <AccountingDataPanel title="خلاصه حوزه‌ها" subtitle="برای محدودکردن اسکن بعدی، تعداد موارد هر حوزه را ببینید.">
            <div className="acct-control-grid">
              {DOMAIN_OPTIONS.map((domain) => {
                const group = (report.groups || []).find((item) => item.domain === domain.id)
                return (
                  <article key={domain.id} className={`acct-control-check${group?.count ? ' is-error' : ' is-ok'}`}>
                    <Icon name={group?.count ? 'warning' : 'check'} size={17} />
                    <div>
                      <strong>{domain.label}</strong>
                      <p>{Number(group?.count || 0).toLocaleString('fa-IR')} مورد</p>
                      {!!group?.difference && <small>مجموع قدرمطلق اختلاف: {formatRial(group.difference)}</small>}
                    </div>
                  </article>
                )
              })}
            </div>
          </AccountingDataPanel>

          <AccountingDataPanel
            title="موارد نیازمند رسیدگی"
            subtitle={`${Number(report.pagination?.total || 0).toLocaleString('fa-IR')} مورد مطابق فیلترهای اسکن`}
          >
            {(report.items || []).length === 0 ? (
              <EmptyState text="در این بازه و با فیلترهای انتخابی ناترازی پیدا نشد." />
            ) : (
              <div className="acct-card-stack is-compact">
                {report.items.map((item) => (
                  <article key={item.id} className={`acct-doc-card${item.severity === 'critical' ? ' is-off' : ''}`}>
                    <div className="acct-doc-id">
                      <strong>{DOMAIN_LABELS[item.domain] || item.domain}</strong>
                      <small>{item.occurred_at ? formatDate(item.occurred_at) : 'بدون تاریخ'}</small>
                    </div>
                    <div className="acct-doc-copy">
                      <strong>{item.title}</strong>
                      <p>{item.message}</p>
                      <small>{referenceLabel(item)} · {item.source_module || 'کنترل داخلی'}</small>
                    </div>
                    <div className="acct-doc-amounts">
                      <div>
                        <span>اختلاف</span>
                        <strong className="acct-number">{formatRial(Math.abs(item.difference || 0))}</strong>
                      </div>
                    </div>
                    <div className="acct-doc-actions">
                      <span className={`acct-balance ${item.severity === 'critical' ? 'is-off' : ''}`}>
                        {SEVERITY_LABELS[item.severity] || item.severity}
                      </span>
                      {item.blocking && <span className="acct-balance is-off">مسدودکننده</span>}
                      <Button size="sm" variant="ghost" onClick={() => setSelectedItem(item)}>
                        جزئیات
                      </Button>
                    </div>
                  </article>
                ))}
              </div>
            )}
            <AccountingPagination
              page={currentPage}
              pageSize={report.pagination?.limit || PAGE_SIZE}
              total={report.pagination?.total || 0}
              onPageChange={(page) => runScan(page, appliedFilters)}
              disabled={loading}
            />
          </AccountingDataPanel>
        </>
      )}

      <Modal
        title={selectedItem?.title || 'جزئیات ناترازی'}
        open={Boolean(selectedItem)}
        onClose={() => setSelectedItem(null)}
      >
        {selectedItem && (
          <div className="acct-card-stack is-compact">
            <div className="acct-control-detail-head">
              <span className={`acct-balance is-${SEVERITY_TONES[selectedItem.severity] || 'warning'}`}>
                {SEVERITY_LABELS[selectedItem.severity] || selectedItem.severity}
              </span>
              {selectedItem.blocking && <span className="acct-balance is-off">مانع بستن دوره</span>}
            </div>
            <p>{selectedItem.message}</p>
            <div className="acct-control-grid">
              {amountRows(selectedItem).map(([label, value]) => (
                <div key={label} className="acct-control-check">
                  <div>
                    <span>{label}</span>
                    <strong className="acct-number">{formatRial(value)}</strong>
                  </div>
                </div>
              ))}
            </div>
            <AccountingDataPanel title="اطلاعات پیگیری">
              <div className="acct-control-reference-list">
                {Object.entries(selectedItem.refs || {}).filter(([, value]) => value !== '' && value != null).map(([key, value]) => (
                  <div key={key}>
                    <span>{key}</span>
                    <strong className="acct-number">{String(value)}</strong>
                  </div>
                ))}
                {Object.entries(selectedItem.details || {}).filter(([, value]) => value !== '' && value != null).map(([key, value]) => (
                  <div key={key}>
                    <span>{key}</span>
                    <strong>{String(value)}</strong>
                  </div>
                ))}
              </div>
            </AccountingDataPanel>
          </div>
        )}
      </Modal>
    </div>
  )
}
