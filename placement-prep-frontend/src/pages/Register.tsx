import React, { useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { usersApi } from '../services/api';
import { useAuth } from '../context/AuthContext';

const Register: React.FC = () => {
  const navigate = useNavigate();
  const { login } = useAuth();

  const [form, setForm] = useState({
    first_name: '',
    last_name: '',
    username: '',
    email: '',
    password: '',
    confirmPassword: '',
  });
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');

  const onChange = (key: keyof typeof form, value: string) => setForm((prev) => ({ ...prev, [key]: value }));

  const onSubmit = async (event: React.FormEvent) => {
    event.preventDefault();
    setError('');

    if (form.password !== form.confirmPassword) {
      setError('Passwords do not match.');
      return;
    }

    setLoading(true);
    try {
      await usersApi.create({
        first_name: form.first_name,
        last_name: form.last_name,
        username: form.username,
        email: form.email,
        password: form.password,
      });

      await login({ email: form.email, password: form.password });
      navigate('/', { replace: true });
    } catch {
      setError('Registration failed. Verify password length and unique email/username.');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="mx-auto max-w-lg">
      <div className="surface p-7 sm:p-8">
        <p className="text-xs font-semibold uppercase tracking-[0.16em] text-slate-500">New account</p>
        <h1 className="mt-2 text-3xl text-slate-900">Join PlacementReady</h1>
        <p className="mt-2 text-sm text-slate-600">Creates /api/users/ then signs in with /api/token/.</p>

        <form className="mt-6 space-y-4" onSubmit={onSubmit}>
          <div className="grid gap-3 sm:grid-cols-2">
            <input
              value={form.first_name}
              onChange={(event) => onChange('first_name', event.target.value)}
              placeholder="First name"
              required
              className="rounded-xl border border-amber-200 bg-white px-3 py-2.5 text-sm"
            />
            <input
              value={form.last_name}
              onChange={(event) => onChange('last_name', event.target.value)}
              placeholder="Last name"
              required
              className="rounded-xl border border-amber-200 bg-white px-3 py-2.5 text-sm"
            />
          </div>

          <input
            value={form.username}
            onChange={(event) => onChange('username', event.target.value)}
            placeholder="Username"
            required
            className="w-full rounded-xl border border-amber-200 bg-white px-3 py-2.5 text-sm"
          />

          <input
            type="email"
            value={form.email}
            onChange={(event) => onChange('email', event.target.value)}
            placeholder="Email"
            required
            className="w-full rounded-xl border border-amber-200 bg-white px-3 py-2.5 text-sm"
          />

          <input
            type="password"
            value={form.password}
            onChange={(event) => onChange('password', event.target.value)}
            placeholder="Password"
            required
            className="w-full rounded-xl border border-amber-200 bg-white px-3 py-2.5 text-sm"
          />

          <input
            type="password"
            value={form.confirmPassword}
            onChange={(event) => onChange('confirmPassword', event.target.value)}
            placeholder="Confirm password"
            required
            className="w-full rounded-xl border border-amber-200 bg-white px-3 py-2.5 text-sm"
          />

          {error && <p className="text-sm font-semibold text-red-600">{error}</p>}

          <button
            type="submit"
            disabled={loading}
            className="w-full rounded-xl bg-slate-900 px-4 py-2.5 text-sm font-semibold text-white hover:bg-slate-700 disabled:opacity-50"
          >
            {loading ? 'Creating account...' : 'Create account'}
          </button>
        </form>

        <p className="mt-4 text-sm text-slate-600">
          Already registered?{' '}
          <Link to="/login" className="font-semibold text-sky-700 hover:text-sky-800">
            Sign in
          </Link>
        </p>
      </div>
    </div>
  );
};

export default Register;
