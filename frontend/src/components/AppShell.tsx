import Link from "next/link";
import { useRouter } from "next/router";
import { ReactNode } from "react";

import { useAuth } from "../hooks/useAuth";

const links = [
  { href: "/dashboard", label: "Overview", mark: "01" },
  { href: "/transactions", label: "Transactions", mark: "02" },
  { href: "/simulator", label: "Simulator", mark: "03" },
  { href: "/alerts", label: "Fraud alerts", mark: "04" },
  { href: "/analytics", label: "Analytics", mark: "05" },
  { href: "/admin", label: "Admin", mark: "06" },
];

export default function AppShell({ children }: { children: ReactNode }) {
  const router = useRouter();
  const { ready, token, logout } = useAuth();
  if (!ready || !token) return <div className="boot-screen">Loading secure workspace...</div>;

  return (
    <div className="app-shell">
      <aside className="sidebar">
        <Link className="brand" href="/dashboard"><span className="brand-mark">F</span><span>FRAUD<span>GUARD</span></span></Link>
        <div className="workspace-label">Risk operations / 01</div>
        <nav>{links.map((link) => <Link className={router.pathname.startsWith(link.href) ? "nav-link active" : "nav-link"} href={link.href} key={link.href}><span>{link.mark}</span>{link.label}</Link>)}</nav>
        <div className="sidebar-foot"><div className="status-dot"><i /> Systems operational</div><button className="logout-button" onClick={logout}>Sign out <span>↗</span></button></div>
      </aside>
      <main className="main-content">
        <header className="topbar"><div className="mobile-brand">FRAUDGUARD</div><div className="topbar-meta"><span className="pulse" />Live risk monitor <span className="divider" /> UTC 09:42:18</div></header>
        {children}
      </main>
    </div>
  );
}
