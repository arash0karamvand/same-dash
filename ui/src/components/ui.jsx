// مجموعه کامپوننت‌های پایه و قابل‌استفاده مجدد رابط کاربری.

// کارت آماری داشبورد
export function StatCard({ label, value, hint, accent = '#6366f1' }) {
  return (
    <div className="stat-card">
      <div className="stat-bar" style={{ background: accent }} />
      <div className="stat-body">
        <span className="stat-label">{label}</span>
        <span className="stat-value">{value}</span>
        {hint && <span className="stat-hint">{hint}</span>}
      </div>
    </div>
  )
}

// نشان (badge) رنگی برای سطح مشتری یا وضعیت
export function Badge({ children, color = '#6366f1' }) {
  return (
    <span className="badge" style={{ background: `${color}22`, color, borderColor: `${color}55` }}>
      {children}
    </span>
  )
}

// دکمه با انواع مختلف
export function Button({ children, variant = 'primary', className = '', ...props }) {
  return (
    <button className={`btn btn-${variant}${className ? ` ${className}` : ''}`} {...props}>
      {children}
    </button>
  )
}

// کارت ساده با عنوان
export function Card({ title, actions, children, className = '' }) {
  return (
    <div className={`card ${className}`.trim()}>
      {(title || actions) && (
        <div className="card-head">
          <h3>{title}</h3>
          <div className="card-actions">{actions}</div>
        </div>
      )}
      <div className="card-body">{children}</div>
    </div>
  )
}

// پنجره مودال ساده
export function Modal({ title, open, onClose, children, wide = false }) {
  if (!open) return null
  return (
    <div className="modal-overlay" onClick={onClose}>
      <div className={`modal ${wide ? 'modal-wide' : ''}`} onClick={(e) => e.stopPropagation()}>
        <div className="modal-head">
          <h3>{title}</h3>
          <button className="modal-close" onClick={onClose}>
            ×
          </button>
        </div>
        <div className="modal-body">{children}</div>
      </div>
    </div>
  )
}

// فیلد فرم (label + input/children)
export function Field({ label, children }) {
  return (
    <label className="field">
      <span className="field-label">{label}</span>
      {children}
    </label>
  )
}

// نوار فیلتر یکدست صفحات (جستجو، select، تاریخ)
export function FilterBar({ children, className = '' }) {
  return (
    <div className={`page-filters${className ? ` ${className}` : ''}`}>
      {children}
    </div>
  )
}

// نمایش پیام خالی بودن داده
export function EmptyState({ text = 'داده‌ای برای نمایش وجود ندارد.', children }) {
  return (
    <div className="empty-state">
      <p>{text}</p>
      {children}
    </div>
  )
}
