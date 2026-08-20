import { factoryApi } from '../api/client'
import WorkflowOrdersPage from './WorkflowOrdersPage'

export default function FactoryOrders() {
  return (
    <WorkflowOrdersPage
      title="کارخانه"
      subtitle="فقط سفارش‌های تاییدشده اداری — تا پایان ساخت؛ بدون قیمت"
      emptyTitle="سفارشی برای کارخانه نیست"
      listApi={factoryApi.list}
      showCustomer={false}
      showAmounts={false}
      actions={[
        {
          key: 'receive',
          label: 'دریافت سفارش',
          variant: 'success',
          permission: 'manage_factory_orders',
          when: (o) => o.workflow_stage === 'accounting_approved',
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
