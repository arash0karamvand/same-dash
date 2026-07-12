// باربری — تحویل بر اساس تاریخ

import { useState } from 'react'
import { factoryApi } from '../api/client'
import PersianDateInput from '../components/PersianDateInput'
import { Field } from '../components/ui'
import { formatJalali, todayIso } from '../utils/jalali'
import WorkflowOrdersPage from './WorkflowOrdersPage'

export default function FreightOrders() {
  const [deliveryDate, setDeliveryDate] = useState(todayIso())

  const extraParams = {
    section: 'freight',
    delivery_date: deliveryDate,
  }

  return (
    <WorkflowOrdersPage
      title="باربری"
      subtitle={`تحویل‌های ${formatJalali(deliveryDate)} — اطلاعات مشتری بدون مبلغ`}
      emptyTitle="برای این تاریخ سفارشی برای تحویل نیست"
      listApi={factoryApi.list}
      extraParams={extraParams}
      showCustomer
      showAmounts={false}
      showStage
      filters={(
        <div className="workflow-filter-bar">
          <Field label="تاریخ تحویل">
            <PersianDateInput
              value={deliveryDate}
              onChange={setDeliveryDate}
              placeholder="انتخاب تاریخ"
            />
          </Field>
          <button type="button" className="link workflow-filter-today" onClick={() => setDeliveryDate(todayIso())}>
            امروز
          </button>
        </div>
      )}
      actions={[
        {
          key: 'receive',
          label: 'شروع ارسال',
          permission: 'manage_freight_orders',
          when: (o) => o.workflow_stage === 'production_done',
          run: (id) => factoryApi.freightReceive(id),
        },
        {
          key: 'complete',
          label: 'تحویل شد',
          permission: 'manage_freight_orders',
          when: (o) => o.workflow_stage === 'in_freight',
          run: (id) => factoryApi.freightComplete(id),
        },
      ]}
    />
  )
}
