// صف انبار — ارسال از انبار یا شعبه مبدأ

import { cycleApi } from '../api/client'
import WorkflowOrdersPage from './WorkflowOrdersPage'

export default function WarehouseOrders({ portal }) {
  return (
    <WorkflowOrdersPage
      portal={portal}
      cyclePage="warehouse"
      title="انبار"
      subtitle="سفارش‌هایی که باید از انبار یا شعبه مبدأ ارسال شوند"
      emptyTitle="سفارشی در انبار نیست"
      listApi={cycleApi.warehouseOrders}
      showStage
      showBranch
      showCustomer
      showAmounts
      actions={[
        {
          key: 'complete',
          label: 'ارسال شد',
          variant: 'success',
          permission: 'manage_warehouse_orders',
          when: (o) => o.workflow_stage === 'in_warehouse',
          run: (id) => cycleApi.warehouseComplete(id),
        },
      ]}
    />
  )
}
