import client, { localClient } from './client'
import type { BalanceResult, CheckpointRequest, ConfirmRequest, ConfirmResponse, SyncedPage, Transaction, UploadResult } from '../types'

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

export async function getBalance(): Promise<BalanceResult> {
  const res = await client.get<BalanceResult>('/transactions/balance')
  return res.data
}

export async function setBalanceCheckpoint(body: CheckpointRequest): Promise<void> {
  await client.post('/transactions/balance/checkpoint', body)
}

export async function fetchFromAmex(startDate: string): Promise<UploadResult> {
  // Step 1: pull raw CSV from AMEX via the local backend (reads Chrome cookies)
  const csvRes = await localClient.get<string>('/transactions/fetch-amex', {
    params: { start_date: startDate },
    responseType: 'text',
  })

  // Step 2: upload the CSV to the prod backend so it writes to the real DB
  const file = new File([csvRes.data], 'amex.csv', { type: 'text/csv' })
  return uploadCsv(file)
}
