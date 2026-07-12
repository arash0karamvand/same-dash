// صفحه حسابداری — CRUD کامل اسناد

import { useEffect, useMemo, useState } from 'react'
import { accountingApi, salesApi } from '../api/client'
import PersianDateInput from '../components/PersianDateInput'
import PersianMonthPicker from '../components/PersianMonthPicker'
import MoneyInput from '../components/MoneyInput'
import Select from '../components/Select'
import { Badge, Button, Card, EmptyState, Field, FilterBar, Modal, StatCard } from '../components/ui'
import { useAuth } from '../context/AuthContext'
import { useConfirm } from '../context/ConfirmContext'
import { formatDate, formatMoney, formatNumber } from '../utils/format'
import { hasPermission } from '../utils/permissions'
import { currentJalali, jalaliMonthToGregorian, todayIso } from '../utils/jalali'

const TYPE_COLORS = {
  sale: '#6366f1',
  receivable: '#ef4444',
  payment: '#10b981',
  refund: '#f59e0b',
  adjustment: '#8b5cf6',
  other: '#94a3b8',
}

const ENTRY_TYPES = [
  { value: 'sale', label: 'فروش (درآمد)', direction: 'credit' },
  { value: 'receivable', label: 'مطالبات (بدهکار مشتری)', direction: 'debit' },
  { value: 'payment', label: 'دریافت وجه', direction: 'credit' },
  { value: 'refund', label: 'مرجوعی', direction: 'credit' },
  { value: 'adjustment', label: 'اصلاح', direction: 'debit' },
  { value: 'other', label: 'سایر', direction: 'credit' },
]

const PAGE_SIZE = 50

const EMPTY_FORM = {
  entry_type: 'other',
  direction: 'credit',
  amount: '',
  entry_date: todayIso(),
  description: '',
  sale_id: '',
}

export default function Accounting() {
  const { user } = useAuth()
  const confirm = useConfirm()
  const skipEntryApproval = hasPermission(user, 'approve_sale_accounting')
  const init = currentJalali()
  const [entries, setEntries] = useState([])
  const [summary, setSummary] = useState(null)
  const [total, setTotal] = useState(0)
  const [filteredTotals, setFilteredTotals] = useState({ debit: 0, credit: 0 })
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')

  const [typeFilter, setTypeFilter] = useState('')
  const [approvedFilter, setApprovedFilter] = useState('')
  const [monthMode, setMonthMode] = useState(false)
  const [jYear, setJYear] = useState(init.year)
  const [jMonth, setJMonth] = useState(init.month)
  const [searchInput, setSearchInput] = useState('')
  const [search, setSearch] = useState('')
  const [offset, setOffset] = useState(0)

  const [modalOpen, setModalOpen] = useState(false)
  const [editing, setEditing] = useState(null)
  const [editMode, setEditMode] = useState('full') // full | partial
  const [form, setForm] = useState(EMPTY_FORM)
  const [saving, setSaving] = useState(false)
  const [modalError, setModalError] = useState('')
  const [openSales, setOpenSales] = useState([])

  const dateRange = useMemo(() => {
    if (!monthMode) return {}
    const range = jalaliMonthToGregorian(jYear, jMonth)
    return { dateFrom: range.dateFrom, dateTo: range.dateTo }
  }, [monthMode, jYear, jMonth])

  useEffect(() => {
    const t = setTimeout(() => {
      setSearch(searchInput.trim())
      setOffset(0)
    }, 400)
    return () => clearTimeout(t)
  }, [searchInput])

  const listOpts = {
    type: typeFilter,
    approved: approvedFilter,
    search,
    ...dateRange,
    offset,
    limit: PAGE_SIZE,
  }

  const load = async () => {
    setLoading(true)
    try {
      const [listData, summaryData] = await Promise.all([
        accountingApi.list(listOpts),
        accountingApi.summary(dateRange),
      ])
      setEntries(listData.results)
      setTotal(listData.total)
      setFilteredTotals({ debit: listData.filtered_debit, credit: listData.filtered_credit })
      setSummary(summaryData)
      setError('')
    } catch (e) {
      setError(e.message)
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    load()
  }, [typeFilter, approvedFilter, search, monthMode, jYear, jMonth, offset])

  useEffect(() => {
    if (!modalOpen || editing || form.entry_type !== 'payment') {
      setOpenSales([])
      return
    }
    salesApi.list('has_balance=1&limit=100')
      .then((data) => setOpenSales(data.results || []))
      .catch(() => setOpenSales([]))
  }, [modalOpen, editing, form.entry_type])

  const toggleApprove = async (entry) => {
    try {
      await accountingApi.approve(entry.id, !entry.is_approved)
      load()
    } catch (e) {
      setError(e.message)
    }
  }

  const approveAllPending = async () => {
    if (!await confirm({
      title: 'تایید گروهی',
      message: 'همه اسناد در انتظار تایید شوند؟',
      confirmText: 'بله، تایید شوند',
      variant: 'warning',
    })) return
    try {
      const res = await accountingApi.bulkApprove()
      setError('')
      load()
      if (!res.approved_count) setError('سندی برای تایید وجود نداشت.')
    } catch (e) {
      setError(e.message)
    }
  }

  const openCreate = () => {
    setEditing(null)
    setEditMode('full')
    setModalError('')
    const defaultType = ENTRY_TYPES[ENTRY_TYPES.length - 1]
    setForm({ ...EMPTY_FORM, entry_type: defaultType.value, direction: defaultType.direction })
    setModalOpen(true)
  }

  const openEdit = (entry) => {
    setEditing(entry)
    setEditMode(entry.edit_mode || 'full')
    setModalError('')
    setForm({
      entry_type: entry.entry_type,
      direction: entry.debit > 0 ? 'debit' : 'credit',
      amount: String(entry.amount),
      entry_date: entry.entry_date?.slice(0, 10) || todayIso(),
      description: entry.description || '',
    })
    setModalOpen(true)
  }

  const onTypeChange = (value) => {
    const t = ENTRY_TYPES.find((x) => x.value === value)
    setForm((prev) => ({
      ...prev,
      entry_type: value,
      direction: t ? t.direction : prev.direction,
      sale_id: value === 'payment' ? prev.sale_id : '',
    }))
  }

  const onSaleSelect = (saleId) => {
    const sale = openSales.find((s) => String(s.id) === String(saleId))
    setForm((prev) => ({
      ...prev,
      sale_id: saleId,
      direction: 'credit',
      amount: sale ? String(sale.balance_due) : prev.amount,
      description: sale
        ? `دریافت وجه فاکتور ${sale.invoice_number || sale.id} — ${sale.customer_name}`
        : prev.description,
    }))
  }

  const save = async (e) => {
    e.preventDefault()
    setModalError('')
    const amount = Number(form.amount)
    if (editMode === 'full' && (!amount || amount <= 0)) {
      setModalError('مبلغ سند باید بزرگ‌تر از صفر باشد.')
      return
    }
    if (!form.description.trim()) {
      setModalError('شرح سند الزامی است.')
      return
    }

    let payload
    if (editMode === 'partial') {
      payload = {
        description: form.description.trim(),
        entry_date: form.entry_date,
      }
    } else {
      payload = {
        entry_type: form.entry_type,
        debit: form.direction === 'debit' ? amount : 0,
        credit: form.direction === 'credit' ? amount : 0,
        amount,
        entry_date: form.entry_date,
        description: form.description.trim(),
      }
      if (form.entry_type === 'payment' && form.sale_id) {
        payload.sale_id = Number(form.sale_id)
      }
    }

    setSaving(true)
    try {
      if (editing) {
        await accountingApi.update(editing.id, payload)
      } else {
        await accountingApi.create(payload)
      }
      setModalOpen(false)
      setEditing(null)
      setForm(EMPTY_FORM)
      setError('')
      load()
    } catch (err) {
      setModalError(err.message)
    } finally {
      setSaving(false)
    }
  }

  const remove = async (entry) => {
    let msg = `سند «${entry.entry_type_display} — ${formatMoney(entry.amount)}» حذف شود؟`
    if (entry.is_approved) msg = `این سند تایید شده است.\n${msg}`
    if (entry.sale_id) {
      if (entry.entry_type === 'sale') {
        msg += `\n\nاین سند درآمد فاکتور #${entry.sale_id} است — با حذف، فاکتور از فروشگاه، اداری و کارخانه هم حذف می‌شود.`
      } else if (entry.entry_type === 'payment') {
        msg += `\n\nمبلغ پرداخت از فاکتور #${entry.sale_id} برگردانده می‌شود.`
      } else {
        msg += `\n\nاین سند به فاکتور #${entry.sale_id} متصل است.`
      }
    }
    if (!await confirm({
      title: 'حذف سند',
      message: msg,
      confirmText: 'بله، حذف شود',
      variant: 'danger',
    })) return
    try {
      await accountingApi.remove(entry.id)
      load()
    } catch (e) {
      setError(e.message)
    }
  }

  const EntryActions = ({ entry, stacked = false }) => (
    <div className={`entry-actions ${stacked ? 'entry-actions-stacked' : ''}`}>
      {entry.can_edit && (
        <button className="link" type="button" onClick={() => openEdit(entry)}>
          ویرایش
        </button>
      )}
      {entry.can_delete && (
        <button className="link danger" type="button" onClick={() => remove(entry)}>
          حذف
        </button>
      )}
      {!skipEntryApproval && (
        <button className="link" type="button" onClick={() => toggleApprove(entry)}>
          {entry.is_approved ? 'لغو تایید' : 'تایید'}
        </button>
      )}
    </div>
  )

  const exportCsv = async () => {
    try {
      const data = await accountingApi.list({ ...listOpts, offset: 0, limit: 1000 })
      const header = ['نوع سند', 'شرح', 'مشتری', 'فاکتور', 'بدهکار', 'بستانکار', 'تاریخ', 'وضعیت']
      const rows = data.results.map((e) => [
        e.entry_type_display,
        e.description,
        e.customer_name || '',
        e.invoice_number || (e.sale_id ? `#${e.sale_id}` : ''),
        e.debit,
        e.credit,
        formatDate(e.entry_date),
        e.is_approved ? 'تایید شده' : 'در انتظار',
      ])
      const csv = [header, ...rows]
        .map((row) => row.map((cell) => `"${String(cell ?? '').replace(/"/g, '""')}"`).join(','))
        .join('\r\n')
      const blob = new Blob(['\uFEFF' + csv], { type: 'text/csv;charset=utf-8' })
      const url = URL.createObjectURL(blob)
      const a = document.createElement('a')
      a.href = url
      a.download = `accounting-${todayIso()}.csv`
      a.click()
      URL.revokeObjectURL(url)
    } catch (e) {
      setError(e.message)
    }
  }

  const page = Math.floor(offset / PAGE_SIZE) + 1
  const pageCount = Math.max(1, Math.ceil(total / PAGE_SIZE))
  const isPartial = editMode === 'partial'

  return (
    <div className="page accounting-page">
      <div className="accounting-toolbar">
        <Button type="button" onClick={openCreate}>
          + ثبت سند
        </Button>
        {!skipEntryApproval && summary?.pending_count > 0 && (
          <Button variant="ghost" type="button" onClick={approveAllPending}>
            تایید همه ({formatNumber(summary.pending_count)})
          </Button>
        )}
        <Button variant="ghost" type="button" onClick={exportCsv}>
          CSV
        </Button>
      </div>

      {summary && (
        <div className="stat-grid accounting-stats">
          <StatCard label="بستانکار (درآمد)" value={formatMoney(summary.total_credit)} accent="#10b981" />
          <StatCard label="مطالبات" value={formatMoney(summary.total_receivables)} accent="#ef4444" />
          <StatCard
            label="مانده فاکتور باز"
            value={formatMoney(summary.total_balance_due)}
            hint={`${formatNumber(summary.open_invoices_count)} فاکتور`}
            accent="#f59e0b"
          />
          <StatCard
            label="در انتظار تایید"
            value={formatNumber(summary.pending_count)}
            hint={`از ${formatNumber(summary.entry_count)} سند`}
            accent="#6366f1"
          />
        </div>
      )}

      <Card title="اسناد حسابداری">
        {error && <div className="alert-error">{error}</div>}

        <FilterBar>
          <Field label="جستجو">
            <input
              className="search-input"
              placeholder="شرح، مشتری، فاکتور…"
              value={searchInput}
              onChange={(e) => setSearchInput(e.target.value)}
            />
          </Field>
          <Field label="نوع سند">
            <Select
              value={typeFilter}
              onChange={(v) => { setTypeFilter(v); setOffset(0) }}
              options={[
                { value: '', label: 'همه انواع' },
                { value: 'sale', label: 'فروش' },
                { value: 'receivable', label: 'مطالبات' },
                { value: 'payment', label: 'دریافت وجه' },
                { value: 'refund', label: 'مرجوعی' },
                { value: 'adjustment', label: 'اصلاح' },
                { value: 'other', label: 'سایر' },
              ]}
              placeholder="همه انواع"
            />
          </Field>
          <Field label="تایید">
            <Select
              value={approvedFilter}
              onChange={(v) => { setApprovedFilter(v); setOffset(0) }}
              options={[
                { value: '', label: 'همه' },
                { value: 'true', label: 'تایید شده' },
                { value: 'false', label: 'در انتظار' },
              ]}
              placeholder="همه"
            />
          </Field>
          <Field label="بازه زمانی">
            <PersianMonthPicker
              year={monthMode ? jYear : null}
              month={monthMode ? jMonth : null}
              onChange={(y, m) => {
                setMonthMode(true)
                setJYear(y)
                setJMonth(m)
                setOffset(0)
              }}
              onClear={() => {
                setMonthMode(false)
                setOffset(0)
              }}
              placeholder="همه تاریخ‌ها"
            />
          </Field>
        </FilterBar>

        {loading ? (
          <div className="loading">در حال بارگذاری…</div>
        ) : entries.length === 0 ? (
          <EmptyState text="سندی با این فیلترها یافت نشد.">
            <Button type="button" onClick={openCreate} style={{ marginTop: 12 }}>
              + ثبت اولین سند
            </Button>
          </EmptyState>
        ) : (
          <>
            <div className="table-wrap accounting-table-desktop">
              <table className="table">
                <thead>
                  <tr>
                    <th>نوع سند</th>
                    <th>شرح</th>
                    <th>مشتری / فاکتور</th>
                    <th>بدهکار</th>
                    <th>بستانکار</th>
                    <th>تاریخ</th>
                    <th>تایید</th>
                    <th>عملیات</th>
                  </tr>
                </thead>
                <tbody>
                  {entries.map((e) => (
                    <tr key={e.id}>
                      <td>
                        <div className="entry-badges">
                          <Badge color={TYPE_COLORS[e.entry_type] || '#94a3b8'}>
                            {e.entry_type_display}
                          </Badge>
                          {e.is_system && <Badge color="#64748b">خودکار</Badge>}
                        </div>
                      </td>
                      <td className="text-cell">{e.description || '—'}</td>
                      <td className="text-cell">
                        {e.customer_name
                          ? `${e.customer_name}${e.invoice_number ? ` — ${e.invoice_number}` : e.sale_id ? ` — #${e.sale_id}` : ''}`
                          : e.sale_id ? `فاکتور #${e.sale_id}` : '—'}
                      </td>
                      <td>{e.debit ? formatMoney(e.debit) : '—'}</td>
                      <td>{e.credit ? formatMoney(e.credit) : '—'}</td>
                      <td>{formatDate(e.entry_date)}</td>
                      <td>
                        <Badge color={e.is_approved ? '#10b981' : '#f59e0b'}>
                          {e.is_approved ? 'تایید شده' : 'در انتظار'}
                        </Badge>
                      </td>
                      <td className="row-actions">
                        <EntryActions entry={e} />
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>

            <div className="accounting-cards-mobile">
              {entries.map((e) => (
                <div key={e.id} className="accounting-entry-card m-card">
                  <div className="accounting-entry-card-head m-card-head">
                    <div className="entry-badges">
                      <Badge color={TYPE_COLORS[e.entry_type] || '#94a3b8'}>
                        {e.entry_type_display}
                      </Badge>
                      {e.is_system && <Badge color="#64748b">خودکار</Badge>}
                    </div>
                    <strong className="accounting-entry-amount">
                      {e.debit ? formatMoney(e.debit) : formatMoney(e.credit)}
                    </strong>
                  </div>
                  <Badge color={e.is_approved ? '#10b981' : '#f59e0b'}>
                    {e.is_approved ? 'تایید شده' : 'در انتظار'}
                  </Badge>
                  <p className="accounting-entry-desc">{e.description || '—'}</p>
                  {(e.customer_name || e.sale_id) && (
                    <p className="muted accounting-entry-meta">
                      {e.customer_name || ''}
                      {e.invoice_number ? ` — ${e.invoice_number}` : e.sale_id ? ` — #${e.sale_id}` : ''}
                    </p>
                  )}
                  <div className="m-card-grid">
                    <div><span className="muted">تاریخ</span>{formatDate(e.entry_date)}</div>
                    <div><span className="muted">بدهکار</span>{e.debit ? formatMoney(e.debit) : '—'}</div>
                    <div><span className="muted">بستانکار</span>{e.credit ? formatMoney(e.credit) : '—'}</div>
                  </div>
                  <EntryActions entry={e} stacked />
                </div>
              ))}
            </div>

            <div className="accounting-footer">
              <p className="accounting-footer-summary muted">
                {formatNumber(total)} سند · بدهکار {formatMoney(filteredTotals.debit)} · بستانکار {formatMoney(filteredTotals.credit)}
              </p>
              {pageCount > 1 && (
                <div className="accounting-pagination">
                  <Button variant="ghost" type="button" disabled={offset === 0} onClick={() => setOffset(Math.max(0, offset - PAGE_SIZE))}>
                    قبلی
                  </Button>
                  <span className="muted">{formatNumber(page)} / {formatNumber(pageCount)}</span>
                  <Button variant="ghost" type="button" disabled={offset + PAGE_SIZE >= total} onClick={() => setOffset(offset + PAGE_SIZE)}>
                    بعدی
                  </Button>
                </div>
              )}
            </div>
          </>
        )}
      </Card>

      <Modal
        title={editing ? (isPartial ? 'ویرایش شرح/تاریخ سند' : 'ویرایش سند حسابداری') : 'ثبت سند حسابداری'}
        open={modalOpen}
        onClose={() => { setModalOpen(false); setEditing(null); setModalError('') }}
      >
        <form onSubmit={save} className="form">
          {isPartial && (
            <div className="alert-error" style={{ background: '#fef3c7', color: '#92400e', border: '1px solid #fcd34d' }}>
              این سند از فروش خودکار ساخته شده — فقط شرح و تاریخ قابل ویرایش است. برای تغییر مبلغ، فاکتور را در بخش فروش ویرایش کنید.
            </div>
          )}
          {modalError && <div className="alert-error">{modalError}</div>}

          {!isPartial && (
            <>
              <Field label="نوع سند">
                <Select
                  value={form.entry_type}
                  onChange={(v) => onTypeChange(v)}
                  options={ENTRY_TYPES}
                />
              </Field>
              <Field label="نوع تراکنش">
                <Select
                  value={form.direction}
                  onChange={(v) => setForm({ ...form, direction: v })}
                  options={[
                    { value: 'credit', label: 'بستانکار (درآمد / دریافت)' },
                    { value: 'debit', label: 'بدهکار (هزینه / مطالبات)' },
                  ]}
                />
              </Field>
              {form.entry_type === 'payment' && (
                <Field label="فاکتور فروش (اختیاری)">
                  <Select
                    value={form.sale_id ? String(form.sale_id) : ''}
                    onChange={onSaleSelect}
                    options={[
                      { value: '', label: 'بدون ارتباط با فاکتور' },
                      ...openSales.map((s) => ({
                        value: String(s.id),
                        label: `#${s.invoice_number || s.id} — ${s.customer_name}${s.order_kind !== 'normal' ? ` (${s.order_kind_display})` : ''} — مانده ${formatMoney(s.balance_due)}`,
                      })),
                    ]}
                    placeholder="انتخاب فاکتور با مانده"
                  />
                  <span className="muted small">با انتخاب فاکتور، مبلغ مانده به‌صورت خودکار پر می‌شود و روی فروش ثبت می‌گردد.</span>
                </Field>
              )}
              <Field label="مبلغ (تومان)">
                <MoneyInput
                  min="1"
                  value={form.amount}
                  onChange={(e) => setForm({ ...form, amount: e.target.value })}
                  required
                />
              </Field>
            </>
          )}

          {isPartial && editing && (
            <p className="muted">
              نوع: {editing.entry_type_display} — مبلغ: {formatMoney(editing.amount)}
              {editing.customer_name && ` — مشتری: ${editing.customer_name}`}
            </p>
          )}

          <Field label="تاریخ سند">
            <PersianDateInput
              value={form.entry_date}
              onChange={(v) => setForm({ ...form, entry_date: v })}
              required
            />
          </Field>
          <Field label="شرح سند">
            <input
              value={form.description}
              onChange={(e) => setForm({ ...form, description: e.target.value })}
              placeholder="مثلاً: هزینه حمل، دریافت نقدی…"
              required
            />
          </Field>
          <Button type="submit" disabled={saving}>
            {saving ? 'در حال ذخیره…' : editing ? 'ذخیره تغییرات' : 'ثبت سند'}
          </Button>
        </form>
      </Modal>
    </div>
  )
}
