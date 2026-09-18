// ساخته‌شده‌ها — بعد از پایان ساخت کارخانه

import { useState } from 'react'
import { factoryApi } from '../api/client'
import PersianDateInput from '../components/PersianDateInput'
import { Field } from '../components/ui'
import { formatJalali, todayIso } from '../utils/jalali'
import WorkflowOrdersPage from './WorkflowOrdersPage'
import { fromLegacy } from '../styles/tw.js'

export default function FactoryBuilt() {
  const [builtDate, setBuiltDate] = useState('')

  const extraParams = {
    section: 'built',
    ...(builtDate ? { built_date: builtDate } : {}),
  }

  const subtitle = builtDate
    ? `سفارش‌های ساخته‌شده در ${formatJalali(builtDate)}`
    : 'سفارش‌های ساخته‌شده؛ تا تایید نهایی و ارسال به باربری در باربری دیده نمی‌شوند'

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
      rowUrgency
      filters={(
        <div className={fromLegacy("workflow-filter-bar")}>
          <Field label="تاریخ پایان ساخت">
            <PersianDateInput
              value={builtDate}
              onChange={setBuiltDate}
              placeholder="همه تاریخ‌ها"
              onClear={() => setBuiltDate('')}
              clearLabel="همه"
            />
          </Field>
          <button type="button" className={fromLegacy("link workflow-filter-today")} onClick={() => setBuiltDate(todayIso())}>
            امروز
          </button>
        </div>
      )}
      actions={[
        {
          key: 'confirm-ready',
          label: 'تایید نهایی',
          variant: 'success',
          permission: 'manage_factory_orders',
          when: (o) => o.workflow_stage === 'production_done' && !o.delivery_ready_at,
          run: (id) => factoryApi.confirmReady(id),
        },
        {
          key: 'send-freight',
          label: 'ارسال به باربری',
          variant: 'primary',
          permission: 'manage_factory_orders',
          when: (o) => (
            o.workflow_stage === 'production_done'
            && Boolean(o.delivery_ready_at)
            && !o.early_disposition_pending
            && (!o.early_ship_allowed_date || o.early_ship_allowed_date <= todayIso())
          ),
          run: (id) => factoryApi.sendToFreight(id),
        },
      ]}
    />
  )
}
