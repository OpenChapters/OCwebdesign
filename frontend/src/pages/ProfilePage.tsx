import { useState, FormEvent } from 'react';
import { Link } from 'react-router-dom';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import client from '../api/client';
import { examplesApi } from '../api/examples';
import { useToast } from '../components/Toast';
import type { ExampleListItem, ExampleStatus } from '../types';

interface Profile {
  id: number;
  email: string;
  full_name: string;
  is_staff: boolean;
  date_joined: string;
  last_login: string | null;
  share_builds: boolean;
  /** ISO 8601 — non-null when the account is on the deletion calendar. */
  deletion_scheduled_at: string | null;
}

export default function ProfilePage() {
  const toast = useToast();
  const queryClient = useQueryClient();

  const { data: profile, isLoading } = useQuery({
    queryKey: ['profile'],
    queryFn: () => client.get<Profile>('/auth/profile/').then((r) => r.data),
  });

  const { data: myExamplesPayload } = useQuery({
    queryKey: ['my-examples'],
    queryFn: () => examplesApi.mine(),
  });
  const myExamples = myExamplesPayload?.results ?? [];

  // Full name editing
  const [editingName, setEditingName] = useState(false);
  const [nameValue, setNameValue] = useState('');
  const [nameSaving, setNameSaving] = useState(false);

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

  // Schedule account deletion (7-day grace).
  async function handleDeleteAccount() {
    if (!confirm(
      'Schedule your account for deletion?\n\n'
      + 'Your account will be permanently removed in 7 days. Until then '
      + 'you can sign in and cancel the deletion at any time.'
    )) return;
    try {
      await client.delete('/auth/profile/');
      queryClient.invalidateQueries({ queryKey: ['profile'] });
      toast('Account scheduled for deletion in 7 days.', 'info');
    } catch {
      toast('Failed to schedule deletion.', 'error');
    }
  }

  async function handleCancelDeletion() {
    try {
      await client.post('/auth/profile/cancel-deletion/');
      queryClient.invalidateQueries({ queryKey: ['profile'] });
      toast('Deletion cancelled.', 'success');
    } catch {
      toast('Failed to cancel deletion.', 'error');
    }
  }


  if (isLoading || !profile) {
    return (
      <div className="max-w-2xl mx-auto px-4 sm:px-6 py-6 sm:py-8">
        <p className="text-gray-500 dark:text-gray-400">Loading…</p>
      </div>
    );
  }

  const deletionDate = profile.deletion_scheduled_at
    ? new Date(profile.deletion_scheduled_at)
    : null;

  return (
    <div className="max-w-2xl mx-auto px-4 sm:px-6 py-6 sm:py-8">
      <h1 className="text-2xl font-bold text-gray-900 dark:text-gray-50 mb-6">Profile</h1>

      {deletionDate && (
        <div
          role="alert"
          className="bg-amber-50 dark:bg-amber-950/40 border border-amber-200 dark:border-amber-900 rounded-lg p-4 mb-6 flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3"
        >
          <div>
            <p className="text-sm font-medium text-amber-900 dark:text-amber-100">
              Account scheduled for deletion
            </p>
            <p className="text-xs text-amber-800 dark:text-amber-200 mt-1">
              Your account and all its data will be removed on{' '}
              <strong>{deletionDate.toLocaleString()}</strong>. Cancel any
              time before then to keep it.
            </p>
          </div>
          <button
            onClick={handleCancelDeletion}
            className="text-sm bg-amber-600 text-white px-4 py-2 rounded-lg hover:bg-amber-700 shrink-0"
          >
            Cancel deletion
          </button>
        </div>
      )}

      {/* Account info */}
      <div className="bg-white dark:bg-gray-800 border border-gray-200 dark:border-gray-700 rounded-lg p-6 mb-6">
        <h2 className="text-sm font-semibold text-gray-500 dark:text-gray-400 uppercase tracking-wide mb-3">Account</h2>
        <dl className="text-sm space-y-3">
          <div className="flex justify-between items-center">
            <dt className="text-gray-500 dark:text-gray-400">Full Name</dt>
            <dd className="text-gray-900 dark:text-gray-50 flex items-center gap-2">
              {editingName ? (
                <form
                  onSubmit={async (e) => {
                    e.preventDefault();
                    setNameSaving(true);
                    try {
                      await client.patch('/auth/profile/', { full_name: nameValue });
                      queryClient.invalidateQueries({ queryKey: ['profile'] });
                      setEditingName(false);
                      toast('Name updated.', 'success');
                    } catch { toast('Failed to update name.', 'error'); }
                    finally { setNameSaving(false); }
                  }}
                  className="flex items-center gap-1"
                >
                  <label htmlFor="profile-fullname" className="sr-only">Full name</label>
                  <input
                    id="profile-fullname"
                    value={nameValue}
                    onChange={(e) => setNameValue(e.target.value)}
                    autoFocus
                    className="border border-gray-300 dark:border-gray-600 rounded px-2 py-0.5 text-sm w-48 focus:outline-none focus:ring-2 focus:ring-blue-500"
                  />
                  <button type="submit" disabled={nameSaving} className="text-xs text-blue-600 dark:text-blue-400 hover:underline">Save</button>
                  <button type="button" onClick={() => setEditingName(false)} className="text-xs text-gray-400 dark:text-gray-500">Cancel</button>
                </form>
              ) : (
                <>
                  {profile.full_name || <span className="text-gray-400 dark:text-gray-500 italic">Not set</span>}
                  <button
                    onClick={() => { setNameValue(profile.full_name); setEditingName(true); }}
                    className="text-xs text-blue-600 dark:text-blue-400 hover:underline"
                  >
                    Edit
                  </button>
                </>
              )}
            </dd>
          </div>
          <div className="flex justify-between">
            <dt className="text-gray-500 dark:text-gray-400">Email</dt>
            <dd className="text-gray-900 dark:text-gray-50">{profile.email}</dd>
          </div>
          <div className="flex justify-between">
            <dt className="text-gray-500 dark:text-gray-400">Member since</dt>
            <dd className="text-gray-900 dark:text-gray-50">{new Date(profile.date_joined).toLocaleDateString()}</dd>
          </div>
          {profile.last_login && (
            <div className="flex justify-between">
              <dt className="text-gray-500 dark:text-gray-400">Last login</dt>
              <dd className="text-gray-900 dark:text-gray-50">{new Date(profile.last_login).toLocaleString()}</dd>
            </div>
          )}
          {profile.is_staff && (
            <div className="flex justify-between">
              <dt className="text-gray-500 dark:text-gray-400">Role</dt>
              <dd><span className="text-xs bg-blue-100 dark:bg-blue-900/40 text-blue-800 dark:text-blue-300 px-2 py-0.5 rounded-full">Staff</span></dd>
            </div>
          )}
        </dl>
      </div>

      {/* Visibility */}
      <div className="bg-white dark:bg-gray-800 border border-gray-200 dark:border-gray-700 rounded-lg p-6 mb-6">
        <h2 className="text-sm font-semibold text-gray-500 dark:text-gray-400 uppercase tracking-wide mb-3">Visibility</h2>
        <label className="flex items-start gap-3 cursor-pointer">
          <input
            type="checkbox"
            checked={profile.share_builds}
            onChange={async (e) => {
              const next = e.target.checked;
              try {
                await client.patch('/auth/profile/', { share_builds: next });
                queryClient.invalidateQueries({ queryKey: ['profile'] });
                toast(
                  next
                    ? 'Your completed books are now visible in the Community library.'
                    : 'Your books are no longer visible in the Community library.',
                  'success',
                );
              } catch {
                toast('Failed to update setting.', 'error');
              }
            }}
            className="mt-1"
          />
          <div className="text-sm">
            <div className="text-gray-900 dark:text-gray-50 font-medium">
              Make my completed books visible in the Community library
            </div>
            <p className="text-xs text-gray-500 dark:text-gray-400 mt-1 leading-relaxed">
              When on, every completed book you build is listed publicly with its title,
              parts, and chapter list. Your full name (if set) is shown as the author —
              otherwise the entry is attributed to "Anonymous". Your email is never shown.
              No PDFs or HTML downloads are exposed.
            </p>
          </div>
        </label>
      </div>

      {/* My Examples */}
      <div className="bg-white dark:bg-gray-800 border border-gray-200 dark:border-gray-700 rounded-lg p-6 mb-6">
        <div className="flex items-center justify-between mb-3">
          <h2 className="text-sm font-semibold text-gray-500 dark:text-gray-400 uppercase tracking-wide">
            My worked examples
          </h2>
          <Link to="/examples/new" className="text-sm text-blue-600 dark:text-blue-400 hover:underline">
            + New example
          </Link>
        </div>
        {myExamples.length === 0 ? (
          <p className="text-sm text-gray-400 dark:text-gray-500">
            You haven't submitted any examples yet.{' '}
            <Link to="/examples/new" className="text-blue-600 dark:text-blue-400 hover:underline">
              Create one
            </Link>{' '}
            to share a worked problem with other authors.
          </p>
        ) : (
          <MyExamplesList items={myExamples} />
        )}
      </div>

      {/* Change password */}
      <div className="bg-white dark:bg-gray-800 border border-gray-200 dark:border-gray-700 rounded-lg p-6 mb-6">
        <div className="flex items-center justify-between mb-3">
          <h2 className="text-sm font-semibold text-gray-500 dark:text-gray-400 uppercase tracking-wide">Password</h2>
          {!showPwForm && (
            <button
              onClick={() => setShowPwForm(true)}
              className="text-sm text-blue-600 dark:text-blue-400 hover:underline"
            >
              Change password
            </button>
          )}
        </div>

        {pwSuccess && <p className="text-sm text-green-600 dark:text-green-400 mb-3">{pwSuccess}</p>}

        {showPwForm && (
          <form onSubmit={handleChangePassword} className="space-y-3">
            <div>
              <label htmlFor="current-password" className="block text-sm font-medium text-gray-700 dark:text-gray-200 mb-1">Current password</label>
              <input
                id="current-password"
                type="password"
                autoComplete="current-password"
                value={currentPw}
                onChange={(e) => setCurrentPw(e.target.value)}
                required
                className="w-full border border-gray-300 dark:border-gray-600 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
              />
            </div>
            <div>
              <label htmlFor="new-password" className="block text-sm font-medium text-gray-700 dark:text-gray-200 mb-1">New password</label>
              <input
                id="new-password"
                type="password"
                autoComplete="new-password"
                value={newPw}
                onChange={(e) => setNewPw(e.target.value)}
                required
                minLength={8}
                className="w-full border border-gray-300 dark:border-gray-600 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
              />
            </div>
            <div>
              <label htmlFor="confirm-new-password" className="block text-sm font-medium text-gray-700 dark:text-gray-200 mb-1">Confirm new password</label>
              <input
                id="confirm-new-password"
                type="password"
                autoComplete="new-password"
                value={confirmPw}
                onChange={(e) => setConfirmPw(e.target.value)}
                required
                minLength={8}
                className="w-full border border-gray-300 dark:border-gray-600 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
              />
            </div>
            {pwError && <p className="text-sm text-red-600 dark:text-red-400">{pwError}</p>}
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
                className="text-sm text-gray-500 dark:text-gray-400"
              >
                Cancel
              </button>
            </div>
          </form>
        )}
      </div>

      {/* Danger zone */}
      {!deletionDate && (
        <div className="bg-white dark:bg-gray-800 border border-red-200 dark:border-red-900 rounded-lg p-6">
          <h2 className="text-sm font-semibold text-red-600 dark:text-red-400 uppercase tracking-wide mb-2">Danger zone</h2>
          <p className="text-sm text-gray-500 dark:text-gray-400 mb-3">
            Schedule your account for deletion. Your data (books, builds,
            worked examples) will be permanently removed seven days later.
            You can sign in and cancel any time before then.
          </p>
          <button
            onClick={handleDeleteAccount}
            className="text-sm bg-red-50 dark:bg-red-950/40 text-red-700 dark:text-red-300 px-4 py-2 rounded-lg hover:bg-red-100 dark:hover:bg-red-900/40 font-medium"
          >
            Schedule deletion (7 days)
          </button>
        </div>
      )}
    </div>
  );
}

const STATUS_ORDER: ExampleStatus[] = ['draft', 'rejected', 'pending', 'published'];
const STATUS_LABEL: Record<ExampleStatus, string> = {
  draft: 'Drafts',
  rejected: 'Rejected',
  pending: 'Pending review',
  published: 'Published',
};
const STATUS_BADGE: Record<ExampleStatus, string> = {
  draft: 'bg-gray-100 dark:bg-gray-800 text-gray-700 dark:text-gray-200',
  rejected: 'bg-red-100 dark:bg-red-900/40 text-red-700 dark:text-red-300',
  pending: 'bg-amber-100 dark:bg-amber-900/40 text-amber-800 dark:text-amber-200',
  published: 'bg-emerald-100 dark:bg-emerald-900/40 text-emerald-800 dark:text-emerald-200',
};

function MyExamplesList({ items }: { items: ExampleListItem[] }) {
  const grouped: Record<ExampleStatus, ExampleListItem[]> = {
    draft: [], pending: [], published: [], rejected: [],
  };
  for (const ex of items) grouped[ex.status].push(ex);

  return (
    <div className="space-y-4 max-h-[60vh] overflow-y-auto pr-1">
      {STATUS_ORDER.map((s) => {
        const group = grouped[s];
        if (group.length === 0) return null;
        return (
          <div key={s}>
            <h3 className="text-xs font-semibold text-gray-500 dark:text-gray-400 uppercase tracking-wide mb-1.5">
              {STATUS_LABEL[s]}{' '}
              <span className="font-normal text-gray-400 dark:text-gray-500">({group.length})</span>
            </h3>
            <ul className="space-y-1.5">
              {group.map((ex) => {
                const editable = ex.status === 'draft' || ex.status === 'rejected';
                const target = editable ? `/examples/${ex.id}/edit` : `/examples/${ex.id}`;
                const preview = ex.statement_tex.length > 100
                  ? ex.statement_tex.slice(0, 100) + '…'
                  : ex.statement_tex;
                return (
                  <li key={ex.id}>
                    <Link
                      to={target}
                      className="block px-3 py-2 bg-gray-50 dark:bg-gray-900 hover:bg-gray-100 dark:hover:bg-gray-700 border border-gray-200 dark:border-gray-700 rounded transition"
                    >
                      <div className="flex items-center gap-2 mb-0.5">
                        <span className={`text-xs px-1.5 py-0.5 rounded font-medium ${STATUS_BADGE[ex.status]}`}>
                          #{ex.id}
                        </span>
                        <span className="text-xs text-gray-500 dark:text-gray-400">
                          {ex.primary_chapter.chabbr} · {ex.difficulty}
                        </span>
                      </div>
                      <p className="font-mono text-xs text-gray-700 dark:text-gray-200 line-clamp-1">{preview}</p>
                    </Link>
                  </li>
                );
              })}
            </ul>
          </div>
        );
      })}
    </div>
  );
}