// نمایش وضعیت Workflow اسناد حسابداری

import { Badge } from '../ui'

const WORKFLOW_STATES = {
  draft: { label: 'پیش‌نویس', color: 'var(--muted)' },
  pending_review: { label: 'در انتظار بررسی', color: 'var(--acct-warning-text, var(--warning))' },
  human_overridden: { label: 'ویرایش شده', color: 'var(--acct-focus-color, var(--info))' },
  posted: { label: 'ثبت شده', color: 'var(--acct-credit-text, var(--success))' },
  rejected: { label: 'رد شده', color: 'var(--acct-debit-text, var(--danger))' },
}

export default function WorkflowStatusBadge({ status, className = '' }) {
  const state = WORKFLOW_STATES[status] || WORKFLOW_STATES.draft
  
  return (
    <span className={className}>
      <Badge color={state.color}>
      {state.label}
      </Badge>
    </span>
  )
}

export { WORKFLOW_STATES }
