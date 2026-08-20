// صفحه سفارش‌های گردش کار — کارخانه / باربری / حسابداری

import { useCallback, useEffect, useState } from 'react'
import { salesApi } from '../api/client'
import { useAuth } from '../context/AuthContext'
import { useConfig } from '../context/ConfigContext'
import { Badge, Button, Card, EmptyState } from '../components/ui'
import { formatDate, formatMoney } from '../utils/format'
import { hasPermission } from '../utils/permissions'

const WORKFLOW_COLORS = {
  pending_branch: 'var(--warning)',
  branch_approved: 'var(--accent)',
  accounting_approved: '#8b5cf6',
  in_production: '#0ea5e9',
  production_done: '#14b8a6',
  in_freight: '#f97316',
  completed: 'var(--success)',
}

export default function WorkflowOrdersPage({
  title,
  subtitle,
  workflowFilter,
  listApi = salesApi.list,
  extraParams = {},
  filterQuery = '',
  filters = null,
  actions = [],
  showCustomer = true,
  showAmounts = true,
  showStage = true,
  showBranch = false,
  showProductionDate = false,
  showStatus = false,
  showWorkflowHolder = false,
  showMaterials = false,
  showAccountingMode = false,
  onEditOrder = null,
  emptyTitle = 'سفارشی در این مرحله نیست',
  embedInSection = false,
}) {
  const { user } = useAuth()
  const { choices } = useConfig()
  const stageChoices = choices('workflow_stage')
  const [orders, setOrders] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [busyId, setBusyId] = useState(null)

  const stageColor = (stage) => {
    const fromDb = stageChoices.find((o) => o.value === stage)?.meta?.color
    return fromDb || WORKFLOW_COLORS[stage] || 'var(--accent)'
  }

  const load = useCallback(async () => {
    setLoading(true)
    setError('')
    try {
      const params = new URLSearchParams()
      if (workflowFilter) params.set('workflow_stage', workflowFilter)
      Object.entries(extraParams).forEach(([key, value]) => {
        if (value != null && value !== '') params.set(key, String(value))
      })
      if (filterQuery) {
        const extra = new URLSearchParams(filterQuery)
        extra.forEach((value, key) => params.set(key, value))
      }
      const data = await listApi(params.toString())
      setOrders(data.results || [])
    } catch (e) {
      setError(e.message)
      setOrders([])
    } finally {
      setLoading(false)
    }
  }, [workflowFilter, listApi, filterQuery, JSON.stringify(extraParams)])

  useEffect(() => {
    load()
  }, [load])

  const runAction = async (order, fn) => {
    setBusyId(order.id)
    try {
      await fn(order.id, order)
      await load()
    } catch (e) {
      setError(e.message)
    } finally {
      setBusyId(null)
    }
  }

  const visibleActions = (order) =>
    actions.filter((a) => !a.permission || hasPermission(user, a.permission))
      .filter((a) => !a.when || a.when(order))

  const renderOrderActions = (o) => (
    <>
      {onEditOrder && o.can_edit && hasPermission(user, 'edit_sale') && (
        <Button
          type="button"
          size="sm"
          variant="ghost"
          disabled={busyId === o.id}
          onClick={() => onEditOrder(o)}
        >
          اصلاح فاکتور
        </Button>
      )}
      {visibleActions(o).map((a) => (
        <Button
          key={a.key}
          type="button"
          size="sm"
          variant={a.variant || 'primary'}
          disabled={busyId === o.id}
          onClick={() => runAction(o, a.run)}
        >
          {typeof a.label === 'function' ? a.label(o) : a.label}
        </Button>
      ))}
    </>
  )

  const renderLineItems = (o) =>
    (o.line_items || []).map((li) => (
      <div key={li.id}>
        {li.product_name} × {li.quantity}
        {li.fabric ? ` — ${li.fabric}` : ''}
      </div>
    ))

  const renderMaterialRequirements = (o) => {
    const items = o.material_requirements || []
    if (!items.length) {
      return <span className="muted">—</span>
    }
    return (
      <div className="order-materials-list">
        {items.map((item) => (
          <div
            key={item.material_id}
            className={`order-material-row${item.sufficient === false ? ' shortage' : ''}`}
          >
            <span className="order-material-name">
              {item.material?.name}
              {item.material?.color_name ? ` (${item.material.color_name})` : ''}
            </span>
            <span className="order-material-qty">
              نیاز: <strong>{item.required_quantity}</strong> {item.unit}
              {item.unit_cost != null && (
                <> × {formatMoney(item.unit_cost)}</>
              )}
              {item.available_stock != null && (
                <> — موجود: <strong>{item.available_stock}</strong></>
              )}
            </span>
            {item.line_cost != null && item.line_cost > 0 && (
              <span className="order-material-cost muted small">
                بهای ردیف: <strong>{formatMoney(item.line_cost)}</strong>
              </span>
            )}
            {item.sufficient === false && (
              <Badge color="var(--danger)">کمبود {item.shortage}</Badge>
            )}
          </div>
        ))}
        {o.materials_deducted && (
          <div className="muted small order-materials-deducted">✓ متریال کسر شده</div>
        )}
        {o.material_cost_total > 0 && (
          <div className="order-material-total">
            جمع بهای متریال: <strong>{formatMoney(o.material_cost_total)}</strong>
          </div>
        )}
      </div>
    )
  }

  const listContent = (
    <>
      {loading ? (
        <p className="muted loading">در حال بارگذاری…</p>
      ) : orders.length === 0 ? (
        <EmptyState text={emptyTitle} />
      ) : (
        <>
        <div className="table-wrap workflow-table-desktop">
            <table className="table">
              <thead>
                <tr>
                  <th>فاکتور</th>
                  {showBranch && <th>شعبه</th>}
                  {showCustomer && <th>مشتری</th>}
                  <th>کالاها</th>
                  {showMaterials && <th>متریال</th>}
                  <th>تاریخ تحویل</th>
                  {showProductionDate && <th>تاریخ پایان ساخت</th>}
                  {showStatus && <th>وضعیت</th>}
                  {showAmounts && <th>مبلغ</th>}
                  {showAccountingMode && <th>حسابداری</th>}
                  {showStage && <th>وضعیت کالا</th>}
                  {showWorkflowHolder && <th>دست</th>}
                  <th />
                </tr>
              </thead>
              <tbody>
                {orders.map((o) => (
                  <tr key={o.id}>
                    <td className="ltr">{o.invoice_number || o.id}</td>
                    {showBranch && <td>{o.branch_label || o.branch || '—'}</td>}
                    {showCustomer && (
                      <td>
                        <div>{o.customer_name}</div>
                        {o.customer_phone && <div className="muted ltr">{o.customer_phone}</div>}
                        {o.customer_address && <div className="muted">{o.customer_address}</div>}
                      </td>
                    )}
                    <td>{renderLineItems(o)}</td>
                    {showMaterials && <td>{renderMaterialRequirements(o)}</td>}
                    <td>{o.delivery_date ? formatDate(o.delivery_date) : '—'}</td>
                    {showProductionDate && (
                      <td>{o.production_done_at ? formatDate(o.production_done_at) : '—'}</td>
                    )}
                    {showStatus && <td>{o.status_display || o.status || '—'}</td>}
                    {showAmounts && (
                      <td>{o.amounts_masked ? '—' : formatMoney(o.final_amount)}</td>
                    )}
                    {showAccountingMode && (
                      <td>
                        <Badge color={o.accounting_mode === 'automatic' ? 'var(--success)' : 'var(--muted)'}>
                          {o.accounting_mode_display || (o.accounting_mode === 'automatic' ? 'خودکار' : 'دستی')}
                        </Badge>
                        {o.accounting_mode === 'automatic' && o.payment_account_label && (
                          <div className="muted small">{o.payment_account_label}</div>
                        )}
                      </td>
                    )}
                    {showStage && (
                    <td>
                      <Badge color={stageColor(o.workflow_stage)}>
                        {o.workflow_stage_display || o.workflow_stage}
                      </Badge>
                      {o.holder_detail && (
                        <div className="muted small workflow-holder-detail">{o.holder_detail}</div>
                      )}
                    </td>
                    )}
                    {showWorkflowHolder && (
                    <td>
                      <div>{o.holder_department || '—'}</div>
                      {o.holder_name && (
                        <div className="muted small">{o.holder_name}</div>
                      )}
                    </td>
                    )}
                    <td>
                      <div className="row-actions">
                        {renderOrderActions(o)}
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          <div className="workflow-cards-mobile">
            {orders.map((o) => (
              <div key={o.id} className="m-card workflow-order-card">
                <div className="m-card-head">
                  <div>
                    <strong>{o.customer_name || '—'}</strong>
                    <div className="muted small ltr">{o.invoice_number || `#${o.id}`}</div>
                    {showBranch && (
                      <div className="muted small">{o.branch_label || o.branch || '—'}</div>
                    )}
                  </div>
                  {showStage && (
                    <Badge color={stageColor(o.workflow_stage)}>
                      {o.workflow_stage_display || o.workflow_stage}
                    </Badge>
                  )}
                </div>
                <div className="m-card-grid">
                  {showCustomer && o.customer_phone && (
                    <div><span className="muted">تلفن</span><span className="ltr">{o.customer_phone}</span></div>
                  )}
                  {showAmounts && (
                    <div><span className="muted">مبلغ</span><strong>{o.amounts_masked ? '—' : formatMoney(o.final_amount)}</strong></div>
                  )}
                  <div><span className="muted">تحویل</span>{o.delivery_date ? formatDate(o.delivery_date) : '—'}</div>
                  {showProductionDate && (
                    <div><span className="muted">پایان ساخت</span>{o.production_done_at ? formatDate(o.production_done_at) : '—'}</div>
                  )}
                  {showStatus && (
                    <div><span className="muted">وضعیت</span>{o.status_display || o.status || '—'}</div>
                  )}
                  {showWorkflowHolder && (
                    <div><span className="muted">دست</span>{o.holder_department || '—'}{o.holder_name ? ` — ${o.holder_name}` : ''}</div>
                  )}
                </div>
                {(o.line_items || []).length > 0 && (
                  <div className="muted small" style={{ marginTop: 8 }}>{renderLineItems(o)}</div>
                )}
                {showMaterials && (o.material_requirements || []).length > 0 && (
                  <div className="order-materials-mobile" style={{ marginTop: 8 }}>
                    <div className="muted small" style={{ marginBottom: 4 }}>متریال</div>
                    {renderMaterialRequirements(o)}
                  </div>
                )}
                {showStage && o.holder_detail && (
                  <div className="muted small workflow-holder-detail">{o.holder_detail}</div>
                )}
                {showCustomer && o.customer_address && (
                  <div className="muted small" style={{ marginTop: 6 }}>{o.customer_address}</div>
                )}
                <div className="m-card-actions row-actions">
                  {renderOrderActions(o)}
                </div>
              </div>
            ))}
          </div>
          </>
        )}
    </>
  )

  if (embedInSection) {
    return (
      <div className="workflow-orders-embedded">
        <div className="office-section-list-toolbar">
          <Button type="button" variant="ghost" onClick={load}>بروزرسانی لیست</Button>
        </div>
        {error && <div className="alert alert-error">{error}</div>}
        {listContent}
      </div>
    )
  }

  return (
    <div className="page workflow-orders-page">
      <div className="page-head">
        <div>
          <h1>{title}</h1>
          {subtitle && <p className="muted">{subtitle}</p>}
        </div>
        <Button type="button" variant="ghost" onClick={load}>بروزرسانی</Button>
      </div>

      {filters}

      {error && <div className="alert alert-error">{error}</div>}

      <Card>
        {listContent}
      </Card>
    </div>
  )
}
