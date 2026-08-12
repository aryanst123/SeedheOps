import {
  Bell,
  Terminal,
  Activity,
  Check,
  ChevronRight,
  Shield,
  Layers,
  LayoutDashboard,
  Cpu,
  Settings,
  Sparkles,
  Server,
  Radio,
  UserRound,
} from 'lucide-react'
import ThemeToggle from './ThemeToggle'

const navigation = [
  [LayoutDashboard, 'Incident Overview'],
  [Layers, 'Cluster Topology'],
  [Activity, 'Telemetry Stream'],
  [Terminal, 'Runbook Sequences'],
  [Shield, 'Risk Mitigation'],
]

/** Shared shell — 248px sidebar + topbar */
export default function DashboardShell({
  children,
  active,
  setActive,
  notice,
  setNotice,
  onOpenSwarm,
}) {
  return (
    <div className="app-shell">
      <div className="app-layout">
        <aside className="sidebar">
          <div className="brand">
            <div className="brand-mark">
              <Sparkles size={17} />
            </div>
            <span>SeedheOps</span>
          </div>
          <div className="brand-subtitle">DevOps Swarm Co-Pilot</div>

          <nav className="nav">
            {navigation.map(([Icon, label]) => (
              <button
                key={label}
                type="button"
                className={active === label ? 'active' : ''}
                onClick={() => setActive(label)}
              >
                <Icon size={17} />
                <span>{label}</span>
              </button>
            ))}
            <button type="button">
              <Server size={17} />
              <span>Node telemetry</span>
            </button>
            <button type="button">
              <Radio size={17} />
              <span>Audio sitrep</span>
            </button>
            <button type="button" onClick={onOpenSwarm}>
              <Sparkles size={17} />
              <span>DevOps agents</span>
            </button>
            <button type="button">
              <Settings size={17} />
              <span>Settings</span>
            </button>
          </nav>

          <div className="user-card">
            <div className="user-avatar">OC</div>
            <div>
              <strong>DevOps On-Call</strong>
              <span>Site Reliability Engineer</span>
              <span>Cluster prod-us-east-1</span>
            </div>
          </div>

          <div className="pro-card">
            <h4>Autonomous mitigation mode</h4>
            <p>
              Let your AI swarm triage alerts, match historical incident runbooks, and generate remediation commands in real time.
            </p>
            <button type="button" onClick={() => setNotice(true)}>
              Open agent controls
            </button>
          </div>
        </aside>

        <main className="main">
          <header className="topbar">
            <div className="crumb">
              SeedheOps{' '}
              <ChevronRight size={12} style={{ verticalAlign: 'middle' }} /> Autonomous DevOps Incident Response
            </div>
            <div className="top-actions">
              <ThemeToggle />
              <button
                type="button"
                className="icon-button"
                onClick={() => setNotice(true)}
                aria-label="Notifications"
              >
                <Bell size={17} />
              </button>
              <div className="profile">
                <div className="avatar">OC</div>
                <span>On-Call SRE</span>
              </div>
            </div>
          </header>

          {notice && (
            <div className="notice">
              Agent controls are live. Your DevOps swarm is triaging cluster telemetry and sequencing hotfix commands.
            </div>
          )}

          {children}

          <footer className="team-footer">
            © 2026 SeedheOps<span>·</span> Autonomous DevOps Incident Response Swarm
          </footer>
        </main>
      </div>
    </div>
  )
}
