import { useState } from "react";
import { Link, Navigate, useNavigate } from "react-router-dom";
import { errorMessage } from "../api/client.js";
import { Logo } from "../components/Navbar.jsx";
import { useAuth } from "../context/AuthContext.jsx";

export function AuthLayout({ title, subtitle, children }) {
  return (
    <div className="grid min-h-screen lg:grid-cols-2">
      <aside className="hidden flex-col justify-between bg-accent-strong p-10 text-white lg:flex">
        <span className="[&_span]:text-white">
          <Logo />
        </span>
        <div>
          <p className="font-serif text-4xl font-semibold leading-tight">
            Revise from your own slides.
            <br />
            Every answer, cited.
          </p>
          <ul className="mt-6 space-y-2 text-sm text-white/80">
            <li>· Upload lecture PPTX and PDFs, organised by subject</li>
            <li>· Ask questions, get answers with the exact slide or page</li>
            <li>· Your files are private to you, encrypted on AWS</li>
          </ul>
        </div>
        <div aria-hidden="true" />
      </aside>
      <main className="flex items-center justify-center p-6">
        <div className="w-full max-w-sm">
          <div className="mb-8 lg:hidden">
            <Logo />
          </div>
          <h1 className="font-serif text-3xl font-semibold tracking-tight">{title}</h1>
          <p className="mt-1 text-sm text-ink-soft">{subtitle}</p>
          <div className="mt-6">{children}</div>
        </div>
      </main>
    </div>
  );
}

export default function Login() {
  const { user, login } = useAuth();
  const navigate = useNavigate();
  const [form, setForm] = useState({ email: "", password: "" });
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  if (user) return <Navigate to="/" replace />;

  const submit = async (e) => {
    e.preventDefault();
    setBusy(true);
    setError("");
    try {
      const u = await login(form.email, form.password);
      navigate(u.role === "admin" ? "/admin" : "/dashboard");
    } catch (err) {
      setError(errorMessage(err, "Login failed"));
    } finally {
      setBusy(false);
    }
  };

  return (
    <AuthLayout title="Welcome back" subtitle="Log in to your study space.">
      <form onSubmit={submit} className="space-y-4">
        <div>
          <label className="label" htmlFor="email">Email</label>
          <input id="email" type="email" className="input" autoComplete="email" required
            value={form.email} onChange={(e) => setForm({ ...form, email: e.target.value })} />
        </div>
        <div>
          <label className="label" htmlFor="password">Password</label>
          <input id="password" type="password" className="input" autoComplete="current-password" required
            value={form.password} onChange={(e) => setForm({ ...form, password: e.target.value })} />
        </div>
        {error && <p className="rounded-md bg-bad-soft px-3 py-2 text-sm text-bad">{error}</p>}
        <button className="btn-primary w-full" disabled={busy}>{busy ? "Logging in…" : "Log in"}</button>
      </form>
      <p className="mt-6 text-sm text-ink-soft">
        New here? <Link to="/register" className="font-medium text-accent hover:underline">Create an account</Link>
      </p>
    </AuthLayout>
  );
}
