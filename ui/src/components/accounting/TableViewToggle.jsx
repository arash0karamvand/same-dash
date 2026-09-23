// دکمه تغییر حالت نمایش جداول حسابداری

import Icon from '../icons/Icon'
import { usePersistedState } from '../../hooks/usePersistedState'

export default function TableViewToggle({ showPrint = false }) {
  const [compactView, setCompactView] = usePersistedState('accounting-table-compact', false)
  
  const handlePrint = () => {
    window.print()
  }
  
  return (
    <div style={{ display: 'flex', gap: '0.5rem' }}>
      <button
        type="button"
        className="acct-btn acct-btn--sm"
        onClick={() => setCompactView(!compactView)}
        title={compactView ? 'حالت عادی' : 'حالت فشرده'}
        tabIndex={0}
      >
                  <Icon name={compactView ? 'minus' : 'plus'} size={16} />
        <span>{compactView ? 'عادی' : 'فشرده'}</span>
      </button>
      
      {showPrint && (
        <button
          type="button"
          className="acct-btn acct-btn--sm"
          onClick={handlePrint}
          title="چاپ جدول"
          tabIndex={0}
        >
          <Icon name="printer" size={16} />
          <span>چاپ</span>
        </button>
      )}
    </div>
  )
}
