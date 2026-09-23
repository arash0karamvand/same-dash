// مدیریت وجوه سرگردان

import { useState } from 'react'
import { Button, Field, Modal } from '../ui'
import { AccountingDataPanel, AccountingSummary } from './AccountingERP'
import Select from '../Select'
import Icon from '../icons/Icon'
import { formatDate, formatRial } from '../../utils/format'
import { fromLegacy } from '../../styles/tw'

export default function DepositsManager({ deposits = [], customers = [], onAllocate, onRefresh, loading = false }) {
  const [showAllocateModal, setShowAllocateModal] = useState(false)
  const [selectedDeposit, setSelectedDeposit] = useState(null)
  const [selectedCustomer, setSelectedCustomer] = useState('')

  const handleAllocate = async () => {
    if (!selectedDeposit || !selectedCustomer) return
    try {
      await onAllocate(selectedDeposit.id, selectedCustomer)
      setShowAllocateModal(false)
      setSelectedDeposit(null)
      setSelectedCustomer('')
      onRefresh && onRefresh()
    } catch (err) {
      alert('خطا در تخصیص: ' + err.message)
    }
  }

  const openAllocateModal = (deposit) => {
    setSelectedDeposit(deposit)
    setShowAllocateModal(true)
  }

  const unallocatedDeposits = Array.isArray(deposits) ? deposits.filter((d) => !d.customer_id) : []
  const allocatedDeposits = Array.isArray(deposits) ? deposits.filter((d) => d.customer_id) : []
  
  const totalUnallocated = unallocatedDeposits.reduce((sum, d) => sum + (d.amount || 0), 0)
  const totalAllocated = allocatedDeposits.reduce((sum, d) => sum + (d.amount || 0), 0)

  return (
    <div className={fromLegacy('deposits-manager')}>
      <AccountingSummary items={[
        { label: 'وجوه تخصیص‌نیافته', value: formatRial(totalUnallocated), tone: 'warning' },
        { label: 'وجوه تخصیص‌یافته', value: formatRial(totalAllocated), tone: 'success' },
      ]} />

      <AccountingDataPanel
        title="وجوه نیازمند تخصیص"
        subtitle={`${unallocatedDeposits.length.toLocaleString('fa-IR')} واریز شناسایی‌نشده`}
        actions={(
          <Button variant="secondary" onClick={onRefresh} disabled={loading}>
            <Icon name="refresh-cw" size={16} />
            <span>به‌روزرسانی</span>
          </Button>
        )}
      >
        {unallocatedDeposits.length === 0 ? (
          <p style={{ textAlign: 'center', padding: '2rem', color: 'var(--text-secondary)' }}>
            وجه سرگردانی وجود ندارد
          </p>
        ) : (
          <div className="acct-card-stack is-compact">
            {unallocatedDeposits.map((deposit) => (
              <article key={deposit.id} className="acct-doc-card">
                <div className="acct-doc-id">
                  <strong className="acct-number acct-debit">{formatRial(deposit.amount)}</strong>
                  <small>{formatDate(deposit.date)}</small>
                </div>
                <div className="acct-doc-copy">
                  <span>{deposit.bank_account || '-'}</span>
                  <p>{deposit.description || '-'}</p>
                </div>
                <div />
                <div className="acct-doc-actions">
                  <Button variant="primary" size="sm" onClick={() => openAllocateModal(deposit)}>
                    تخصیص
                  </Button>
                </div>
              </article>
            ))}
          </div>
        )}
      </AccountingDataPanel>

      <AccountingDataPanel title="سوابق تخصیص" subtitle={`${allocatedDeposits.length.toLocaleString('fa-IR')} ردیف`}>
        {allocatedDeposits.length === 0 ? (
          <p style={{ textAlign: 'center', padding: '2rem', color: 'var(--text-secondary)' }}>
            تخصیصی ثبت نشده است
          </p>
        ) : (
          <div className="acct-card-stack is-compact">
            {allocatedDeposits.map((deposit) => (
              <article key={deposit.id} className="acct-doc-card">
                <div className="acct-doc-id">
                  <strong className="acct-number acct-credit">{formatRial(deposit.amount)}</strong>
                  <small>{formatDate(deposit.date)}</small>
                </div>
                <div className="acct-doc-copy">
                  <span>{deposit.customer_name || '-'}</span>
                  <p>{deposit.description || '-'}</p>
                </div>
              </article>
            ))}
          </div>
        )}
      </AccountingDataPanel>

      <Modal
        title="تخصیص وجه سرگردان"
        open={showAllocateModal}
        onClose={() => setShowAllocateModal(false)}
      >
        {selectedDeposit && (
          <div style={{ display: 'flex', flexDirection: 'column', gap: '1rem' }}>
            <div>
              <p style={{ marginBottom: '0.5rem' }}>
                <strong>مبلغ:</strong> {formatRial(selectedDeposit.amount)}
              </p>
              <p>
                <strong>تاریخ:</strong> {formatDate(selectedDeposit.date)}
              </p>
            </div>

            <Field label="انتخاب مشتری">
              <Select
                value={selectedCustomer}
                onChange={(e) => setSelectedCustomer(e.target.value)}
                options={[
                  { value: '', label: 'انتخاب...' },
                  ...customers.map((c) => ({
                    value: String(c.id),
                    label: c.name,
                  })),
                ]}
              />
            </Field>

            <div style={{ display: 'flex', gap: '0.5rem', justifyContent: 'flex-end', marginTop: '1rem' }}>
              <Button variant="secondary" onClick={() => setShowAllocateModal(false)}>
                انصراف
              </Button>
              <Button variant="primary" onClick={handleAllocate} disabled={!selectedCustomer}>
                تخصیص
              </Button>
            </div>
          </div>
        )}
      </Modal>
    </div>
  )
}
