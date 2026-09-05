import Link from "next/link";
import { useRouter } from "next/router";
import { ReactNode } from "react";

import { useAuth } from "../hooks/useAuth";

const links = [
  { href: "/dashboard", label: "Command Center", icon: "⌂" },
  { href: "/transactions", label: "Transaction Intelligence", icon: "↯" },
  { href: "/investigations", label: "Fraud Investigations", icon: "◈" },
  { href: "/network", label: "Fraud Network", icon: "◎" },
  { href: "/simulator", label: "Attack Simulator", icon: "▷" },
  { href: "/behavioral", label: "Behavioral Intelligence", icon: "◌" },
  { href: "/model-lab", label: "Model Lab", icon: "⌁" },
  { href: "/analytics", label: "Analytics", icon: "▥" },
  { href: "/admin", label: "System Administration", icon: "⚙" },
];

export default function AppShell({ children }: { children: ReactNode }) {
  const router = useRouter();
  const { ready, token, logout } = useAuth();
  if (!ready || !token) return <div className="boot-screen">Loading secure workspace...</div>;

  return (
    <div className="app-shell">
      <aside className="sidebar">
        <div className="brand-row"><Link className="brand" href="/dashboard"><span className="brand-mark">X</span><span>FRAUD<span>GUARD</span><b> X</b></span></Link><span className="version-chip">02</span></div>
        <div className="workspace-label">Intelligence console <span>● live</span></div>
        <nav aria-label="Primary navigation">{links.map((link) => <Link className={router.pathname.startsWith(link.href) ? "nav-link active" : "nav-link"} href={link.href} key={link.href}><span className="nav-icon">{link.icon}</span><span>{link.label}</span></Link>)}</nav>
        <div className="sidebar-foot"><div className="operator-card"><span className="operator-avatar">A</span><span><strong>Analyst workspace</strong><small>Authenticated session</small></span><i title="Session active" /></div><button className="logout-button" onClick={logout}>End session <span>↗</span></button></div>
      </aside>
      <main className="main-content">
        <header className="topbar"><div className="mobile-brand">FRAUDGUARD X</div><div className="topbar-context"><span className="pulse" />Connected to decision stream <span className="divider" /> <span className="mono">UTC</span></div><button className="icon-button" title="Open command palette" aria-label="Open command palette">⌘K</button></header>
        {children}
      </main>
    </div>
  );
}
