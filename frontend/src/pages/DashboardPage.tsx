import { Button, Callout, Card, H4, Spinner, Tag } from "@blueprintjs/core"
import { useEffect, useRef, useState } from "react"
import { useNavigate } from "react-router-dom"
import {
  fetchFromAmex,
  getLastTransactionDate,
  getSyncedTransactions,
  listUnsynced,
  uploadCsv,
} from "../api/transactions"
import { fmt } from "../utils/calculations"
import type { SyncedTransaction, SplitType, UploadResult } from "../types"

const SPLIT_LABELS: Record<SplitType, string> = {
  equal: "50 / 50",
  full_you: "You owe all",
  full_other: "They owe all",
  percent: "Percent",
  exact: "Exact",
  personal: "Personal",
  already_added: "Already added",
}

function SplitBadge({ splitType }: { splitType: SplitType | null }) {
  if (!splitType) return <span style={{ color: "#738091" }}>—</span>
  const intent =
    splitType === "personal" || splitType === "already_added"
      ? undefined
      : splitType === "equal"
        ? "primary"
        : "none"
  return (
    <Tag minimal intent={intent}>
      {SPLIT_LABELS[splitType]}
    </Tag>
  )
}

const PAGE_SIZE = 25

export default function DashboardPage() {
  const navigate = useNavigate()
  const fileInputRef = useRef<HTMLInputElement>(null)

  const [unsyncedCount, setUnsyncedCount] = useState<number | null>(null)
  const [lastDate, setLastDate] = useState<string | null | undefined>(undefined)
  const [uploading, setUploading] = useState(false)
  const [fetching, setFetching] = useState(false)
  const [amexAuthRequired, setAmexAuthRequired] = useState(false)
  const [amexLoginOpened, setAmexLoginOpened] = useState(false)
  const [uploadResult, setUploadResult] = useState<UploadResult | null>(null)
  const [error, setError] = useState<string | null>(null)

  const [page, setPage] = useState(0)
  const [history, setHistory] = useState<SyncedTransaction[]>([])
  const [historyTotal, setHistoryTotal] = useState(0)
  const [historyLoading, setHistoryLoading] = useState(false)

  const totalPages = Math.ceil(historyTotal / PAGE_SIZE)

  useEffect(() => {
    listUnsynced()
      .then((txs) => setUnsyncedCount(txs.length))
      .catch(() => setUnsyncedCount(0))
    getLastTransactionDate()
      .then(setLastDate)
      .catch(() => setLastDate(null))
  }, [])

  useEffect(() => {
    setHistoryLoading(true)
    getSyncedTransactions(page * PAGE_SIZE, PAGE_SIZE)
      .then((data) => {
        setHistory(data.items)
        setHistoryTotal(data.total)
      })
      .catch(console.error)
      .finally(() => setHistoryLoading(false))
  }, [page])

  async function handleFetchAmex() {
    setFetching(true)
    setError(null)
    setUploadResult(null)
    setAmexAuthRequired(false)
    setAmexLoginOpened(false)
    try {
      const startDate = lastDate ?? new Date().toISOString().slice(0, 7) + "-01"
      const result = await fetchFromAmex(startDate)
      setUploadResult(result)
      setUnsyncedCount((c) => (c ?? 0) + result.inserted)
      if (result.inserted > 0) navigate("/review")
    } catch (err: unknown) {
      const status = (err as { response?: { status?: number } })?.response
        ?.status
      if (status === 401) {
        setAmexAuthRequired(true)
      } else {
        setError(err instanceof Error ? err.message : "Fetch failed.")
      }
    } finally {
      setFetching(false)
    }
  }

  function handleOpenAmex() {
    window.open(
      "https://www.americanexpress.com/en-us/account/login?inav=en_us_menu_login",
      "_blank",
    )
    setAmexLoginOpened(true)
  }

  async function handleFile(e: React.ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0]
    if (!file) return
    setUploading(true)
    setError(null)
    setUploadResult(null)
    try {
      const result = await uploadCsv(file)
      setUploadResult(result)
      setUnsyncedCount((c) => (c ?? 0) + result.inserted)
      if (result.inserted > 0) navigate("/review")
    } catch (err: unknown) {
      setError(
        err instanceof Error
          ? err.message
          : "Upload failed. Check the file and try again.",
      )
    } finally {
      setUploading(false)
      if (fileInputRef.current) fileInputRef.current.value = ""
    }
  }

  return (
    <div>
      {/* Pending banner */}
      {(unsyncedCount ?? 0) > 0 && (
        <Callout
          intent="warning"
          icon="time"
          style={{
            marginBottom: 28,
            display: "flex",
            alignItems: "center",
            justifyContent: "space-between",
          }}>
          <span>
            <strong>{unsyncedCount}</strong> transaction
            {unsyncedCount !== 1 ? "s" : ""} waiting for review
          </span>
          <Button
            intent="warning"
            icon="arrow-right"
            onClick={() => navigate("/review")}
            style={{ marginLeft: 16 }}>
            Review &amp; push
          </Button>
        </Callout>
      )}

      {/* Stats row */}
      <div className="dashboard-stats">
        <div className="stat-card">
          {unsyncedCount === null ? (
            <Spinner size={28} />
          ) : (
            <span className="stat-number">{unsyncedCount}</span>
          )}
          <span className="stat-label">Pending transactions</span>
        </div>
        <div className="stat-card">
          {lastDate === undefined ? (
            <Spinner size={28} />
          ) : (
            <span className="stat-number stat-number--date">
              {lastDate ?? "—"}
            </span>
          )}
          <span className="stat-label">Last imported date</span>
        </div>
      </div>

      {/* Upload */}
      <Card className="upload-card">
        <div className="upload-card-body">
          <div>
            <H4 style={{ margin: "0 0 4px" }}>Upload AMEX CSV</H4>
            <p style={{ margin: 0, color: "#738091", fontSize: 13 }}>
              {lastDate
                ? `Your last transaction was on ${lastDate} — export from that date onwards.`
                : "Duplicate references are automatically skipped."}
            </p>
          </div>
          <div style={{ flexShrink: 0, display: "flex", gap: 8 }}>
            {import.meta.env.DEV && (
              <Button
                intent="success"
                icon="download"
                large
                loading={fetching}
                onClick={handleFetchAmex}>
                Fetch from AMEX
              </Button>
            )}
            <input
              ref={fileInputRef}
              type="file"
              accept=".csv"
              style={{ display: "none" }}
              onChange={handleFile}
            />
            <Button
              intent="primary"
              icon="upload"
              large
              loading={uploading}
              onClick={() => fileInputRef.current?.click()}>
              Choose CSV file
            </Button>
          </div>
        </div>
        {uploadResult && uploadResult.inserted === 0 && (
          <p style={{ margin: "12px 0 0", color: "#738091", fontSize: 13 }}>
            No new transactions — {uploadResult.skipped} already imported.
          </p>
        )}
        {amexAuthRequired && (
          <div
            style={{
              marginTop: 12,
              padding: "10px 14px",
              background: "#fef3e2",
              border: "1px solid #f0b429",
              borderRadius: 6,
              display: "flex",
              alignItems: "center",
              justifyContent: "space-between",
              gap: 12,
            }}>
            <span style={{ fontSize: 13, color: "#7d4e00" }}>
              {amexLoginOpened
                ? "Done logging in? Click Try Again."
                : "Session expired — log in to americanexpress.com first."}
            </span>
            {amexLoginOpened ? (
              <Button
                intent="warning"
                icon="refresh"
                loading={fetching}
                onClick={handleFetchAmex}>
                Try Again
              </Button>
            ) : (
              <Button intent="warning" icon="log-in" onClick={handleOpenAmex}>
                Log in to AMEX
              </Button>
            )}
          </div>
        )}
        {error && (
          <p style={{ margin: "12px 0 0", color: "#c23030", fontSize: 13 }}>
            {error}
          </p>
        )}
      </Card>

      {/* Transaction history */}
      <div style={{ marginTop: 32 }}>
        <div
          style={{
            display: "flex",
            alignItems: "center",
            justifyContent: "space-between",
            marginBottom: 12,
          }}>
          <div style={{ display: "flex", alignItems: "baseline", gap: 10 }}>
            <h4
              style={{
                margin: 0,
                fontSize: 14,
                fontWeight: 600,
                color: "#1c2127",
              }}>
              Transaction history
            </h4>
            {historyTotal > 0 && (
              <span style={{ fontSize: 12, color: "#738091" }}>
                {historyTotal} synced
              </span>
            )}
          </div>
          {totalPages > 1 && (
            <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
              <Button
                minimal
                small
                icon="chevron-left"
                disabled={page === 0}
                onClick={() => setPage((p) => p - 1)}
              />
              <span style={{ fontSize: 13, color: "#738091" }}>
                Page {page + 1} of {totalPages}
              </span>
              <Button
                minimal
                small
                icon="chevron-right"
                disabled={page >= totalPages - 1}
                onClick={() => setPage((p) => p + 1)}
              />
            </div>
          )}
        </div>

        <div
          style={{
            background: "#fff",
            border: "1px solid #e1e8ed",
            borderRadius: 8,
            overflowX: "auto",
            position: "relative",
          }}>
          {historyLoading && (
            <div
              style={{
                position: "absolute",
                inset: 0,
                background: "rgba(255,255,255,0.7)",
                display: "flex",
                alignItems: "center",
                justifyContent: "center",
                zIndex: 1,
              }}>
              <Spinner size={28} />
            </div>
          )}
          <table className="review-table">
            <thead>
              <tr>
                <th>Date</th>
                <th>Description</th>
                <th style={{ textAlign: "right" }}>Amount</th>
                <th>Paid by</th>
                <th>Split</th>
              </tr>
            </thead>
            <tbody>
              {history.map((tx) => (
                <tr key={tx.id}>
                  <td style={{ color: "#738091", whiteSpace: "nowrap" }}>
                    {tx.date}
                  </td>
                  <td>
                    <div style={{ fontWeight: 500, fontSize: 14 }}>
                      {tx.description_raw}
                    </div>
                    <div
                      style={{ fontSize: 12, color: "#738091", marginTop: 2 }}>
                      {tx.merchant_key}
                      {tx.sub_merchant_key ? ` · ${tx.sub_merchant_key}` : ""}
                    </div>
                  </td>
                  <td
                    style={{
                      textAlign: "right",
                      fontWeight: 600,
                      whiteSpace: "nowrap",
                    }}>
                    {fmt(parseFloat(tx.amount))}
                  </td>
                  <td style={{ fontSize: 13, color: "#738091" }}>
                    {tx.card_member ?? "—"}
                  </td>
                  <td>
                    <SplitBadge splitType={tx.split_type} />
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>

        {totalPages > 1 && (
          <div
            style={{
              display: "flex",
              justifyContent: "flex-end",
              marginTop: 10,
              gap: 8,
              alignItems: "center",
            }}>
            <Button
              minimal
              small
              icon="chevron-left"
              disabled={page === 0}
              onClick={() => setPage((p) => p - 1)}
            />
            <span style={{ fontSize: 13, color: "#738091" }}>
              Page {page + 1} of {totalPages}
            </span>
            <Button
              minimal
              small
              icon="chevron-right"
              disabled={page >= totalPages - 1}
              onClick={() => setPage((p) => p + 1)}
            />
          </div>
        )}
      </div>
    </div>
  )
}
