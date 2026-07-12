// کارخانه — صف ساخت: منتظر دریافت و در حال ساخت

import { useState } from 'react'
import { factoryApi } from '../api/client'
import WorkflowOrdersPage from './WorkflowOrdersPage'

const QUEUE_OPTIONS = [
  { value: 'all', label: 'همه سفارش‌ها' },
  { value: 'needs_build', label: 'منتظر ساخت' },
  { value: 'in_production', label: 'در حال ساخت' },
]

export default function Factory() {
  const [queue, setQueue] = useState('all')

  const extraParams = {
    section: 'production',
    ...(queue !== 'all' ? { queue } : {}),
  }

  return (
    <WorkflowOrdersPage
      title="ساخت کارخانه"
      subtitle="سفارش‌هایی که باید ساخته شوند — بدون نمایش قیمت"
      emptyTitle="سفارشی برای ساخت نیست"
      listApi={factoryApi.list}
      extraParams={extraParams}
      showStage
      showCustomer={false}
      showAmounts={false}
      filters={(
        <div className="workflow-filter-bar">
          <span className="workflow-filter-label">فیلتر ساخت:</span>
          <div className="workflow-filter-tabs">
            {QUEUE_OPTIONS.map((opt) => (
              <button
                key={opt.value}
                type="button"
                className={`workflow-filter-tab ${queue === opt.value ? 'active' : ''}`}
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
          permission: 'manage_factory_orders',
          when: (o) => o.workflow_stage === 'accounting_approved',
          run: (id) => factoryApi.receive(id),
        },
        {
          key: 'complete',
          label: 'پایان ساخت',
          permission: 'manage_factory_orders',
          when: (o) => o.workflow_stage === 'in_production',
          run: (id) => factoryApi.complete(id),
        },
      ]}
    />
  )
}
