// کامپوننت WidgetGrid برای نمایش ویجت‌های داشبورد

import { cn } from '../styles/tw'

const SIZE_CLASSES = {
  small: 'col-span-3',
  medium: 'col-span-4',
  large: 'col-span-6',
  wide: 'col-span-12',
}

export default function WidgetGrid({ widgets, editMode, onEdit, onDelete }) {
  return (
    <div className="grid grid-cols-12 gap-5 auto-rows-fr max-compact:grid-cols-6 max-md:grid-cols-1">
      {widgets.map((widget) => (
        <div
          key={widget.id}
          className={cn(
            SIZE_CLASSES[widget.size] || SIZE_CLASSES.medium,
            'max-compact:col-span-full'
          )}
        >
          <WidgetContainer
            widget={widget}
            editMode={editMode}
            onEdit={onEdit}
            onDelete={onDelete}
          />
        </div>
      ))}
    </div>
  )
}

function WidgetContainer({ widget, editMode, onEdit, onDelete }) {
  return (
    <div className="liquid-glass liquid-glass--panel liquid-glass--jelly h-full rounded-pill overflow-hidden">
      {editMode && (
        <div className="flex items-center justify-between border-b border-border-subtle px-4 py-2 bg-layer-1">
          <span className="text-xs text-muted">{widget.widget_type}</span>
          <div className="flex gap-1">
            <button
              onClick={() => onEdit(widget)}
              className="text-xs text-accent hover:underline"
            >
              ویرایش
            </button>
            <button
              onClick={() => onDelete(widget.id)}
              className="text-xs text-danger hover:underline"
            >
              حذف
            </button>
          </div>
        </div>
      )}
      
      <div className="p-4">
        <h3 className="mb-3 font-display text-base font-bold">{widget.title}</h3>
        <div className="text-sm text-muted">
          <WidgetContent widget={widget} />
        </div>
      </div>
    </div>
  )
}

function WidgetContent({ widget }) {
  // این بخش می‌تواند بر اساس widget.widget_type متفاوت باشد
  // فعلاً یک placeholder ساده نمایش می‌دهیم
  
  return (
    <div className="flex items-center justify-center py-10 text-muted">
      ویجت {widget.widget_type}
    </div>
  )
}
