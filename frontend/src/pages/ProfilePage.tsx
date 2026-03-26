import { useState, FormEvent } from 'react';
import { useNavigate } from 'react-router-dom';
import { useQuery } from '@tanstack/react-query';
import client from '../api/client';
import { useAuth } from '../contexts/AuthContext';
import { useToast } from '../components/Toast';

interface Profile {
  id: number;
  email: string;
  is_staff: boolean;
  date_joined: string;
  last_login: string | null;
}

export default function ProfilePage() {
  const toast = useToast();
  const { logout } = useAuth();
  const navigate = useNavigate();

  const { data: profile, isLoading } = useQuery({
    queryKey: ['profile'],
    queryFn: () => client.get<Profile>('/auth/profile/').then((r) => r.data),
  });

  // Change password
  const [showPwForm, setShowPwForm] = useState(false);
  const [currentPw, setCurrentPw] = useState('');
  const [newPw, setNewPw] = useState('');
  const [confirmPw, setConfirmPw] = useState('');
  const [pwError, setPwError] = useState('');
  const [pwSuccess, setPwSuccess] = useState('');
  const [pwLoading, setPwLoading] = useState(false);

  async function handleChangePassword(e: FormEvent) {
    e.preventDefault();
    setPwError('');
    setPwSuccess('');
    if (newPw !== confirmPw) {
      setPwError('New passwords do not match.');
      return;
    }
    setPwLoading(true);
    try {
      const { data } = await client.post('/auth/change-password/', {
        current_password: currentPw,
        new_password: newPw,
      });
      setPwSuccess(data.detail);
      setCurrentPw('');
      setNewPw('');
      setConfirmPw('');
      setShowPwForm(false);
    } catch (err: any) {
      setPwError(err?.response?.data?.detail ?? 'Failed to change password.');
    } finally {
      setPwLoading(false);
    }
  }

  // Delete account
  async function handleDeleteAccount() {
    if (!confirm('Are you sure you want to permanently delete your account? All your books and data will be lost.')) return;
    if (!confirm('This cannot be undone. Delete your account?')) return;
    try {
      await client.delete('/auth/profile/');
      logout();
      navigate('/');
    } catch {
      toast('Failed to delete account.', 'error');
    }
  }

  if (isLoading || !profile) {
    return (
      <div className="max-w-2xl mx-auto px-6 py-8">
        <p className="text-gray-500">Loading…</p>
      </div>
    );
  }

  return (
    <div className="max-w-2xl mx-auto px-6 py-8">
      <h1 className="text-2xl font-bold text-gray-900 mb-6">Profile</h1>

      {/* Account info */}
      <div className="bg-white border border-gray-200 rounded-lg p-6 mb-6">
        <h2 className="text-sm font-semibold text-gray-500 uppercase tracking-wide mb-3">Account</h2>
        <dl className="text-sm space-y-3">
          <div className="flex justify-between">
            <dt className="text-gray-500">Email</dt>
            <dd className="text-gray-900">{profile.email}</dd>
          </div>
          <div className="flex justify-between">
            <dt className="text-gray-500">Member since</dt>
            <dd className="text-gray-900">{new Date(profile.date_joined).toLocaleDateString()}</dd>
          </div>
          {profile.last_login && (
            <div className="flex justify-between">
              <dt className="text-gray-500">Last login</dt>
              <dd className="text-gray-900">{new Date(profile.last_login).toLocaleString()}</dd>
            </div>
          )}
          {profile.is_staff && (
            <div className="flex justify-between">
              <dt className="text-gray-500">Role</dt>
              <dd><span className="text-xs bg-blue-100 text-blue-800 px-2 py-0.5 rounded-full">Staff</span></dd>
            </div>
          )}
        </dl>
      </div>

      {/* Change password */}
      <div className="bg-white border border-gray-200 rounded-lg p-6 mb-6">
        <div className="flex items-center justify-between mb-3">
          <h2 className="text-sm font-semibold text-gray-500 uppercase tracking-wide">Password</h2>
          {!showPwForm && (
            <button
              onClick={() => setShowPwForm(true)}
              className="text-sm text-blue-600 hover:underline"
            >
              Change password
            </button>
          )}
        </div>

        {pwSuccess && <p className="text-sm text-green-600 mb-3">{pwSuccess}</p>}

        {showPwForm && (
          <form onSubmit={handleChangePassword} className="space-y-3">
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">Current password</label>
              <input
                type="password"
                value={currentPw}
                onChange={(e) => setCurrentPw(e.target.value)}
                required
                className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
              />
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">New password</label>
              <input
                type="password"
                value={newPw}
                onChange={(e) => setNewPw(e.target.value)}
                required
                minLength={8}
                className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
              />
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">Confirm new password</label>
              <input
                type="password"
                value={confirmPw}
                onChange={(e) => setConfirmPw(e.target.value)}
                required
                minLength={8}
                className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
              />
            </div>
            {pwError && <p className="text-sm text-red-600">{pwError}</p>}
            <div className="flex gap-3">
              <button
                type="submit"
                disabled={pwLoading}
                className="bg-blue-600 text-white text-sm px-5 py-2 rounded-lg hover:bg-blue-700 disabled:opacity-50"
              >
                {pwLoading ? 'Saving…' : 'Update password'}
              </button>
              <button
                type="button"
                onClick={() => { setShowPwForm(false); setPwError(''); }}
                className="text-sm text-gray-500"
              >
                Cancel
              </button>
            </div>
          </form>
        )}
      </div>

      {/* Danger zone */}
      <div className="bg-white border border-red-200 rounded-lg p-6">
        <h2 className="text-sm font-semibold text-red-600 uppercase tracking-wide mb-2">Danger zone</h2>
        <p className="text-sm text-gray-500 mb-3">
          Permanently delete your account and all associated data (books, builds).
        </p>
        <button
          onClick={handleDeleteAccount}
          className="text-sm bg-red-50 text-red-700 px-4 py-2 rounded-lg hover:bg-red-100 font-medium"
        >
          Delete my account
        </button>
      </div>
    </div>
  );
}