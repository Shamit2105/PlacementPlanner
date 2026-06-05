import React, { useState } from 'react';
import { Link, NavLink, useNavigate } from 'react-router-dom';
import { Menu, X, Sparkles, LogOut, UserRound } from 'lucide-react';
import { motion, AnimatePresence } from 'framer-motion';
import { useAuth } from '../../context/AuthContext';

const navItems = [
  { to: '/', label: 'Home' },
  { to: '/companies', label: 'Companies' },
  { to: '/experiences', label: 'Question Bank' },
  { to: '/interviews', label: 'Interviews' },
  { to: '/ops', label: 'Ops Lab' },
];

const linkClass = ({ isActive }: { isActive: boolean }) =>
  `rounded-xl px-3 py-2 text-sm font-semibold ${
    isActive
      ? 'bg-amber-100 text-amber-800 shadow-sm shadow-amber-200/60'
      : 'text-slate-700 hover:bg-white/70 hover:text-slate-900'
  }`;

const Navbar: React.FC = () => {
  const [open, setOpen] = useState(false);
  const navigate = useNavigate();
  const { isAuthenticated, user, logout } = useAuth();

  const handleLogout = () => {
    logout();
    navigate('/');
    setOpen(false);
  };

  return (
    <header className="sticky top-0 z-40 border-b border-amber-100/70 bg-[#fff8ef]/90 backdrop-blur">
      <div className="mx-auto flex h-16 w-full max-w-7xl items-center justify-between px-4 sm:px-6">
        <Link to="/" className="flex items-center gap-2">
          <span className="flex h-9 w-9 items-center justify-center rounded-xl bg-gradient-to-br from-orange-500 to-sky-500 text-white shadow-md shadow-orange-300/60">
            <Sparkles size={18} />
          </span>
          <div>
            <p className="font-display text-sm uppercase tracking-[0.18em] text-slate-500">PlacementReady</p>
            <p className="font-display text-base text-slate-900">Interview Studio</p>
          </div>
        </Link>

        <nav className="hidden items-center gap-1 md:flex">
          {navItems.map((item) => (
            <NavLink key={item.to} className={linkClass} to={item.to}>
              {item.label}
            </NavLink>
          ))}
        </nav>

        <div className="hidden items-center gap-2 md:flex">
          {isAuthenticated ? (
            <>
              <Link
                to="/profile"
                className="inline-flex items-center gap-2 rounded-xl border border-amber-200 bg-white px-3 py-2 text-sm font-semibold text-slate-700 hover:border-amber-300"
              >
                <UserRound size={16} />
                {user?.first_name || user?.email || 'Profile'}
              </Link>
              <button
                type="button"
                onClick={handleLogout}
                className="inline-flex items-center gap-2 rounded-xl bg-slate-900 px-3 py-2 text-sm font-semibold text-white hover:bg-slate-700"
              >
                <LogOut size={16} />
                Logout
              </button>
            </>
          ) : (
            <>
              <Link to="/login" className="rounded-xl px-3 py-2 text-sm font-semibold text-slate-700 hover:bg-white">
                Login
              </Link>
              <Link
                to="/register"
                className="rounded-xl bg-slate-900 px-3 py-2 text-sm font-semibold text-white hover:bg-slate-700"
              >
                Register
              </Link>
            </>
          )}
        </div>

        <button
          type="button"
          className="rounded-xl p-2 text-slate-700 hover:bg-white md:hidden"
          onClick={() => setOpen((prev) => !prev)}
          aria-label="Toggle menu"
        >
          {open ? <X size={22} /> : <Menu size={22} />}
        </button>
      </div>

      <AnimatePresence>
        {open && (
          <motion.div
            initial={{ opacity: 0, y: -10 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: -10 }}
            className="border-t border-amber-100 bg-[#fffaf4] px-4 py-4 md:hidden"
          >
            <nav className="grid gap-2">
              {navItems.map((item) => (
                <NavLink
                  key={item.to}
                  to={item.to}
                  className={linkClass}
                  onClick={() => setOpen(false)}
                >
                  {item.label}
                </NavLink>
              ))}
              {isAuthenticated ? (
                <>
                  <NavLink to="/profile" className={linkClass} onClick={() => setOpen(false)}>
                    Profile
                  </NavLink>
                  <button
                    type="button"
                    onClick={handleLogout}
                    className="rounded-xl bg-slate-900 px-3 py-2 text-left text-sm font-semibold text-white"
                  >
                    Logout
                  </button>
                </>
              ) : (
                <>
                  <NavLink to="/login" className={linkClass} onClick={() => setOpen(false)}>
                    Login
                  </NavLink>
                  <NavLink to="/register" className={linkClass} onClick={() => setOpen(false)}>
                    Register
                  </NavLink>
                </>
              )}
            </nav>
          </motion.div>
        )}
      </AnimatePresence>
    </header>
  );
};

export default Navbar;
