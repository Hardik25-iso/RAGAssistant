import { useState } from "react";
import { Link, Navigate, useNavigate } from "react-router-dom";
import { errorMessage } from "../api/client.js";
import { useAuth } from "../context/AuthContext.jsx";
import { AuthLayout } from "./Login.jsx";

export default function Register() {
  const { user, register } = useAuth();
  const navigate = useNavigate();
  const [form, setForm] = useState({ name: "", email: "", password: "" });
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  if (user) return <Navigate to="/" replace />;

  const weak = form.password && (form.password.length < 8 || !/\d/.test(form.password) || !/[a-z]/i.test(form.password));

  const submit = async (e) => {
    e.preventDefault();
    if (weak) return;
    setBusy(true);
    setError("");
    try {
      await register(form.name, form.email, form.password);
      navigate("/dashboard");
    } catch (err) {
      setError(errorMessage(err, "Registration failed"));
    } finally {
      setBusy(false);
    }
  };

  const field = (key, label, type, auto) => (
    <div>
      <label className="label" htmlFor={key}>{label}</label>
      <input id={key} type={type} className="input" autoComplete={auto} required
        value={form[key]} onChange={(e) => setForm({ ...form, [key]: e.target.value })} />
    </div>
  );

  return (
    <AuthLayout title="Create your account" subtitle="Your files and chats stay private to you.">
      <form onSubmit={submit} className="space-y-4">
        {field("name", "Name", "text", "name")}
        {field("email", "Email", "email", "email")}
        {field("password", "Password", "password", "new-password")}
        <p className={`text-xs ${weak ? "text-bad" : "text-ink-faint"}`}>At least 8 characters, with letters and numbers.</p>
        {error && <p className="rounded-md bg-bad-soft px-3 py-2 text-sm text-bad">{error}</p>}
        <button className="btn-primary w-full" disabled={busy}>{busy ? "Creating…" : "Create account"}</button>
      </form>
      <p className="mt-6 text-sm text-ink-soft">
        Already have an account? <Link to="/login" className="font-medium text-accent hover:underline">Log in</Link>
      </p>
    </AuthLayout>
  );
}
