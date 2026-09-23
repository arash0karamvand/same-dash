import type { BalanceSnapshot, JournalLine, LineBalanceRow, TrialRow } from './types'

export function money(value: unknown): number {
  const amount = Number(value ?? 0)
  return Number.isFinite(amount) ? amount : 0
}

export function snapshot(debit: number, credit: number): BalanceSnapshot {
  const difference = debit - credit
  return {
    debit,
    credit,
    difference,
    balanced: difference === 0 && (debit > 0 || credit > 0),
  }
}

export function emptySnapshot(): BalanceSnapshot {
  return { debit: 0, credit: 0, difference: 0, balanced: false }
}

export function linesBalance(lines: JournalLine[]): { rows: LineBalanceRow[]; totals: BalanceSnapshot } {
  let debit = 0
  let credit = 0
  const rows = lines.map((line) => {
    const lineDebit = money(line.debit)
    const lineCredit = money(line.credit)
    debit += lineDebit
    credit += lineCredit
    return {
      ...line,
      debit: lineDebit,
      credit: lineCredit,
      runningDebit: debit,
      runningCredit: credit,
      runningDifference: debit - credit,
    }
  })
  return { rows, totals: snapshot(debit, credit) }
}

export function trialSnapshot(rows: TrialRow[]): BalanceSnapshot {
  return rows.reduce(
    (acc, row) => snapshot(acc.debit + money(row.total_debit), acc.credit + money(row.total_credit)),
    emptySnapshot(),
  )
}
