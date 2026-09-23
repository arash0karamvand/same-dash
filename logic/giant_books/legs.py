"""قاعدهٔ Django-Hordak: هر سند مجموعه‌ای از پاها با مبلغ علامت‌دار است.

بدهکار مثبت و بستانکار منفی است. جمع پاهای یک سند باید صفر باشد.
py-moneyed همان کتابخانه‌ای است که Hordak برای مبلغ استفاده می‌کند.
"""

from logic.giant_books.money import money_int, rial


def hordak_check(frame):
    if frame.empty:
        return {"transaction_count": 0, "balanced": True, "unbalanced": []}
    unbalanced = []
    count = 0
    for journal_id, group in frame.groupby("journal_id", sort=False):
        count += 1
        total = rial(0)
        for row in group.itertuples(index=False):
            total = total + rial(row.debit) - rial(row.credit)
        if money_int(total) != 0:
            unbalanced.append({
                "journal_id": int(journal_id),
                "document_code": str(group.iloc[0].document_code),
                "difference": money_int(total),
            })
    return {
        "transaction_count": count,
        "balanced": not unbalanced,
        "unbalanced": unbalanced,
    }
