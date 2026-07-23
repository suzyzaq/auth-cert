import type { PropsWithChildren } from "react";
import { NavLink } from "react-router-dom";

export function AppShell({ children }: PropsWithChildren) {
  return (
    <div className="app-shell">
      <header className="topbar">
        <NavLink className="brand-lockup" to="/">
          <span className="brand-mark" aria-hidden="true" />
          <span>
            <b>授权资质巡检</b>
            <small>AUTH & QUALIFICATION CONTROL</small>
          </span>
        </NavLink>
        <nav aria-label="主导航">
          <NavLink to="/">任务中心</NavLink>
          <NavLink to="/dashboard">管理总览</NavLink>
          <NavLink to="/rules">规则中心</NavLink>
          <a
            className="external-nav"
            href="https://suzyzaq.github.io/auth-cert-db/"
            target="_blank"
            rel="noopener noreferrer"
          >
            授权资质数据库
          </a>
        </nav>
        <div className="user-chip">
          <span>管</span>
          管理员
        </div>
      </header>
      <main>{children}</main>
    </div>
  );
}
