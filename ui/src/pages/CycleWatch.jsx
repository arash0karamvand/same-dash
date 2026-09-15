// نظارت چرخه — ناظر فروشگاه↔CRM و ناظر مسیرهای ارسال

import { useMemo, useState } from 'react'
import { cycleApi } from '../api/client'
import { useAuth } from '../context/AuthContext'
import WorkflowOrdersPage from './WorkflowOrdersPage'
import { fromLegacy } from '../styles/tw.js'

export default function CycleWatch() {
  const { user } = useAuth()
  const canShop = Boolean(user?.cycle?.is_shop_crm_monitor || user?.cycle?.can_watch_cycle || user?.is_superuser)
  const canFulfillment = Boolean(user?.cycle?.is_fulfillment_supervisor || user?.is_superuser || user?.grants_full_access)
  const [scope, setScope] = useState(canShop ? 'shop_crm' : 'fulfillment')

  const tabs = useMemo(() => {
    const items = []
    if (canShop) items.push({ value: 'shop_crm', label: 'فروشگاه و CRM' })
    if (canFulfillment || canShop) items.push({ value: 'fulfillment', label: 'مسیرهای ارسال' })
    return items
  }, [canShop, canFulfillment])

  return (
    <WorkflowOrdersPage
      key={scope}
      title="نظارت چرخه"
      subtitle="فقط مشاهده — تایید یا رد از این صفحه انجام نمی‌شود"
      emptyTitle="سفارشی برای نظارت نیست"
      listApi={(params) => {
        const extra = params ? `&${String(params).replace(/^\?/, '')}` : ''
        return cycleApi.watch(`scope=${scope}${extra}`)
      }}
      extraParams={{}}
      showStage
      showBranch
      showCustomer
      showAmounts
      filters={(
        <div className={fromLegacy('workflow-filter-bar')}>
          <span className={fromLegacy('workflow-filter-label')}>محدوده نظارت:</span>
          <div className={fromLegacy('workflow-filter-tabs')}>
            {tabs.map((opt) => (
              <button
                key={opt.value}
                type="button"
                className={fromLegacy(`workflow-filter-tab ${scope === opt.value ? 'active' : ''}`)}
                onClick={() => setScope(opt.value)}
              >
                {opt.label}
              </button>
            ))}
          </div>
        </div>
      )}
      actions={[]}
    />
  )
}
