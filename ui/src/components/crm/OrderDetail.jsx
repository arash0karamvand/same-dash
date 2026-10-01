// کامپوننت جزئیات سفارش برای SlideOver

import { Badge, Button, FormSection, StatCard } from '../ui'
import { formatDate, formatMoney } from '../../utils/format'
import { toPersianDigits } from '../../utils/jalali'
import Icon from '../icons/Icon'

function WorkflowProgress({ percent, stage, stageLabel, stageColor }) {
  const safe = Math.min(100, Math.max(0, Number(percent) || 0))
  
  return (
    <div className="space-y-2">
      <div className="flex items-center justify-between">
        <Badge color={stageColor}>{stageLabel || stage}</Badge>
        <span className="text-sm text-muted">{toPersianDigits(safe)}٪</span>
      </div>
      <div
        className="h-2 overflow-hidden rounded-full bg-layer-1"
        role="progressbar"
        aria-valuenow={safe}
        aria-valuemin={0}
        aria-valuemax={100}
      >
        <div
          className="h-full rounded-full transition-all duration-300"
          style={{ width: `${safe}%`, backgroundColor: stageColor }}
        />
      </div>
    </div>
  )
}

function PurchaseLinesTable({ lines }) {
  if (!lines?.length) {
    return <p className="text-sm text-muted">ردیف کالا ثبت نشده.</p>
  }

  return (
    <div className="overflow-x-auto rounded-pill border border-jelly-rim">
      <table className="w-full min-w-[400px] text-sm">
        <thead>
          <tr className="border-b border-border-subtle bg-layer-1">
            <th className="px-3 py-2 text-right text-xs font-semibold uppercase">
              محصول
            </th>
            <th className="px-3 py-2 text-right text-xs font-semibold uppercase">
              تعداد
            </th>
            <th className="px-3 py-2 text-right text-xs font-semibold uppercase">
              فی
            </th>
            <th className="px-3 py-2 text-right text-xs font-semibold uppercase">
              جمع
            </th>
          </tr>
        </thead>
        <tbody>
          {lines.map((line) => (
            <tr key={line.id} className="border-b border-border-subtle last:border-0">
              <td className="px-3 py-2">
                <div>{line.product_name}</div>
                {(line.fabric || line.color_name) && (
                  <div className="text-xs text-muted">
                    {[line.fabric, line.color_name].filter(Boolean).join(' — ')}
                  </div>
                )}
              </td>
              <td className="px-3 py-2">{toPersianDigits(line.quantity)}</td>
              <td className="px-3 py-2">{formatMoney(line.unit_price)}</td>
              <td className="px-3 py-2">{formatMoney(line.line_total)}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}

export default function OrderDetail({ order }) {
  return (
    <div className="space-y-5">
      {/* Header stats */}
      <div className="grid grid-cols-3 gap-3 max-md:grid-cols-1">
        <StatCard label="مبلغ کل" value={formatMoney(order.amount)} size="small" />
        <StatCard
          label="وضعیت"
          value={
            <Badge color={order.stage_color}>{order.stage_label}</Badge>
          }
          size="small"
        />
        <StatCard
          label="تاریخ"
          value={formatDate(order.created_at)}
          size="small"
        />
      </div>

      {/* Customer info */}
      <FormSection title="مشتری">
        <div className="flex items-center gap-3">
          <div className="flex h-10 w-10 items-center justify-center rounded-full bg-layer-2">
            <Icon name="user" size={20} />
          </div>
          <div className="flex-1">
            <div className="font-semibold">{order.customer_name}</div>
            <div className="text-sm text-muted ltr">{order.customer_phone}</div>
          </div>
          <Button size="sm" variant="ghost">
            مشاهده پروفایل
          </Button>
        </div>
      </FormSection>

      {/* Workflow progress */}
      {order.workflow_progress !== undefined && (
        <FormSection title="پیشرفت گردش کار">
          <WorkflowProgress
            percent={order.workflow_progress}
            stage={order.workflow_stage}
            stageLabel={order.stage_label}
            stageColor={order.stage_color}
          />
        </FormSection>
      )}

      {/* Purchase lines */}
      <FormSection title="اقلام سفارش">
        <PurchaseLinesTable lines={order.lines} />
      </FormSection>

      {/* Actions */}
      <div className="flex gap-2 max-md:flex-col">
        <Button>ویرایش</Button>
        <Button variant="success">تایید</Button>
        <Button variant="danger">رد</Button>
      </div>
    </div>
  )
}
