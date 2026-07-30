// فروشگاه — شعب کمرد و پاسداران؛ ثبت و ارسال به اداری

import Sales from './Sales'

export default function Shop({ page = 'shop' }) {
  return <Sales portal="shop" pageKey={page} />
}
