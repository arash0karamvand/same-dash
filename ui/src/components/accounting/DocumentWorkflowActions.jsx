// دکمه‌های عملیات Workflow برای اسناد حسابداری

import { useState } from 'react'
import { Button, Modal, Field } from '../ui'
import Icon from '../icons/Icon'
import { fromLegacy } from '../../styles/tw'

export default function DocumentWorkflowActions({
  status,
  onSubmit,
  onApprove,
  onReject,
  onEdit,
  canEdit = true,
  canApprove = true,
  loading = false,
}) {
  const [showRejectModal, setShowRejectModal] = useState(false)
  const [rejectReason, setRejectReason] = useState('')
  const [actionLoading, setActionLoading] = useState(false)

  const handleSubmit = async () => {
    if (!onSubmit) return
    setActionLoading(true)
    try {
      await onSubmit()
    } finally {
      setActionLoading(false)
    }
  }

  const handleApprove = async () => {
    if (!onApprove) return
    setActionLoading(true)
    try {
      await onApprove()
    } finally {
      setActionLoading(false)
    }
  }

  const handleReject = async () => {
    if (!onReject) return
    setActionLoading(true)
    try {
      await onReject(rejectReason)
      setShowRejectModal(false)
      setRejectReason('')
    } finally {
      setActionLoading(false)
    }
  }

  const isLoading = loading || actionLoading

  return (
    <>
      <div className={fromLegacy('workflow-actions')} style={{ display: 'flex', gap: '0.5rem', flexWrap: 'wrap' }}>
        {status === 'draft' && onSubmit && (
          <Button
            variant="primary"
            onClick={handleSubmit}
            disabled={isLoading}
          >
            <Icon name="clipboard" size={16} />
            <span>ارسال برای بررسی</span>
          </Button>
        )}

        {status === 'pending_review' && canApprove && (
          <>
            <Button
              variant="success"
              onClick={handleApprove}
              disabled={isLoading}
            >
              <Icon name="check" size={16} />
              <span>تایید و ثبت</span>
            </Button>
            <Button
              variant="danger"
              onClick={() => setShowRejectModal(true)}
              disabled={isLoading}
            >
              <Icon name="x" size={16} />
              <span>رد کردن</span>
            </Button>
          </>
        )}

        {(status === 'pending_review' || status === 'human_overridden') && canEdit && onEdit && (
          <Button
            variant="secondary"
            onClick={onEdit}
            disabled={isLoading}
          >
            <Icon name="pencil" size={16} />
            <span>ویرایش</span>
          </Button>
        )}

        {status === 'posted' && (
          <div style={{ padding: '0.5rem 1rem', color: 'var(--color-success)', fontWeight: '500' }}>
            <Icon name="check" size={16} />
            <span style={{ marginRight: '0.5rem' }}>سند ثبت قطعی شده است</span>
          </div>
        )}
      </div>

      <Modal
        title="رد کردن سند"
        open={showRejectModal}
        onClose={() => !isLoading && setShowRejectModal(false)}
      >
        <Field label="دلیل رد">
          <textarea
            value={rejectReason}
            onChange={(e) => setRejectReason(e.target.value)}
            placeholder="توضیحات..."
            rows={4}
            className="acct-textarea"
            style={{ width: '100%', fontFamily: 'inherit' }}
            disabled={isLoading}
          />
        </Field>
        <div style={{ display: 'flex', gap: '0.5rem', marginTop: '1rem', justifyContent: 'flex-end' }}>
          <Button
            variant="secondary"
            onClick={() => setShowRejectModal(false)}
            disabled={isLoading}
          >
            انصراف
          </Button>
          <Button
            variant="danger"
            onClick={handleReject}
            disabled={isLoading || !rejectReason.trim()}
          >
            {isLoading ? 'در حال ثبت...' : 'رد کردن'}
          </Button>
        </div>
      </Modal>
    </>
  )
}
