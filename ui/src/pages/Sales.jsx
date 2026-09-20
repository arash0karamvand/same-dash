// فروش — CRUD، فیلتر، گزارش روز/ماه، قسطی و چک



import { useCallback, useEffect, useRef, useState } from 'react'
import { fromLegacy } from '../styles/tw.js'

import { salesApi, attendanceApi } from '../api/client'
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
import AttendanceWidget from '../components/AttendanceWidget'
import PersianDateInput from '../components/PersianDateInput'
import SaleDiscountFields, { saleBalanceDue } from '../components/SaleDiscountFields'
import Select from '../components/Select'
import { Badge, Button, Card, EmptyState, Field, FilterBar, LoadMoreButton, Modal, StatCard } from '../components/ui'
import { PAGE_SIZE, withPageParams } from '../config/pagination'
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
  { value: 'normal', label: 'فروش و پرداخت آنی' },
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
  seat_count: '',
  stock_source_kind: 'warehouse',
  stock_source_warehouse_id: '',
  stock_source_branch: '',
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

function isStockSourceSelected(form) {
  if (form.stock_source_kind === 'warehouse') return Boolean(form.stock_source_warehouse_id)
  if (form.stock_source_kind === 'branch') return Boolean(form.stock_source_branch)
  return false
}

function validateSaleSubmit({
  editing,
  form,
  selectedCustomer,
  pickBranchOnSale,
  isShop,
  shopDeliveryMinIso,
  shopDeliveryMaxIso,
  saleGate,
  stockLocations,
}) {
  if (!editing && saleGate?.blocked) return saleGate.reason

  if (editing) {
    if (!Number(form.amount) || Number(form.amount) <= 0) {
      return 'مبلغ فروش را وارد کنید.'
    }
    return null
  }

  if (!selectedCustomer?.id && !selectedCustomer?.full_name) {
    return 'مشتری را انتخاب یا ثبت کنید.'
  }
  if (!selectedCustomer?.id && (!selectedCustomer?.phone || !selectedCustomer?.address)) {
    return 'برای مشتری جدید، شماره تماس و آدرس الزامی است.'
  }
  if (pickBranchOnSale && !form.branch) {
    return 'انتخاب شعبه الزامی است.'
  }
  if ((stockLocations || []).length > 0 && !isStockSourceSelected(form)) {
    return 'منبع موجودی را انتخاب کنید.'
  }
  if (isDeposit(form) && !form.delivery_date) {
    return 'برای بیعانیه، تاریخ تحویل الزامی است.'
  }
  if (form.line_items?.length) {
    const invalid = form.line_items.some((i) => !i.product_id || !Number(i.unit_price))
    if (invalid) return 'هر ردیف باید محصول با قیمت تعریف‌شده در کاتالوگ داشته باشد.'
    const amount = form.line_items.reduce(
      (s, i) => s + Number(i.unit_price || 0) * Number(i.quantity || 1),
      0,
    )
    if (amount <= 0) return 'مبلغ فروش باید بیشتر از صفر باشد — قیمت محصول را در کاتالوگ بررسی کنید.'
  } else if (!Number(form.amount)) {
    return 'محصول انتخاب کنید یا مبلغ فروش را وارد کنید.'
  }
  if (form.payment_method === 'check' && !isPreInvoice(form) && !isDeposit(form) && form.paid_amount === '') {
    return 'برای فروش با چک، پرداخت اولیه را وارد کنید (۰ اگر پرداختی نبود).'
  }
  if (showInstallmentSection(form, isShop) && form.installments.length) {
    if (form.installments.length > CHECK_FORM_MAX_ROWS) {
      return `حداکثر ${CHECK_FORM_MAX_ROWS} چک مطابق فرم اکسل قابل ثبت است.`
    }
    const incomplete = form.installments.some((i) => Number(i.amount) > 0 && !i.due_date)
    if (incomplete) return 'برای هر چک، تاریخ سررسید الزامی است.'
  }
  if (isShop && form.delivery_date) {
    if (form.delivery_date < shopDeliveryMinIso || form.delivery_date > shopDeliveryMaxIso) {
      return `تاریخ تحویل باید بین ${formatJalali(shopDeliveryMinIso)} و ${formatJalali(shopDeliveryMaxIso)} باشد.`
    }
  }
  return null
}

function ShopDailyBreakdownSection({ data, loading, breakdownMonth, onMonthChange, compact = false }) {
  const monthLabel = `${PERSIAN_MONTHS[breakdownMonth.month - 1]} ${toPersianDigits(breakdownMonth.year)}`
  const hideAmounts = Boolean(data?.amounts_masked)
  return (
    <div className={fromLegacy(`shop-daily-breakdown${compact ? ' shop-daily-breakdown-compact' : ''}`)}>
      <div className={fromLegacy("shop-daily-breakdown-head")}>
        <div>
          <h3 className={fromLegacy("shop-daily-breakdown-title")}>خلاصه فروش روزانه</h3>
          {data && (
            <p className={fromLegacy("shop-daily-breakdown-total")}>
              جمع {monthLabel}:{' '}
              {hideAmounts ? (
                <strong>{toPersianDigits(data.count || 0)} سفارش</strong>
              ) : (
                <>
                  <strong>{formatMoney(data.total_final || 0)}</strong>
                  <span className={fromLegacy("shop-daily-breakdown-count")}>{toPersianDigits(data.count || 0)} سفارش</span>
                </>
              )}
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
        <div className={fromLegacy("loading")}>در حال بارگذاری…</div>
      ) : !data?.days?.length ? (
        <EmptyState text="در این ماه فروشی ثبت نشده." />
      ) : (
        <div className={fromLegacy("shop-daily-breakdown-table")}>
          <div className={fromLegacy("table-wrap")}>
            <table className={fromLegacy("table shop-daily-table")}>
              <thead>
                <tr>
                  <th>تاریخ</th>
                  <th>تعداد</th>
                  {!hideAmounts && <th>مبلغ فروش</th>}
                </tr>
              </thead>
              <tbody>
                {data.days.map((d) => (
                  <tr key={`${d.jalali_year}-${d.jalali_month}-${d.jalali_day}`}>
                    <td>{formatJalali(jalaliToIso(d.jalali_year, d.jalali_month, d.jalali_day))}</td>
                    <td>{toPersianDigits(d.count)}</td>
                    {!hideAmounts && <td>{formatMoney(d.total_final)}</td>}
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
  const { choices, branchOptions, stockLocations } = useConfig()
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

  const [weekly, setWeekly] = useState(null)

  const [dailyBreakdown, setDailyBreakdown] = useState(null)
  const [breakdownMonth, setBreakdownMonth] = useState(() => {
    const j = currentJalali()
    return { year: j.year, month: j.month }
  })
  const [breakdownLoading, setBreakdownLoading] = useState(false)

  const [customers, setCustomers] = useState([])
  const [selectedCustomer, setSelectedCustomer] = useState(null)

  const [loading, setLoading] = useState(true)
  const [loadingMore, setLoadingMore] = useState(false)
  const [salesTotal, setSalesTotal] = useState(0)
  const [salesOffset, setSalesOffset] = useState(0)

  const [error, setError] = useState('')
  const [formError, setFormError] = useState('')
  const formErrorRef = useRef(null)

  useEffect(() => {
    if (formError && formErrorRef.current) {
      formErrorRef.current.scrollIntoView({ block: 'nearest', behavior: 'smooth' })
    }
  }, [formError])

  const [modalOpen, setModalOpen] = useState(false)

  const [editing, setEditing] = useState(null)

  const [payModal, setPayModal] = useState(null)

  const [payAmount, setPayAmount] = useState('')

  const [invoiceSale, setInvoiceSale] = useState(null)
  const [invoiceLoadingId, setInvoiceLoadingId] = useState(null)
  const [excelLoadingId, setExcelLoadingId] = useState(null)

  const [form, setForm] = useState(EMPTY_FORM)
  const [saleGate, setSaleGate] = useState(null)
  const pickBranchOnSale = Boolean(canCreateSale && (saleGate?.must_pick_branch || (isExecutiveUser(user) && !saleGate)))

  const refreshSaleGate = useCallback(async () => {
    if (!canCreateSale) return
    try {
      const data = await attendanceApi.saleGate()
      setSaleGate(data)
    } catch {
      setSaleGate({
        blocked: true,
        reason: 'وضعیت حضور قابل بررسی نیست؛ اتصال به سرور را بررسی کنید.',
        must_pick_branch: false,
      })
    }
  }, [canCreateSale, user?.id])

  useEffect(() => {
    if (!canCreateSale) return undefined
    let cancelled = false
    refreshSaleGate().catch(() => {
      if (!cancelled) setSaleGate(null)
    })
    return () => { cancelled = true }
  }, [canCreateSale, refreshSaleGate])

  const [filters, setFilters] = useState({ payment_method: '', payment_status: '', order_kind: '', date_from: '', date_to: '', search: '' })

  useEffect(() => {
    if (summaryOnly) setPersonalCollapsed(false)
    else setPersonalCollapsed(isSystemAdmin(user))
  }, [user?.id, user?.role, summaryOnly])

  const buildParams = (source = filters) => {

    const p = new URLSearchParams()

    Object.entries(source).forEach(([k, v]) => { if (v) p.set(k, v) })

    return p.toString()

  }



  const load = async (nextFilters = filters, { append = false, offset = 0 } = {}) => {
    if (append) setLoadingMore(true)
    else setLoading(true)
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
        setSalesTotal(0)
        setSalesOffset(0)
        setSummary({ total_final: monthlyData.total_final, count: monthlyData.count })
        setMonthly(monthlyData)
        setDaily(null)
        setWeekly(null)
        setDailyBreakdown(breakdownData)
        setCustomers([])
        setError('')
        return
      }
      if (!canViewList) {
        setSales([])
        setSalesTotal(0)
        setSummary(null)
        setError('')
        return
      }

      const params = withPageParams(buildParams(nextFilters), { offset, limit: PAGE_SIZE })
      if (branchQueueView) {
        const q = new URLSearchParams(params)
        q.set('queue', 'branch')
        if (append) {
          const listData = await salesApi.list(q.toString())
          setSales((prev) => [...prev, ...(listData.results || [])])
          setSalesTotal(listData.total || 0)
          setSalesOffset(listData.offset ?? offset)
          setError('')
          return
        }
        const bm = breakdownMonth
        const reportTasks = [
          salesApi.monthlyReport(jNow.year, jNow.month),
          salesApi.yearlyReport(jNow.year),
        ]
        if (isShop) {
          reportTasks.push(salesApi.dailyBreakdown(bm.year, bm.month))
        }
        const needDaily = viewAllSales || shopOfficeQueue
        if (needDaily) {
          reportTasks.push(salesApi.dailyReport(todayIso()))
        }
        if (shopOfficeQueue) {
          reportTasks.push(salesApi.weeklyReport(todayIso()))
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
        const dailyData = needDaily ? allResults[nextIdx++] : null
        const weeklyData = shopOfficeQueue ? allResults[nextIdx++] : null
        setSales(listData.results)
        setSalesTotal(listData.total || 0)
        setSalesOffset(listData.offset ?? 0)
        setSummary(null)
        setMonthly(monthlyData)
        setYearly(yearlyData)
        setDaily(needDaily ? dailyData : null)
        setWeekly(shopOfficeQueue ? weeklyData : null)
        setDailyBreakdown(breakdownData)
        setCustomers([])
        setError('')
        return
      }

      if (append) {
        const salesData = await salesApi.list(params)
        setSales((prev) => [...prev, ...(salesData.results || [])])
        setSalesTotal(salesData.total || 0)
        setSalesOffset(salesData.offset ?? offset)
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
      setSalesTotal(salesData.total || 0)
      setSalesOffset(salesData.offset ?? 0)
      setSummary(salesData.summary)
      setCustomers([])
      if (viewAllSales) {
        setDaily(dailyData)
        setMonthly(monthlyData)
        setYearly(yearlyData)
        setWeekly(null)
      } else {
        setDaily(null)
        setMonthly(null)
        setYearly(null)
        setWeekly(null)
      }
      setError('')
    } catch (e) {
      setError(e.message)
    } finally {
      setLoading(false)
      setLoadingMore(false)
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
    const defaultLocation = (stockLocations || [])[0]
    setEditing(null)
    setForm({
      ...EMPTY_FORM,
      stock_source_kind: defaultLocation?.kind || '',
      stock_source_warehouse_id: defaultLocation?.warehouse_id
        ? String(defaultLocation.warehouse_id)
        : '',
      stock_source_branch: defaultLocation?.branch || '',
    })
    setSelectedCustomer(null)
    setFormError('')
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

    setFormError('')
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

  const shopDeliveryMinIso = todayIso()
  const shopDeliveryMaxIso = addYearsToIso(shopDeliveryMinIso, 3)
  const shopDeliveryDateProps = isShop
    ? { minIso: shopDeliveryMinIso, maxIso: shopDeliveryMaxIso }
    : {}

  const save = async (e) => {
    e.preventDefault()
    const validationError = validateSaleSubmit({
      editing,
      form,
      selectedCustomer,
      pickBranchOnSale,
      isShop,
      shopDeliveryMinIso,
      shopDeliveryMaxIso,
      saleGate,
      stockLocations,
    })
    if (validationError) {
      setFormError(validationError)
      return
    }

    try {
      setFormError('')
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

        if (pickBranchOnSale) {
          payload.branch = form.branch
        }

        payload.stock_source_kind = form.stock_source_kind
        if (form.stock_source_kind === 'warehouse') {
          payload.stock_source_warehouse_id = Number(form.stock_source_warehouse_id)
        }
        if (form.stock_source_kind === 'branch') {
          payload.stock_source_branch = form.stock_source_branch
        }

        if (isDeposit(form)) {
          payload.delivery_date = form.delivery_date
          payload.paid_amount = Number(form.paid_amount || 0)
        }

        if (isPreInvoice(form)) {
          payload.paid_amount = Number(form.paid_amount || 0)
        }

        if (form.line_items?.length) {
          payload.line_items = form.line_items.map((i) => ({
            product_id: i.product_id,
            variant_id: i.variant_id || null,
            quantity: Number(i.quantity || 1),
            frame_id: i.frame_id || null,
            frame_model_id: i.frame_model_id || null,
            frame_config: i.frame_config || {},
            workset_config: i.workset_config || {},
            furniture_workset_id: i.furniture_workset_id || null,
          }))
          if (form.seat_count) payload.seat_count = Number(form.seat_count)
          payload.amount = form.line_items.reduce(
            (s, i) => s + Number(i.unit_price || 0) * Number(i.quantity || 1),
            0,
          )
        }

        if (selectedCustomer?.id) {
          payload.customer_id = selectedCustomer.id
        } else {
          payload.new_customer = {
            full_name: selectedCustomer.full_name,
            phone: selectedCustomer.phone,
            address: selectedCustomer.address || '',
            birthday: selectedCustomer.birthday || '',
          }
        }

        if (form.payment_method === 'check' && !isPreInvoice(form) && !isDeposit(form)) {
          payload.paid_amount = Number(form.paid_amount || 0)
        }

        if (showInstallmentSection(form, isShop) && form.installments.length) {
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

        if (!isDeposit(form) && form.delivery_date) {
          payload.delivery_date = form.delivery_date
        }

        await salesApi.create(payload)
      }

      setModalOpen(false)
      setForm(EMPTY_FORM)
      setEditing(null)
      setSelectedCustomer(null)
      setFormError('')
      load()
    } catch (err) {
      setFormError(err.message)
    }
  }



  const submitPayment = async (e) => {
    e.preventDefault()
    if (!Number(payAmount) || Number(payAmount) <= 0) {
      setFormError('مبلغ پرداخت را وارد کنید.')
      return
    }

    try {
      setFormError('')
      await salesApi.recordPayment(payModal.id, { amount: Number(payAmount) })
      setPayModal(null)
      load()
    } catch (err) {
      setFormError(err.message)
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
  const walletBalance = selectedCustomer?.wallet_balance ?? editing?.customer_wallet_balance ?? 0
  const customerSelected = Boolean(selectedCustomer?.id || editing?.customer_id)

  const monthLabel = `${PERSIAN_MONTHS[jNow.month - 1]} ${toPersianDigits(jNow.year)}`
  const yearLabel = toPersianDigits(jNow.year)
  const branchStatsTitle = isExecutiveUser(user) ? 'همه شعب' : (user?.branch_label || 'شعبه من')
  const pendingSendCount = sales.filter((s) => s.workflow_stage === 'pending_branch').length
  const dayCountLabel = daily?.jalali_year
    ? formatJalali(jalaliToIso(daily.jalali_year, daily.jalali_month, daily.jalali_day))
    : formatJalali(todayIso())
  const weekCountHint = weekly?.start_jalali_year
    ? `${formatJalali(jalaliToIso(weekly.start_jalali_year, weekly.start_jalali_month, weekly.start_jalali_day))} تا ${formatJalali(jalaliToIso(weekly.end_jalali_year, weekly.end_jalali_month, weekly.end_jalali_day))}`
    : 'شنبه تا جمعه'



  return (

    <div className={fromLegacy(`page sales-page${shopOfficeQueue ? ' sales-page-shop-office' : ''}`)}>

      {isShop && hasPermission(user, 'self_check_in') && !isSystemAdmin(user) && (
        <AttendanceWidget onStatusChange={refreshSaleGate} />
      )}

      {(summaryOnly || (viewOwnSales && !branchQueueOnly)) && (
        <PersonalSalesPanel
          collapsed={personalCollapsed}
          onToggleCollapse={() => setPersonalCollapsed((v) => !v)}
          onApplyListFilter={summaryOnly ? undefined : applyPersonalFilter}
          monthOnly={false}
        />
      )}

      {viewAllSales && (
      <div className={fromLegacy("stats-grid")}>

        <Card
          title={
            daily?.jalali_year
              ? `فروش ${formatJalali(jalaliToIso(daily.jalali_year, daily.jalali_month, daily.jalali_day))}`
              : `فروش ${formatJalali(todayIso())}`
          }
        >
          <p className={fromLegacy("stat-value")}>{formatMoney(daily?.total_final || 0)}</p>
          <p className={fromLegacy("muted")}>{daily?.count || 0} فقره — فقط همین روز</p>
        </Card>

        <Card title={`فروش ${monthLabel}`}><p className={fromLegacy("stat-value")}>{formatMoney(monthly?.total_final || 0)}</p><p className={fromLegacy("muted")}>{monthly?.count || 0} فقره — همه شعب</p></Card>

        <Card title={`فروش سال ${yearLabel}`}><p className={fromLegacy("stat-value")}>{formatMoney(yearly?.total_final || 0)}</p><p className={fromLegacy("muted")}>{yearly?.count || 0} فقره — سال جاری</p></Card>

      </div>
      )}

      {shopOfficeQueue && (
      <div className={fromLegacy("shop-office-queue-hero")}>
        <div className={fromLegacy("shop-office-queue-hero-main")}>
          <span className={fromLegacy("shop-office-queue-hero-icon")} aria-hidden>📤</span>
          <div>
            <h2 className={fromLegacy("shop-office-queue-hero-title")}>صف ارسال به اداری</h2>
            <p className={fromLegacy("shop-office-queue-hero-desc")}>
              سفارش‌های ثبت‌شده را بررسی کنید و برای تایید حسابداری ارسال کنید.
            </p>
          </div>
        </div>
        <div className={fromLegacy("shop-office-queue-hero-badge")}>
          <span className={fromLegacy("shop-office-queue-hero-count")}>{toPersianDigits(pendingSendCount)}</span>
          <span className={fromLegacy("shop-office-queue-hero-label")}>در انتظار ارسال</span>
        </div>
      </div>
      )}

      {shopOfficeQueue && !viewAllSales && (
      <div className={fromLegacy("stat-grid shop-office-stats sales-stats-grid shop-office-period-stats")}>
        <StatCard
          label={`فروش ${dayCountLabel}`}
          value={toPersianDigits(daily?.count || 0)}
          hint={`فقره — ${branchStatsTitle}`}
          accent="var(--accent)"
        />
        <StatCard
          label="فروش این هفته"
          value={toPersianDigits(weekly?.count || 0)}
          hint={`فقره — ${weekCountHint}`}
          accent="var(--info)"
        />
        <StatCard
          label={`فروش ${monthLabel}`}
          value={toPersianDigits(monthly?.count || 0)}
          hint={`فقره — ${branchStatsTitle}`}
          accent="var(--accent)"
        />
        <StatCard
          label={`فروش سال ${yearLabel}`}
          value={toPersianDigits(yearly?.count || 0)}
          hint="فقره — سال جاری"
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
      <div className={fromLegacy("stats-grid")}>
        <Card title={`فروش ماه ${monthLabel} — ${branchStatsTitle}`}>
          <p className={fromLegacy("stat-value")}>{toPersianDigits(monthly?.count || 0)} فقره</p>
          <p className={fromLegacy("muted")}>شامل ارسال‌شده به اداری</p>
        </Card>
        <Card title={`فروش سال ${yearLabel} — ${branchStatsTitle}`}>
          <p className={fromLegacy("stat-value")}>{toPersianDigits(yearly?.count || 0)} فقره</p>
          <p className={fromLegacy("muted")}>سال جاری شعبه</p>
        </Card>
      </div>
      )}

      <Card
        title={salesPageTitle()}
        className={shopOfficeQueue ? 'shop-office-queue-card-wrap' : ''}
        actions={canCreateSale ? <Button onClick={openCreate} disabled={Boolean(saleGate?.blocked)}>+ ثبت فروش</Button> : null}
      >

        {error && <div className={fromLegacy("alert-error")}>{error}</div>}

        {shopOfficeQueue && !loading && pendingSendCount > 0 && (
          <p className={fromLegacy("shop-office-queue-hint")}>
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
            {monthly.amounts_masked ? (
              <p className={fromLegacy("stat-value")}>{toPersianDigits(monthly.count || 0)} سفارش</p>
            ) : (
              <>
                <p className={fromLegacy("stat-value")}>{formatMoney(monthly.total_final || 0)}</p>
                <p className={fromLegacy("muted")}>{monthly.count || 0} سفارش ثبت‌شده</p>
              </>
            )}
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
            <Field label="وضعیت پرداخت">
              <Select
                value={filters.payment_status}
                onChange={(v) => setFilters({ ...filters, payment_status: v })}
                options={[
                  { value: '', label: 'همه' },
                  { value: 'paid', label: 'پرداخت‌شده' },
                  { value: 'unpaid', label: 'پرداخت‌نشده' },
                  { value: 'installment', label: 'قسطی' },
                ]}
                placeholder="همه"
              />
            </Field>
            <Field label="نوع سفارش">
              <Select
                value={filters.order_kind}
                onChange={(v) => setFilters({ ...filters, order_kind: v })}
                options={[{ value: '', label: 'همه' }, ...orderKinds]}
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
                className={fromLegacy("search-input")}
                value={filters.search}
                onChange={(e) => setFilters({ ...filters, search: e.target.value })}
                placeholder="فاکتور یا مشتری"
              />
            </Field>
            <div className={fromLegacy("page-filters-actions")}>
              <Button type="submit">اعمال فیلتر</Button>
            </div>
          </FilterBar>
        </form>

        {loading ? <div className={fromLegacy("loading")}>در حال بارگذاری…</div> : sales.length === 0 ? (

          <EmptyState text={shopOfficeQueue ? 'سفارشی در صف ارسال نیست — همه به اداری ارسال شده‌اند.' : 'فروشی یافت نشد.'} />

        ) : (

          <>

          <div className={fromLegacy(`table-wrap sales-table-desktop${shopOfficeQueue ? ' shop-office-table-wrap' : ''}`)}>

          <table className={fromLegacy(`table${shopOfficeQueue ? ' shop-office-table' : ''}`)}>

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
                    <button type="button" className={fromLegacy("link")} onClick={() => openInvoice(s)} disabled={invoiceLoadingId === s.id}>
                      {invoiceLoadingId === s.id ? '…' : 'فاکتور'}
                    </button>
                  </td>

                  <td>
                    <button type="button" className={fromLegacy("link")} onClick={() => downloadExcel(s)} disabled={excelLoadingId === s.id}>
                      {excelLoadingId === s.id ? '…' : 'اکسل'}
                    </button>
                  </td>

                  {(canActOnSale(s)) && (

                    <td className={fromLegacy("row-actions")}>

                      {canApproveBranch && pendingSend && (
                        shopOfficeQueue ? (
                          <Button type="button" variant="success" className={fromLegacy("btn-sm shop-office-send-btn")} onClick={() => approveBranch(s)}>
                            ارسال به اداری
                          </Button>
                        ) : (
                          <button type="button" className={fromLegacy("link link-success")} onClick={() => approveBranch(s)}>{isShop ? 'ارسال به اداری' : 'تایید شعبه'}</button>
                        )
                      )}

                      {canApproveAccounting && s.workflow_stage === 'branch_approved' && (
                        <button type="button" className={fromLegacy("link link-success")} onClick={() => approveAccounting(s)}>تایید حسابداری</button>
                      )}

                      {canEditSale(s) && (
                        <>
                      <button type="button" className={fromLegacy("link")} onClick={() => openEdit(s)}>ویرایش</button>

                      {s.balance_due > 0 && s.order_status !== 'cancelled' && !s.amounts_masked && (
                        <button type="button" className={fromLegacy("link link-success")} onClick={() => { setPayModal(s); setPayAmount(String(s.balance_due)) }}>پرداخت</button>
                      )}

                      {s.order_kind === 'pre_invoice' && s.order_status === 'pending' && (
                        <>
                          <button type="button" className={fromLegacy("link link-success")} onClick={() => confirmOrder(s)}>تایید</button>
                          <button type="button" className={fromLegacy("link danger")} onClick={() => cancelOrder(s)}>لغو</button>
                        </>
                      )}

                      {(s.order_kind === 'deposit') && s.order_status === 'pending' && (
                        <button type="button" className={fromLegacy("link danger")} onClick={() => cancelOrder(s)}>لغو</button>
                      )}

                      {s.order_status !== 'cancelled' && (
                        <button type="button" className={fromLegacy("link danger")} onClick={() => remove(s.id)}>حذف</button>
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

          <div className={fromLegacy(`sales-cards-mobile${shopOfficeQueue ? ' shop-office-cards-mobile' : shopBranchSupervisor ? ' sales-branch-queue-mobile' : ''}`)}>
            {sales.map((s) => {
              const pendingSend = s.workflow_stage === 'pending_branch'
              if (shopOfficeQueue) {
                return (
                  <div key={s.id} className={fromLegacy(`shop-office-card${pendingSend ? ' shop-office-card-pending' : ''}`)}>
                    <div className={fromLegacy("shop-office-card-head")}>
                      <div className={fromLegacy("shop-office-card-meta")}>
                        <span className={fromLegacy("shop-office-card-invoice")}>{s.invoice_number || `#${s.id}`}</span>
                        {isShop && branchQueueView && (
                          <span className={fromLegacy("shop-office-card-branch")}>{s.branch_label || s.branch || '—'}</span>
                        )}
                      </div>
                      <Badge color={resolvedOrderStatusColors[s.order_status] || 'var(--accent)'}>
                        {s.order_kind_display}
                      </Badge>
                    </div>
                    <div className={fromLegacy("shop-office-card-customer")}>{s.customer_name}</div>
                    <div className={fromLegacy("shop-office-card-grid")}>
                      <div className={fromLegacy("shop-office-card-stat")}>
                        <span className={fromLegacy("shop-office-card-stat-label")}>مبلغ نهایی</span>
                        <strong>{s.amounts_masked ? '—' : formatMoney(s.final_amount)}</strong>
                      </div>
                      <div className={fromLegacy("shop-office-card-stat")}>
                        <span className={fromLegacy("shop-office-card-stat-label")}>مانده</span>
                        <strong className={!s.amounts_masked && s.balance_due > 0 ? 'shop-office-balance-due' : ''}>
                          {s.amounts_masked ? '—' : formatMoney(s.balance_due)}
                        </strong>
                      </div>
                      <div className={fromLegacy("shop-office-card-stat")}>
                        <span className={fromLegacy("shop-office-card-stat-label")}>پرداخت‌شده</span>
                        <span>{s.amounts_masked ? '—' : formatMoney(s.paid_amount)}</span>
                      </div>
                      <div className={fromLegacy("shop-office-card-stat")}>
                        <span className={fromLegacy("shop-office-card-stat-label")}>تاریخ</span>
                        <span>{formatDate(s.sold_at)}</span>
                      </div>
                    </div>
                    {canApproveBranch && pendingSend && (
                      <Button
                        type="button"
                        variant="success"
                        className={fromLegacy("shop-office-send-btn")}
                        onClick={() => approveBranch(s)}
                      >
                        ارسال به اداری
                      </Button>
                    )}
                    <div className={fromLegacy("shop-office-card-tools")}>
                      <button type="button" className={fromLegacy("link")} onClick={() => openInvoice(s)} disabled={invoiceLoadingId === s.id}>
                        {invoiceLoadingId === s.id ? '…' : 'فاکتور'}
                      </button>
                      <button type="button" className={fromLegacy("link")} onClick={() => downloadExcel(s)} disabled={excelLoadingId === s.id}>
                        {excelLoadingId === s.id ? '…' : 'اکسل'}
                      </button>
                      {canEditSale(s) && (
                        <>
                          <button type="button" className={fromLegacy("link")} onClick={() => openEdit(s)}>ویرایش</button>
                          {s.balance_due > 0 && s.order_status !== 'cancelled' && !s.amounts_masked && (
                            <button type="button" className={fromLegacy("link link-success")} onClick={() => { setPayModal(s); setPayAmount(String(s.balance_due)) }}>پرداخت</button>
                          )}
                          {s.order_kind === 'pre_invoice' && s.order_status === 'pending' && (
                            <>
                              <button type="button" className={fromLegacy("link link-success")} onClick={() => confirmOrder(s)}>تایید</button>
                              <button type="button" className={fromLegacy("link danger")} onClick={() => cancelOrder(s)}>لغو</button>
                            </>
                          )}
                          {s.order_kind === 'deposit' && s.order_status === 'pending' && (
                            <button type="button" className={fromLegacy("link danger")} onClick={() => cancelOrder(s)}>لغو</button>
                          )}
                          {s.order_status !== 'cancelled' && hasPermission(user, 'delete_sale') && (
                            <button type="button" className={fromLegacy("link danger")} onClick={() => remove(s.id)}>حذف</button>
                          )}
                        </>
                      )}
                    </div>
                  </div>
                )
              }
              return (
              <div key={s.id} className={fromLegacy(`m-card${shopBranchSupervisor ? ' sales-branch-queue-card' : ''}`)}>
                <div className={fromLegacy("m-card-head")}>
                  <div>
                    <strong>{s.customer_name}</strong>
                    <div className={fromLegacy("muted small")}>{s.invoice_number || `#${s.id}`}</div>
                    {isShop && branchQueueView && (
                      <div className={fromLegacy("muted small")}>{s.branch_label || s.branch || '—'}</div>
                    )}
                  </div>
                  <Badge color={resolvedOrderStatusColors[s.order_status] || 'var(--accent)'}>
                    {s.order_kind_display}
                    {!hideWorkflowStage && s.order_status === 'pending' ? ' — در انتظار' : ''}
                  </Badge>
                </div>
                <div className={fromLegacy("m-card-grid")}>
                  <div><span className={fromLegacy("muted")}>نهایی</span><strong>{s.amounts_masked ? '—' : formatMoney(s.final_amount)}</strong></div>
                  <div><span className={fromLegacy("muted")}>مانده</span><strong>{s.amounts_masked ? '—' : formatMoney(s.balance_due)}</strong></div>
                  <div><span className={fromLegacy("muted")}>پرداخت</span>{s.amounts_masked ? '—' : formatMoney(s.paid_amount)}</div>
                  <div><span className={fromLegacy("muted")}>تاریخ</span>{formatDate(s.sold_at)}</div>
                </div>
                {canApproveBranch && s.workflow_stage === 'pending_branch' && (
                  <div className={fromLegacy(`m-card-primary-action${shopBranchSupervisor ? ' m-card-primary-action-prominent' : ''}`)}>
                    <Button
                      type="button"
                      variant="success"
                      className={fromLegacy("m-card-send-office")}
                      onClick={() => approveBranch(s)}
                    >
                      {isShop ? 'ارسال به اداری' : 'تایید شعبه'}
                    </Button>
                  </div>
                )}
                <div className={fromLegacy("m-card-actions")}>
                  <button type="button" className={fromLegacy("link")} onClick={() => openInvoice(s)} disabled={invoiceLoadingId === s.id}>
                    {invoiceLoadingId === s.id ? '…' : 'فاکتور'}
                  </button>
                  <button type="button" className={fromLegacy("link")} onClick={() => downloadExcel(s)} disabled={excelLoadingId === s.id}>
                    {excelLoadingId === s.id ? '…' : 'اکسل'}
                  </button>
                  {canApproveAccounting && s.workflow_stage === 'branch_approved' && (
                    <button type="button" className={fromLegacy("link link-success")} onClick={() => approveAccounting(s)}>تایید حسابداری</button>
                  )}
                  {canEditSale(s) && (
                    <>
                      <button type="button" className={fromLegacy("link")} onClick={() => openEdit(s)}>ویرایش</button>
                      {s.balance_due > 0 && s.order_status !== 'cancelled' && !s.amounts_masked && (
                        <button type="button" className={fromLegacy("link link-success")} onClick={() => { setPayModal(s); setPayAmount(String(s.balance_due)) }}>پرداخت</button>
                      )}
                      {s.order_kind === 'pre_invoice' && s.order_status === 'pending' && (
                        <>
                          <button type="button" className={fromLegacy("link link-success")} onClick={() => confirmOrder(s)}>تایید</button>
                          <button type="button" className={fromLegacy("link danger")} onClick={() => cancelOrder(s)}>لغو</button>
                        </>
                      )}
                      {s.order_kind === 'deposit' && s.order_status === 'pending' && (
                        <button type="button" className={fromLegacy("link danger")} onClick={() => cancelOrder(s)}>لغو</button>
                      )}
                      {s.order_status !== 'cancelled' && hasPermission(user, 'delete_sale') && (
                        <button type="button" className={fromLegacy("link danger")} onClick={() => remove(s.id)}>حذف</button>
                      )}
                    </>
                  )}
                </div>
              </div>
              )
            })}
          </div>

          <LoadMoreButton
            hasMore={sales.length < salesTotal}
            loading={loadingMore}
            onClick={() => load(filters, { append: true, offset: salesOffset + PAGE_SIZE })}
          />

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



      <Modal title={editing ? 'ویرایش فروش' : 'ثبت فروش'} open={modalOpen} onClose={() => { setModalOpen(false); setEditing(null); setFormError('') }}>

        <form onSubmit={save} className={fromLegacy("form")} noValidate>

          {formError ? (
            <div className={fromLegacy("alert-error")} role="alert">{formError}</div>
          ) : null}

          {editing ? (

            <>

              <p className={fromLegacy("muted")}>مشتری: {editing.customer_name}</p>

              <Field label="مبلغ"><MoneyInput min="1" value={form.amount} onChange={(e) => setForm({ ...form, amount: e.target.value })} required /></Field>

              <SaleDiscountFields
                form={form}
                setForm={setForm}
                walletBalance={walletBalance}
                customerSelected={customerSelected}
                customerId={editing?.customer_id}
                excludeSaleId={editing?.id}
              />

              <Field label="پرداخت‌شده"><MoneyInput min="0" value={form.paid_amount} onChange={(e) => setForm({ ...form, paid_amount: e.target.value })} /></Field>

              <Field label="روش پرداخت">
                <Select
                  value={form.payment_method}
                  onChange={(v) => setForm({ ...form, payment_method: v })}
                  options={paymentMethods}
                />
              </Field>

              <Field label="شماره فاکتور"><input className={fromLegacy("ltr")} value={form.invoice_number} onChange={(e) => setForm({ ...form, invoice_number: e.target.value })} /></Field>

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
                  if (c && (c.cashback_balance ?? 0) <= 0 && form.discount_type === 'cashback') {
                    setForm((f) => ({ ...f, discount_type: 'amount', discount_value: '' }))
                  }
                }}
                onCreateNew={(c) => setSelectedCustomer(c)}
              />

              {saleGate?.blocked && (
                <div className={fromLegacy("alert-error")}>{saleGate.reason}</div>
              )}

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

              <Field label="موجودی از کجا">
                <Select
                  value={
                    form.stock_source_kind === 'warehouse'
                      ? `warehouse:${form.stock_source_warehouse_id}`
                      : form.stock_source_kind === 'branch'
                        ? `branch:${form.stock_source_branch}`
                        : ''
                  }
                  onChange={(v) => {
                    const loc = (stockLocations || []).find((item) => item.key === v)
                    if (!loc) {
                      setForm({ ...form, stock_source_kind: '', stock_source_warehouse_id: '', stock_source_branch: '' })
                      return
                    }
                    setForm({
                      ...form,
                      stock_source_kind: loc.kind,
                      stock_source_warehouse_id: loc.warehouse_id ? String(loc.warehouse_id) : '',
                      stock_source_branch: loc.branch || '',
                    })
                  }}
                  options={[
                    { value: '', label: 'انتخاب منبع موجودی…' },
                    ...(stockLocations || []).map((loc) => ({ value: loc.key, label: loc.label })),
                  ]}
                  required
                />
              </Field>


              <ProductLines
                lines={form.line_items}
                seatCount={form.seat_count}
                onSeatCountChange={(seat_count) => setForm({ ...form, seat_count })}
                stockSourceKey={
                  form.stock_source_kind === 'warehouse' && form.stock_source_warehouse_id
                    ? `warehouse:${form.stock_source_warehouse_id}`
                    : form.stock_source_kind === 'branch' && form.stock_source_branch
                      ? `branch:${form.stock_source_branch}`
                      : ''
                }
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
                  <p className={fromLegacy("sale-lines-total")}><strong>{formatMoney(Number(form.amount || 0))}</strong></p>
                </Field>
              ) : (
                <Field label="مبلغ"><MoneyInput min="1" value={form.amount} onChange={(e) => setForm({ ...form, amount: e.target.value })} required /></Field>
              )}

              <SaleDiscountFields
                form={form}
                setForm={setForm}
                walletBalance={walletBalance}
                customerSelected={customerSelected}
                customerId={selectedCustomer?.id}
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

              <Field label="شماره فاکتور"><input className={fromLegacy("ltr")} value={form.invoice_number} onChange={(e) => setForm({ ...form, invoice_number: e.target.value })} placeholder="خالی = شماره سیستمی" /></Field>

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

          {formError ? (
            <div ref={formErrorRef} className={fromLegacy("alert-error")} role="alert">{formError}</div>
          ) : null}
          <Button type="submit" disabled={!editing && Boolean(saleGate?.blocked)}>{editing ? 'ذخیره تغییرات' : 'ثبت'}</Button>

        </form>

      </Modal>



      <Modal title="ثبت پرداخت" open={!!payModal} onClose={() => { setPayModal(null); setFormError('') }}>

        {payModal && (

          <form onSubmit={submitPayment} className={fromLegacy("form")} noValidate>

            {formError ? (
              <div className={fromLegacy("alert-error")} role="alert">{formError}</div>
            ) : null}

            <p className={fromLegacy("muted")}>مانده: {formatMoney(payModal.balance_due)}</p>

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


