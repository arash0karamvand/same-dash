// اداری — پیگیری همه سفارش‌ها، پیشرفت گردش کار و جزئیات خرید

import { Fragment, useCallback, useEffect, useMemo, useState } from 'react'
import { officeApi } from '../api/client'
import OfficeSectionCard from '../components/OfficeSectionCard'
import { OFFICE_ORDERS_FILTER, recordFiltersToQueryString } from '../config/recordFilterSections'
import { useConfig } from '../context/ConfigContext'
import { Badge, Button, EmptyState, Modal } from '../components/ui'
import { formatDate, formatMoney } from '../utils/format'
import { toPersianDigits } from '../utils/jalali'

const WORKFLOW_COLORS = {
  pending_branch: '#f59e0b',
  branch_approved: '#6366f1',
  accounting_approved: '#8b5cf6',
  in_production: '#0ea5e9',
  production_done: '#14b8a6',
  in_freight: '#f97316',
  completed: '#10b981',
}

function WorkflowProgress({ percent, stage, stageLabel, detail, stageColor }) {
  const safe = Math.min(100, Math.max(0, Number(percent) || 0))
  return (
    <div className="order-workflow-progress">
      <div className="order-workflow-progress-head">
        <Badge color={stageColor}>{stageLabel || stage}</Badge>
        <span className="order-workflow-progress-pct">{toPersianDigits(safe)}٪</span>
      </div>
      <div className="order-workflow-progress-track" role="progressbar" aria-valuenow={safe} aria-valuemin={0} aria-valuemax={100}>
        <div className="order-workflow-progress-fill" style={{ width: `${safe}%`, backgroundColor: stageColor }} />
      </div>
      {detail && <p className="muted small order-workflow-progress-detail">{detail}</p>}
    </div>
  )
}

function PurchaseLinesTable({ lines, amountsMasked }) {
  if (!lines?.length) {
    return <p className="muted">ردیف کالا ثبت نشده — فقط مبلغ کلی سفارش.</p>
  }
  return (
    <div className="table-wrap">
      <table className="table table-compact">
        <thead>
          <tr>
            <th>محصول</th>
            <th>تعداد</th>
            {!amountsMasked && <th>فی</th>}
            {!amountsMasked && <th>جمع ردیف</th>}
          </tr>
        </thead>
        <tbody>
          {lines.map((li) => (
            <tr key={li.id}>
              <td>
                <div>{li.product_name}</div>
                {(li.fabric || li.color_name) && (
                  <div className="muted small">
                    {[li.fabric, li.color_name].filter(Boolean).join(' — ')}
                  </div>
                )}
              </td>
              <td>{toPersianDigits(li.quantity)}</td>
              {!amountsMasked && <td>{formatMoney(li.unit_price)}</td>}
              {!amountsMasked && <td>{formatMoney(li.line_total)}</td>}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}

export default function OfficeOrders() {
  const { choices } = useConfig()
  const stageChoices = choices('workflow_stage')
  const [orders, setOrders] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [expandedId, setExpandedId] = useState(null)
  const [detailOrder, setDetailOrder] = useState(null)
  const [detailLoading, setDetailLoading] = useState(false)
  const [listFilterQuery, setListFilterQuery] = useState(() =>
    recordFiltersToQueryString(
      { model: 'office_order', ...OFFICE_ORDERS_FILTER.initialFilters },
      { limit: OFFICE_ORDERS_FILTER.resultLimit, extra: { scope: 'tracking' } },
    ),
  )

  const stageColor = (stage) => {
    const fromDb = stageChoices.find((o) => o.value === stage)?.meta?.color
    return fromDb || WORKFLOW_COLORS[stage] || '#6366f1'
  }

  const load = useCallback(async () => {
    setLoading(true)
    setError('')
    try {
      const data = await officeApi.list(listFilterQuery)
      setOrders(data.results || [])
    } catch (e) {
      setError(e.message)
      setOrders([])
    } finally {
      setLoading(false)
    }
  }, [listFilterQuery])

  useEffect(() => {
    load()
  }, [load])

  const openPurchaseDetail = async (order) => {
    if (order.line_items?.length) {
      setDetailOrder(order)
      return
    }
    setDetailLoading(true)
    try {
      const full = await officeApi.get(order.id)
      setDetailOrder(full)
    } catch (e) {
      setError(e.message)
    } finally {
      setDetailLoading(false)
    }
  }

  const toggleInline = (id) => {
    setExpandedId((prev) => (prev === id ? null : id))
  }

  return (
    <div className="page office-orders-tracking">
      <OfficeSectionCard
        section={OFFICE_ORDERS_FILTER}
        actions={<Button type="button" variant="ghost" onClick={load}>بروزرسانی</Button>}
        onFiltersChange={(filters) => {
          setListFilterQuery(
            recordFiltersToQueryString(filters, {
              limit: OFFICE_ORDERS_FILTER.resultLimit,
              extra: { scope: 'tracking' },
            }),
          )
        }}
      >
      {error && <div className="alert alert-error">{error}</div>}

        {loading ? (
          <p className="muted loading">در حال بارگذاری…</p>
        ) : orders.length === 0 ? (
          <EmptyState text="سفارشی ثبت نشده است." />
        ) : (
          <>
            <div className="table-wrap office-orders-table-desktop">
              <table className="table">
                <thead>
                  <tr>
                    <th>فاکتور</th>
                    <th>مشتری</th>
                    <th>مبلغ خرید</th>
                    <th>تعداد کالا</th>
                    <th>پیشرفت / وضعیت</th>
                    <th>تحویل</th>
                    <th />
                  </tr>
                </thead>
                <tbody>
                  {orders.map((o) => {
                    const color = stageColor(o.workflow_stage)
                    const isOpen = expandedId === o.id
                    return (
                      <Fragment key={o.id}>
                        <tr className={isOpen ? 'office-order-row-expanded' : ''}>
                          <td className="ltr">{o.invoice_number || o.id}</td>
                          <td>
                            <strong>{o.customer_name}</strong>
                            {o.branch_label && o.branch_label !== '—' && (
                              <div className="muted small">{o.branch_label}</div>
                            )}
                          </td>
                          <td>{o.amounts_masked ? '—' : formatMoney(o.final_amount)}</td>
                          <td>
                            {o.line_items_count
                              ? `${toPersianDigits(o.total_quantity || 0)} قلم`
                              : '—'}
                          </td>
                          <td className="office-order-progress-cell">
                            <WorkflowProgress
                              percent={o.workflow_progress}
                              stage={o.workflow_stage}
                              stageLabel={o.workflow_stage_display}
                              detail={[o.holder_department, o.holder_detail].filter(Boolean).join(' — ')}
                              stageColor={color}
                            />
                          </td>
                          <td>{o.delivery_date ? formatDate(o.delivery_date) : '—'}</td>
                          <td>
                            <div className="row-actions">
                              <Button type="button" size="sm" variant="ghost" onClick={() => toggleInline(o.id)}>
                                {isOpen ? 'بستن خرید' : 'مقدار خرید'}
                              </Button>
                              <Button type="button" size="sm" variant="ghost" onClick={() => openPurchaseDetail(o)}>
                                جزئیات
                              </Button>
                            </div>
                          </td>
                        </tr>
                        {isOpen && (
                          <tr className="office-order-lines-row">
                            <td colSpan={7}>
                              <div className="office-order-inline-purchase">
                                <h4 className="office-order-inline-title">مقدار خرید — {o.customer_name}</h4>
                                <PurchaseLinesTable lines={o.line_items} amountsMasked={o.amounts_masked} />
                                {!o.amounts_masked && (
                                  <p className="muted small">
                                    جمع سفارش: <strong>{formatMoney(o.final_amount)}</strong>
                                  </p>
                                )}
                              </div>
                            </td>
                          </tr>
                        )}
                      </Fragment>
                    )
                  })}
                </tbody>
              </table>
            </div>

            <div className="office-orders-cards-mobile">
              {orders.map((o) => {
                const color = stageColor(o.workflow_stage)
                return (
                  <div key={o.id} className="m-card office-order-track-card">
                    <div className="m-card-head">
                      <div>
                        <strong>{o.customer_name}</strong>
                        <div className="muted small ltr">{o.invoice_number || `#${o.id}`}</div>
                      </div>
                      {!o.amounts_masked && (
                        <strong>{formatMoney(o.final_amount)}</strong>
                      )}
                    </div>
                    <WorkflowProgress
                      percent={o.workflow_progress}
                      stage={o.workflow_stage}
                      stageLabel={o.workflow_stage_display}
                      detail={o.holder_detail}
                      stageColor={color}
                    />
                    <div className="m-card-grid">
                      <div>
                        <span className="muted">تعداد</span>
                        {o.line_items_count ? toPersianDigits(o.total_quantity || 0) : '—'}
                      </div>
                      <div>
                        <span className="muted">تحویل</span>
                        {o.delivery_date ? formatDate(o.delivery_date) : '—'}
                      </div>
                    </div>
                    {expandedId === o.id && (
                      <div className="office-order-inline-purchase">
                        <PurchaseLinesTable lines={o.line_items} amountsMasked={o.amounts_masked} />
                      </div>
                    )}
                    <div className="m-card-actions row-actions">
                      <Button type="button" size="sm" variant="ghost" onClick={() => toggleInline(o.id)}>
                        {expandedId === o.id ? 'بستن' : 'مقدار خرید'}
                      </Button>
                      <Button type="button" size="sm" variant="ghost" onClick={() => openPurchaseDetail(o)}>
                        جزئیات
                      </Button>
                    </div>
                  </div>
                )
              })}
            </div>
          </>
        )}
      </OfficeSectionCard>

      <Modal
        title={detailOrder ? `جزئیات خرید — ${detailOrder.customer_name}` : 'جزئیات خرید'}
        open={Boolean(detailOrder) || detailLoading}
        onClose={() => { if (!detailLoading) setDetailOrder(null) }}
        wide
      >
        {detailLoading ? (
          <p className="muted loading">در حال بارگذاری…</p>
        ) : detailOrder && (
          <div className="office-purchase-detail">
            <div className="office-purchase-detail-meta muted small">
              <span>فاکتور: {detailOrder.invoice_number || detailOrder.id}</span>
              {' · '}
              <span>ثبت: {formatDate(detailOrder.sold_at)}</span>
              {detailOrder.delivery_date && (
                <>
                  {' · '}
                  <span>تحویل: {formatDate(detailOrder.delivery_date)}</span>
                </>
              )}
            </div>
            <WorkflowProgress
              percent={detailOrder.workflow_progress}
              stage={detailOrder.workflow_stage}
              stageLabel={detailOrder.workflow_stage_display}
              detail={detailOrder.holder_detail}
              stageColor={stageColor(detailOrder.workflow_stage)}
            />
            {!detailOrder.amounts_masked && (
              <p>
                مبلغ نهایی خرید: <strong>{formatMoney(detailOrder.final_amount)}</strong>
                {detailOrder.total_quantity > 0 && (
                  <> — مجموع {toPersianDigits(detailOrder.total_quantity)} قلم</>
                )}
              </p>
            )}
            <PurchaseLinesTable lines={detailOrder.line_items} amountsMasked={detailOrder.amounts_masked} />
          </div>
        )}
      </Modal>
    </div>
  )
}
