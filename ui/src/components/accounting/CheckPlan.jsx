// برنامه پرداخت چک‌ها

import { useState } from 'react'
import { Button, Badge, Modal, Field } from '../ui'
import { AccountingDataPanel, AccountingSummary } from './AccountingERP'
import Select from '../Select'
import Icon from '../icons/Icon'
import { formatDate, formatRial } from '../../utils/format'
import { fromLegacy } from '../../styles/tw'

const CHECK_STATUS = {
  pending: { label: 'در انتظار', color: 'var(--color-warning)' },
  paid: { label: 'پرداخت شده', color: 'var(--color-success)' },
  overdue: { label: 'سررسید گذشته', color: 'var(--color-danger)' },
}

export default function CheckPlan({ checks = [], depositAccounts = [], onPay, onRefresh, loading = false }) {
  const [showPayModal, setShowPayModal] = useState(false)
  const [selectedCheck, setSelectedCheck] = useState(null)
  const [selectedDepositAccount, setSelectedDepositAccount] = useState('')

  const handlePay = async () => {
    if (!selectedCheck || !selectedDepositAccount) return
    try {
      await onPay(selectedCheck.id, selectedDepositAccount)
      setShowPayModal(false)
      setSelectedCheck(null)
      setSelectedDepositAccount('')
      onRefresh && onRefresh()
    } catch (err) {
      alert('خطا در ثبت پرداخت: ' + err.message)
    }
  }

  const openPayModal = (check) => {
    setSelectedCheck(check)
    setShowPayModal(true)
  }

  const pendingChecks = Array.isArray(checks) ? checks.filter((c) => c.status === 'pending') : []
  const overdueChecks = Array.isArray(checks) ? checks.filter((c) => c.status === 'overdue') : []
  
  const totalPending = pendingChecks.reduce((sum, c) => sum + (c.amount || 0), 0)
  const totalOverdue = overdueChecks.reduce((sum, c) => sum + (c.amount || 0), 0)

  return (
    <div className={fromLegacy('check-plan')}>
      <AccountingSummary items={[
        { label: 'در انتظار پرداخت', value: formatRial(totalPending), hint: `${pendingChecks.length.toLocaleString('fa-IR')} چک`, tone: 'warning' },
        { label: 'سررسید گذشته', value: formatRial(totalOverdue), hint: `${overdueChecks.length.toLocaleString('fa-IR')} چک`, tone: 'danger' },
      ]} />

      <AccountingDataPanel
        title="تقویم تعهدات چک"
        subtitle={`${checks.length.toLocaleString('fa-IR')} فقره چک`}
        actions={(
          <Button variant="secondary" onClick={onRefresh} disabled={loading}>
            <Icon name="refresh-cw" size={16} />
            <span>به‌روزرسانی</span>
          </Button>
        )}
      >
        {checks.length === 0 ? (
          <p style={{ textAlign: 'center', padding: '2rem', color: 'var(--text-secondary)' }}>
            چکی برای پرداخت وجود ندارد
          </p>
        ) : (
          <div className="acct-card-stack is-compact">
            {checks.map((check) => {
              const statusInfo = CHECK_STATUS[check.status] || CHECK_STATUS.pending
              return (
                <article key={check.id} className={`acct-doc-card${check.status === 'overdue' ? ' is-off' : ''}`}>
                  <div className="acct-doc-id">
                    <strong className="acct-number">{check.check_number}</strong>
                    <small>{formatDate(check.due_date)}</small>
                  </div>
                  <div className="acct-doc-copy">
                    <span>{check.payee || '-'}</span>
                    <p>{statusInfo.label}</p>
                  </div>
                  <div className="acct-doc-amounts">
                    <div>
                      <span>مبلغ</span>
                      <strong className="acct-number acct-debit">{formatRial(check.amount)}</strong>
                    </div>
                  </div>
                  <div className="acct-doc-actions">
                    <Badge color={statusInfo.color}>{statusInfo.label}</Badge>
                    {check.status === 'pending' || check.status === 'overdue' ? (
                      <Button variant="primary" size="sm" onClick={() => openPayModal(check)}>
                        ثبت پرداخت
                      </Button>
                    ) : (
                      <span style={{ color: 'var(--text-secondary)' }}>پرداخت شده</span>
                    )}
                  </div>
                </article>
              )
            })}
          </div>
        )}
      </AccountingDataPanel>

      <Modal
        title="ثبت پرداخت چک"
        open={showPayModal}
        onClose={() => setShowPayModal(false)}
      >
        {selectedCheck && (
          <div style={{ display: 'flex', flexDirection: 'column', gap: '1rem' }}>
            <div>
              <p style={{ marginBottom: '0.5rem' }}>
                <strong>شماره چک:</strong> {selectedCheck.check_number}
              </p>
              <p style={{ marginBottom: '0.5rem' }}>
                <strong>مبلغ:</strong> {formatRial(selectedCheck.amount)}
              </p>
              <p>
                <strong>سررسید:</strong> {formatDate(selectedCheck.due_date)}
              </p>
            </div>

            <Field label="حساب بانکی پرداخت">
              <Select
                value={selectedDepositAccount}
                onChange={(e) => setSelectedDepositAccount(e.target.value)}
                options={[
                  { value: '', label: 'انتخاب حساب...' },
                  ...depositAccounts.map((acc) => ({
                    value: String(acc.id),
                    label: acc.name,
                  })),
                ]}
              />
            </Field>

            <div style={{ display: 'flex', gap: '0.5rem', justifyContent: 'flex-end', marginTop: '1rem' }}>
              <Button variant="secondary" onClick={() => setShowPayModal(false)}>
                انصراف
              </Button>
              <Button variant="primary" onClick={handlePay} disabled={!selectedDepositAccount}>
                ثبت پرداخت
              </Button>
            </div>
          </div>
        )}
      </Modal>
    </div>
  )
}
