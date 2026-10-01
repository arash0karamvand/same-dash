// کامپوننت کارت وظیفه

import Icon from './icons/Icon'
import { Badge, Button } from './ui'
import { cn, tw } from '../styles/tw'
import { formatDate } from '../utils/format'

const PRIORITY_COLORS = {
  low: 'var(--muted)',
  medium: 'var(--info)',
  high: 'var(--warning)',
  urgent: 'var(--danger)',
}

const PRIORITY_ICONS = {
  low: 'arrow-down',
  medium: 'minus',
  high: 'arrow-up',
  urgent: 'alert-triangle',
}

export default function TaskCard({ task, onUpdate, onComplete, onPin }) {
  const priorityColor = PRIORITY_COLORS[task.priority] || 'var(--accent)'
  const priorityIcon = PRIORITY_ICONS[task.priority] || 'minus'
  const isCompleted = task.status === 'completed'
  const isOverdue = task.due_date && new Date(task.due_date) < new Date() && !isCompleted

  return (
    <div
      className={cn(
        'liquid-glass liquid-glass--panel liquid-glass--jelly',
        tw.card,
        'relative',
        isCompleted && 'opacity-60'
      )}
    >
      <div className="flex items-start gap-3 p-4">
        {/* Checkbox */}
        <input
          type="checkbox"
          checked={isCompleted}
          onChange={() => onComplete && onComplete(task.id)}
          className="mt-0.5 h-5 w-5 shrink-0 accent-accent"
        />

        {/* Content */}
        <div className="min-w-0 flex-1">
          <div className="mb-1 flex flex-wrap items-center gap-2">
            <strong
              className={cn(
                'text-sm font-semibold',
                isCompleted ? 'text-muted line-through' : 'text-text'
              )}
            >
              {task.title}
            </strong>

            <Badge color={priorityColor} className="flex items-center gap-1 text-xs">
              <Icon name={priorityIcon} size={12} />
              {task.priority_display}
            </Badge>

            {task.pinned && (
              <div className="text-warning">
                <Icon name="pin" size={14} />
              </div>
            )}

            {isOverdue && (
              <Badge color="var(--danger)" className="text-xs">
                <Icon name="alert-circle" size={12} />
                سررسید گذشته
              </Badge>
            )}
          </div>

          {task.description && (
            <p className="mb-2 text-sm text-muted">{task.description}</p>
          )}

          <div className="flex flex-wrap gap-3 text-xs text-muted">
            {task.due_date && (
              <div className="flex items-center gap-1">
                <Icon name="calendar" size={12} />
                <span>سررسید: {formatDate(task.due_date)}</span>
              </div>
            )}

            {task.customer_name && (
              <div className="flex items-center gap-1">
                <Icon name="user" size={12} />
                <span>{task.customer_name}</span>
              </div>
            )}

            {task.sale_code && (
              <div className="flex items-center gap-1">
                <Icon name="shopping-cart" size={12} />
                <span>{task.sale_code}</span>
              </div>
            )}

            {task.assigned_to_name && (
              <div className="flex items-center gap-1">
                <Icon name="user" size={12} />
                <span>محول به: {task.assigned_to_name}</span>
              </div>
            )}
          </div>
        </div>

        {/* Actions */}
        <div className="flex shrink-0 gap-1">
          {onPin && (
            <button
              onClick={() => onPin(task.id, !task.pinned)}
              className={cn(
                'flex h-8 w-8 items-center justify-center rounded-capsule border border-jelly-rim bg-layer-1 transition-colors hover:bg-layer-2',
                task.pinned && 'bg-layer-3 text-warning'
              )}
              title={task.pinned ? 'برداشتن پین' : 'پین کردن'}
            >
              <Icon name="pin" size={14} />
            </button>
          )}

          {onUpdate && (
            <button
              onClick={() => onUpdate(task)}
              className="flex h-8 w-8 items-center justify-center rounded-capsule border border-jelly-rim bg-layer-1 transition-colors hover:bg-layer-2"
              title="ویرایش"
            >
              <Icon name="edit" size={14} />
            </button>
          )}
        </div>
      </div>
    </div>
  )
}
