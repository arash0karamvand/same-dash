// اداری — تایید، اصلاح کامل فاکتور و ارسال به کارخانه

import { useEffect, useState } from 'react'
import { cycleApi, officeApi, salesApi } from '../api/client'
import { useAuth } from '../context/AuthContext'
import { useConfig } from '../context/ConfigContext'
import CheckAccountPicker from '../components/CheckAccountPicker'
import CustomerSearch from '../components/CustomerSearch'
import InstallmentLines, { EMPTY_INSTALLMENT } from '../components/InstallmentLines'
import MoneyInput from '../components/MoneyInput'
import PersianDateInput from '../components/PersianDateInput'
import ProductLines from '../components/ProductLines'
import OfficeCycleNav from '../components/OfficeCycleNav'
import OfficeSectionCard from '../components/OfficeSectionCard'
import { OFFICE_APPROVE_FILTER, recordFiltersToQueryString } from '../config/recordFilterSections'
import SaleDiscountFields, { saleBalanceDue } from '../components/SaleDiscountFields'
import Select from '../components/Select'
import { Button, Field, Modal } from '../components/ui'
import { hasPermission } from '../utils/permissions'
import { formatDate, formatMoney } from '../utils/format'
import WorkflowOrdersPage from './WorkflowOrdersPage'
import { fromLegacy } from '../styles/tw.js'

const OFFICE_QUEUE_FILTER_DEFAULTS = OFFICE_APPROVE_FILTER.initialFilters

function buildOfficeListQuery(filters) {
  return recordFiltersToQueryString(filters, { limit: OFFICE_APPROVE_FILTER.resultLimit })
}

const EMPTY_FACTORY_WORK = {
  receive_kind: 'branch_floor',
  customer: null,
  source_invoice_number: '',
  contract_party: '',
  warehouse_id: '',
  source_branch: '',
  description: '',
  delivery_date: '',
  seat_count: '',
  line_items: [],
}

const EMPTY_EDIT = {
  description: '',
  invoice_number: '',
  payment_method: 'cash',
  payment_status: 'paid',
  order_kind: 'normal',
  delivery_date: '',
  amount: '',
  discount_type: 'amount',
  discount_value: '',
  paid_amount: '',
  seat_count: '',
  line_items: [],
  installments: [],
}

function mapInstallmentsFromSale(items = []) {
  return items.map((i) => ({
    amount: String(i.amount ?? ''),
    due_date: i.due_date?.slice(0, 10) || '',
    check_number: i.check_number || '',
    bank_name: i.bank_name || '',
    notes: i.notes || '',
    received_at: i.received_at?.slice(0, 10) || '',
    receiver_name: i.receiver_name || '',
  }))
}

function mapLineItemsFromSale(items = []) {
  return items.map((i) => ({
    product_id: i.product_id || '',
    variant_id: i.variant_id || '',
    frame_id: i.frame_id || '',
    furniture_workset_id: i.furniture_workset_id || '',
    furniture_workset_name: i.furniture_workset_name || '',
    workset_config: i.workset_config || {},
    product_name: i.product_name || '',
    product_model: i.product_model || '',
    fabric: i.fabric || '',
    color_name: i.color_name || '',
    color_hex: i.color_hex || '',
    quantity: i.quantity || 1,
    unit_price: i.unit_price != null ? String(i.unit_price) : '',
  }))
}

export default function Office() {
  const { user } = useAuth()
  const { choices, branches } = useConfig()
  const canCreateFactoryWork = hasPermission(user, 'approve_sale_accounting')
  const paymentMethods = choices('payment_method')
  const orderKinds = choices('order_kind')
  const paymentStatuses = choices('payment_status')
  const receiveKinds = choices('receive_kind')
  const fulfillmentRoutes = choices('fulfillment_route')
  const [editOrder, setEditOrder] = useState(null)
  const [rejectOrder, setRejectOrder] = useState(null)
  const [rollbackOrder, setRollbackOrder] = useState(null)
  const [rollbackReason, setRollbackReason] = useState('')
  const [rollingBack, setRollingBack] = useState(false)
  const [rollbackError, setRollbackError] = useState('')
  const [rejectReason, setRejectReason] = useState('')
  const [rejecting, setRejecting] = useState(false)
  const [rejectError, setRejectError] = useState('')
  const [form, setForm] = useState(EMPTY_EDIT)
  const [saving, setSaving] = useState(false)
  const [editLoading, setEditLoading] = useState(false)
  const [editError, setEditError] = useState('')
  const [reloadKey, setReloadKey] = useState(0)
  const [approveOrder, setApproveOrder] = useState(null)
  const [approveDetail, setApproveDetail] = useState(null)
  const [approveLoading, setApproveLoading] = useState(false)
  const [approveError, setApproveError] = useState('')
  const [regAccountId, setRegAccountId] = useState('')
  const [depAccountId, setDepAccountId] = useState('')
  const [saveCheckDefault, setSaveCheckDefault] = useState(true)
  const [cycleMe, setCycleMe] = useState({ enabled_routes: ['factory'], warehouses: [], colleagues: [] })
  const [fulfillmentRoute, setFulfillmentRoute] = useState('factory')
  const [warehouseId, setWarehouseId] = useState('')
  const [sourceBranch, setSourceBranch] = useState('')
  const [merchantUserId, setMerchantUserId] = useState('')
  const [warehouseSourceKind, setWarehouseSourceKind] = useState('warehouse')
  const [listFilterQuery, setListFilterQuery] = useState(() =>
    buildOfficeListQuery({ ...OFFICE_QUEUE_FILTER_DEFAULTS, model: 'office_order' }),
  )
  const [factoryWorkOpen, setFactoryWorkOpen] = useState(false)
  const [factoryWork, setFactoryWork] = useState(EMPTY_FACTORY_WORK)
  const [factoryWorkError, setFactoryWorkError] = useState('')
  const [factoryWorkSaving, setFactoryWorkSaving] = useState(false)

  const showInstallments = form.payment_status === 'installment' || form.payment_method === 'check'
  const balanceDue = saleBalanceDue(form)
  const enabledRoutes = cycleMe.enabled_routes?.length ? cycleMe.enabled_routes : ['factory']
  const routeOptions = fulfillmentRoutes.filter((opt) => enabledRoutes.includes(opt.value))

  useEffect(() => {
    cycleApi.me().then((data) => {
      setCycleMe({
        enabled_routes: data.enabled_routes || ['factory'],
        warehouses: data.warehouses || [],
        colleagues: data.colleagues || [],
      })
      const routes = data.enabled_routes || ['factory']
      if (routes.length === 1) setFulfillmentRoute(routes[0])
    }).catch(() => {})
  }, [])

  const openEdit = async (order) => {
    setEditLoading(true)
    setEditError('')
    try {
      const sale = await salesApi.get(order.source_sale_id)
      setEditOrder(order)
      setForm({
        description: sale.description || '',
        invoice_number: sale.invoice_number || '',
        payment_method: sale.payment_method || 'cash',
        payment_status: sale.payment_status || 'paid',
        order_kind: sale.order_kind || 'normal',
        delivery_date: sale.delivery_date?.slice(0, 10) || '',
        amount: String(sale.amount ?? ''),
        discount_type: sale.discount_type || 'amount',
        discount_value: String(sale.discount_value ?? sale.discount ?? 0),
        paid_amount: String(sale.paid_amount ?? 0),
        seat_count: sale.seat_count ? String(sale.seat_count) : '',
        line_items: mapLineItemsFromSale(sale.line_items),
        installments: mapInstallmentsFromSale(sale.installments),
      })
    } catch (err) {
      setEditError(err.message)
    } finally {
      setEditLoading(false)
    }
  }

  const setPaymentStatus = (value) => {
    setForm((f) => {
      const next = { ...f, payment_status: value }
      if (value === 'installment') {
        next.payment_method = 'check'
        if (!next.installments.length) next.installments = [{ ...EMPTY_INSTALLMENT }]
      }
      return next
    })
  }

  const setPaymentMethod = (value) => {
    setForm((f) => {
      const next = { ...f, payment_method: value }
      if (value === 'check') {
        next.payment_status = 'installment'
        if (!next.installments.length) next.installments = [{ ...EMPTY_INSTALLMENT }]
      }
      return next
    })
  }

  const saveEdit = async (e) => {
    e.preventDefault()
    if (!editOrder?.source_sale_id) return

    const payload = {
      description: form.description,
      invoice_number: form.invoice_number,
      payment_method: form.payment_method,
      payment_status: form.payment_status,
      order_kind: form.order_kind,
      delivery_date: form.delivery_date || null,
      discount_type: form.discount_type,
      discount_value: Number(form.discount_value) || 0,
      paid_amount: Number(form.paid_amount || 0),
    }

    if (form.line_items?.length) {
      const invalid = form.line_items.some((i) => !i.product_id || !Number(i.unit_price))
      if (invalid) {
        setEditError('هر ردیف باید محصول با قیمت داشته باشد.')
        return
      }
      payload.line_items = form.line_items.map((i) => ({
        product_id: i.product_id,
        variant_id: i.variant_id || null,
        quantity: Number(i.quantity || 1),
        frame_id: i.frame_id || null,
        furniture_workset_id: i.furniture_workset_id || null,
        workset_config: i.workset_config || {},
      }))
      if (form.seat_count) payload.seat_count = Number(form.seat_count)
      payload.amount = form.line_items.reduce(
        (s, i) => s + Number(i.unit_price || 0) * Number(i.quantity || 1),
        0,
      )
    } else {
      payload.amount = Number(form.amount)
    }

    if (showInstallments) {
      payload.installments = form.installments.map((i) => ({
        amount: Number(i.amount || 0),
        due_date: i.due_date,
        payment_method: 'check',
        check_number: i.check_number || '',
        bank_name: i.bank_name || '',
        notes: i.notes || '',
        received_at: i.received_at || null,
        receiver_name: i.receiver_name || '',
      }))
    } else {
      payload.installments = []
    }

    setSaving(true)
    setEditError('')
    try {
      await salesApi.update(editOrder.source_sale_id, payload)
      setEditOrder(null)
      setReloadKey((k) => k + 1)
    } catch (err) {
      setEditError(err.message)
    } finally {
      setSaving(false)
    }
  }

  const confirmReject = async (e) => {
    e.preventDefault()
    if (!rejectOrder) return
    setRejecting(true)
    setRejectError('')
    try {
      await officeApi.reject(rejectOrder.id, rejectReason)
      setRejectOrder(null)
      setRejectReason('')
      setReloadKey((k) => k + 1)
    } catch (err) {
      setRejectError(err.message)
    } finally {
      setRejecting(false)
    }
  }

  const confirmRollback = async (e) => {
    e.preventDefault()
    if (!rollbackOrder) return
    setRollingBack(true)
    setRollbackError('')
    try {
      await officeApi.rollback(rollbackOrder.id, rollbackReason)
      setRollbackOrder(null)
      setRollbackReason('')
      setReloadKey((k) => k + 1)
    } catch (err) {
      setRollbackError(err.message)
    } finally {
      setRollingBack(false)
    }
  }

  const openApprove = async (order) => {
    setApproveError('')
    setRegAccountId('')
    setDepAccountId('')
    setSaveCheckDefault(true)
    setWarehouseId('')
    setSourceBranch('')
    setMerchantUserId('')
    setWarehouseSourceKind('warehouse')
    const routes = cycleMe.enabled_routes?.length ? cycleMe.enabled_routes : ['factory']
    setFulfillmentRoute(routes.includes('factory') ? 'factory' : routes[0])
    setApproveOrder(order)
    setApproveDetail(order.has_pending_checks ? null : order)
    if (order?.has_pending_checks) {
      try {
        const detail = await officeApi.get(order.id)
        setApproveDetail(detail)
      } catch (err) {
        setApproveError(err.message)
      }
    }
  }

  const confirmApprove = async (e) => {
    e.preventDefault()
    if (!approveOrder) return
    if (approveOrder.has_pending_checks && !regAccountId) {
      setApproveError('حساب ثبت چک را انتخاب کنید.')
      return
    }
    if (fulfillmentRoute === 'warehouse') {
      if (warehouseSourceKind === 'warehouse' && !warehouseId) {
        setApproveError('انبار را انتخاب کنید.')
        return
      }
      if (warehouseSourceKind === 'branch' && !sourceBranch) {
        setApproveError('شعبه مبدأ را انتخاب کنید.')
        return
      }
    }
    if (fulfillmentRoute === 'merchant' && !merchantUserId) {
      setApproveError('همکار بازرگان را انتخاب کنید.')
      return
    }
    setApproveLoading(true)
    setApproveError('')
    try {
      const payload = { fulfillment_route: fulfillmentRoute }
      if (approveOrder.has_pending_checks) {
        payload.check_registration_account_id = Number(regAccountId)
        if (depAccountId) payload.check_deposit_account_id = Number(depAccountId)
        payload.save_as_default = saveCheckDefault
      }
      if (fulfillmentRoute === 'warehouse') {
        if (warehouseSourceKind === 'warehouse') payload.warehouse_id = Number(warehouseId)
        else payload.source_branch = sourceBranch
      }
      if (fulfillmentRoute === 'merchant') payload.merchant_user_id = Number(merchantUserId)
      await officeApi.approve(approveOrder.id, payload)
      setApproveOrder(null)
      setApproveDetail(null)
      setReloadKey((k) => k + 1)
    } catch (err) {
      setApproveError(err.message)
    } finally {
      setApproveLoading(false)
    }
  }

  const checkItems = (approveDetail?.installments || []).filter((i) => i.payment_method === 'check')

  const submitFactoryWork = async (e) => {
    e.preventDefault()
    if (!factoryWork.line_items?.length) {
      setFactoryWorkError('حداقل یک محصول انتخاب کنید.')
      return
    }
    if (factoryWork.receive_kind === 'merchant' && !factoryWork.contract_party.trim()) {
      setFactoryWorkError('برای بازرگان طرف قرارداد را وارد کنید.')
      return
    }
    setFactoryWorkSaving(true)
    setFactoryWorkError('')
    try {
      await officeApi.createFactoryWork({
        receive_kind: factoryWork.receive_kind,
        customer_id: factoryWork.customer?.id || null,
        source_invoice_number: factoryWork.source_invoice_number.trim() || '',
        contract_party: factoryWork.contract_party.trim(),
        warehouse_id: factoryWork.warehouse_id || null,
        source_branch: factoryWork.source_branch || '',
        description: factoryWork.description.trim(),
        delivery_date: factoryWork.delivery_date || null,
        seat_count: factoryWork.seat_count ? Number(factoryWork.seat_count) : null,
        line_items: factoryWork.line_items.map((i) => ({
          product_id: i.product_id,
          variant_id: i.variant_id || null,
          quantity: Number(i.quantity) || 1,
          frame_id: i.frame_id || null,
          workset_config: i.workset_config || {},
          furniture_workset_id: i.furniture_workset_id || null,
        })),
      })
      setFactoryWorkOpen(false)
      setFactoryWork(EMPTY_FACTORY_WORK)
      setReloadKey((k) => k + 1)
    } catch (err) {
      setFactoryWorkError(err.message)
    } finally {
      setFactoryWorkSaving(false)
    }
  }

  return (
    <>
      <OfficeCycleNav current="office" />
      <OfficeSectionCard
        section={OFFICE_APPROVE_FILTER}
        onFiltersChange={(filters) => setListFilterQuery(buildOfficeListQuery(filters))}
        actions={canCreateFactoryWork ? (
          <Button type="button" onClick={() => { setFactoryWorkError(''); setFactoryWork(EMPTY_FACTORY_WORK); setFactoryWorkOpen(true) }}>
            ثبت کار کارخانه
          </Button>
        ) : null}
      >
        <WorkflowOrdersPage
          key={`${reloadKey}-${listFilterQuery}`}
          embedInSection
          filterQuery={listFilterQuery}
          title="اداری"
          subtitle=""
          emptyTitle="سفارشی برای بررسی اداری نیست"
          listApi={officeApi.list}
          showStage
          showWorkflowHolder
          showAccountingMode
          showStatus={false}
          showBranch
          showAmounts
          onEditOrder={openEdit}
          actions={[
          {
            key: 'approve',
            label: 'تایید و انتخاب مسیر',
            variant: 'success',
            permission: 'approve_sale_accounting',
            when: (o) => o.status === 'pending_accounting',
            run: (_id, order) => openApprove(order),
          },
          {
            key: 'reject',
            label: 'عدم تایید',
            variant: 'danger',
            permission: 'approve_sale_accounting',
            when: (o) => o.status === 'pending_accounting',
            run: (_id, order) => {
              setRejectError('')
              setRejectReason('')
              setRejectOrder(order)
            },
          },
          {
            key: 'rollback',
            label: (o) => o.rollback_label || 'برگشت به مرحله قبل',
            variant: 'ghost',
            permission: 'approve_sale_accounting',
            when: (o) => o.can_rollback && o.rollback_action && o.rollback_action !== 'to_shop',
            run: (_id, order) => {
              setRollbackError('')
              setRollbackReason('')
              setRollbackOrder(order)
            },
          },
          {
            key: 'rollback-shop',
            label: (o) => o.rollback_label || 'بازگشت به فروشگاه',
            variant: 'danger',
            permission: 'approve_sale_accounting',
            when: (o) => o.can_rollback && o.rollback_action === 'to_shop',
            run: (_id, order) => {
              setRejectError('')
              setRejectReason('')
              setRejectOrder(order)
            },
          },
        ]}
      />
      </OfficeSectionCard>

      <Modal
        title={editOrder ? `اصلاح فاکتور ${editOrder.invoice_number || editOrder.id}` : 'اصلاح فاکتور'}
        open={Boolean(editOrder) || editLoading}
        onClose={() => { if (!editLoading) setEditOrder(null) }}
        wide
      >
        {editLoading ? (
          <p className={fromLegacy("muted loading")}>در حال بارگذاری فاکتور…</p>
        ) : editOrder && (
          <form onSubmit={saveEdit} className={fromLegacy("form office-invoice-form")}>
            <p className={fromLegacy("muted")}>مشتری: {editOrder.customer_name}</p>
            {editError && <div className={fromLegacy("alert alert-error")}>{editError}</div>}

            <Field label="شماره فاکتور">
              <input
                value={form.invoice_number}
                onChange={(e) => setForm({ ...form, invoice_number: e.target.value })}
              />
            </Field>

            <Field label="نوع سفارش">
              <Select
                value={form.order_kind}
                onChange={(v) => setForm({ ...form, order_kind: v })}
                options={orderKinds}
              />
            </Field>

            <ProductLines
              lines={form.line_items}
              seatCount={form.seat_count}
              onSeatCountChange={(seat_count) => setForm({ ...form, seat_count })}
              onChange={(line_items) => setForm({ ...form, line_items })}
            />

            {!form.line_items?.length && (
              <Field label="مبلغ">
                <MoneyInput
                  min="1"
                  value={form.amount}
                  onChange={(e) => setForm({ ...form, amount: e.target.value })}
                  required
                />
              </Field>
            )}

            <SaleDiscountFields
              form={form}
              setForm={setForm}
              walletBalance={editOrder.customer_wallet_balance ?? 0}
              customerSelected
              customerId={editOrder.customer_id}
              excludeSaleId={editOrder.id}
            />

            <Field label="وضعیت پرداخت">
              <Select
                value={form.payment_status}
                onChange={setPaymentStatus}
                options={paymentStatuses}
              />
            </Field>

            <Field label="پرداخت‌شده">
              <MoneyInput
                min="0"
                value={form.paid_amount}
                onChange={(e) => setForm({ ...form, paid_amount: e.target.value })}
              />
            </Field>

            <Field label="روش پرداخت">
              <Select
                value={form.payment_method}
                onChange={setPaymentMethod}
                options={paymentMethods}
              />
            </Field>

            {(form.order_kind === 'deposit' || form.delivery_date) && (
              <Field label="تاریخ تحویل">
                <PersianDateInput
                  value={form.delivery_date}
                  onChange={(v) => setForm({ ...form, delivery_date: v })}
                  onClear={() => setForm({ ...form, delivery_date: '' })}
                  clearLabel="پاک کردن"
                />
              </Field>
            )}

            {showInstallments && (
              <InstallmentLines
                installments={form.installments}
                onChange={(installments) => setForm({ ...form, installments })}
                balanceDue={balanceDue}
                customerName={editOrder?.customer_name || ''}
              />
            )}

            <Field label="توضیحات">
              <input
                value={form.description}
                onChange={(e) => setForm({ ...form, description: e.target.value })}
              />
            </Field>

            <div className={fromLegacy("form-actions")}>
              <Button type="button" variant="ghost" onClick={() => setEditOrder(null)}>انصراف</Button>
              <Button type="submit" disabled={saving}>{saving ? 'در حال ذخیره…' : 'ذخیره اصلاحیه'}</Button>
            </div>
          </form>
        )}
      </Modal>

      <Modal
        title={rejectOrder ? `عدم تایید — ${rejectOrder.invoice_number || rejectOrder.id}` : 'عدم تایید'}
        open={Boolean(rejectOrder)}
        onClose={() => { if (!rejecting) setRejectOrder(null) }}
      >
        {rejectOrder && (
          <form onSubmit={confirmReject} className={fromLegacy("form")}>
            <p className={fromLegacy("muted")}>
              سفارش مشتری {rejectOrder.customer_name} به صف فروشگاه بازگردانده می‌شود تا اصلاح و ارسال مجدد شود.
            </p>
            {rejectError && <div className={fromLegacy("alert alert-error")}>{rejectError}</div>}
            <Field label="دلیل عدم تایید (اختیاری)">
              <textarea
                rows={3}
                value={rejectReason}
                onChange={(e) => setRejectReason(e.target.value)}
                placeholder="مثلاً: اطلاعات مشتری ناقص است"
              />
            </Field>
            <div className={fromLegacy("form-actions")}>
              <Button type="button" variant="ghost" onClick={() => setRejectOrder(null)} disabled={rejecting}>
                انصراف
              </Button>
              <Button type="submit" variant="danger" disabled={rejecting}>
                {rejecting ? 'در حال بازگردانی…' : 'تایید عدم تایید'}
              </Button>
            </div>
          </form>
        )}
      </Modal>

      <Modal
        title={rollbackOrder ? `${rollbackOrder.rollback_label || 'برگشت'} — ${rollbackOrder.invoice_number || rollbackOrder.id}` : 'برگشت به مرحله قبل'}
        open={Boolean(rollbackOrder)}
        onClose={() => { if (!rollingBack) setRollbackOrder(null) }}
      >
        {rollbackOrder && (
          <form onSubmit={confirmRollback} className={fromLegacy("form")}>
            <p className={fromLegacy("muted")}>
              وضعیت فعلی: <strong>{rollbackOrder.workflow_stage_display}</strong>
              {rollbackOrder.holder_department && (
                <> — دست <strong>{rollbackOrder.holder_department}</strong></>
              )}
            </p>
            <p className={fromLegacy("muted")}>
              با این عملیات سفارش یک مرحله به عقب برمی‌گردد تا در صورت اشتباه اصلاح شود.
            </p>
            {rollbackError && <div className={fromLegacy("alert alert-error")}>{rollbackError}</div>}
            <Field label="دلیل برگشت (اختیاری)">
              <textarea
                rows={3}
                value={rollbackReason}
                onChange={(e) => setRollbackReason(e.target.value)}
                placeholder="مثلاً: اشتباه در ارسال به کارخانه"
              />
            </Field>
            <div className={fromLegacy("form-actions")}>
              <Button type="button" variant="ghost" onClick={() => setRollbackOrder(null)} disabled={rollingBack}>
                انصراف
              </Button>
              <Button type="submit" variant="danger" disabled={rollingBack}>
                {rollingBack ? 'در حال برگردانی…' : (rollbackOrder.rollback_label || 'تایید برگشت')}
              </Button>
            </div>
          </form>
        )}
      </Modal>

      <Modal
        title={approveOrder ? `تایید اداری — ${approveOrder.invoice_number || approveOrder.id}` : 'تایید اداری'}
        open={Boolean(approveOrder)}
        onClose={() => { if (!approveLoading) { setApproveOrder(null); setApproveDetail(null) } }}
        wide
      >
        {approveOrder && (
          <form onSubmit={confirmApprove} className={fromLegacy("form")}>
            <p className={fromLegacy("muted")}>مشتری: {approveOrder.customer_name}</p>
            {approveError && <div className={fromLegacy("alert alert-error")}>{approveError}</div>}
            <Field label="مسیر بعد از CRM">
              <Select
                value={fulfillmentRoute}
                onChange={setFulfillmentRoute}
                options={routeOptions}
              />
            </Field>
            {fulfillmentRoute === 'warehouse' && (
              <>
                <Field label="مبدأ ارسال">
                  <Select
                    value={warehouseSourceKind}
                    onChange={(value) => {
                      setWarehouseSourceKind(value)
                      setWarehouseId('')
                      setSourceBranch('')
                    }}
                    options={[
                      { value: 'warehouse', label: 'انبار' },
                      { value: 'branch', label: 'شعبه' },
                    ]}
                  />
                </Field>
                {warehouseSourceKind === 'warehouse' ? (
                  <Field label="انبار">
                    <Select
                      value={warehouseId}
                      onChange={setWarehouseId}
                      options={[
                        { value: '', label: 'انتخاب انبار…' },
                        ...(cycleMe.warehouses || []).map((w) => ({ value: String(w.id), label: w.label })),
                      ]}
                    />
                  </Field>
                ) : (
                  <Field label="شعبه مبدأ">
                    <Select
                      value={sourceBranch}
                      onChange={setSourceBranch}
                      options={[
                        { value: '', label: 'انتخاب شعبه…' },
                        ...(branches || []).map((b) => ({ value: b.code, label: b.label })),
                      ]}
                    />
                  </Field>
                )}
              </>
            )}
            {fulfillmentRoute === 'merchant' && (
              <Field label="همکار بازرگان">
                <Select
                  value={merchantUserId}
                  onChange={setMerchantUserId}
                  options={[
                    { value: '', label: 'انتخاب همکار…' },
                    ...(cycleMe.colleagues || []).map((c) => ({ value: String(c.id), label: c.full_name })),
                  ]}
                />
              </Field>
            )}
            {checkItems.length > 0 && (
              <div className={fromLegacy("check-approve-list")}>
                <h4>چک‌های سفارش</h4>
                <ul className={fromLegacy("check-approve-items")}>
                  {checkItems.map((c) => (
                    <li key={c.id}>
                      <strong>{formatMoney(c.amount)}</strong>
                      {' — '}
                      سررسید {formatDate(c.due_date)}
                      {c.check_number && <> — <span className={fromLegacy("ltr")}>{c.check_number}</span></>}
                      {c.bank_name && <> — {c.bank_name}</>}
                    </li>
                  ))}
                </ul>
              </div>
            )}
            {checkItems.length > 0 && (
              <CheckAccountPicker
                registrationAccountId={regAccountId}
                depositAccountId={depAccountId}
                saveAsDefault={saveCheckDefault}
                onRegistrationChange={setRegAccountId}
                onDepositChange={setDepAccountId}
                onSaveAsDefaultChange={setSaveCheckDefault}
              />
            )}
            <div className={fromLegacy("form-actions")}>
              <Button type="button" variant="ghost" onClick={() => setApproveOrder(null)} disabled={approveLoading}>
                انصراف
              </Button>
              <Button type="submit" variant="success" disabled={approveLoading}>
                {approveLoading ? 'در حال تایید…' : 'تایید و ارسال'}
              </Button>
            </div>
          </form>
        )}
      </Modal>

      <Modal
        title="ثبت کار کارخانه"
        open={factoryWorkOpen}
        onClose={() => { if (!factoryWorkSaving) setFactoryWorkOpen(false) }}
        wide
      >
        <form onSubmit={submitFactoryWork} className={fromLegacy('form')}>
          {factoryWorkError && <div className={fromLegacy('alert alert-error')}>{factoryWorkError}</div>}
          <Field label="نوع دریافت">
            <Select
              value={factoryWork.receive_kind}
              onChange={(v) => setFactoryWork({ ...factoryWork, receive_kind: v })}
              options={receiveKinds}
            />
          </Field>
          <Field label="مشتری (اختیاری)">
            <CustomerSearch
              value={factoryWork.customer}
              onSelect={(customer) => setFactoryWork({ ...factoryWork, customer })}
              onCreateNew={(customer) => setFactoryWork({ ...factoryWork, customer })}
            />
          </Field>
          <Field label="شماره فاکتور مبدأ (اختیاری)">
            <input
              className={fromLegacy('ltr')}
              value={factoryWork.source_invoice_number}
              onChange={(e) => setFactoryWork({ ...factoryWork, source_invoice_number: e.target.value })}
              placeholder="وصل به فاکتور موجود"
            />
          </Field>
          {factoryWork.receive_kind === 'merchant' && (
            <Field label="طرف قرارداد">
              <input
                value={factoryWork.contract_party}
                onChange={(e) => setFactoryWork({ ...factoryWork, contract_party: e.target.value })}
                required
              />
            </Field>
          )}
          {factoryWork.receive_kind === 'warehouse' && (
            <Field label="انبار مقصد">
              <Select
                value={factoryWork.warehouse_id}
                onChange={(v) => setFactoryWork({ ...factoryWork, warehouse_id: v })}
                options={(cycleMe.warehouses || []).map((w) => ({ value: String(w.id), label: w.label }))}
                placeholder="انتخاب انبار"
              />
            </Field>
          )}
          {factoryWork.receive_kind === 'branch_floor' && (
            <Field label="شعبه مقصد">
              <Select
                value={factoryWork.source_branch}
                onChange={(v) => setFactoryWork({ ...factoryWork, source_branch: v })}
                options={(branches || []).map((b) => ({ value: b.code, label: b.label }))}
                placeholder="انتخاب شعبه"
              />
            </Field>
          )}
          <Field label="تاریخ تحویل">
            <PersianDateInput
              value={factoryWork.delivery_date}
              onChange={(v) => setFactoryWork({ ...factoryWork, delivery_date: v })}
            />
          </Field>
          <Field label="توضیحات">
            <textarea
              rows={2}
              value={factoryWork.description}
              onChange={(e) => setFactoryWork({ ...factoryWork, description: e.target.value })}
            />
          </Field>
          <ProductLines
            lines={factoryWork.line_items}
            seatCount={factoryWork.seat_count}
            onSeatCountChange={(seat_count) => setFactoryWork({ ...factoryWork, seat_count })}
            onChange={(line_items) => setFactoryWork({ ...factoryWork, line_items })}
          />
          <div className={fromLegacy('form-actions')}>
            <Button type="button" variant="ghost" onClick={() => setFactoryWorkOpen(false)} disabled={factoryWorkSaving}>انصراف</Button>
            <Button type="submit" disabled={factoryWorkSaving}>{factoryWorkSaving ? 'در حال ثبت…' : 'ثبت و ارسال به کارخانه'}</Button>
          </div>
        </form>
      </Modal>
    </>
  )
}
