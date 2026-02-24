/**
 * DevStatusCard — API health status widget for dev pages only.
 *
 * Renders only when import.meta.env.DEV is true (Vite dev server).
 * Polls /health and /health/deps once on mount; shows a refresh button.
 *
 * Usage:
 *   import { DevStatusCard } from "../components/DevStatusCard";
 *   <DevStatusCard />
 */
import { useEffect, useState } from "react";

const API_BASE =
  import.meta.env.VITE_API_BASE_URL || import.meta.env.VITE_API_URL || "";

interface HealthResponse {
  status: string;
  service?: string;
  version?: string;
  request_id?: string;
}

interface DepsResponse {
  status: string;
  deps?: Record<string, { ok?: boolean; status?: string; [key: string]: unknown }>;
  request_id?: string;
}

type FetchState<T> = { loading: boolean; data: T | null; error: string | null };

function init<T>(): FetchState<T> {
  return { loading: true, data: null, error: null };
}

function StatusBadge({ ok }: { ok: boolean }) {
  return (
    <span
      style={{
        display: "inline-block",
        padding: "1px 7px",
        borderRadius: 4,
        fontSize: 11,
        fontWeight: 600,
        background: ok ? "#166534" : "#7f1d1d",
        color: ok ? "#bbf7d0" : "#fecaca",
        marginLeft: 6,
      }}
    >
      {ok ? "OK" : "FAIL"}
    </span>
  );
}

export function DevStatusCard() {
  // Only render in Vite dev mode
  if (!import.meta.env.DEV) return null;

  const [health, setHealth] = useState<FetchState<HealthResponse>>(init());
  const [deps, setDeps] = useState<FetchState<DepsResponse>>(init());
  const [lastRequestId, setLastRequestId] = useState<string | null>(null);
  const [tick, setTick] = useState(0);

  useEffect(() => {
    let cancelled = false;

    async function fetchAll() {
      setHealth(init());
      setDeps(init());

      // /health
      try {
        const res = await fetch(`${API_BASE}/health`);
        const rid = res.headers.get("x-request-id");
        if (rid) setLastRequestId(rid);
        if (!cancelled) {
          if (res.ok) {
            setHealth({ loading: false, data: await res.json(), error: null });
          } else {
            setHealth({ loading: false, data: null, error: `HTTP ${res.status}` });
          }
        }
      } catch (e) {
        if (!cancelled) {
          setHealth({ loading: false, data: null, error: "unreachable" });
        }
      }

      // /health/deps
      try {
        const res = await fetch(`${API_BASE}/health/deps`);
        const rid = res.headers.get("x-request-id");
        if (rid) setLastRequestId(rid);
        if (!cancelled) {
          if (res.ok) {
            setDeps({ loading: false, data: await res.json(), error: null });
          } else {
            setDeps({ loading: false, data: null, error: `HTTP ${res.status}` });
          }
        }
      } catch (e) {
        if (!cancelled) {
          setDeps({ loading: false, data: null, error: "unreachable" });
        }
      }
    }

    fetchAll();
    return () => { cancelled = true; };
  }, [tick]);

  const healthOk = health.data?.status === "ok";
  const depsOk = deps.data?.status === "ok";
  const anyBad = !health.loading && !deps.loading && (!healthOk || !depsOk);

  return (
    <div
      style={{
        fontFamily: "monospace",
        fontSize: 12,
        background: "#0f172a",
        color: "#94a3b8",
        border: anyBad ? "1px solid #7f1d1d" : "1px solid #1e3a5f",
        borderRadius: 6,
        padding: "10px 14px",
        marginBottom: 12,
        lineHeight: 1.7,
      }}
    >
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 6 }}>
        <span style={{ color: "#64748b", fontWeight: 700, letterSpacing: 1 }}>
          DEV STATUS
        </span>
        <button
          onClick={() => setTick((t) => t + 1)}
          style={{
            background: "none",
            border: "1px solid #334155",
            color: "#64748b",
            borderRadius: 3,
            padding: "1px 7px",
            cursor: "pointer",
            fontSize: 11,
          }}
        >
          ↻ refresh
        </button>
      </div>

      {/* API Base URL */}
      <div>
        <span style={{ color: "#475569" }}>api base:</span>{" "}
        <span style={{ color: "#e2e8f0" }}>{API_BASE || "(proxy)"}</span>
      </div>

      {/* /health */}
      <div>
        <span style={{ color: "#475569" }}>/health:</span>
        {health.loading ? (
          <span style={{ color: "#475569", marginLeft: 6 }}>…</span>
        ) : health.error ? (
          <>
            <StatusBadge ok={false} />
            <span style={{ color: "#f87171", marginLeft: 6 }}>{health.error}</span>
            <span style={{ display: "block", color: "#ef4444", fontWeight: 600, marginTop: 2 }}>
              ⚠ API unreachable — run: make dev-up
            </span>
          </>
        ) : (
          <>
            <StatusBadge ok={healthOk} />
            {health.data?.version && (
              <span style={{ color: "#475569", marginLeft: 8 }}>v{health.data.version}</span>
            )}
          </>
        )}
      </div>

      {/* /health/deps */}
      <div>
        <span style={{ color: "#475569" }}>/health/deps:</span>
        {deps.loading ? (
          <span style={{ color: "#475569", marginLeft: 6 }}>…</span>
        ) : deps.error ? (
          <StatusBadge ok={false} />
        ) : (
          <>
            <StatusBadge ok={depsOk} />
            {deps.data?.deps && (
              <span style={{ color: "#475569", marginLeft: 8 }}>
                {Object.entries(deps.data.deps)
                  .map(([k, v]) => {
                    const ok = v.ok ?? v.status === "ok";
                    return `${k}:${ok ? "✓" : "✗"}`;
                  })
                  .join("  ")}
              </span>
            )}
          </>
        )}
      </div>

      {/* Last Request ID */}
      {lastRequestId && (
        <div style={{ marginTop: 2 }}>
          <span style={{ color: "#475569" }}>last req-id:</span>{" "}
          <span style={{ color: "#64748b" }}>{lastRequestId}</span>
        </div>
      )}
    </div>
  );
}
