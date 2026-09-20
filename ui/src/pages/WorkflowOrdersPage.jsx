// صفحه سفارش‌های گردش کار — کارخانه / باربری / حسابداری

import { useCallback, useEffect, useState } from 'react'
import { salesApi } from '../api/client'
import { useAuth } from '../context/AuthContext'
import { useConfig } from '../context/ConfigContext'
import { useConfirm } from '../context/ConfirmContext'
import { Badge, Button, Card, EmptyState, Field, FilterBar, LoadMoreButton } from '../components/ui'
import { PAGE_SIZE, withPageParams } from '../config/pagination'
import { formatDate, formatMoney } from '../utils/format'
import { hasPermission } from '../utils/permissions'
import { fromLegacy } from '../styles/tw.js'

const WORKFLOW_COLORS = {
  pending_branch: 'var(--warning)',
  branch_approved: 'var(--accent)',
  accounting_approved: '#8b5cf6',
  in_production: '#0ea5e9',
  production_done: '#14b8a6',
  in_freight: '#f97316',
  in_warehouse: '#64748b',
  ready_for_pickup: '#22c55e',
  merchant_assigned: '#a855f7',
  completed: 'var(--success)',
}

const READY_DELIVERY_COLOR = '#22c55e'

function amountCell(order) {
  if (order.amounts_masked) return '—'
  return (
    <>
      <div>{formatMoney(order.final_amount)}</div>
      <div className={fromLegacy('muted small')}>مانده {formatMoney(order.balance_due ?? 0)}</div>
    </>
  )
}

function rowToneClass(order, enabled) {
  if (!enabled) return ''
  if (order.delivery_ready_at) return 'workflow-row-ready'
  if (order.urgency === 'red') return 'workflow-row-urgent-red'
  if (order.urgency === 'orange') return 'workflow-row-urgent-orange'
  return ''
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
  rowUrgency = false,
  onEditOrder = null,
  emptyTitle = 'سفارشی در این مرحله نیست',
  embedInSection = false,
}) {
  const { user } = useAuth()
  const { choices } = useConfig()
  const confirm = useConfirm()
  const stageChoices = choices('workflow_stage')
  const [orders, setOrders] = useState([])
  const [total, setTotal] = useState(0)
  const [offset, setOffset] = useState(0)
  const [search, setSearch] = useState('')
  const [loading, setLoading] = useState(true)
  const [loadingMore, setLoadingMore] = useState(false)
  const [error, setError] = useState('')
  const [busyId, setBusyId] = useState(null)

  const stageColor = (stage) => {
    const fromDb = stageChoices.find((o) => o.value === stage)?.meta?.color
    return fromDb || WORKFLOW_COLORS[stage] || 'var(--accent)'
  }

  const badgeColor = (order) => order.stage_badge_color || (order.delivery_ready_at ? READY_DELIVERY_COLOR : stageColor(order.workflow_stage))
  const badgeLabel = (order) => order.stage_badge_label || order.workflow_stage_display || order.workflow_stage

  const load = useCallback(async ({ append = false, offset: nextOffset = 0 } = {}) => {
    if (append) setLoadingMore(true)
    else setLoading(true)
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
      if (search.trim()) params.set('search', search.trim())
      const data = await listApi(withPageParams(params, { offset: nextOffset, limit: PAGE_SIZE }))
      setOrders((prev) => (append ? [...prev, ...(data.results || [])] : (data.results || [])))
      setTotal(data.total || 0)
      setOffset(data.offset ?? nextOffset)
    } catch (e) {
      setError(e.message)
      if (!append) setOrders([])
    } finally {
      setLoading(false)
      setLoadingMore(false)
    }
  }, [workflowFilter, listApi, filterQuery, search, JSON.stringify(extraParams)])

  useEffect(() => {
    load({ offset: 0 })
  }, [load])

  const runAction = async (order, action) => {
    if (action.confirm) {
      const opts = typeof action.confirm === 'function' ? action.confirm(order) : action.confirm
      if (!(await confirm(opts))) return
    }
    setBusyId(order.id)
    try {
      await action.run(order.id, order)
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
          onClick={() => runAction(o, a)}
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
        {li.frame_id ? ` — کلاف (${li.frame_config?.seat_count || '—'} نفره)` : ''}
        {li.workset_config?.paint?.name ? ` — رنگ ${li.workset_config.paint.name}` : ''}
        {li.workset_config?.fabric?.name ? ` — پارچه ${li.workset_config.fabric.name}` : ''}
        {li.workset_config?.foam?.name ? ` — اسفنج ${li.workset_config.foam.name}` : ''}
        {li.workset_config?.webbing?.name ? ` — تسمه ${li.workset_config.webbing.name}` : ''}
        {li.workset_config?.cushion?.name ? ` — کوسن ${li.workset_config.cushion.name}` : ''}
      </div>
    ))

  const renderWorksetSummary = (o) => {
    const summary = o.workset_summary || {}
    const parts = [
      summary.frame && `کلاف ${summary.frame}`,
      summary.paint && `رنگ ${summary.paint}`,
      summary.fabric && `پارچه ${summary.fabric}`,
      summary.foam && `اسفنج ${summary.foam}`,
      summary.webbing && `تسمه ${summary.webbing}`,
      summary.cushion && `کوسن ${summary.cushion}`,
      summary.pipeline_end === 'assembly' && 'مونتاژ',
    ].filter(Boolean)
    if (!parts.length) return null
    return <div className={fromLegacy('muted small')}>دست کار: {parts.join(' • ')}</div>
  }

  const renderMaterialRequirements = (o) => {
    const items = o.material_requirements || []
    if (!items.length) {
      return <span className={fromLegacy("muted")}>—</span>
    }
    return (
      <div className={fromLegacy("order-materials-list")}>
        {items.map((item) => (
          <div
            key={item.material_id}
            className={fromLegacy(`order-material-row${item.sufficient === false ? ' shortage' : ''}`)}
          >
            <span className={fromLegacy("order-material-name")}>
              {item.material?.name}
              {item.material?.color_name ? ` (${item.material.color_name})` : ''}
              {(item.source === 'frame' || (item.sources || []).includes('frame')) && (
                <span className={fromLegacy("muted small")}> — کلاف</span>
              )}
              {item.source && !['product', 'frame', 'mixed'].includes(item.source) && (
                <span className={fromLegacy("muted small")}> — {item.source}</span>
              )}
            </span>
            <span className={fromLegacy("order-material-qty")}>
              نیاز: <strong>{item.required_quantity}</strong> {item.unit}
              {item.unit_cost != null && (
                <> × {formatMoney(item.unit_cost)}</>
              )}
              {item.available_stock != null && (
                <> — موجود: <strong>{item.available_stock}</strong></>
              )}
              {item.committed_by_others > 0 && (
                <> — در جریان <strong>{item.committed_by_others}</strong> می‌خواهند</>
              )}
              {item.available_after_queue != null && item.committed_by_others > 0 && (
                <> / برای این سفارش: <strong>{item.available_after_queue}</strong></>
              )}
            </span>
            {item.line_cost != null && item.line_cost > 0 && (
              <span className={fromLegacy("order-material-cost muted small")}>
                بهای ردیف: <strong>{formatMoney(item.line_cost)}</strong>
              </span>
            )}
            {item.sufficient === false && (
              <Badge color="var(--danger)">کمبود {item.shortage}</Badge>
            )}
          </div>
        ))}
        {o.materials_deducted && (
          <div className={fromLegacy("muted small order-materials-deducted")}>✓ متریال کسر شده</div>
        )}
        {o.material_cost_total > 0 && (
          <div className={fromLegacy("order-material-total")}>
            جمع بهای متریال: <strong>{formatMoney(o.material_cost_total)}</strong>
          </div>
        )}
      </div>
    )
  }

  const listContent = (
    <>
      <FilterBar>
        <Field label="جستجو">
          <input
            className={fromLegacy("search-input")}
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            placeholder="مشتری، فاکتور یا توضیحات…"
          />
        </Field>
      </FilterBar>
      {loading ? (
        <p className={fromLegacy("muted loading")}>در حال بارگذاری…</p>
      ) : orders.length === 0 ? (
        <EmptyState text={emptyTitle} />
      ) : (
        <>
        <div className={fromLegacy("table-wrap workflow-table-desktop")}>
            <table className={fromLegacy("table")}>
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
                  <tr key={o.id} className={fromLegacy(rowToneClass(o, rowUrgency))}>
                    <td className={fromLegacy("ltr")}>
                      {o.invoice_number || o.id}
                      {o.receive_kind_display && (
                        <div className={fromLegacy("muted small")}>نوع دریافت: {o.receive_kind_display}{o.contract_party ? ` — ${o.contract_party}` : ''}</div>
                      )}
                      {o.shipped_early && (
                        <div><Badge color="#f97316">ارسال زودتر از موعد</Badge></div>
                      )}
                      {o.fulfillment_route_display && (
                        <div className={fromLegacy("muted small")}>{o.fulfillment_route_display}{o.merchant_user_name ? ` — ${o.merchant_user_name}` : ''}{o.fulfillment_warehouse_label ? ` — ${o.fulfillment_warehouse_label}` : ''}{o.fulfillment_source_branch_label ? ` — ${o.fulfillment_source_branch_label}` : ''}</div>
                      )}
                    </td>
                    {showBranch && <td>{o.branch_label || o.branch || '—'}</td>}
                    {showCustomer && (
                      <td>
                        <div>{o.customer_name}</div>
                        {o.customer_phone && <div className={fromLegacy("muted ltr")}>{o.customer_phone}</div>}
                        {o.customer_address && <div className={fromLegacy("muted")}>{o.customer_address}</div>}
                      </td>
                    )}
                    <td>
                      {renderLineItems(o)}
                      {showMaterials && renderWorksetSummary(o)}
                    </td>
                    {showMaterials && <td>{renderMaterialRequirements(o)}</td>}
                    <td>{o.delivery_date ? formatDate(o.delivery_date) : '—'}</td>
                    {showProductionDate && (
                      <td>{o.production_done_at ? formatDate(o.production_done_at) : '—'}</td>
                    )}
                    {showStatus && <td>{o.status_display || o.status || '—'}</td>}
                    {showAmounts && (
                      <td>{amountCell(o)}</td>
                    )}
                    {showAccountingMode && (
                      <td>
                        <Badge color={o.accounting_mode === 'automatic' ? 'var(--success)' : 'var(--muted)'}>
                          {o.accounting_mode_display || (o.accounting_mode === 'automatic' ? 'خودکار' : 'دستی')}
                        </Badge>
                        {o.accounting_mode === 'automatic' && o.payment_account_label && (
                          <div className={fromLegacy("muted small")}>{o.payment_account_label}</div>
                        )}
                      </td>
                    )}
                    {showStage && (
                    <td>
                      <Badge color={badgeColor(o)}>
                        {badgeLabel(o)}
                      </Badge>
                      {o.early_disposition_required && !o.early_ship_allowed_date && !o.shipped_early && (
                        <div className={fromLegacy("muted small")}>منتظر تعیین تکلیف اداری</div>
                      )}
                      {o.holder_detail && (
                        <div className={fromLegacy("muted small workflow-holder-detail")}>{o.holder_detail}</div>
                      )}
                    </td>
                    )}
                    {showWorkflowHolder && (
                    <td>
                      <div>{o.holder_department || '—'}</div>
                      {o.holder_name && (
                        <div className={fromLegacy("muted small")}>{o.holder_name}</div>
                      )}
                    </td>
                    )}
                    <td>
                      <div className={fromLegacy("row-actions")}>
                        {renderOrderActions(o)}
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          <div className={fromLegacy("workflow-cards-mobile")}>
            {orders.map((o) => (
              <div key={o.id} className={fromLegacy(`m-card workflow-order-card ${rowToneClass(o, rowUrgency)}`.trim())}>
                <div className={fromLegacy("m-card-head")}>
                  <div>
                    <strong>{o.customer_name || '—'}</strong>
                    <div className={fromLegacy("muted small ltr")}>{o.invoice_number || `#${o.id}`}</div>
                    {showBranch && (
                      <div className={fromLegacy("muted small")}>{o.branch_label || o.branch || '—'}</div>
                    )}
                    {o.shipped_early && (
                      <div style={{ marginTop: 4 }}><Badge color="#f97316">ارسال زودتر از موعد</Badge></div>
                    )}
                  </div>
                  {showStage && (
                    <Badge color={badgeColor(o)}>
                      {badgeLabel(o)}
                    </Badge>
                  )}
                </div>
                <div className={fromLegacy("m-card-grid")}>
                  {showCustomer && o.customer_phone && (
                    <div><span className={fromLegacy("muted")}>تلفن</span><span className={fromLegacy("ltr")}>{o.customer_phone}</span></div>
                  )}
                  {showAmounts && (
                    <div>
                      <span className={fromLegacy("muted")}>مبلغ</span>
                      <strong>{o.amounts_masked ? '—' : formatMoney(o.final_amount)}</strong>
                      {!o.amounts_masked && (
                        <div className={fromLegacy("muted small")}>مانده {formatMoney(o.balance_due ?? 0)}</div>
                      )}
                    </div>
                  )}
                  <div><span className={fromLegacy("muted")}>تحویل</span>{o.delivery_date ? formatDate(o.delivery_date) : '—'}</div>
                  {showProductionDate && (
                    <div><span className={fromLegacy("muted")}>پایان ساخت</span>{o.production_done_at ? formatDate(o.production_done_at) : '—'}</div>
                  )}
                  {showStatus && (
                    <div><span className={fromLegacy("muted")}>وضعیت</span>{o.status_display || o.status || '—'}</div>
                  )}
                  {showWorkflowHolder && (
                    <div><span className={fromLegacy("muted")}>دست</span>{o.holder_department || '—'}{o.holder_name ? ` — ${o.holder_name}` : ''}</div>
                  )}
                </div>
                {(o.line_items || []).length > 0 && (
                  <div className={fromLegacy("muted small")} style={{ marginTop: 8 }}>
                    {renderLineItems(o)}
                    {showMaterials && renderWorksetSummary(o)}
                  </div>
                )}
                {showMaterials && (o.material_requirements || []).length > 0 && (
                  <div className={fromLegacy("order-materials-mobile")} style={{ marginTop: 8 }}>
                    <div className={fromLegacy("muted small")} style={{ marginBottom: 4 }}>متریال</div>
                    {renderMaterialRequirements(o)}
                  </div>
                )}
                {showStage && o.holder_detail && (
                  <div className={fromLegacy("muted small workflow-holder-detail")}>{o.holder_detail}</div>
                )}
                {showCustomer && o.customer_address && (
                  <div className={fromLegacy("muted small")} style={{ marginTop: 6 }}>{o.customer_address}</div>
                )}
                <div className={fromLegacy("m-card-actions row-actions")}>
                  {renderOrderActions(o)}
                </div>
              </div>
            ))}
          </div>
          <LoadMoreButton
            hasMore={orders.length < total}
            loading={loadingMore}
            onClick={() => load({ append: true, offset: offset + PAGE_SIZE })}
          />
          </>
        )}
    </>
  )

  if (embedInSection) {
    return (
      <div className={fromLegacy("workflow-orders-embedded")}>
        <div className={fromLegacy("office-section-list-toolbar")}>
          <Button type="button" variant="ghost" onClick={() => load({ offset: 0 })}>بروزرسانی لیست</Button>
        </div>
        {error && <div className={fromLegacy("alert alert-error")}>{error}</div>}
        {listContent}
      </div>
    )
  }

  return (
    <div className={fromLegacy("page workflow-orders-page")}>
      <div className={fromLegacy("page-head")}>
        <div>
          <h1>{title}</h1>
          {subtitle && <p className={fromLegacy("muted")}>{subtitle}</p>}
        </div>
        <Button type="button" variant="ghost" onClick={() => load({ offset: 0 })}>بروزرسانی</Button>
      </div>

      {filters}

      {error && <div className={fromLegacy("alert alert-error")}>{error}</div>}

      <Card>
        {listContent}
      </Card>
    </div>
  )
}
