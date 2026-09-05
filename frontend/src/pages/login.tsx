import Link from "next/link";
import { FormEvent, useState } from "react";
import { useRouter } from "next/router";

import { api } from "../services/api";

export default function Login() {
  const router = useRouter(); const [email, setEmail] = useState(""); const [password, setPassword] = useState(""); const [error, setError] = useState(""); const [busy, setBusy] = useState(false);
  async function submit(event: FormEvent) { event.preventDefault(); setBusy(true); setError(""); try { const result = await api.login({ email, password }); localStorage.setItem("fraudguard_token", result.access_token); await router.push("/dashboard"); } catch (err) { setError(err instanceof Error ? err.message : "Sign in failed"); } finally { setBusy(false); } }
  return <div className="auth-page"><div className="auth-aside"><Link className="brand" href="/"><span className="brand-mark">X</span><span>FRAUD<span>GUARD</span><b> X</b></span></Link><div className="auth-statement"><span className="eyebrow">Intelligence console / 02</span><h1>See the<br /><em>whole signal.</em></h1><p>Investigate the relationships behind every fraud decision.</p></div><div className="auth-aside-foot">SECURITY OPERATIONS<br />DECISION STREAM READY</div></div><main className="auth-form-wrap"><div className="auth-form"><div className="eyebrow">Secure access</div><h2>Enter the intelligence console</h2><p className="form-intro">Authenticate to access your fraud operations workspace.</p><form onSubmit={submit}><label>Email address<input type="email" required value={email} onChange={(event) => setEmail(event.target.value)} placeholder="you@company.com" /></label><label>Password<input type="password" required value={password} onChange={(event) => setPassword(event.target.value)} placeholder="Enter your password" /></label>{error && <div className="form-error">{error}</div>}<button className="primary-button" disabled={busy}>{busy ? "Authenticating..." : "Enter console"}<span>↗</span></button></form><p className="form-switch">New operator? <Link href="/register">Create an account</Link></p></div></main></div>;
}
