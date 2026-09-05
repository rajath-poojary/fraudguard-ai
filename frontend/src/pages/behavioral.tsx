import { useEffect, useState } from "react";
import AppShell from "../components/AppShell";
import { ErrorState, LoadingState, NotConnected, PageHeader, Panel, EvidenceBar } from "../components/UI";
import { api, BehavioralProfile } from "../services/api";

export default function Behavioral() {
  const [profiles, setProfiles] = useState<BehavioralProfile[] | null>(null);
  const [error, setError] = useState("");
  useEffect(() => { api.behavioralProfiles().then((data) => setProfiles(data.items)).catch((err) => setError(err instanceof Error ? err.message : "Behavior service unavailable")); }, []);
  return <AppShell><section className="page"><PageHeader eyebrow="Behavior / profiles" title="Behavioral intelligence" description="Compare current activity with learned account behavior across amount, timing, location, merchant, and device signals." />
    {error ? <ErrorState message={error} /> : !profiles ? <LoadingState /> : profiles.length === 0 ? <NotConnected detail="No behavioral profiles are available from the backend." /> : <div className="workspace-grid"><Panel className="wide" title="Account behavior profiles" eyebrow="Historical context"><div className="table-wrap"><table><thead><tr><th>Account</th><th>Profile version</th><th>Deviation</th><th>Updated</th><th /></tr></thead><tbody>{profiles.map((profile) => <tr key={profile.account_id}><td className="mono">{profile.account_id}</td><td>{profile.profile_version}</td><td>{profile.deviation_score === undefined ? "Not available" : `${(profile.deviation_score * 100).toFixed(0)}%`}</td><td>{new Date(profile.updated_at).toLocaleString()}</td><td><button className="ghost-button">Inspect profile</button></td></tr>)}</tbody></table></div></Panel><Panel title="Deviation evidence" eyebrow="Selected profile"><NotConnected detail="Select an account to load its baseline, deviations, and historical transaction sequence." /><div className="evidence-list"><EvidenceBar label="Amount deviation" /><EvidenceBar label="Time-of-day deviation" tone="amber" /><EvidenceBar label="Location deviation" tone="red" /><EvidenceBar label="Device novelty" tone="green" /></div></Panel></div>}
  </section></AppShell>;
}
