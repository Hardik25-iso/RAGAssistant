import { Link } from "react-router-dom";
import { useAuth } from "../context/AuthContext.jsx";

export function Logo() {
  return (
    <span className="flex items-center gap-2">
      <svg width="22" height="22" viewBox="0 0 32 32" aria-hidden="true">
        <rect width="32" height="32" rx="7" fill="#1f5c4a" />
        <path d="M9 10h9a5 5 0 0 1 0 10h-4l5 4" stroke="white" strokeWidth="2.4" fill="none" strokeLinecap="round" />
      </svg>
      <span className="font-serif text-[17px] font-semibold tracking-tight">StudyRAG</span>
    </span>
  );
}

export default function Navbar() {
  const { user, logout } = useAuth();
  return (
    <header className="sticky top-0 z-20 border-b border-line bg-paper/90 backdrop-blur">
      <div className="mx-auto flex h-14 max-w-6xl items-center justify-between px-4">
        <Link to="/">
          <Logo />
        </Link>
        <div className="flex items-center gap-3 text-sm">
          <span className="hidden text-ink-soft sm:inline">{user.name}</span>
          {user.role === "admin" && <span className="chip bg-warn-soft text-warn">admin</span>}
          <button className="btn-ghost" onClick={logout}>
            Log out
          </button>
        </div>
      </div>
    </header>
  );
}
