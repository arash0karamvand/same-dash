// Semantic status colors — gray monochromatic tokens

export const STATUS = {
  success: 'var(--success)',
  warning: 'var(--warning)',
  danger: 'var(--danger)',
  accent: 'var(--accent)',
  muted: 'var(--muted)',
  info: 'var(--info)',
}

export function approvalColor(status) {
  if (status === 'approved') return STATUS.success
  if (status === 'rejected') return STATUS.danger
  return STATUS.warning
}

export function saleStatusColor(status) {
  const map = {
    draft: STATUS.muted,
    pending: STATUS.warning,
    approved: STATUS.success,
    rejected: STATUS.danger,
    cancelled: STATUS.muted,
  }
  return map[status] || STATUS.accent
}

export function badgeVariantFromColor(color) {
  if (color === STATUS.success || color === 'var(--success)') return 'success'
  if (color === STATUS.warning || color === 'var(--warning)') return 'warning'
  if (color === STATUS.danger || color === 'var(--danger)') return 'danger'
  if (color === STATUS.muted || color === 'var(--muted)') return 'muted'
  return 'accent'
}

/** Parse CSS var to rgba background for badges */
export function badgeStyle(color) {
  const variants = {
    [STATUS.success]: { bg: 'var(--success-soft)', border: 'var(--border)' },
    [STATUS.warning]: { bg: 'var(--warning-soft)', border: 'var(--border-subtle)' },
    [STATUS.danger]: { bg: 'var(--danger-soft)', border: 'var(--border)' },
    [STATUS.muted]: { bg: 'var(--surface-2)', border: 'var(--border)' },
    [STATUS.accent]: { bg: 'var(--accent-soft)', border: 'var(--border)' },
    [STATUS.info]: { bg: 'var(--info-soft)', border: 'var(--border-subtle)' },
  }
  const v = variants[color] || variants[STATUS.accent]
  return {
    background: v.bg,
    color,
    borderColor: v.border,
  }
}

export const STAT_ACCENTS = [
  STATUS.accent,
  STATUS.success,
  STATUS.warning,
  STATUS.info,
]
