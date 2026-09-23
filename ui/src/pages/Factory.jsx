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

export default function Factory({ portal }) {
  const [queue, setQueue] = useState('all')

  const extraParams = {
    section: 'production',
    ...(queue === 'merchant' ? { workflow_stage: 'merchant_assigned' } : {}),
    ...(queue !== 'all' && queue !== 'merchant' ? { queue } : {}),
  }

  return (
    <WorkflowOrdersPage
      key={queue}
      portal={portal}
      cyclePage="factory"
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
          confirm: (o) => {
            const summary = o.workset_summary || {}
            const workset = [
              o.receive_kind_display && `نوع دریافت: ${o.receive_kind_display}`,
              o.contract_party && `طرف قرارداد: ${o.contract_party}`,
              summary.frame && `کلاف ${summary.frame}`,
              summary.needs_paint === false ? 'بدون رنگ' : (summary.paint && `رنگ ${summary.paint}`),
              summary.fabric && `پارچه ${summary.fabric}`,
              summary.foam && `اسفنج ${summary.foam}`,
              summary.webbing && `تسمه ${summary.webbing}`,
              summary.cushion && `کوسن ${summary.cushion}`,
              summary.pipeline_end === 'assembly' ? 'تا مونتاژ' : (summary.pipeline_end ? 'تا رویه‌کوبی' : ''),
            ].filter(Boolean).join(' • ')
            const shortages = (o.material_requirements || [])
              .filter((item) => item.sufficient === false)
              .map((item) => {
                const name = item.material?.color_name
                  ? `${item.material.name} (${item.material.color_name})`
                  : item.material?.name
                const others = item.committed_by_others > 0 ? ` / در جریان ${item.committed_by_others} می‌خواهند` : ''
                return `${name}: نیاز ${item.required_quantity}، موجود ${item.available_stock}${others}`
              })
            const message = [
              workset ? `دست کار: ${workset}` : 'این سفارش دست کار تعریف‌شده ندارد.',
              shortages.length
                ? `نسبت به صف در جریان کمبود دارد (دریافت مسدود نمی‌شود):\n${shortages.join('\n')}`
                : 'نسبت به صف در جریان کمبود متریال دیده نشد.',
              'سفارش دریافت شود و کارهای کارگاه ساخته شوند؟',
            ].join('\n\n')
            return { title: 'دریافت سفارش کارخانه', message, confirmText: 'دریافت' }
          },
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
