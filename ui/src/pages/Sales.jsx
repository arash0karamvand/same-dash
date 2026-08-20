// فروش — CRUD، فیلتر، گزارش روز/ماه، قسطی و چک



import { useEffect, useState } from 'react'

import { salesApi } from '../api/client'
import { PAGE_GUIDE_DEFAULTS } from '../config/pageGuideDefaults'
import { useRegisterPageGuide } from '../context/PageGuideContext'

import { useAuth } from '../context/AuthContext'
import { useConfig } from '../context/ConfigContext'
import { useConfirm } from '../context/ConfirmContext'

import CustomerSearch from '../components/CustomerSearch'
import InstallmentLines, { EMPTY_INSTALLMENT } from '../components/InstallmentLines'
import { CHECK_FORM_MAX_ROWS } from '../config/checkForm'
import InvoiceModal from '../components/InvoiceModal'
import MoneyInput from '../components/MoneyInput'
import ProductLines from '../components/ProductLines'
import PersianDateInput from '../components/PersianDateInput'
import SaleDiscountFields, { saleBalanceDue } from '../components/SaleDiscountFields'
import Select from '../components/Select'
import { Badge, Button, Card, EmptyState, Field, FilterBar, Modal, StatCard } from '../components/ui'
import PersonalSalesPanel from '../components/PersonalSalesPanel'
import PersianMonthPicker from '../components/PersianMonthPicker'
import { formatDate, formatMoney } from '../utils/format'
import { hasAnyPermission, hasPermission, isBranchSupervisor, isExecutiveUser, isSystemAdmin, canApproveSaleBranch } from '../utils/permissions'

import { currentJalali, formatJalali, jalaliToIso, PERSIAN_MONTHS, todayIso, toPersianDigits, addYearsToIso } from '../utils/jalali'



const PAYMENT_METHODS = [

  { value: 'cash', label: 'نقدی' },

  { value: 'card', label: 'کارت‌خوان' },

  { value: 'check', label: 'چک' },

]



const ORDER_KINDS = [
  { value: 'normal', label: 'فروش عادی' },
  { value: 'pre_invoice', label: 'پیش‌فاکتور (بیعانه + تایید/لغو)' },
  { value: 'deposit', label: 'بیعانیه (پرداخت روز قبل تحویل)' },
]

const ACCOUNTING_MODES = [
  { value: 'automatic', label: 'خودکار — ثبت در حساب متناسب با روش پرداخت' },
  { value: 'manual', label: 'دستی — فقط ارسال اطلاعات به اداری' },
]

const ORDER_STATUS_COLORS = {
  pending: 'var(--warning)',
  confirmed: 'var(--success)',
  cancelled: '#94a3b8',
}



const EMPTY_FORM = {

  customer_id: '',

  branch: '',

  amount: '',

  discount_type: 'amount',
  discount_value: '',

  paid_amount: '',

  description: '',

  payment_method: 'cash',

  order_kind: 'normal',

  accounting_mode: 'automatic',

  delivery_date: '',

  invoice_number: '',

  installments: [],

  line_items: [],

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

function showInstallmentSection(form, isShop) {
  if (form.payment_method !== 'check') return false
  if (isDeposit(form)) return false
  if (isShop) return true
  return form.order_kind === 'normal'
}

function resolvePaymentStatus(form, isShop) {
  if (form.payment_method === 'check') return 'installment'
  if (isPreInvoice(form) || isDeposit(form)) return 'unpaid'
  if (isShop) return 'paid'
  return 'paid'
}

function isPreInvoice(form) {
  return form.order_kind === 'pre_invoice'
}

function isDeposit(form) {
  return form.order_kind === 'deposit'
}

function ShopDailyBreakdownSection({ data, loading, breakdownMonth, onMonthChange, compact = false }) {
  const monthLabel = `${PERSIAN_MONTHS[breakdownMonth.month - 1]} ${toPersianDigits(breakdownMonth.year)}`
  return (
    <div className={`shop-daily-breakdown${compact ? ' shop-daily-breakdown-compact' : ''}`}>
      <div className="shop-daily-breakdown-head">
        <div>
          <h3 className="shop-daily-breakdown-title">خلاصه فروش روزانه</h3>
          {data && (
            <p className="shop-daily-breakdown-total">
              جمع {monthLabel}: <strong>{formatMoney(data.total_final || 0)}</strong>
              <span className="shop-daily-breakdown-count">{toPersianDigits(data.count || 0)} سفارش</span>
            </p>
          )}
        </div>
        <Field label="ماه">
          <PersianMonthPicker
            year={breakdownMonth.year}
            month={breakdownMonth.month}
            onChange={onMonthChange}
          />
        </Field>
      </div>
      {loading && !data ? (
        <div className="loading">در حال بارگذاری…</div>
      ) : !data?.days?.length ? (
        <EmptyState text="در این ماه فروشی ثبت نشده." />
      ) : (
        <div className="shop-daily-breakdown-table">
          <div className="table-wrap">
            <table className="table shop-daily-table">
              <thead>
                <tr>
                  <th>تاریخ</th>
                  <th>تعداد</th>
                  <th>مبلغ فروش</th>
                </tr>
              </thead>
              <tbody>
                {data.days.map((d) => (
                  <tr key={`${d.jalali_year}-${d.jalali_month}-${d.jalali_day}`}>
                    <td>{formatJalali(jalaliToIso(d.jalali_year, d.jalali_month, d.jalali_day))}</td>
                    <td>{toPersianDigits(d.count)}</td>
                    <td>{formatMoney(d.total_final)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}
    </div>
  )
}


export default function Sales({ portal = 'sales', pageKey = 'shop' }) {
  const isShop = portal === 'shop'
  const salesGuideKey = pageKey === 'orders' ? 'orders' : isShop ? 'shop' : pageKey
  useRegisterPageGuide(
    isShop || pageKey === 'orders' ? salesGuideKey : null,
    PAGE_GUIDE_DEFAULTS[salesGuideKey] || '',
  )

  const { user } = useAuth()
  const confirm = useConfirm()
  const { choices, branchOptions } = useConfig()
  const paymentMethods = choices('payment_method').length ? choices('payment_method') : PAYMENT_METHODS
  const orderKinds = choices('order_kind').length ? choices('order_kind') : ORDER_KINDS
  const orderStatusColors = Object.fromEntries(
    (choices('order_status').length ? choices('order_status') : []).map((o) => [o.value, o.meta?.color || 'var(--accent)'])
  )
  const resolvedOrderStatusColors = Object.keys(orderStatusColors).length ? orderStatusColors : ORDER_STATUS_COLORS

  const canEdit = hasAnyPermission(user, ['edit_sale', 'create_sale', 'delete_sale'])
  const viewAllSales = hasPermission(user, 'view_sales')
  const viewOwnSales = hasPermission(user, 'view_own_sales')
  const viewSalesSummary = hasPermission(user, 'view_sales_summary')
  const summaryOnly = viewSalesSummary && !viewAllSales && !viewOwnSales
  const canViewList = !summaryOnly
  const canCreateSale = hasPermission(user, 'create_sale')
  const pickBranchOnSale = isExecutiveUser(user) && canCreateSale
  const canApproveBranch = canApproveSaleBranch(user)
  const canApproveAccounting = hasPermission(user, 'approve_sale_accounting')
  const branchQueueOnly = canApproveBranch && !viewAllSales
  const branchQueueView = branchQueueOnly || (isShop && canApproveBranch && isExecutiveUser(user))
  const shopBranchSupervisor = isShop && (branchQueueOnly || isBranchSupervisor(user))
  const shopOfficeQueue = isShop && branchQueueView
  const accountingQueueOnly = canApproveAccounting && !viewAllSales && !viewOwnSales
  const workflowColors = Object.fromEntries(
    (choices('workflow_stage').length ? choices('workflow_stage') : []).map((o) => [o.value, o.meta?.color || 'var(--accent)'])
  )
  const [personalCollapsed, setPersonalCollapsed] = useState(summaryOnly ? false : true)

  const salesPageTitle = () => {
    if (isShop && summaryOnly) return 'فروشگاه — ثبت سفارش'
    if (isShop && branchQueueView && canCreateSale) return 'فروشگاه — ارسال به اداری'
    if (isShop && branchQueueView) return 'فروشگاه — صف ارسال به اداری'
    if (summaryOnly) return 'ثبت سفارش'
    if (accountingQueueOnly) return 'سفارش‌های منتظر تایید حسابداری'
    if (branchQueueOnly && canCreateSale) return 'فروش و تایید شعبه'
    if (branchQueueOnly) return 'سفارش‌های منتظر تایید شعبه'
    if (viewOwnSales && !viewAllSales) return 'فروش‌های من'
    return 'فروش‌ها'
  }

  const hideWorkflowStage = isShop && branchQueueView

  const canEditSale = (sale) => {
    if (!sale) return canEdit
    // سرپرست شعبه: فقط قبل از تایید خودش
    if (canApproveBranch && !viewAllSales) {
      return sale.workflow_stage === 'pending_branch'
    }
    // حسابداری: فقط قبل از تایید خودش — بعد از تایید شعبه دیگر دسترسی ندارد
    if (canApproveAccounting && !viewAllSales) {
      return sale.workflow_stage === 'branch_approved'
    }
    if (canApproveBranch && sale.workflow_stage === 'pending_branch') return true
    if (canApproveAccounting && sale.workflow_stage === 'branch_approved') return true
    return canEdit && viewAllSales
  }

  const canActOnSale = (sale) =>
    canEditSale(sale)
    || (canApproveBranch && sale.workflow_stage === 'pending_branch')
    || (canApproveAccounting && sale.workflow_stage === 'branch_approved')

  const showActionsColumn = canEdit || canApproveBranch || canApproveAccounting

  const [sales, setSales] = useState([])

  const [summary, setSummary] = useState(null)

  const [monthly, setMonthly] = useState(null)

  const [yearly, setYearly] = useState(null)

  const [daily, setDaily] = useState(null)

  const [dailyBreakdown, setDailyBreakdown] = useState(null)
  const [breakdownMonth, setBreakdownMonth] = useState(() => {
    const j = currentJalali()
    return { year: j.year, month: j.month }
  })
  const [breakdownLoading, setBreakdownLoading] = useState(false)

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
  const [excelLoadingId, setExcelLoadingId] = useState(null)

  const [form, setForm] = useState(EMPTY_FORM)

  const [filters, setFilters] = useState({ payment_method: '', date_from: '', date_to: '', search: '' })

  useEffect(() => {
    if (summaryOnly) setPersonalCollapsed(false)
    else setPersonalCollapsed(isSystemAdmin(user))
  }, [user?.id, user?.role, summaryOnly])

  const buildParams = (source = filters) => {

    const p = new URLSearchParams()

    Object.entries(source).forEach(([k, v]) => { if (v) p.set(k, v) })

    return p.toString()

  }



  const load = async (nextFilters = filters) => {
    setLoading(true)
    try {
      const jNow = currentJalali()
      if (summaryOnly) {
        const bm = breakdownMonth
        const tasks = [salesApi.monthlyReport(jNow.year, jNow.month)]
        if (isShop) tasks.push(salesApi.dailyBreakdown(bm.year, bm.month))
        const results = await Promise.all(tasks)
        const monthlyData = results[0]
        const breakdownData = isShop ? results[1] : null
        setSales([])
        setSummary({ total_final: monthlyData.total_final, count: monthlyData.count })
        setMonthly(monthlyData)
        setDaily(null)
        setDailyBreakdown(breakdownData)
        setCustomers([])
        setError('')
        return
      }
      if (!canViewList) {
        setSales([])
        setSummary(null)
        setError('')
        return
      }

      const params = buildParams(nextFilters)
      if (branchQueueView) {
        const q = new URLSearchParams(params)
        q.set('queue', 'branch')
        const bm = breakdownMonth
        const reportTasks = [
          salesApi.monthlyReport(jNow.year, jNow.month),
          salesApi.yearlyReport(jNow.year),
        ]
        if (isShop) {
          reportTasks.push(salesApi.dailyBreakdown(bm.year, bm.month))
        }
        if (viewAllSales) {
          reportTasks.push(salesApi.dailyReport(todayIso()))
        }
        const allResults = await Promise.all([
          salesApi.list(q.toString()),
          ...reportTasks,
        ])
        const listData = allResults[0]
        const monthlyData = allResults[1]
        const yearlyData = allResults[2]
        let nextIdx = 3
        const breakdownData = isShop ? allResults[nextIdx++] : null
        const dailyData = viewAllSales ? allResults[nextIdx] : null
        setSales(listData.results)
        setSummary(null)
        setMonthly(monthlyData)
        setYearly(yearlyData)
        setDaily(viewAllSales ? dailyData : null)
        setDailyBreakdown(breakdownData)
        setCustomers([])
        setError('')
        return
      }

      const tasks = [salesApi.list(params)]
      if (viewAllSales) {
        tasks.push(salesApi.dailyReport(todayIso()))
        tasks.push(salesApi.monthlyReport(jNow.year, jNow.month))
        tasks.push(salesApi.yearlyReport(jNow.year))
      }

      const results = await Promise.all(tasks)
      const salesData = results[0]
      const dailyData = viewAllSales ? results[1] : null
      const monthlyData = viewAllSales ? results[2] : null
      const yearlyData = viewAllSales ? results[3] : null

      setSales(salesData.results)
      setSummary(salesData.summary)
      setCustomers([])
      if (viewAllSales) {
        setDaily(dailyData)
        setMonthly(monthlyData)
        setYearly(yearlyData)
      } else {
        setDaily(null)
        setMonthly(null)
        setYearly(null)
      }
      setError('')
    } catch (e) {
      setError(e.message)
    } finally {
      setLoading(false)
    }
  }



  useEffect(() => { load() }, [])

  const onBreakdownMonthChange = async (year, month) => {
    setBreakdownMonth({ year, month })
    setBreakdownLoading(true)
    try {
      const data = await salesApi.dailyBreakdown(year, month)
      setDailyBreakdown(data)
      setError('')
    } catch (e) {
      setError(e.message)
    } finally {
      setBreakdownLoading(false)
    }
  }

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

  const downloadExcel = async (sale) => {
    setExcelLoadingId(sale.id)
    setError('')
    try {
      await salesApi.exportExcel(sale.id)
    } catch (e) {
      setError(e.message)
    } finally {
      setExcelLoadingId(null)
    }
  }

  const setPaymentMethod = (value) => {
    setForm((f) => {
      const next = { ...f, payment_method: value }
      if (value === 'check') {
        if (next.paid_amount === '') next.paid_amount = '0'
        if (!next.installments.length) {
          next.installments = [{ ...EMPTY_INSTALLMENT }]
        }
      }
      return next
    })
  }



  const confirmOrder = async (sale) => {
    if (!await confirm({
      title: 'تایید پیش‌فاکتور',
      message: `پیش‌فاکتور «${sale.customer_name}» تایید شود؟`,
      confirmText: 'بله، تایید شود',
      variant: 'warning',
    })) return
    try {
      await salesApi.confirm(sale.id)
      load()
    } catch (err) {
      setError(err.message)
    }
  }

  const cancelOrder = async (sale) => {
    const msg = sale.paid_amount > 0
      ? `سفارش «${sale.customer_name}» لغو شود؟ بیعانه ${formatMoney(sale.paid_amount)} در حسابداری برگشت داده می‌شود.`
      : `سفارش «${sale.customer_name}» لغو شود؟`
    if (!await confirm({
      title: 'لغو سفارش',
      message: msg,
      confirmText: 'بله، لغو شود',
      variant: 'danger',
    })) return
    try {
      await salesApi.cancel(sale.id)
      load()
    } catch (err) {
      setError(err.message)
    }
  }

  const approveBranch = async (sale) => {
    if (!await confirm({
      title: 'ارسال به اداری',
      message: `سفارش «${sale.customer_name}» به اداری ارسال شود؟`,
      confirmText: 'بله، ارسال شود',
      variant: 'warning',
    })) return
    try {
      await salesApi.approveBranch(sale.id)
      load()
    } catch (err) {
      setError(err.message)
    }
  }

  const approveAccounting = async (sale) => {
    if (!await confirm({
      title: 'تایید حسابداری',
      message: `سفارش «${sale.customer_name}» تایید حسابداری و ارسال به کارخانه شود؟`,
      confirmText: 'بله، ارسال شود',
      variant: 'warning',
    })) return
    try {
      await salesApi.approveAccounting(sale.id)
      load()
    } catch (err) {
      setError(err.message)
    }
  }

  const setOrderKind = (value) => {
    setForm((f) => {
      const next = { ...f, order_kind: value }
      if (value === 'pre_invoice' || value === 'deposit') {
        next.installments = []
      }
      if (value === 'deposit') {
        if (next.paid_amount === '') next.paid_amount = '0'
      }
      if (value === 'normal') {
        next.delivery_date = ''
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
          order_kind: form.order_kind || 'normal',
          accounting_mode: form.accounting_mode || 'automatic',
          payment_status: resolvePaymentStatus(form, isShop),
          invoice_number: form.invoice_number,
          description: form.description,
        }

        if (pickBranchOnSale && !editing) {
          if (!form.branch) {
            setError('انتخاب شعبه الزامی است.')
            return
          }
          payload.branch = form.branch
        }

        if (isDeposit(form)) {
          if (!form.delivery_date) {
            setError('برای بیعانیه، تاریخ تحویل الزامی است.')
            return
          }
          payload.delivery_date = form.delivery_date
          payload.paid_amount = Number(form.paid_amount || 0)
        }

        if (isPreInvoice(form)) {
          payload.paid_amount = Number(form.paid_amount || 0)
        }

        if (form.line_items?.length) {
          const invalid = form.line_items.some((i) => !i.product_id || !Number(i.unit_price))
          if (invalid) {
            setError('هر ردیف باید محصول با قیمت تعریف‌شده در کاتالوگ داشته باشد.')
            return
          }
          payload.line_items = form.line_items.map((i) => ({
            product_id: i.product_id,
            variant_id: i.variant_id || null,
            quantity: Number(i.quantity || 1),
          }))

          payload.amount = form.line_items.reduce(
            (s, i) => s + Number(i.unit_price || 0) * Number(i.quantity || 1),
            0,
          )
          if (payload.amount <= 0) {
            setError('مبلغ فروش باید بیشتر از صفر باشد — قیمت محصول را در کاتالوگ بررسی کنید.')
            return
          }
        } else if (!Number(form.amount)) {
          setError('محصول انتخاب کنید یا مبلغ فروش را وارد کنید.')
          return
        }

        if (selectedCustomer?.id) payload.customer_id = selectedCustomer.id

        else if (selectedCustomer?.full_name) {

          payload.new_customer = {

            full_name: selectedCustomer.full_name,

            phone: selectedCustomer.phone,

            address: selectedCustomer.address || '',

            birthday: selectedCustomer.birthday || '',

          }

        }

        if (!selectedCustomer?.id && !selectedCustomer?.full_name) {
          setError('مشتری را انتخاب یا ثبت کنید.')
          return
        }

        if (!selectedCustomer?.id && (!selectedCustomer?.phone || !selectedCustomer?.address)) {
          setError('برای مشتری جدید، شماره تماس و آدرس الزامی است.')
          return
        }

        if (form.payment_method === 'check' && !isPreInvoice(form) && !isDeposit(form)) {
          payload.paid_amount = Number(form.paid_amount || 0)
        }

        if (showInstallmentSection(form, isShop) && form.installments.length) {
          if (form.installments.length > CHECK_FORM_MAX_ROWS) {
            setError(`حداکثر ${CHECK_FORM_MAX_ROWS} چک مطابق فرم اکسل قابل ثبت است.`)
            return
          }
          payload.installments = form.installments
            .filter((i) => Number(i.amount) > 0)
            .map((i) => ({
              amount: Number(i.amount),
              due_date: i.due_date,
              payment_method: 'check',
              check_number: i.check_number || '',
              bank_name: i.bank_name || '',
              notes: i.notes || '',
              received_at: i.received_at || null,
              receiver_name: i.receiver_name || '',
            }))
        }

        if (form.payment_method === 'check' && !isPreInvoice(form) && !isDeposit(form) && form.paid_amount === '') {
          setError('برای فروش با چک، پرداخت اولیه را وارد کنید (۰ اگر پرداختی نبود).')
          return
        }

        if (!isDeposit(form) && form.delivery_date) {
          payload.delivery_date = form.delivery_date
        }

        if (isShop && form.delivery_date) {
          if (form.delivery_date < shopDeliveryMinIso || form.delivery_date > shopDeliveryMaxIso) {
            setError(`تاریخ تحویل باید بین ${formatJalali(shopDeliveryMinIso)} و ${formatJalali(shopDeliveryMaxIso)} باشد.`)
            return
          }
        }

        await salesApi.create(payload)

      }

      setModalOpen(false)

      setForm(EMPTY_FORM)

      setEditing(null)

      setSelectedCustomer(null)

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

    if (!await confirm({
      title: 'حذف فروش',
      message: 'حذف نرم این فروش؟',
      confirmText: 'بله، حذف شود',
      variant: 'danger',
    })) return

    try {

      await salesApi.remove(id)

      load()

    } catch (err) {

      setError(err.message)

    }

  }



  const jNow = currentJalali()
  const shopDeliveryMinIso = todayIso()
  const shopDeliveryMaxIso = addYearsToIso(shopDeliveryMinIso, 3)
  const shopDeliveryDateProps = isShop
    ? { minIso: shopDeliveryMinIso, maxIso: shopDeliveryMaxIso }
    : {}
  const walletBalance = selectedCustomer?.wallet_balance ?? editing?.customer_wallet_balance ?? 0
  const customerSelected = Boolean(selectedCustomer?.id || editing?.customer_id)

  const monthLabel = `${PERSIAN_MONTHS[jNow.month - 1]} ${toPersianDigits(jNow.year)}`
  const yearLabel = toPersianDigits(jNow.year)
  const branchStatsTitle = isExecutiveUser(user) ? 'همه شعب' : (user?.branch_label || 'شعبه من')
  const pendingSendCount = sales.filter((s) => s.workflow_stage === 'pending_branch').length



  return (

    <div className={`page sales-page${shopOfficeQueue ? ' sales-page-shop-office' : ''}`}>

      {(summaryOnly || (viewOwnSales && !branchQueueOnly)) && (
        <PersonalSalesPanel
          collapsed={personalCollapsed}
          onToggleCollapse={() => setPersonalCollapsed((v) => !v)}
          onApplyListFilter={summaryOnly ? undefined : applyPersonalFilter}
          monthOnly={summaryOnly}
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

        <Card title={`فروش ${monthLabel}`}><p className="stat-value">{formatMoney(monthly?.total_final || 0)}</p><p className="muted">{monthly?.count || 0} فقره — همه شعب</p></Card>

        <Card title={`فروش سال ${yearLabel}`}><p className="stat-value">{formatMoney(yearly?.total_final || 0)}</p><p className="muted">{yearly?.count || 0} فقره — سال جاری</p></Card>

      </div>
      )}

      {shopOfficeQueue && (
      <div className="shop-office-queue-hero">
        <div className="shop-office-queue-hero-main">
          <span className="shop-office-queue-hero-icon" aria-hidden>📤</span>
          <div>
            <h2 className="shop-office-queue-hero-title">صف ارسال به اداری</h2>
            <p className="shop-office-queue-hero-desc">
              سفارش‌های ثبت‌شده را بررسی کنید و برای تایید حسابداری ارسال کنید.
            </p>
          </div>
        </div>
        <div className="shop-office-queue-hero-badge">
          <span className="shop-office-queue-hero-count">{toPersianDigits(pendingSendCount)}</span>
          <span className="shop-office-queue-hero-label">در انتظار ارسال</span>
        </div>
      </div>
      )}

      {shopOfficeQueue && !viewAllSales && (
      <div className="stat-grid shop-office-stats sales-stats-grid">
        <StatCard
          label={`فروش ${monthLabel}`}
          value={formatMoney(monthly?.total_final || 0)}
          hint={`${toPersianDigits(monthly?.count || 0)} فقره — ${branchStatsTitle}`}
          accent="var(--accent)"
        />
        <StatCard
          label={`فروش سال ${yearLabel}`}
          value={formatMoney(yearly?.total_final || 0)}
          hint={`${toPersianDigits(yearly?.count || 0)} فقره — سال جاری`}
          accent="var(--info)"
        />
        <StatCard
          label="منتظر ارسال"
          value={toPersianDigits(pendingSendCount)}
          hint="سفارش در صف شعبه"
          accent={pendingSendCount > 0 ? 'var(--warning)' : 'var(--success)'}
        />
      </div>
      )}

      {branchQueueView && !viewAllSales && !shopOfficeQueue && (
      <div className="stats-grid">
        <Card title={`فروش ماه ${monthLabel} — ${branchStatsTitle}`}>
          <p className="stat-value">{formatMoney(monthly?.total_final || 0)}</p>
          <p className="muted">{monthly?.count || 0} فقره — شامل ارسال‌شده به اداری</p>
        </Card>
        <Card title={`فروش سال ${yearLabel} — ${branchStatsTitle}`}>
          <p className="stat-value">{formatMoney(yearly?.total_final || 0)}</p>
          <p className="muted">{yearly?.count || 0} فقره — سال جاری شعبه</p>
        </Card>
      </div>
      )}

      <Card
        title={salesPageTitle()}
        className={shopOfficeQueue ? 'shop-office-queue-card-wrap' : ''}
        actions={canCreateSale ? <Button onClick={openCreate}>+ ثبت فروش</Button> : null}
      >

        {error && <div className="alert-error">{error}</div>}

        {shopOfficeQueue && !loading && pendingSendCount > 0 && (
          <p className="shop-office-queue-hint">
            {toPersianDigits(pendingSendCount)} سفارش هنوز به اداری ارسال نشده — پس از بررسی، دکمه «ارسال به اداری» را بزنید.
          </p>
        )}

        {summaryOnly && isShop && (
          <ShopDailyBreakdownSection
            data={dailyBreakdown}
            loading={loading || breakdownLoading}
            breakdownMonth={breakdownMonth}
            onMonthChange={onBreakdownMonthChange}
          />
        )}

        {summaryOnly && !isShop && monthly && (
          <Card title={`فروش ماه ${monthLabel}`}>
            <p className="stat-value">{formatMoney(monthly.total_final || 0)}</p>
            <p className="muted">{monthly.count || 0} سفارش ثبت‌شده</p>
          </Card>
        )}

        {!summaryOnly && (
        <>
        <form onSubmit={applyFilters} className={shopOfficeQueue ? 'sales-filters-shop-office' : shopBranchSupervisor ? 'sales-filters-branch-queue' : ''}>
          <FilterBar>
            <Field label="روش پرداخت">
              <Select
                value={filters.payment_method}
                onChange={(v) => setFilters({ ...filters, payment_method: v })}
                options={[{ value: '', label: 'همه' }, ...paymentMethods]}
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

          <EmptyState text={shopOfficeQueue ? 'سفارشی در صف ارسال نیست — همه به اداری ارسال شده‌اند.' : 'فروشی یافت نشد.'} />

        ) : (

          <>

          <div className={`table-wrap sales-table-desktop${shopOfficeQueue ? ' shop-office-table-wrap' : ''}`}>

          <table className={`table${shopOfficeQueue ? ' shop-office-table' : ''}`}>

            <thead>

              <tr>

                <th>فاکتور</th>
                {isShop && branchQueueView && <th>شعبه</th>}
                <th>مشتری</th><th>نوع</th>
                {!hideWorkflowStage && <th>مرحله</th>}
                <th>نهایی</th><th>پرداخت‌شده</th><th>مانده</th><th>تاریخ</th><th>فاکتور</th><th>اکسل</th>

                {showActionsColumn && <th>عملیات</th>}

              </tr>

            </thead>

            <tbody>

              {sales.map((s) => {

                const pendingSend = s.workflow_stage === 'pending_branch'
                return (
                <tr key={s.id} className={shopOfficeQueue && pendingSend ? 'shop-office-pending-row' : ''}>

                  <td>{s.invoice_number || s.id}</td>

                  {isShop && branchQueueView && <td>{s.branch_label || s.branch || '—'}</td>}

                  <td>{s.customer_name}</td>

                  <td>
                    <Badge color={resolvedOrderStatusColors[s.order_status] || 'var(--accent)'}>
                      {s.order_kind_display}
                      {!hideWorkflowStage && s.order_status === 'pending' ? ' — در انتظار' : ''}
                    </Badge>
                  </td>

                  {!hideWorkflowStage && (
                  <td>
                    {s.workflow_stage && s.workflow_stage !== 'completed' && (
                      <Badge color={workflowColors[s.workflow_stage] || 'var(--accent)'}>
                        {s.workflow_stage_display}
                      </Badge>
                    )}
                  </td>
                  )}

                  <td>{s.amounts_masked ? '—' : formatMoney(s.final_amount)}</td>

                  <td>{s.amounts_masked ? '—' : formatMoney(s.paid_amount)}</td>

                  <td>{s.amounts_masked ? '—' : formatMoney(s.balance_due)}</td>

                  <td>{formatDate(s.sold_at)}</td>

                  <td>
                    <button type="button" className="link" onClick={() => openInvoice(s)} disabled={invoiceLoadingId === s.id}>
                      {invoiceLoadingId === s.id ? '…' : 'فاکتور'}
                    </button>
                  </td>

                  <td>
                    <button type="button" className="link" onClick={() => downloadExcel(s)} disabled={excelLoadingId === s.id}>
                      {excelLoadingId === s.id ? '…' : 'اکسل'}
                    </button>
                  </td>

                  {(canActOnSale(s)) && (

                    <td className="row-actions">

                      {canApproveBranch && pendingSend && (
                        shopOfficeQueue ? (
                          <Button type="button" variant="success" className="btn-sm shop-office-send-btn" onClick={() => approveBranch(s)}>
                            ارسال به اداری
                          </Button>
                        ) : (
                          <button type="button" className="link link-success" onClick={() => approveBranch(s)}>{isShop ? 'ارسال به اداری' : 'تایید شعبه'}</button>
                        )
                      )}

                      {canApproveAccounting && s.workflow_stage === 'branch_approved' && (
                        <button type="button" className="link link-success" onClick={() => approveAccounting(s)}>تایید حسابداری</button>
                      )}

                      {canEditSale(s) && (
                        <>
                      <button type="button" className="link" onClick={() => openEdit(s)}>ویرایش</button>

                      {s.balance_due > 0 && s.order_status !== 'cancelled' && !s.amounts_masked && (
                        <button type="button" className="link link-success" onClick={() => { setPayModal(s); setPayAmount(String(s.balance_due)) }}>پرداخت</button>
                      )}

                      {s.order_kind === 'pre_invoice' && s.order_status === 'pending' && (
                        <>
                          <button type="button" className="link link-success" onClick={() => confirmOrder(s)}>تایید</button>
                          <button type="button" className="link danger" onClick={() => cancelOrder(s)}>لغو</button>
                        </>
                      )}

                      {(s.order_kind === 'deposit') && s.order_status === 'pending' && (
                        <button type="button" className="link danger" onClick={() => cancelOrder(s)}>لغو</button>
                      )}

                      {s.order_status !== 'cancelled' && (
                        <button type="button" className="link danger" onClick={() => remove(s.id)}>حذف</button>
                      )}
                        </>
                      )}

                    </td>

                  )}

                </tr>
                )
              })}

            </tbody>

          </table>

          </div>

          <div className={`sales-cards-mobile${shopOfficeQueue ? ' shop-office-cards-mobile' : shopBranchSupervisor ? ' sales-branch-queue-mobile' : ''}`}>
            {sales.map((s) => {
              const pendingSend = s.workflow_stage === 'pending_branch'
              if (shopOfficeQueue) {
                return (
                  <div key={s.id} className={`shop-office-card${pendingSend ? ' shop-office-card-pending' : ''}`}>
                    <div className="shop-office-card-head">
                      <div className="shop-office-card-meta">
                        <span className="shop-office-card-invoice">{s.invoice_number || `#${s.id}`}</span>
                        {isShop && branchQueueView && (
                          <span className="shop-office-card-branch">{s.branch_label || s.branch || '—'}</span>
                        )}
                      </div>
                      <Badge color={resolvedOrderStatusColors[s.order_status] || 'var(--accent)'}>
                        {s.order_kind_display}
                      </Badge>
                    </div>
                    <div className="shop-office-card-customer">{s.customer_name}</div>
                    <div className="shop-office-card-grid">
                      <div className="shop-office-card-stat">
                        <span className="shop-office-card-stat-label">مبلغ نهایی</span>
                        <strong>{s.amounts_masked ? '—' : formatMoney(s.final_amount)}</strong>
                      </div>
                      <div className="shop-office-card-stat">
                        <span className="shop-office-card-stat-label">مانده</span>
                        <strong className={!s.amounts_masked && s.balance_due > 0 ? 'shop-office-balance-due' : ''}>
                          {s.amounts_masked ? '—' : formatMoney(s.balance_due)}
                        </strong>
                      </div>
                      <div className="shop-office-card-stat">
                        <span className="shop-office-card-stat-label">پرداخت‌شده</span>
                        <span>{s.amounts_masked ? '—' : formatMoney(s.paid_amount)}</span>
                      </div>
                      <div className="shop-office-card-stat">
                        <span className="shop-office-card-stat-label">تاریخ</span>
                        <span>{formatDate(s.sold_at)}</span>
                      </div>
                    </div>
                    {canApproveBranch && pendingSend && (
                      <Button
                        type="button"
                        variant="success"
                        className="shop-office-send-btn"
                        onClick={() => approveBranch(s)}
                      >
                        ارسال به اداری
                      </Button>
                    )}
                    <div className="shop-office-card-tools">
                      <button type="button" className="link" onClick={() => openInvoice(s)} disabled={invoiceLoadingId === s.id}>
                        {invoiceLoadingId === s.id ? '…' : 'فاکتور'}
                      </button>
                      <button type="button" className="link" onClick={() => downloadExcel(s)} disabled={excelLoadingId === s.id}>
                        {excelLoadingId === s.id ? '…' : 'اکسل'}
                      </button>
                      {canEditSale(s) && (
                        <>
                          <button type="button" className="link" onClick={() => openEdit(s)}>ویرایش</button>
                          {s.balance_due > 0 && s.order_status !== 'cancelled' && !s.amounts_masked && (
                            <button type="button" className="link link-success" onClick={() => { setPayModal(s); setPayAmount(String(s.balance_due)) }}>پرداخت</button>
                          )}
                          {s.order_kind === 'pre_invoice' && s.order_status === 'pending' && (
                            <>
                              <button type="button" className="link link-success" onClick={() => confirmOrder(s)}>تایید</button>
                              <button type="button" className="link danger" onClick={() => cancelOrder(s)}>لغو</button>
                            </>
                          )}
                          {s.order_kind === 'deposit' && s.order_status === 'pending' && (
                            <button type="button" className="link danger" onClick={() => cancelOrder(s)}>لغو</button>
                          )}
                          {s.order_status !== 'cancelled' && hasPermission(user, 'delete_sale') && (
                            <button type="button" className="link danger" onClick={() => remove(s.id)}>حذف</button>
                          )}
                        </>
                      )}
                    </div>
                  </div>
                )
              }
              return (
              <div key={s.id} className={`m-card${shopBranchSupervisor ? ' sales-branch-queue-card' : ''}`}>
                <div className="m-card-head">
                  <div>
                    <strong>{s.customer_name}</strong>
                    <div className="muted small">{s.invoice_number || `#${s.id}`}</div>
                    {isShop && branchQueueView && (
                      <div className="muted small">{s.branch_label || s.branch || '—'}</div>
                    )}
                  </div>
                  <Badge color={resolvedOrderStatusColors[s.order_status] || 'var(--accent)'}>
                    {s.order_kind_display}
                    {!hideWorkflowStage && s.order_status === 'pending' ? ' — در انتظار' : ''}
                  </Badge>
                </div>
                <div className="m-card-grid">
                  <div><span className="muted">نهایی</span><strong>{s.amounts_masked ? '—' : formatMoney(s.final_amount)}</strong></div>
                  <div><span className="muted">مانده</span><strong>{s.amounts_masked ? '—' : formatMoney(s.balance_due)}</strong></div>
                  <div><span className="muted">پرداخت</span>{s.amounts_masked ? '—' : formatMoney(s.paid_amount)}</div>
                  <div><span className="muted">تاریخ</span>{formatDate(s.sold_at)}</div>
                </div>
                {canApproveBranch && s.workflow_stage === 'pending_branch' && (
                  <div className={`m-card-primary-action${shopBranchSupervisor ? ' m-card-primary-action-prominent' : ''}`}>
                    <Button
                      type="button"
                      variant="success"
                      className="m-card-send-office"
                      onClick={() => approveBranch(s)}
                    >
                      {isShop ? 'ارسال به اداری' : 'تایید شعبه'}
                    </Button>
                  </div>
                )}
                <div className="m-card-actions">
                  <button type="button" className="link" onClick={() => openInvoice(s)} disabled={invoiceLoadingId === s.id}>
                    {invoiceLoadingId === s.id ? '…' : 'فاکتور'}
                  </button>
                  <button type="button" className="link" onClick={() => downloadExcel(s)} disabled={excelLoadingId === s.id}>
                    {excelLoadingId === s.id ? '…' : 'اکسل'}
                  </button>
                  {canApproveAccounting && s.workflow_stage === 'branch_approved' && (
                    <button type="button" className="link link-success" onClick={() => approveAccounting(s)}>تایید حسابداری</button>
                  )}
                  {canEditSale(s) && (
                    <>
                      <button type="button" className="link" onClick={() => openEdit(s)}>ویرایش</button>
                      {s.balance_due > 0 && s.order_status !== 'cancelled' && !s.amounts_masked && (
                        <button type="button" className="link link-success" onClick={() => { setPayModal(s); setPayAmount(String(s.balance_due)) }}>پرداخت</button>
                      )}
                      {s.order_kind === 'pre_invoice' && s.order_status === 'pending' && (
                        <>
                          <button type="button" className="link link-success" onClick={() => confirmOrder(s)}>تایید</button>
                          <button type="button" className="link danger" onClick={() => cancelOrder(s)}>لغو</button>
                        </>
                      )}
                      {s.order_kind === 'deposit' && s.order_status === 'pending' && (
                        <button type="button" className="link danger" onClick={() => cancelOrder(s)}>لغو</button>
                      )}
                      {s.order_status !== 'cancelled' && hasPermission(user, 'delete_sale') && (
                        <button type="button" className="link danger" onClick={() => remove(s.id)}>حذف</button>
                      )}
                    </>
                  )}
                </div>
              </div>
              )
            })}
          </div>

          </>

        )}

        </>
        )}

        {shopOfficeQueue && (
          <ShopDailyBreakdownSection
            data={dailyBreakdown}
            loading={loading || breakdownLoading}
            breakdownMonth={breakdownMonth}
            onMonthChange={onBreakdownMonthChange}
            compact
          />
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
                  options={paymentMethods}
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

              {pickBranchOnSale && (
                <Field label="شعبه">
                  <Select
                    value={form.branch}
                    onChange={(v) => setForm({ ...form, branch: v })}
                    options={[{ value: '', label: 'انتخاب شعبه…' }, ...branchOptions]}
                    required
                  />
                </Field>
              )}

              <Field label="نوع فروش">
                <Select
                  value={form.order_kind}
                  onChange={setOrderKind}
                  options={orderKinds}
                />
              </Field>


              <ProductLines
                lines={form.line_items}
                onChange={(line_items) => {
                  const amount = line_items.reduce(
                    (s, i) => s + Number(i.unit_price || 0) * Number(i.quantity || 1),
                    0,
                  )
                  setForm({ ...form, line_items, amount: amount ? String(amount) : form.amount })
                }}
              />

              {form.line_items?.length > 0 ? (
                <Field label="جمع محصولات">
                  <p className="sale-lines-total"><strong>{formatMoney(Number(form.amount || 0))}</strong></p>
                </Field>
              ) : (
                <Field label="مبلغ"><MoneyInput min="1" value={form.amount} onChange={(e) => setForm({ ...form, amount: e.target.value })} required /></Field>
              )}

              <SaleDiscountFields
                form={form}
                setForm={setForm}
                walletBalance={walletBalance}
                customerSelected={customerSelected}
              />

              {isDeposit(form) && (
                <>
                  <Field label="تاریخ تحویل">
                    <PersianDateInput
                      value={form.delivery_date}
                      onChange={(v) => setForm({ ...form, delivery_date: v })}
                      required
                      {...shopDeliveryDateProps}
                    />
                  </Field>
                  <Field label="بیعانه اولیه">
                    <MoneyInput min="0" value={form.paid_amount} onChange={(e) => setForm({ ...form, paid_amount: e.target.value })} />
                  </Field>
                </>
              )}

              {isPreInvoice(form) && (
                <Field label="مبلغ بیعانه (اختیاری)">
                  <MoneyInput min="0" value={form.paid_amount} onChange={(e) => setForm({ ...form, paid_amount: e.target.value })} />
                </Field>
              )}

              {!isPreInvoice(form) && !isDeposit(form) && form.payment_method === 'check' && (
                <Field label="پرداخت اولیه">
                  <MoneyInput min="0" value={form.paid_amount} onChange={(e) => setForm({ ...form, paid_amount: e.target.value })} required />
                </Field>
              )}

              <Field label="روش پرداخت">
                <Select
                  value={form.payment_method}
                  onChange={(v) => setPaymentMethod(v)}
                  options={paymentMethods}
                />
              </Field>

              {!editing && (
                <Field label="ثبت حسابداری">
                  <Select
                    value={form.accounting_mode}
                    onChange={(v) => setForm({ ...form, accounting_mode: v })}
                    options={ACCOUNTING_MODES}
                  />
                </Field>
              )}

              {showInstallmentSection(form, isShop) && (
                <InstallmentLines
                  installments={form.installments}
                  onChange={(installments) => setForm({ ...form, installments })}
                  balanceDue={saleBalanceDue(form, walletBalance)}
                  customerName={selectedCustomer?.full_name || ''}
                />
              )}

              <Field label="شماره فاکتور"><input className="ltr" value={form.invoice_number} onChange={(e) => setForm({ ...form, invoice_number: e.target.value })} placeholder="خالی = شماره سیستمی" /></Field>

              {!isDeposit(form) && (
                <Field label="تاریخ تحویل">
                  <PersianDateInput
                    value={form.delivery_date}
                    onChange={(v) => setForm({ ...form, delivery_date: v })}
                    {...shopDeliveryDateProps}
                  />
                </Field>
              )}

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


