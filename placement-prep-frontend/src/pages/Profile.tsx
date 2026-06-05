import React, { useEffect, useState } from 'react';
import { useAuth } from '../context/AuthContext';
import { usersApi } from '../services/api';
import LoadingSpinner from '../components/common/LoadingSpinner';

const Profile: React.FC = () => {
  const { user, updateUser } = useAuth();
  const [form, setForm] = useState({
    first_name: '',
    last_name: '',
    username: '',
    email: '',
  });
  const [saving, setSaving] = useState(false);
  const [message, setMessage] = useState('');

  useEffect(() => {
    if (!user) return;
    setForm({
      first_name: user.first_name || '',
      last_name: user.last_name || '',
      username: user.username || '',
      email: user.email || '',
    });
  }, [user]);

  const onSave = async () => {
    if (!user) return;
    setSaving(true);
    setMessage('');

    try {
      const nextUser = await usersApi.patch(user.id, form);
      updateUser(nextUser);
      setMessage('Profile updated.');
    } catch {
      setMessage('Update failed.');
    } finally {
      setSaving(false);
    }
  };

  if (!user) {
    return <LoadingSpinner label="Loading profile" />;
  }

  return (
    <div className="mx-auto max-w-3xl space-y-6">
      <section className="surface p-6 sm:p-8">
        <h1 className="text-3xl text-slate-900">Your Profile</h1>
        <p className="mt-2 text-sm text-slate-600">Editable fields via /api/users/&lt;id&gt;/</p>

        <div className="mt-6 grid gap-4 sm:grid-cols-2">
          <label className="grid gap-1 text-sm">
            <span className="font-semibold text-slate-600">First name</span>
            <input
              value={form.first_name}
              onChange={(event) => setForm((prev) => ({ ...prev, first_name: event.target.value }))}
              className="rounded-xl border border-amber-200 bg-white px-3 py-2.5"
            />
          </label>
          <label className="grid gap-1 text-sm">
            <span className="font-semibold text-slate-600">Last name</span>
            <input
              value={form.last_name}
              onChange={(event) => setForm((prev) => ({ ...prev, last_name: event.target.value }))}
              className="rounded-xl border border-amber-200 bg-white px-3 py-2.5"
            />
          </label>
          <label className="grid gap-1 text-sm">
            <span className="font-semibold text-slate-600">Username</span>
            <input
              value={form.username}
              onChange={(event) => setForm((prev) => ({ ...prev, username: event.target.value }))}
              className="rounded-xl border border-amber-200 bg-white px-3 py-2.5"
            />
          </label>
          <label className="grid gap-1 text-sm">
            <span className="font-semibold text-slate-600">Email</span>
            <input
              value={form.email}
              onChange={(event) => setForm((prev) => ({ ...prev, email: event.target.value }))}
              className="rounded-xl border border-amber-200 bg-white px-3 py-2.5"
            />
          </label>
        </div>

        <button
          type="button"
          onClick={onSave}
          disabled={saving}
          className="mt-5 rounded-xl bg-slate-900 px-5 py-2.5 text-sm font-semibold text-white disabled:opacity-50"
        >
          {saving ? 'Saving...' : 'Save profile'}
        </button>

        {message && <p className="mt-3 text-sm font-semibold text-orange-700">{message}</p>}
      </section>

      {user.profile && (
        <section className="surface p-6">
          <h2 className="text-xl text-slate-900">Profile extension</h2>
          <p className="mt-2 text-sm text-slate-600">Bio: {user.profile.bio || 'Not set'}</p>
          <p className="mt-1 text-sm text-slate-600">Target role: {user.profile.target_role || 'Not set'}</p>
          <p className="mt-1 text-sm text-slate-600">Batch year: {user.profile.batch_year || 'Not set'}</p>
        </section>
      )}
    </div>
  );
};

export default Profile;
