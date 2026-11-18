import { NavLink } from "react-router-dom";
import type { ReactNode } from "react";
import { AdminIcon, HomeIcon, PanelIcon, SlidersIcon } from "./Icons";

interface NavItem {
  to: string;
  label: string;
  icon: ReactNode;
}

// Add new pages here: they appear in the sidebar automatically.
const MAIN_NAV: NavItem[] = [{ to: "/", label: "Home", icon: <HomeIcon /> }];

const BOTTOM_NAV: NavItem[] = [
  { to: "/settings", label: "Settings", icon: <SlidersIcon /> },
  { to: "/admin", label: "Admin", icon: <AdminIcon /> },
];

function Item({ item, collapsed }: { item: NavItem; collapsed: boolean }) {
  return (
    <NavLink
      to={item.to}
      end={item.to === "/"}
      className={({ isActive }) => `nav-link${isActive ? " active" : ""}`}
      title={collapsed ? item.label : undefined}
    >
      {item.icon}
      <span className="nav-label">{item.label}</span>
    </NavLink>
  );
}

export default function Sidebar({ collapsed, onToggle }: { collapsed: boolean; onToggle: () => void }) {
  return (
    <aside className={`sidebar${collapsed ? " collapsed" : ""}`}>
      <div className="sidebar-head">
        <div className="brand">
          <div className="brand-mark">R</div>
          <span className="brand-name">Research</span>
        </div>
        <button className="icon-btn" onClick={onToggle} aria-label="Toggle sidebar" title="Toggle sidebar">
          <PanelIcon />
        </button>
      </div>

      <div className="nav-group-title">Workspace</div>
      {MAIN_NAV.map((i) => (
        <Item key={i.to} item={i} collapsed={collapsed} />
      ))}

      <div className="sidebar-spacer" />

      <div className="nav-group-title">Configure</div>
      {BOTTOM_NAV.map((i) => (
        <Item key={i.to} item={i} collapsed={collapsed} />
      ))}
    </aside>
  );
}
