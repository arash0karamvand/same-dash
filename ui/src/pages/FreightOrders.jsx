// باربری — تحویل بر اساس تاریخ

import { useState } from 'react'
import { factoryApi } from '../api/client'
import PersianDateInput from '../components/PersianDateInput'
import { Field } from '../components/ui'
import { formatJalali, todayIso } from '../utils/jalali'
import WorkflowOrdersPage from './WorkflowOrdersPage'
import { fromLegacy } from '../styles/tw.js'

export default function FreightOrders() {
  const [deliveryDate, setDeliveryDate] = useState('')

  const extraParams = {
    section: 'freight',
    ...(deliveryDate ? { delivery_date: deliveryDate } : {}),
  }

  const subtitle = deliveryDate
    ? `تحویل‌های ${formatJalali(deliveryDate)} و ارسال‌های زودتر از موعد — اطلاعات مشتری بدون مبلغ`
    : 'صف ارسال به مشتری و سفارش‌های ارسال‌شده زودتر از موعد — اطلاعات مشتری بدون مبلغ'

  return (
    <WorkflowOrdersPage
      title="باربری"
      subtitle={subtitle}
      emptyTitle="سفارشی در صف باربری نیست"
      listApi={factoryApi.list}
      extraParams={extraParams}
      showCustomer
      showAmounts={false}
      showStage
      filters={(
        <div className={fromLegacy("workflow-filter-bar")}>
          <Field label="تاریخ تحویل">
            <PersianDateInput
              value={deliveryDate}
              onChange={setDeliveryDate}
              placeholder="همه تاریخ‌ها"
              onClear={() => setDeliveryDate('')}
              clearLabel="همه"
            />
          </Field>
          <button type="button" className={fromLegacy("link workflow-filter-today")} onClick={() => setDeliveryDate(todayIso())}>
            امروز
          </button>
        </div>
      )}
      actions={[
        {
          key: 'complete',
          label: 'تحویل شد',
          variant: 'success',
          permission: 'manage_freight_orders',
          when: (o) => o.workflow_stage === 'in_freight',
          run: (id) => factoryApi.freightComplete(id),
        },
      ]}
    />
  )
}
