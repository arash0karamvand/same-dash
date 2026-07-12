// صفحه سفارش‌های گردش کار — کارخانه / باربری / حسابداری

import { useCallback, useEffect, useState } from 'react'
import { salesApi } from '../api/client'
import { useAuth } from '../context/AuthContext'
import { useConfig } from '../context/ConfigContext'
import { Badge, Button, Card, EmptyState } from '../components/ui'
import { formatDate, formatMoney } from '../utils/format'
import { hasPermission } from '../utils/permissions'

const WORKFLOW_COLORS = {
  pending_branch: '#f59e0b',
  branch_approved: '#6366f1',
  accounting_approved: '#8b5cf6',
  in_production: '#0ea5e9',
  production_done: '#14b8a6',
  in_freight: '#f97316',
  completed: '#10b981',
}

export default function WorkflowOrdersPage({
  title,
  subtitle,
  workflowFilter,
  listApi = salesApi.list,
  extraParams = {},
  filters = null,
  actions = [],
  showCustomer = true,
  showAmounts = true,
  showStage = true,
  showBranch = false,
  showProductionDate = false,
  showStatus = false,
  showWorkflowHolder = false,
  onEditOrder = null,
  emptyTitle = 'سفارشی در این مرحله نیست',
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
    return fromDb || WORKFLOW_COLORS[stage] || '#6366f1'
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
      const data = await listApi(params.toString())
      setOrders(data.results || [])
    } catch (e) {
      setError(e.message)
      setOrders([])
    } finally {
      setLoading(false)
    }
  }, [workflowFilter, listApi, JSON.stringify(extraParams)])

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

  return (
    <div className="page">
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
        {loading ? (
          <p className="muted loading">در حال بارگذاری…</p>
        ) : orders.length === 0 ? (
          <EmptyState text={emptyTitle} />
        ) : (
          <div className="table-wrap">
            <table className="table">
              <thead>
                <tr>
                  <th>فاکتور</th>
                  {showBranch && <th>شعبه</th>}
                  {showCustomer && <th>مشتری</th>}
                  <th>کالاها</th>
                  <th>تاریخ تحویل</th>
                  {showProductionDate && <th>تاریخ پایان ساخت</th>}
                  {showStatus && <th>وضعیت</th>}
                  {showAmounts && <th>مبلغ</th>}
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
                    <td>
                      {(o.line_items || []).map((li) => (
                        <div key={li.id}>
                          {li.product_name} × {li.quantity}
                          {li.fabric ? ` — ${li.fabric}` : ''}
                        </div>
                      ))}
                    </td>
                    <td>{o.delivery_date ? formatDate(o.delivery_date) : '—'}</td>
                    {showProductionDate && (
                      <td>{o.production_done_at ? formatDate(o.production_done_at) : '—'}</td>
                    )}
                    {showStatus && <td>{o.status_display || o.status || '—'}</td>}
                    {showAmounts && (
                      <td>{o.amounts_masked ? '—' : formatMoney(o.final_amount)}</td>
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
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </Card>
    </div>
  )
}
