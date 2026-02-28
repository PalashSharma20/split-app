import client from './client'
import type { ConfirmRequest, ConfirmResponse, SyncedPage, Transaction, UploadResult } from '../types'

export async function uploadCsv(file: File): Promise<UploadResult> {
  const form = new FormData()
  form.append('file', file)
  const res = await client.post<UploadResult>('/transactions/upload', form)
  return res.data
}

export async function listUnsynced(): Promise<Transaction[]> {
  const res = await client.get<Transaction[]>('/transactions/')
  return res.data
}

export async function confirmTransaction(
  id: number,
  body: ConfirmRequest,
): Promise<ConfirmResponse> {
  const res = await client.post<ConfirmResponse>(`/transactions/${id}/confirm`, body)
  return res.data
}

export async function clearPending(): Promise<void> {
  await client.delete('/transactions/pending')
}

export async function getLastTransactionDate(): Promise<string | null> {
  const res = await client.get<{ date: string | null }>('/transactions/last-date')
  return res.data.date
}

export async function getSyncedTransactions(offset: number, limit = 25): Promise<SyncedPage> {
  const res = await client.get<SyncedPage>('/transactions/history', { params: { offset, limit } })
  return res.data
}
