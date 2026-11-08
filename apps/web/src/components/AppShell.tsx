import {
  useRef,
  useState,
  type ReactNode,
} from "react";

import {
  NavLink,
  useLocation,
} from "react-router-dom";

import {
  ArrowUpRight,
  BookOpenText,
  FlaskConical,
  LayoutDashboard,
  LogOut,
  Menu,
  ShieldAlert,
  X,
} from "lucide-react";

import { Brand } from "./Brand";

const links = [
  { label: "Workloads", path: "/workloads", icon: LayoutDashboard, end: false },
  { label: "Deployments", path: "/deployments", icon: ArrowUpRight, end: false },
  { label: "Capacity", path: "/capacity", icon: LayoutDashboard, end: false },
  { label: "Runbooks", path: "/runbooks", icon: BookOpenText, end: false },
  {
    label: "Overview",
    path: "/",
    icon: LayoutDashboard,
    end: true,
  },
  {
    label: "Incidents",
    path: "/incidents",
    icon: ShieldAlert,
    end: false,
  },
  {
    label: "Experiments",
    path: "/experiments",
    icon: FlaskConical,
    end: false,
  },
  {
    label: "Evidence",
    path: "/reports",
    icon: BookOpenText,
    end: false,
  },
];

function NavItems({
  onNavigate,
}: {
  onNavigate?: () => void;
}) {
  return (
    <nav className="primary-nav" aria-label="Main navigation">
      <p className="nav-kicker">WORKSPACE</p>

      {links.map(({ label, path, icon: Icon, end }) => (
        <NavLink
          key={path}
          to={path}
          end={end}
          onClick={onNavigate}
          className={({ isActive }) =>
            `nav-link${isActive ? " nav-link--active" : ""}`
          }
        >
          <Icon size={18} aria-hidden="true" />
          <span>{label}</span>
        </NavLink>
      ))}
    </nav>
  );
}

export function AppShell({
  children,
  onSignOut,
}: {
  children: ReactNode;
  onSignOut: () => Promise<void>;
}) {
  const drawer = useRef<HTMLDialogElement>(null);
  const trigger = useRef<HTMLButtonElement>(null);

  const [signingOut, setSigningOut] = useState(false);
  const [signOutError, setSignOutError] = useState("");

  const location = useLocation();

  const section =
    location.pathname === "/"
      ? "Overview"
      : location.pathname.startsWith("/experiments")
        ? "Experiments"
        : location.pathname.startsWith("/reports")
          ? "Evidence"
          : "Workspace";

  function closeDrawer() {
    drawer.current?.close();
  }

  async function handleSignOut() {
    setSigningOut(true);
    setSignOutError("");

    try {
      await onSignOut();
    } catch {
      setSignOutError(
        "Sign out failed. Check your connection and try again.",
      );
    } finally {
      setSigningOut(false);
    }
  }

  return (
    <div className="app-shell">
      <a className="skip-link" href="#main-content">
        Skip to content
      </a>

      {/* Persistent desktop navigation */}
      <aside
        className="sidebar"
        aria-label="Workspace sidebar"
      >
        <div className="sidebar__brand">
          <Brand />
        </div>

        <NavItems />

        <div className="sidebar__lower">
          <div className="sidebar-context">
            <span className="nav-kicker">TARGET</span>
            <strong>Local sandbox</strong>
            <span>
              Only configured integrations are shown as available.
            </span>
          </div>

          <a
            href="https://github.com/Aoun62336"
            target="_blank"
            rel="noreferrer"
            className="sidebar-link"
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
            className="sidebar-signout"
            onClick={handleSignOut}
            disabled={signingOut}
            type="button"
          >
            <LogOut size={16} aria-hidden="true" />
            {signingOut ? "Signing out…" : "Sign out"}
          </button>
        </div>
      </aside>

      {/* Native accessible modal navigation on mobile */}
      <dialog
        ref={drawer}
        className="mobile-drawer"
        aria-label="Workspace navigation"
        onClose={() => trigger.current?.focus()}
        onClick={(event) => {
          if (event.target === drawer.current) {
            closeDrawer();
          }
        }}
      >
        <div className="mobile-drawer__content">
          <div className="mobile-drawer__head">
            <Brand />

            <button
              type="button"
              className="icon-button"
              aria-label="Close navigation"
              onClick={closeDrawer}
              autoFocus
            >
              <X size={20} />
            </button>
          </div>

          <NavItems onNavigate={closeDrawer} />

          <div className="mobile-drawer__bottom">
            <span>Local sandbox · Development</span>

            <button
              type="button"
              className="sidebar-signout"
              disabled={signingOut}
              onClick={() => {
                closeDrawer();
                void handleSignOut();
              }}
            >
              <LogOut size={16} aria-hidden="true" />
              Sign out
            </button>
          </div>
        </div>
      </dialog>

      {/* Main application */}
      <div className="workspace">
        <header className="topbar">
          <div className="topbar__left">
            <button
              ref={trigger}
              type="button"
              className="icon-button mobile-menu"
              aria-label="Open navigation"
              onClick={() => drawer.current?.showModal()}
            >
              <Menu size={21} />
            </button>

            <div className="topbar__mobile-brand">
              <Brand compact />
            </div>

            <div className="topbar__breadcrumbs">
              <span>WORKSPACE</span>
              <span aria-hidden="true">/</span>
              <strong>{section}</strong>
            </div>
          </div>

          <div className="topbar__right">
            <span className="topbar__environment">
              <span
                className="environment-square"
                aria-hidden="true"
              />
              Local sandbox
            </span>

            <span className="topbar__session">
              Operator session
            </span>
          </div>
        </header>

        <main className="main-content" id="main-content">
          {children}
        </main>

        <footer className="workspace-footer">
          <span>
            OpsProof · Cloud Reliability & Safe Operations
          </span>
          <span>Local development environment</span>
        </footer>
      </div>
    </div>
  );
}
