// تحویل حضوری از مغازه

import { cycleApi } from '../api/client'
import WorkflowOrdersPage from './WorkflowOrdersPage'

export default function PickupOrders() {
  return (
    <WorkflowOrdersPage
      title="تحویل حضوری"
      subtitle="سفارش‌های سبک که از مغازه به مشتری تحویل می‌شوند"
      emptyTitle="سفارشی برای تحویل حضوری نیست"
      listApi={cycleApi.pickupOrders}
      showStage
      showBranch
      showCustomer
      showAmounts
      actions={[
        {
          key: 'complete',
          label: 'تحویل شد',
          variant: 'success',
          when: (o) => o.workflow_stage === 'ready_for_pickup',
          run: (id) => cycleApi.pickupComplete(id),
        },
      ]}
    />
  )
}
