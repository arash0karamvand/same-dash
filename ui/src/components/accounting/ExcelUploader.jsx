// آپلود و وارد کردن اکسل — بررسی اول، سپس ثبت نهایی

import { useCallback, useRef, useState } from 'react'
import { Button } from '../ui'
import { AccountingDataPanel, AccountingSummary } from './AccountingERP'
import Icon from '../icons/Icon'
import { fromLegacy } from '../../styles/tw'

const ACCEPT = '.xlsx,.xlsm'
const MAX_MB = 10

function formatFa(n) {
  return Number(n || 0).toLocaleString('fa-IR')
}

function buildSummaryItems(result) {
  const counts = result?.counts || {}
  const stats = result?.stats || {}
  const detection = result?.account_detection || {}
  return [
    { label: 'حساب شناسایی‌شده', value: formatFa(detection.total) },
    { label: 'حساب جدید', value: formatFa(detection.new), tone: detection.new ? 'success' : undefined },
    { label: 'حساب موجود', value: formatFa(detection.existing) },
    { label: 'ردیف تراز کل', value: formatFa(counts.general_rows) },
    { label: 'ردیف تراز معین', value: formatFa(counts.subsidiary_rows) },
    { label: 'ردیف تراز تفصیلی', value: formatFa(counts.detailed_rows) },
    { label: 'حساب کل جدید', value: formatFa(stats.accounts_created), tone: stats.accounts_created ? 'success' : undefined },
    { label: 'معین جدید', value: formatFa(stats.subsidiaries_created), tone: stats.subsidiaries_created ? 'success' : undefined },
    { label: 'تفصیلی جدید', value: formatFa(stats.details_created), tone: stats.details_created ? 'success' : undefined },
    { label: 'ردیف سند افتتاحیه', value: formatFa(stats.opening_lines) },
    { label: 'ردیف سند گردش دوره', value: formatFa(stats.turnover_lines) },
    {
      label: 'اختلاف تراز فایل (ریال)',
      value: formatFa(Math.abs(stats.imbalance || 0)),
      tone: stats.imbalance ? 'warning' : 'success',
      hint: stats.imbalance ? 'فقط هشدار؛ اختلاف خودکار در حساب فنی واردات ثبت می‌شود' : 'تراز است',
    },
    {
      label: 'اسناد تراز',
      value: formatFa(stats.journals_created),
      hint: stats.journals_existing ? 'این دوره قبلاً وارد شده' : '',
      tone: stats.journals_existing ? 'warning' : undefined,
    },
  ]
}

export default function ExcelUploader({ api }) {
  const [file, setFile] = useState(null)
  const [dragOver, setDragOver] = useState(false)
  const [busy, setBusy] = useState(false)
  const [autoApprove, setAutoApprove] = useState(true)
  const [replaceExisting, setReplaceExisting] = useState(false)
  const [preview, setPreview] = useState(null)
  const [error, setError] = useState(null)
  const fileInputRef = useRef(null)

  const resetResults = useCallback(() => {
    setPreview(null)
    setError(null)
  }, [])

  const pickFile = useCallback((selected) => {
    if (!selected) return
    const name = (selected.name || '').toLowerCase()
    if (!name.endsWith('.xlsx') && !name.endsWith('.xlsm')) {
      setError({ message: 'فقط فایل Excel با پسوند .xlsx یا .xlsm پذیرفته می‌شود.' })
      setFile(null)
      return
    }
    if (selected.size > MAX_MB * 1024 * 1024) {
      setError({ message: `حداکثر حجم فایل ${MAX_MB} مگابایت است.` })
      setFile(null)
      return
    }
    setFile(selected)
    resetResults()
  }, [resetResults])

  const handleFileSelect = (e) => {
    pickFile(e.target.files?.[0])
  }

  const handleDrop = (e) => {
    e.preventDefault()
    setDragOver(false)
    pickFile(e.dataTransfer.files?.[0])
  }

  const handleClearFile = () => {
    setFile(null)
    resetResults()
    if (fileInputRef.current) fileInputRef.current.value = ''
  }

  const runImport = async ({ dryRun, approve }) => {
    if (!file) return
    setBusy(true)
    setError(null)
    if (dryRun) setPreview(null)

    try {
      const report = await api.importExcel(file, { dryRun, approve, force: !dryRun && replaceExisting })
      if (report?.errors?.length) {
        setError({ message: report.errors[0], errors: report.errors, report })
        return
      }
      if (dryRun) {
        setPreview(report)
      } else {
        setPreview(null)
        setError(null)
        setFile(null)
        if (fileInputRef.current) fileInputRef.current.value = ''
        setPreview({ ...report, committed: true, justCommitted: true })
      }
    } catch (err) {
      const report = err.data?.data || err.data
      setError({
        message: err.message || 'خطا در پردازش فایل',
        errors: report?.errors || [],
        warnings: report?.warnings || [],
        report,
      })
    } finally {
      setBusy(false)
    }
  }

  const showSuccess = preview && !error
  const justCommitted = preview?.justCommitted

  return (
    <div className={fromLegacy('excel-uploader-layout')}>
      <AccountingDataPanel
        title="انتخاب فایل"
        subtitle="فایل خروجی نرم‌افزار حسابداری — فرمت xlsx"
        className={fromLegacy('excel-uploader-panel')}
      >
        <div
          className={fromLegacy(`excel-dropzone${dragOver ? ' is-dragover' : ''}${file ? ' has-file' : ''}`)}
          onDragOver={(e) => { e.preventDefault(); setDragOver(true) }}
          onDragLeave={() => setDragOver(false)}
          onDrop={handleDrop}
          onClick={() => fileInputRef.current?.click()}
          role="button"
          tabIndex={0}
          onKeyDown={(e) => { if (e.key === 'Enter') fileInputRef.current?.click() }}
        >
          <input
            ref={fileInputRef}
            type="file"
            accept={ACCEPT}
            onChange={handleFileSelect}
            hidden
          />
          <div className={fromLegacy('excel-dropzone-icon')}>
            <Icon name={file ? 'clipboard' : 'package'} size={32} />
          </div>
          {file ? (
            <>
              <p className={fromLegacy('excel-dropzone-title')}>{file.name}</p>
              <p className={fromLegacy('excel-dropzone-meta')}>
                {(file.size / 1024).toFixed(1)} کیلوبایت
              </p>
            </>
          ) : (
            <>
              <p className={fromLegacy('excel-dropzone-title')}>فایل را اینجا رها کنید یا کلیک کنید</p>
              <p className={fromLegacy('excel-dropzone-meta')}>xlsx / xlsm — حداکثر {MAX_MB} مگابایت</p>
            </>
          )}
        </div>

        {file && (
          <div
            className={fromLegacy('excel-uploader-actions')}
            onClick={(e) => e.stopPropagation()}
            onKeyDown={(e) => e.stopPropagation()}
          >
            <label className={fromLegacy('excel-uploader-check')}>
              <input
                type="checkbox"
                checked={autoApprove}
                onChange={(e) => setAutoApprove(e.target.checked)}
              />
              <span>ثبت اسناد به‌صورت تایید‌شده</span>
            </label>
            {preview?.stats?.journals_existing > 0 && !justCommitted && (
              <label className={fromLegacy('excel-uploader-check')}>
                <input
                  type="checkbox"
                  checked={replaceExisting}
                  onChange={(e) => setReplaceExisting(e.target.checked)}
                />
                <span>جایگزینی تراز قبلی این دوره (سند قبلی با سند اصلاحی برگشت می‌خورد)</span>
              </label>
            )}
            <div className={fromLegacy('excel-uploader-buttons')}>
              <Button variant="secondary" size="sm" onClick={handleClearFile} disabled={busy}>
                <Icon name="x" size={16} />
                <span>حذف فایل</span>
              </Button>
              <Button
                variant="secondary"
                onClick={() => runImport({ dryRun: true, approve: false })}
                disabled={busy}
              >
                {busy && !preview ? <Icon name="hourglass" size={16} /> : <Icon name="search" size={16} />}
                <span>{busy && !preview ? 'در حال بررسی…' : 'بررسی فایل'}</span>
              </Button>
              <Button
                variant="primary"
                onClick={() => runImport({ dryRun: false, approve: autoApprove })}
                disabled={busy || !preview || justCommitted}
              >
                {busy && preview ? <Icon name="hourglass" size={16} /> : <Icon name="check" size={16} />}
                <span>{busy && preview ? 'در حال ثبت… (۱–۳ دقیقه)' : 'ثبت نهایی'}</span>
              </Button>
            </div>
            {busy && (
              <p className={fromLegacy('excel-guide-note')}>
                {preview ? 'در حال ساخت درخت حساب‌ها در دیتابیس… لطفاً صبر کنید.' : 'در حال خواندن فایل اکسل…'}
              </p>
            )}
          </div>
        )}
      </AccountingDataPanel>

      <AccountingDataPanel
        title="راهنمای فرمت"
        subtitle="ساختار مورد انتظار فایل اکسل"
        className={fromLegacy('excel-guide-panel')}
      >
        <ul className={fromLegacy('excel-guide-list')}>
          <li><strong>تراز کل</strong> — کد 1120، 1210، … + افتتاحیه / گردش / مانده</li>
          <li><strong>تراز معین</strong> — کد 1210/1، 1310/2، …</li>
          <li><strong>تراز تفصیلی</strong> — کد 1210/1/6، 1130/1/1، …</li>
          <li><strong>ریز نمونه</strong> — گردش یک حساب (اختیاری؛ فقط نمایشی)</li>
        </ul>
        <p className={fromLegacy('excel-guide-note')}>
          فرمت استاندارد خروجی «گزارشات مالی» — ۴ شیت: تراز کل، تراز معین، تراز تفصیلی، ریز نمونه.
          ثبت نهایی، درخت حساب‌ها را می‌سازد و مانده افتتاحیه و گردش دوره هر حساب را
          به‌صورت سند افتتاحیه و سند گردش ثبت می‌کند؛ اختلاف تراز فایل به حساب موجود
          «سود و زیان انباشته» افزوده می‌شود.
        </p>
      </AccountingDataPanel>

      {showSuccess && (
        <AccountingDataPanel
          title={justCommitted ? 'ثبت موفق' : 'نتیجه بررسی'}
          subtitle={justCommitted ? 'اطلاعات در دفتر کل ذخیره شد' : 'فایل معتبر است — برای ثبت، دکمه «ثبت نهایی» را بزنید'}
          className={fromLegacy(`excel-result-panel${justCommitted ? ' is-committed' : ' is-preview'}`)}
        >
          <div className={fromLegacy('excel-result-banner')}>
            <Icon name={justCommitted ? 'check' : 'info'} size={22} />
            <div>
              <strong>{justCommitted ? 'بارگذاری با موفقیت انجام شد' : 'بررسی بدون خطای قطعی'}</strong>
              {preview.metadata?.date_from && (
                <span>
                  بازه: {preview.metadata.date_from}
                  {preview.metadata.date_to ? ` تا ${preview.metadata.date_to}` : ''}
                </span>
              )}
            </div>
          </div>
          <AccountingSummary items={buildSummaryItems(preview)} />
          {preview.recognized_accounts?.length > 0 && (
            <div className={fromLegacy('excel-account-detection')}>
              <div className={fromLegacy('excel-account-detection-head')}>
                <strong>حساب‌های شناسایی‌شده از فایل</strong>
                <span>
                  {formatFa(preview.recognized_accounts.length)} حساب
                  {' · '}
                  {formatFa(preview.account_detection?.new)} جدید
                </span>
              </div>
              <div className="acct-card-stack is-compact">
                {preview.recognized_accounts.slice(0, 150).map((account) => (
                  <div key={`${account.level}-${account.path}`} className="acct-strip acct-strip--4">
                    <strong>{account.name}</strong>
                    <span className="acct-number">{account.path}</span>
                    <span>
                      {{
                        general: 'کل',
                        subsidiary: 'معین',
                        detailed: 'تفصیلی',
                      }[account.level] || account.level}
                    </span>
                    <span className={`acct-balance-badge ${account.status === 'new' ? 'acct-balance-badge--credit' : 'acct-balance-badge--balanced'}`}>
                      {account.status === 'new' ? 'جدید' : 'موجود'}
                    </span>
                  </div>
                ))}
              </div>
              {preview.recognized_accounts.length > 150 && (
                <p className={fromLegacy('excel-guide-note')}>
                  ۱۵۰ حساب اول نمایش داده شده است؛ همهٔ {formatFa(preview.recognized_accounts.length)} حساب هنگام ثبت پردازش می‌شوند.
                </p>
              )}
            </div>
          )}
          {preview.warnings?.length > 0 && (
            <div className={fromLegacy('excel-warnings')}>
              <p><Icon name="warning" size={16} /> هشدارها ({formatFa(preview.warnings.length)})</p>
              <ul>
                {preview.warnings.slice(0, 8).map((w, i) => (
                  <li key={i}>{w}</li>
                ))}
              </ul>
            </div>
          )}
        </AccountingDataPanel>
      )}

      {error && (
        <AccountingDataPanel
          title="خطا در پردازش"
          subtitle="فایل بررسی یا ثبت نشد"
          className={fromLegacy('excel-result-panel is-error')}
        >
          <div className={fromLegacy('excel-result-banner is-error')}>
            <Icon name="warning" size={22} />
            <div>
              <strong>{error.message}</strong>
            </div>
          </div>
          {error.errors?.length > 0 && (
            <table className="accounting-table accounting-table--compact">
              <thead><tr><th>#</th><th>شرح</th></tr></thead>
              <tbody>
                {error.errors.slice(0, 20).map((err, idx) => (
                  <tr key={idx}>
                    <td className="col-code">{formatFa(idx + 1)}</td>
                    <td>{typeof err === 'string' ? err : err.message || JSON.stringify(err)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </AccountingDataPanel>
      )}
    </div>
  )
}
