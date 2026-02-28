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

export interface SyncedTransaction {
  id: number
  date: string
  description_raw: string
  amount: string
  merchant_key: string
  sub_merchant_key: string | null
  card_member: string | null
  splitwise_expense_id: string | null
  split_type: SplitType | null
}

export interface SyncedPage {
  items: SyncedTransaction[]
  total: number
  has_more: boolean
}

export interface User {
  email: string
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
