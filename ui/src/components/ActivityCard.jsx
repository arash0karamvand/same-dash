// کامپوننت کارت فعالیت برای نمایش در تایم‌لاین

import Icon from './icons/Icon'
import { Badge } from './ui'
import { cn, tw } from '../styles/tw'
import { formatDate } from '../utils/format'

const ACTIVITY_ICONS = {
  call: 'phone',
  email: 'mail',
  meeting: 'users',
  note: 'file-text',
  sale: 'shopping-cart',
  task_created: 'plus-square',
  task_completed: 'check-square',
  order_status: 'package',
  customer_created: 'user-plus',
}

const ACTIVITY_COLORS = {
  call: 'var(--info)',
  email: 'var(--accent)',
  meeting: 'var(--warning)',
  note: 'var(--muted)',
  sale: 'var(--success)',
  task_created: 'var(--info)',
  task_completed: 'var(--success)',
  order_status: 'var(--accent)',
  customer_created: 'var(--success)',
}

export default function ActivityCard({ activity, onClick }) {
  const icon = ACTIVITY_ICONS[activity.activity_type] || 'activity'
  const color = ACTIVITY_COLORS[activity.activity_type] || 'var(--accent)'

  return (
    <div
      className={cn(
        'liquid-glass liquid-glass--panel liquid-glass--jelly',
        tw.card,
        'relative',
        onClick && 'cursor-pointer hover:border-jelly-rim-strong transition-colors'
      )}
      onClick={onClick}
    >
      <div className="flex items-start gap-4 p-4">
        {/* Icon */}
        <div
          className="flex h-10 w-10 shrink-0 items-center justify-center rounded-capsule border border-jelly-rim shadow-[inset_0_1px_0_var(--jelly-gloss-top)]"
          style={{ backgroundColor: 'var(--layer-2)', color }}
        >
          <Icon name={icon} size={20} />
        </div>

        {/* Content */}
        <div className="min-w-0 flex-1">
          <div className="mb-1 flex flex-wrap items-center gap-2">
            <strong className="text-sm font-semibold text-text">
              {activity.title}
            </strong>
            <span className="text-xs text-muted">
              {formatDate(activity.occurred_at)}
            </span>
            <Badge color={color} className="text-xs">
              {activity.activity_type_display}
            </Badge>
          </div>

          {activity.description && (
            <p className="mb-2 text-sm text-muted">{activity.description}</p>
          )}

          <div className="flex flex-wrap gap-2">
            {activity.customer_name && (
              <div className="flex items-center gap-1 text-xs text-muted">
                <Icon name="user" size={12} />
                <span>{activity.customer_name}</span>
              </div>
            )}
            {activity.sale_code && (
              <div className="flex items-center gap-1 text-xs text-muted">
                <Icon name="shopping-cart" size={12} />
                <span>{activity.sale_code}</span>
              </div>
            )}
            {activity.user_name && (
              <div className="flex items-center gap-1 text-xs text-muted">
                <Icon name="user" size={12} />
                <span>{activity.user_name}</span>
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  )
}
