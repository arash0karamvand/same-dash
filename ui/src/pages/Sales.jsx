// فروش — CRUD، فیلتر، گزارش روز/ماه، قسطی و چک



import { useEffect, useState } from 'react'

import { salesApi } from '../api/client'

import { useAuth } from '../context/AuthContext'

import CustomerSearch from '../components/CustomerSearch'
import InstallmentLines, { EMPTY_INSTALLMENT } from '../components/InstallmentLines'
import InvoiceModal from '../components/InvoiceModal'
import MoneyInput from '../components/MoneyInput'
import ProductLines from '../components/ProductLines'
import PersianDateInput from '../components/PersianDateInput'
import SaleDiscountFields, { saleBalanceDue } from '../components/SaleDiscountFields'
import Select from '../components/Select'
import { Badge, Button, Card, EmptyState, Field, FilterBar, Modal } from '../components/ui'
import PersonalSalesPanel from '../components/PersonalSalesPanel'
import { formatDate, formatMoney } from '../utils/format'
import { hasAnyPermission, hasPermission, isSystemAdmin } from '../utils/permissions'

import { currentJalali, formatJalali, jalaliToIso, PERSIAN_MONTHS, todayIso, toPersianDigits } from '../utils/jalali'



const PAYMENT_METHODS = [

  { value: 'cash', label: 'نقدی' },

  { value: 'card', label: 'کارت‌خوان' },

  { value: 'online', label: 'آنلاین' },

  { value: 'credit', label: 'اعتباری' },

  { value: 'check', label: 'چک' },

]



const PAYMENT_STATUSES = [

  { value: 'paid', label: 'پرداخت‌شده' },

  { value: 'unpaid', label: 'پرداخت‌نشده' },

  { value: 'installment', label: 'قسطی' },

]



const STATUS_COLORS = { paid: '#10b981', unpaid: '#ef4444', installment: '#f59e0b', partial: '#f59e0b' }



const EMPTY_FORM = {

  customer_id: '',

  amount: '',

  discount_type: 'amount',
  discount_value: '',

  paid_amount: '',

  description: '',

  payment_method: 'cash',

  payment_status: 'paid',

  invoice_number: '',

  installments: [],

  line_items: [],

  new_customer_phone: '',

}



const EMPTY_EDIT = {
  description: '',
  invoice_number: '',
  payment_method: 'cash',
  amount: '',
  discount_type: 'amount',
  discount_value: '',
  paid_amount: '',
}

function showInstallmentSection(form) {
  return form.payment_status === 'installment' || form.payment_method === 'check'
}



export default function Sales() {

  const { user } = useAuth()

  const canEdit = hasAnyPermission(user, ['edit_sale', 'create_sale', 'delete_sale'])
  const viewAllSales = hasPermission(user, 'view_sales')
  const viewOwnSales = hasPermission(user, 'view_own_sales')
  const [personalCollapsed, setPersonalCollapsed] = useState(true)

  const [sales, setSales] = useState([])

  const [summary, setSummary] = useState(null)

  const [daily, setDaily] = useState(null)

  const [monthly, setMonthly] = useState(null)

  const [customers, setCustomers] = useState([])
  const [selectedCustomer, setSelectedCustomer] = useState(null)

  const [loading, setLoading] = useState(true)

  const [error, setError] = useState('')

  const [modalOpen, setModalOpen] = useState(false)

  const [editing, setEditing] = useState(null)

  const [payModal, setPayModal] = useState(null)

  const [payAmount, setPayAmount] = useState('')

  const [invoiceSale, setInvoiceSale] = useState(null)
  const [invoiceLoadingId, setInvoiceLoadingId] = useState(null)

  const [form, setForm] = useState(EMPTY_FORM)

  const [filters, setFilters] = useState({ payment_status: '', payment_method: '', date_from: '', date_to: '', search: '' })

  useEffect(() => {
    setPersonalCollapsed(isSystemAdmin(user))
  }, [user?.id, user?.role])

  const buildParams = (source = filters) => {

    const p = new URLSearchParams()

    Object.entries(source).forEach(([k, v]) => { if (v) p.set(k, v) })

    return p.toString()

  }



  const load = async (nextFilters = filters) => {

    setLoading(true)

    try {

      const params = buildParams(nextFilters)

      const jNow = currentJalali()

      const tasks = [salesApi.list(params)]
      if (viewAllSales) {
        tasks.push(salesApi.dailyReport(todayIso()))
        tasks.push(salesApi.monthlyReport(jNow.year, jNow.month))
      }

      const [salesData, dailyData, monthlyData] = await Promise.all(tasks)

      setSales(salesData.results)

      setSummary(salesData.summary)

      setCustomers([])

      if (viewAllSales) {
        setDaily(dailyData)
        setMonthly(monthlyData)
      } else {
        setDaily(null)
        setMonthly(null)
      }

      setError('')

    } catch (e) {

      setError(e.message)

    } finally {

      setLoading(false)

    }

  }



  useEffect(() => { load() }, [])



  const applyPersonalFilter = (range) => {
    const next = { ...filters, ...range }
    setFilters(next)
    load(next)
  }

  const applyFilters = (e) => {

    e.preventDefault()

    load()

  }



  const openCreate = () => {
    setEditing(null)
    setForm(EMPTY_FORM)
    setSelectedCustomer(null)
    setModalOpen(true)
  }



  const openEdit = (sale) => {

    setEditing(sale)

    setForm({

      ...EMPTY_EDIT,

      description: sale.description || '',

      invoice_number: sale.invoice_number || '',

      payment_method: sale.payment_method || 'cash',

      amount: String(sale.amount ?? ''),
      discount_type: sale.discount_type || 'amount',
      discount_value: String(sale.discount_value ?? sale.discount ?? 0),

      paid_amount: String(sale.paid_amount ?? 0),

    })

    setModalOpen(true)

  }



  const openInvoice = async (sale) => {
    setInvoiceLoadingId(sale.id)
    setError('')
    try {
      const full = await salesApi.get(sale.id)
      setInvoiceSale(full)
    } catch (e) {
      setError(e.message)
    } finally {
      setInvoiceLoadingId(null)
    }
  }

  const setPaymentStatus = (value) => {
    setForm((f) => {
      const next = { ...f, payment_status: value }
      if (value === 'installment') {
        next.payment_method = 'check'
        if (!next.installments.length) {
          next.installments = [{ ...EMPTY_INSTALLMENT }]
        }
      }
      return next
    })
  }

  const setPaymentMethod = (value) => {
    setForm((f) => {
      const next = { ...f, payment_method: value }
      if (value === 'check') {
        next.payment_status = 'installment'
        if (next.paid_amount === '') next.paid_amount = '0'
        if (!next.installments.length) {
          next.installments = [{ ...EMPTY_INSTALLMENT }]
        }
      }
      return next
    })
  }



  const save = async (e) => {

    e.preventDefault()

    try {

      if (editing) {

        await salesApi.update(editing.id, {
          description: form.description,
          invoice_number: form.invoice_number,
          payment_method: form.payment_method,
          amount: Number(form.amount),
          discount_type: form.discount_type,
          discount_value: Number(form.discount_value) || 0,
          paid_amount: Number(form.paid_amount),
        })

      } else {

        const payload = {
          amount: Number(form.amount),
          discount_type: form.discount_type || 'amount',
          discount_value: Number(form.discount_value) || 0,
          payment_method: form.payment_method,

          payment_status: form.payment_status,

          invoice_number: form.invoice_number,

          description: form.description,

        }

        if (form.line_items?.length) {

          payload.line_items = form.line_items.map((i) => ({
            product_id: i.product_id || null,
            variant_id: i.variant_id || null,
            product_name: i.product_name,
            color_name: i.color_name || '',
            color_hex: i.color_hex || '',
            quantity: Number(i.quantity || 1),
            unit_price: Number(i.unit_price),
          }))

          payload.amount = payload.line_items.reduce((s, i) => s + i.quantity * i.unit_price, 0)

        }

        if (selectedCustomer?.id) payload.customer_id = selectedCustomer.id

        else if (selectedCustomer?.full_name) {

          payload.new_customer = {

            full_name: selectedCustomer.full_name,

            phone: form.new_customer_phone || `09${String(Date.now()).slice(-9)}`,

          }

        }

        if (form.payment_status === 'installment') {
          payload.paid_amount = Number(form.paid_amount)
        }

        if (showInstallmentSection(form) && form.installments.length) {
          payload.installments = form.installments
            .filter((i) => Number(i.amount) > 0)
            .map((i) => ({
              amount: Number(i.amount),
              due_date: i.due_date,
              payment_method: i.payment_method || 'check',
              check_number: i.check_number || '',
              bank_name: i.bank_name || '',
              notes: i.notes || '',
            }))
        }

        if (form.payment_status === 'installment' && form.paid_amount === '') {
          setError('برای فروش قسطی، پرداخت اولیه را وارد کنید (۰ اگر پرداختی نبود).')
          return
        }

        await salesApi.create(payload)

      }

      setModalOpen(false)

      setForm(EMPTY_FORM)

      setEditing(null)

      load()

    } catch (err) {

      setError(err.message)

    }

  }



  const submitPayment = async (e) => {

    e.preventDefault()

    try {

      await salesApi.recordPayment(payModal.id, { amount: Number(payAmount) })

      setPayModal(null)

      load()

    } catch (err) {

      setError(err.message)

    }

  }



  const remove = async (id) => {

    if (!confirm('حذف نرم این فروش؟')) return

    try {

      await salesApi.remove(id)

      load()

    } catch (err) {

      setError(err.message)

    }

  }



  const jNow = currentJalali()
  const walletBalance = selectedCustomer?.wallet_balance ?? editing?.customer_wallet_balance ?? 0
  const customerSelected = Boolean(selectedCustomer?.id || editing?.customer_id)

  const monthLabel = `${PERSIAN_MONTHS[jNow.month - 1]} ${toPersianDigits(jNow.year)}`



  return (

    <div className="page sales-page">

      {viewOwnSales && (
        <PersonalSalesPanel
          collapsed={personalCollapsed}
          onToggleCollapse={() => setPersonalCollapsed((v) => !v)}
          onApplyListFilter={applyPersonalFilter}
        />
      )}

      {viewAllSales && (
      <div className="stats-grid">

        <Card
          title={
            daily?.jalali_year
              ? `فروش ${formatJalali(jalaliToIso(daily.jalali_year, daily.jalali_month, daily.jalali_day))}`
              : `فروش ${formatJalali(todayIso())}`
          }
        >
          <p className="stat-value">{formatMoney(daily?.total_final || 0)}</p>
          <p className="muted">{daily?.count || 0} فقره — فقط همین روز</p>
        </Card>

        <Card title={`فروش ${monthLabel}`}><p className="stat-value">{formatMoney(monthly?.total_final || 0)}</p><p className="muted">{monthly?.count || 0} فقره</p></Card>

        <Card title="فیلتر فعلی"><p className="stat-value">{formatMoney(summary?.total_final || 0)}</p><p className="muted">{summary?.count || 0} فقره</p></Card>

      </div>
      )}

      <Card title={viewOwnSales && !viewAllSales ? 'فروش‌های من' : 'فروش‌ها'} actions={canEdit ? <Button onClick={openCreate}>+ ثبت فروش</Button> : null}>

        {error && <div className="alert-error">{error}</div>}

        <form onSubmit={applyFilters}>
          <FilterBar>
            <Field label="وضعیت پرداخت">
              <Select
                value={filters.payment_status}
                onChange={(v) => setFilters({ ...filters, payment_status: v })}
                options={[{ value: '', label: 'همه' }, ...PAYMENT_STATUSES]}
                placeholder="همه"
              />
            </Field>
            <Field label="روش پرداخت">
              <Select
                value={filters.payment_method}
                onChange={(v) => setFilters({ ...filters, payment_method: v })}
                options={[{ value: '', label: 'همه' }, ...PAYMENT_METHODS]}
                placeholder="همه"
              />
            </Field>
            <Field label="از تاریخ">
              <PersianDateInput
                value={filters.date_from}
                onChange={(v) => setFilters({ ...filters, date_from: v })}
                placeholder="از تاریخ"
                onClear={() => setFilters({ ...filters, date_from: '' })}
                clearLabel="پاک کردن"
              />
            </Field>
            <Field label="تا تاریخ">
              <PersianDateInput
                value={filters.date_to}
                onChange={(v) => setFilters({ ...filters, date_to: v })}
                placeholder="تا تاریخ"
                onClear={() => setFilters({ ...filters, date_to: '' })}
                clearLabel="پاک کردن"
              />
            </Field>
            <Field label="جستجو">
              <input
                className="search-input"
                value={filters.search}
                onChange={(e) => setFilters({ ...filters, search: e.target.value })}
                placeholder="فاکتور یا مشتری"
              />
            </Field>
            <div className="page-filters-actions">
              <Button type="submit">اعمال فیلتر</Button>
            </div>
          </FilterBar>
        </form>

        {loading ? <div className="loading">در حال بارگذاری…</div> : sales.length === 0 ? (

          <EmptyState text="فروشی یافت نشد." />

        ) : (

          <>

          <div className="table-wrap sales-table-desktop">

          <table className="table">

            <thead>

              <tr>

                <th>فاکتور</th><th>مشتری</th><th>نهایی</th><th>پرداخت‌شده</th><th>مانده</th><th>وضعیت</th>                <th>تاریخ</th><th>فاکتور</th>

                {canEdit && <th>عملیات</th>}

              </tr>

            </thead>

            <tbody>

              {sales.map((s) => (

                <tr key={s.id}>

                  <td>{s.invoice_number || s.id}</td>

                  <td>{s.customer_name}</td>

                  <td>{formatMoney(s.final_amount)}</td>

                  <td>{formatMoney(s.paid_amount)}</td>

                  <td>{formatMoney(s.balance_due)}</td>

                  <td><Badge color={STATUS_COLORS[s.payment_status] || '#6366f1'}>{s.payment_status_display}</Badge></td>

                  <td>{formatDate(s.sold_at)}</td>

                  <td>
                    <button type="button" className="link" onClick={() => openInvoice(s)} disabled={invoiceLoadingId === s.id}>
                      {invoiceLoadingId === s.id ? '…' : 'فاکتور'}
                    </button>
                  </td>

                  {canEdit && (

                    <td className="row-actions">

                      <button type="button" className="link" onClick={() => openEdit(s)}>ویرایش</button>

                      {s.balance_due > 0 && <button type="button" className="link" onClick={() => { setPayModal(s); setPayAmount(String(s.balance_due)) }}>پرداخت</button>}

                      <button type="button" className="link danger" onClick={() => remove(s.id)}>حذف</button>

                    </td>

                  )}

                </tr>

              ))}

            </tbody>

          </table>

          </div>

          <div className="sales-cards-mobile">
            {sales.map((s) => (
              <div key={s.id} className="m-card">
                <div className="m-card-head">
                  <div>
                    <strong>{s.customer_name}</strong>
                    <div className="muted small">{s.invoice_number || `#${s.id}`}</div>
                  </div>
                  <Badge color={STATUS_COLORS[s.payment_status] || '#6366f1'}>{s.payment_status_display}</Badge>
                </div>
                <div className="m-card-grid">
                  <div><span className="muted">نهایی</span><strong>{formatMoney(s.final_amount)}</strong></div>
                  <div><span className="muted">مانده</span><strong>{formatMoney(s.balance_due)}</strong></div>
                  <div><span className="muted">پرداخت</span>{formatMoney(s.paid_amount)}</div>
                  <div><span className="muted">تاریخ</span>{formatDate(s.sold_at)}</div>
                </div>
                <div className="m-card-actions">
                  <button type="button" className="link" onClick={() => openInvoice(s)} disabled={invoiceLoadingId === s.id}>
                    {invoiceLoadingId === s.id ? '…' : 'فاکتور'}
                  </button>
                  {canEdit && (
                    <>
                      <button type="button" className="link" onClick={() => openEdit(s)}>ویرایش</button>
                      {s.balance_due > 0 && (
                        <button type="button" className="link" onClick={() => { setPayModal(s); setPayAmount(String(s.balance_due)) }}>پرداخت</button>
                      )}
                      <button type="button" className="link danger" onClick={() => remove(s.id)}>حذف</button>
                    </>
                  )}
                </div>
              </div>
            ))}
          </div>

          </>

        )}

      </Card>



      <Modal title={editing ? 'ویرایش فروش' : 'ثبت فروش'} open={modalOpen} onClose={() => { setModalOpen(false); setEditing(null) }}>

        <form onSubmit={save} className="form">

          {editing ? (

            <>

              <p className="muted">مشتری: {editing.customer_name}</p>

              <Field label="مبلغ"><MoneyInput min="1" value={form.amount} onChange={(e) => setForm({ ...form, amount: e.target.value })} required /></Field>

              <SaleDiscountFields
                form={form}
                setForm={setForm}
                walletBalance={walletBalance}
                customerSelected={customerSelected}
              />

              <Field label="پرداخت‌شده"><MoneyInput min="0" value={form.paid_amount} onChange={(e) => setForm({ ...form, paid_amount: e.target.value })} /></Field>

              <Field label="روش پرداخت">
                <Select
                  value={form.payment_method}
                  onChange={(v) => setForm({ ...form, payment_method: v })}
                  options={PAYMENT_METHODS}
                />
              </Field>

              <Field label="شماره فاکتور"><input className="ltr" value={form.invoice_number} onChange={(e) => setForm({ ...form, invoice_number: e.target.value })} /></Field>

              <Field label="توضیحات"><textarea value={form.description} onChange={(e) => setForm({ ...form, description: e.target.value })} rows={3} /></Field>

            </>

          ) : (

            <>

              <CustomerSearch
                value={selectedCustomer}
                onSelect={(c) => {
                  setSelectedCustomer(c)
                  if (c && (c.wallet_balance ?? 0) <= 0 && form.discount_type === 'wallet') {
                    setForm((f) => ({ ...f, discount_type: 'amount', discount_value: '' }))
                  }
                }}
                onCreateNew={(c) => setSelectedCustomer(c)}
              />

              {selectedCustomer && !selectedCustomer.id && (

                <Field label="موبایل مشتری جدید">

                  <input className="ltr" value={form.new_customer_phone} onChange={(e) => setForm({ ...form, new_customer_phone: e.target.value })} placeholder="09xxxxxxxxx" required />

                </Field>

              )}

              <ProductLines lines={form.line_items} onChange={(line_items) => setForm({ ...form, line_items })} />

              <Field label="مبلغ"><MoneyInput min="1" value={form.amount} onChange={(e) => setForm({ ...form, amount: e.target.value })} required /></Field>

              <SaleDiscountFields
                form={form}
                setForm={setForm}
                walletBalance={walletBalance}
                customerSelected={customerSelected}
              />

              <Field label="وضعیت پرداخت">
                <Select
                  value={form.payment_status}
                  onChange={(v) => setPaymentStatus(v)}
                  options={PAYMENT_STATUSES}
                />
              </Field>

              {form.payment_status === 'installment' && (
                <Field label="پرداخت اولیه">
                  <MoneyInput min="0" value={form.paid_amount} onChange={(e) => setForm({ ...form, paid_amount: e.target.value })} required />
                  <span className="muted">مبلغی که همین الان دریافت شده (۰ اگر نبود)</span>
                </Field>
              )}

              <Field label="روش پرداخت">
                <Select
                  value={form.payment_method}
                  onChange={(v) => setPaymentMethod(v)}
                  options={PAYMENT_METHODS}
                />
              </Field>

              {showInstallmentSection(form) && (
                <InstallmentLines
                  installments={form.installments}
                  onChange={(installments) => setForm({ ...form, installments })}
                  balanceDue={saleBalanceDue(form, walletBalance)}
                />
              )}

              <Field label="شماره فاکتور"><input className="ltr" value={form.invoice_number} onChange={(e) => setForm({ ...form, invoice_number: e.target.value })} placeholder="خالی = شماره سیستمی" /></Field>

              <Field label="توضیحات فاکتور"><textarea value={form.description} onChange={(e) => setForm({ ...form, description: e.target.value })} rows={2} /></Field>

            </>

          )}

          <Button type="submit">{editing ? 'ذخیره تغییرات' : 'ثبت'}</Button>

        </form>

      </Modal>



      <Modal title="ثبت پرداخت" open={!!payModal} onClose={() => setPayModal(null)}>

        {payModal && (

          <form onSubmit={submitPayment} className="form">

            <p className="muted">مانده: {formatMoney(payModal.balance_due)}</p>

            <Field label="مبلغ"><MoneyInput min="1" max={payModal.balance_due} value={payAmount} onChange={(e) => setPayAmount(e.target.value)} required /></Field>

            <Button type="submit">ثبت</Button>

          </form>

        )}

      </Modal>

      <InvoiceModal
        sale={invoiceSale}
        open={Boolean(invoiceSale)}
        onClose={() => setInvoiceSale(null)}
      />

    </div>

  )

}


