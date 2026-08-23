export type SplitType =
  | "equal"
  | "full_you"
  | "full_other"
  | "percent"
  | "exact"
  | "personal"
  | "already_added"

export interface SplitSuggestion {
  split_type: SplitType
  percent_you: number | null
  exact_you: number | null
  you_owed: number
  other_owed: number
  confidence: number | null
}

export interface Transaction {
  id: number
  date: string
  description_raw: string
  amount: string
  merchant_key: string
  sub_merchant_key: string | null
  card_member: string | null
  paid_by: string
  you_paid: boolean
  suggestion: SplitSuggestion
}

export interface UploadResult {
  inserted: number
  skipped: number
  transactions: Transaction[]
}

export interface ConfirmRequest {
  split_type: SplitType
  percent_you?: number | null
  exact_you?: number | null
}

export interface ConfirmResponse {
  splitwise_expense_id: string | null
  you_owed: number
  other_owed: number
}

export interface BatchConfirmItem extends ConfirmRequest {
  transaction_id: number
}

export interface BatchConfirmResponse {
  confirmed: Array<ConfirmResponse & { transaction_id: number }>
  balance: BalanceResult
}

export interface SyncedTransaction {
  id: number
  date: string
  description_raw: string
  amount: string
  merchant_key: string
  sub_merchant_key: string | null
  card_member: string | null
  paid_by: string
  splitwise_expense_id: string | null
  split_type: SplitType | null
  percent_you: number | null
  exact_you: number | null
  you_paid: boolean
  source: "amex" | "custom" | "recurring"
}

export interface EditTransactionRequest extends ConfirmRequest {
  payer: "you" | "other"
  description?: string
  amount?: number
  date?: string
}

export interface SyncedPage {
  items: SyncedTransaction[]
  total: number
  has_more: boolean
}

export interface User {
  email: string
}

export interface BalanceResult {
  your_amex_total: number
  other_amex_total: number
  your_name: string
  other_name: string
  settlement_from: string | null
  settlement_to: string | null
  settlement_amount: number
}

export interface CustomExpenseRequest extends ConfirmRequest {
  description: string
  amount: number
  date: string
  payer: "you" | "other"
}

export interface RecurringExpenseRequest extends ConfirmRequest {
  description: string
  amount: number
  start_date: string
  cadence: "weekly" | "monthly"
  payer: "you" | "other"
}

export interface RecurringExpense {
  id: number
  description: string
  amount: number
  start_date: string
  cadence: "weekly" | "monthly"
  active: boolean
  payer: "you" | "other"
  split_type: SplitType
  percent_you: number | null
  exact_you: number | null
}


export interface RowState {
  tx: Transaction
  splitType: SplitType
  percentYou: string
  exactYou: string
  youOwed: number
  otherOwed: number
  confirmed: boolean
  error: string | null
}
