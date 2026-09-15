// کارخانه — صف ساخت: منتظر دریافت و در حال ساخت

import { useState } from 'react'
import { factoryApi } from '../api/client'
import WorkflowOrdersPage from './WorkflowOrdersPage'
import { fromLegacy } from '../styles/tw.js'

const QUEUE_OPTIONS = [
  { value: 'all', label: 'همه سفارش‌ها' },
  { value: 'needs_build', label: 'منتظر ساخت' },
  { value: 'in_production', label: 'در حال ساخت' },
  { value: 'merchant', label: 'بازرگان' },
]

export default function Factory() {
  const [queue, setQueue] = useState('all')

  const extraParams = {
    section: 'production',
    ...(queue === 'merchant' ? { workflow_stage: 'merchant_assigned' } : {}),
    ...(queue !== 'all' && queue !== 'merchant' ? { queue } : {}),
  }

  return (
    <WorkflowOrdersPage
      key={queue}
      title="ساخت کارخانه"
      subtitle="سفارش‌هایی که باید ساخته شوند — بدون نمایش قیمت"
      emptyTitle="سفارشی برای ساخت نیست"
      listApi={factoryApi.list}
      extraParams={extraParams}
      showStage
      showCustomer={false}
      showAmounts={false}
      showMaterials
      filters={(
        <div className={fromLegacy("workflow-filter-bar")}>
          <span className={fromLegacy("workflow-filter-label")}>فیلتر ساخت:</span>
          <div className={fromLegacy("workflow-filter-tabs")}>
            {QUEUE_OPTIONS.map((opt) => (
              <button
                key={opt.value}
                type="button"
                className={fromLegacy(`workflow-filter-tab ${queue === opt.value ? 'active' : ''}`)}
                onClick={() => setQueue(opt.value)}
              >
                {opt.label}
              </button>
            ))}
          </div>
        </div>
      )}
      actions={[
        {
          key: 'receive',
          label: 'دریافت سفارش',
          variant: 'success',
          permission: 'manage_factory_orders',
          when: (o) => o.workflow_stage === 'accounting_approved' || o.workflow_stage === 'merchant_assigned',
          run: (id) => factoryApi.receive(id),
        },
        {
          key: 'complete',
          label: 'پایان ساخت',
          variant: 'success',
          permission: 'manage_factory_orders',
          when: (o) => o.workflow_stage === 'in_production',
          run: (id) => factoryApi.complete(id),
        },
      ]}
    />
  )
}
