import React, { useState } from 'react';
import { Link, useLocation, useNavigate } from 'react-router-dom';
import { Eye, EyeOff, Lock, Mail } from 'lucide-react';
import { useAuth } from '../context/AuthContext';

const Login: React.FC = () => {
  const { login } = useAuth();
  const navigate = useNavigate();
  const location = useLocation();

  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [showPassword, setShowPassword] = useState(false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');

  const onSubmit = async (event: React.FormEvent) => {
    event.preventDefault();
    setLoading(true);
    setError('');

    try {
      await login({ email, password });
      const from = (location.state as { from?: { pathname?: string } })?.from?.pathname || '/';
      navigate(from, { replace: true });
    } catch {
      setError('Login failed. Verify email/password and backend availability.');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="mx-auto max-w-md">
      <div className="surface p-7 sm:p-8">
        <p className="text-xs font-semibold uppercase tracking-[0.16em] text-slate-500">Authentication</p>
        <h1 className="mt-2 text-3xl text-slate-900">Welcome back</h1>
        <p className="mt-2 text-sm text-slate-600">Sign in using the JWT endpoint at /api/token/.</p>

        <form onSubmit={onSubmit} className="mt-6 space-y-4">
          <label className="relative block">
            <Mail className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-400" size={16} />
            <input
              type="email"
              value={email}
              onChange={(event) => setEmail(event.target.value)}
              placeholder="email"
              required
              className="w-full rounded-xl border border-cyan-200 bg-white py-2.5 pl-9 pr-3 text-sm outline-none ring-cyan-200 focus:ring"
            />
          </label>

          <label className="relative block">
            <Lock className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-400" size={16} />
            <input
              type={showPassword ? 'text' : 'password'}
              value={password}
              onChange={(event) => setPassword(event.target.value)}
              placeholder="password"
              required
              className="w-full rounded-xl border border-cyan-200 bg-white py-2.5 pl-9 pr-9 text-sm outline-none ring-cyan-200 focus:ring"
            />
            <button
              type="button"
              onClick={() => setShowPassword((prev) => !prev)}
              className="absolute right-3 top-1/2 -translate-y-1/2 text-slate-500"
            >
              {showPassword ? <EyeOff size={16} /> : <Eye size={16} />}
            </button>
          </label>

          {error && <p className="text-sm font-semibold text-red-600">{error}</p>}

          <button
            type="submit"
            disabled={loading}
            className="w-full rounded-xl bg-slate-900 px-4 py-2.5 text-sm font-semibold text-white hover:bg-slate-700 disabled:opacity-50"
          >
            {loading ? 'Signing in...' : 'Sign in'}
          </button>
        </form>

        <p className="mt-4 text-sm text-slate-600">
          No account yet?{' '}
          <Link to="/register" className="font-semibold text-sky-700 hover:text-sky-800">
            Create one
          </Link>
        </p>
      </div>
    </div>
  );
};

export default Login;
