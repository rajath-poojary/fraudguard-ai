import Link from "next/link";
import { useRouter } from "next/router";
import { useEffect, useState } from "react";
import AppShell from "../../components/AppShell";
import { ErrorState, LoadingState, PageHeader, RiskBadge } from "../../components/UI";
import { Alert, api } from "../../services/api";

export default function AlertDetails() { const router = useRouter(); const [alert, setAlert] = useState<Alert | null>(null); const [error, setError] = useState(""); useEffect(() => { if (typeof router.query.id === "string") api.alert(router.query.id).then(setAlert).catch((err) => setError(err.message)); }, [router.query.id]); return <AppShell><section className="page narrow-page"><Link className="back-link" href="/alerts">← Back to alerts</Link>{error ? <ErrorState message={error} /> : !alert ? <LoadingState /> : <><PageHeader eyebrow={`Alert / ${alert.id.slice(0, 12)}`} title="Alert details" description={new Date(alert.created_at).toLocaleString()} action={<RiskBadge value={alert.status} />} /><div className="alert-detail panel"><div><span className="eyebrow">Risk score</span><strong>{Number(alert.risk_score).toFixed(1)}</strong><span>/ 100</span></div><div><span className="eyebrow">Reason code</span><strong className="mono">{alert.reason_code}</strong></div><Link className="primary-button compact" href={`/transactions/${alert.transaction_id}`}>Open transaction <span>↗</span></Link></div></>}</section></AppShell>; }
