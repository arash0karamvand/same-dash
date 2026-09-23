import Icon from '../icons/Icon'
import { formatRial } from '../../utils/format'

/**
 * Live T-Balance dock — two parallel monospaced rails for debit/credit.
 * Blinks a red lamp when the two sides do not match.
 */
export default function LiveTBalance({
  debit = 0,
  credit = 0,
  label = 'تراز آزمایشی لحظه‌ای',
  compact = false,
}) {
  const debitValue = Number(debit) || 0
  const creditValue = Number(credit) || 0
  const difference = debitValue - creditValue
  const balanced = Math.abs(difference) < 0.01

  return (
    <aside
      className={`acct-tbalance${compact ? ' is-compact' : ''}${balanced ? ' is-balanced' : ' is-unbalanced'}`}
      role="status"
      aria-live="polite"
      aria-label={balanced ? `${label}: متوازن` : `${label}: نامتوازن`}
    >
      <div className="acct-tbalance-meta">
        <span className={`acct-tbalance-lamp${balanced ? '' : ' is-alert'}`} aria-hidden />
        <span className="acct-tbalance-label">{label}</span>
        {balanced ? (
          <span className="acct-tbalance-state is-ok">
            <Icon name="check" size={14} />
            متوازن
          </span>
        ) : (
          <span className="acct-tbalance-state is-off">
            <Icon name="warning" size={14} />
            اختلاف {formatRial(Math.abs(difference))}
          </span>
        )}
      </div>
      <div className="acct-tbalance-rails">
        <div className="acct-tbalance-rail is-debit">
          <span>بدهکار</span>
          <strong className="acct-number acct-debit">{formatRial(debitValue)}</strong>
        </div>
        <div className="acct-tbalance-rail is-credit">
          <span>بستانکار</span>
          <strong className="acct-number acct-credit">{formatRial(creditValue)}</strong>
        </div>
      </div>
    </aside>
  )
}
