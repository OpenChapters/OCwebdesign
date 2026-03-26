import { useState, useEffect } from 'react';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import { adminApi } from '../api';
import type { SiteSettings } from '../api';

export default function SettingsPage() {
  const queryClient = useQueryClient();
  const [form, setForm] = useState<SiteSettings | null>(null);
  const [saving, setSaving] = useState(false);
  const [message, setMessage] = useState('');

  const { data, isLoading } = useQuery({
    queryKey: ['admin-settings'],
    queryFn: adminApi.settingsGet,
  });

  useEffect(() => {
    if (data) setForm(data);
  }, [data]);

  async function handleSave() {
    if (!form) return;
    setSaving(true);
    setMessage('');
    try {
      const result = await adminApi.settingsUpdate(form);
      setMessage(result.detail);
      queryClient.invalidateQueries({ queryKey: ['admin-settings'] });
    } catch {
      setMessage('Failed to save settings.');
    } finally {
      setSaving(false);
    }
  }

  if (isLoading || !form) {
    return <div className="p-8 text-gray-500">Loading…</div>;
  }

  return (
    <div className="p-8 max-w-3xl">
      <h1 className="text-2xl font-bold text-gray-900 mb-6">Site Settings</h1>

      <div className="bg-white border border-gray-200 rounded-lg p-6 space-y-6">
        {/* Site name */}
        <div>
          <label className="block text-sm font-medium text-gray-700 mb-1">Site name</label>
          <input
            value={form.site_name}
            onChange={(e) => setForm({ ...form, site_name: e.target.value })}
            className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
          />
          <p className="text-xs text-gray-400 mt-1">Displayed in the navbar and emails.</p>
        </div>

        {/* Welcome message */}
        <div>
          <label className="block text-sm font-medium text-gray-700 mb-1">Welcome message</label>
          <textarea
            value={form.welcome_message}
            onChange={(e) => setForm({ ...form, welcome_message: e.target.value })}
            rows={2}
            className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
          />
          <p className="text-xs text-gray-400 mt-1">Shown on the chapter browser page (optional).</p>
        </div>

        {/* Announcement banner */}
        <div>
          <label className="block text-sm font-medium text-gray-700 mb-1">Announcement banner</label>
          <textarea
            value={form.announcement_banner}
            onChange={(e) => setForm({ ...form, announcement_banner: e.target.value })}
            rows={2}
            className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
          />
          <p className="text-xs text-gray-400 mt-1">Shown at the top of all pages. Leave blank to hide.</p>
        </div>

        {/* Toggles */}
        <div className="flex flex-wrap gap-6">
          <label className="flex items-center gap-2 text-sm text-gray-700">
            <input
              type="checkbox"
              checked={form.registration_enabled}
              onChange={(e) => setForm({ ...form, registration_enabled: e.target.checked })}
              className="rounded"
            />
            Registration enabled
          </label>
          <label className="flex items-center gap-2 text-sm text-gray-700">
            <input
              type="checkbox"
              checked={form.build_enabled}
              onChange={(e) => setForm({ ...form, build_enabled: e.target.checked })}
              className="rounded"
            />
            Build pipeline enabled
          </label>
        </div>

        {/* Numeric settings */}
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">Max chapters per book</label>
            <input
              type="number"
              min={1}
              value={form.max_chapters_per_book}
              onChange={(e) => setForm({ ...form, max_chapters_per_book: parseInt(e.target.value) || 1 })}
              className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
            />
          </div>
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">Max concurrent builds</label>
            <input
              type="number"
              min={1}
              value={form.max_concurrent_builds}
              onChange={(e) => setForm({ ...form, max_concurrent_builds: parseInt(e.target.value) || 1 })}
              className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
            />
          </div>
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">PDF retention (days)</label>
            <input
              type="number"
              min={1}
              value={form.pdf_retention_days}
              onChange={(e) => setForm({ ...form, pdf_retention_days: parseInt(e.target.value) || 1 })}
              className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
            />
          </div>
        </div>

        {/* Save */}
        <div className="flex items-center gap-3 pt-2">
          <button
            onClick={handleSave}
            disabled={saving}
            className="bg-blue-600 text-white text-sm px-5 py-2 rounded-lg hover:bg-blue-700 disabled:opacity-50"
          >
            {saving ? 'Saving…' : 'Save settings'}
          </button>
          {message && <p className="text-sm text-green-600">{message}</p>}
        </div>
      </div>
    </div>
  );
}
