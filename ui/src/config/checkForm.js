/** فیلدهای فرم لیست چک‌های دریافتی — مطابق قالب Excel (ردیف ۶). */

export const CHECK_FORM_MAX_ROWS = 16

/** ترتیب ستون‌ها در اکسل: C=تحویل، D=بانک، E=سررسید، F=شماره، G=مبلغ، H=تحویل‌گیرنده */
export const CHECK_ROW_FIELDS = [
  { key: 'received_at', label: 'تاریخ تحویل چک به شعبه', type: 'date' },
  { key: 'bank_name', label: 'نام بانک', type: 'text' },
  { key: 'due_date', label: 'تاریخ سررسید', type: 'date' },
  { key: 'check_number', label: 'شماره چک', type: 'text', ltr: true },
  { key: 'amount', label: 'مبلغ', type: 'money' },
  { key: 'receiver_name', label: 'تحویل‌گیرنده', type: 'text' },
]

export const CHECK_NOTES_LABEL = 'توضیحات'

export const EMPTY_CHECK_ROW = {
  received_at: '',
  bank_name: '',
  due_date: '',
  check_number: '',
  amount: '',
  receiver_name: '',
  notes: '',
}
