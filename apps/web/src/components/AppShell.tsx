import { useState, type ReactNode } from "react";
import { NavLink } from "react-router-dom";
import {
  Activity,
  ArrowUpRight,
  BookOpenText,
  FlaskConical,
  LayoutDashboard,
  LogOut,
  Menu,
  X,
} from "lucide-react";

import { Brand } from "./Brand";

const navigation = [
  {
    label: "Overview",
    path: "/",
    icon: LayoutDashboard,
    end: true,
  },
  {
    label: "Experiments",
    path: "/experiments",
    icon: FlaskConical,
    end: false,
  },
  {
    label: "Evidence reports",
    path: "/reports",
    icon: BookOpenText,
    end: false,
  },
];

interface Props {
  children: ReactNode;
  onSignOut: () => Promise<void>;
}

export function AppShell({
  children,
  onSignOut,
}: Props) {
  const [menuOpen, setMenuOpen] = useState(false);
  const [signingOut, setSigningOut] = useState(false);
  const [signOutError, setSignOutError] = useState("");

  async function handleSignOut() {
    setSigningOut(true);
    setSignOutError("");

    try {
      await onSignOut();
    } catch {
      setSignOutError("Could not end the session. Try again.");
    } finally {
      setSigningOut(false);
    }
  }

  return (
    <div className="app-layout">
      <a className="skip-link" href="#main-content">
        Skip to content
      </a>

      {menuOpen && (
        <button
          className="sidebar-backdrop"
          type="button"
          aria-label="Close navigation"
          onClick={() => setMenuOpen(false)}
        />
      )}

      <aside
        className={`sidebar ${menuOpen ? "sidebar--open" : ""}`}
        aria-label="Application sidebar"
      >
        <div className="sidebar__top">
          <Brand />

          <button
            className="icon-button sidebar__close"
            type="button"
            aria-label="Close navigation"
            onClick={() => setMenuOpen(false)}
          >
            <X size={18} />
          </button>
        </div>

        <nav className="primary-nav" aria-label="Main navigation">
          <span className="nav-label">WORKSPACE</span>

          {navigation.map((item) => {
            const Icon = item.icon;

            return (
              <NavLink
                key={item.path}
                to={item.path}
                end={item.end}
                onClick={() => setMenuOpen(false)}
                className={({ isActive }) =>
                  `nav-link ${isActive ? "nav-link--active" : ""}`
                }
              >
                <Icon size={18} aria-hidden="true" />
                <span>{item.label}</span>
              </NavLink>
            );
          })}
        </nav>

        <div className="sidebar__section">
          <span className="nav-label">PLATFORM INTEGRATIONS</span>

          <div className="integration-note">
            <Activity size={17} aria-hidden="true" />
            <div>
              <strong>Incident intelligence</strong>
              <p>
                Telemetry and Kubernetes integrations will appear
                when connected.
              </p>
            </div>
          </div>
        </div>

        <div className="sidebar__bottom">
          <a
            className="docs-link"
            href="https://github.com/Aoun62336"
            target="_blank"
            rel="noopener noreferrer"
          >
            GitHub profile
            <ArrowUpRight size={15} aria-hidden="true" />
          </a>

          {signOutError && (
            <p className="inline-error" role="alert">
              {signOutError}
            </p>
          )}

          <button
            className="signout-button"
            type="button"
            onClick={handleSignOut}
            disabled={signingOut}
          >
            <LogOut size={17} aria-hidden="true" />
            {signingOut ? "Signing out..." : "Sign out"}
          </button>
        </div>
      </aside>

      <div className="workspace">
        <header className="topbar">
          <button
            className="icon-button mobile-menu"
            type="button"
            aria-label="Open navigation"
            onClick={() => setMenuOpen(true)}
          >
            <Menu size={20} />
          </button>

          <div className="topbar__context">
            <span className="context-label">ENVIRONMENT</span>
            <span className="context-value">Local control plane</span>
          </div>

          <div className="topbar__right">
            <span className="connection-indicator">
              <span className="connection-indicator__dot" />
              Authenticated session
            </span>

            <span className="topbar__version">
              v0.2 development
            </span>
          </div>
        </header>

        <main id="main-content" className="main-content">
          {children}
        </main>

        <footer className="workspace-footer">
          <span>OpsProof · Evidence before assumption</span>
          <span>Local development environment</span>
        </footer>
      </div>
    </div>
  );
}
