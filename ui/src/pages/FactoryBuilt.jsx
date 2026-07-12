// ساخته‌شده‌ها — بعد از پایان ساخت کارخانه

import { useState } from 'react'
import { factoryApi } from '../api/client'
import PersianDateInput from '../components/PersianDateInput'
import { Field } from '../components/ui'
import { formatJalali, todayIso } from '../utils/jalali'
import WorkflowOrdersPage from './WorkflowOrdersPage'

export default function FactoryBuilt() {
  const [builtDate, setBuiltDate] = useState('')

  const extraParams = {
    section: 'built',
    ...(builtDate ? { built_date: builtDate } : {}),
  }

  const subtitle = builtDate
    ? `سفارش‌های ساخته‌شده در ${formatJalali(builtDate)}`
    : 'همه سفارش‌هایی که ساختشان تمام شده و آماده باربری هستند'

  return (
    <WorkflowOrdersPage
      title="ساخته‌شده‌ها"
      subtitle={subtitle}
      emptyTitle="سفارش ساخته‌شده‌ای یافت نشد"
      listApi={factoryApi.list}
      extraParams={extraParams}
      showStage
      showCustomer={false}
      showAmounts={false}
      showProductionDate
      filters={(
        <div className="workflow-filter-bar">
          <Field label="تاریخ پایان ساخت">
            <PersianDateInput
              value={builtDate}
              onChange={setBuiltDate}
              placeholder="همه تاریخ‌ها"
              onClear={() => setBuiltDate('')}
              clearLabel="همه"
            />
          </Field>
          <button type="button" className="link workflow-filter-today" onClick={() => setBuiltDate(todayIso())}>
            امروز
          </button>
        </div>
      )}
      actions={[]}
    />
  )
}
