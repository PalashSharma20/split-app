import type { SplitType } from '../types'

function r2(n: number): number {
  return Math.round(n * 100) / 100
}

export function calculateSplit(
  splitType: SplitType,
  amount: number,
  percentYou?: number | null,
  exactYou?: number | null,
): { youOwed: number; otherOwed: number } {
  switch (splitType) {
    case 'equal':
      return { youOwed: r2(amount / 2), otherOwed: r2(amount - r2(amount / 2)) }

    case 'full_you':
      return { youOwed: r2(amount), otherOwed: 0 }

    case 'full_other':
      return { youOwed: 0, otherOwed: r2(amount) }

    case 'percent': {
      const you = r2(amount * ((percentYou ?? 50) / 100))
      return { youOwed: you, otherOwed: r2(amount - you) }
    }

    case 'exact': {
      const you = r2(exactYou ?? 0)
      return { youOwed: you, otherOwed: r2(amount - you) }
    }

    case 'personal':
    case 'already_added':
      return { youOwed: 0, otherOwed: 0 }
  }
}

export function fmt(n: number): string {
  return n.toLocaleString('en-US', { style: 'currency', currency: 'USD' })
}
