import { useState, useEffect, useRef } from 'react';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import { adminApi } from '../api';
import type { SiteSettings, SplashConfig } from '../api';

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
    return <div className="p-8 text-gray-500 dark:text-gray-400">Loading…</div>;
  }

  return (
    <div className="p-8 max-w-3xl">
      <h1 className="text-2xl font-bold text-gray-900 dark:text-gray-50 mb-6">Site Settings</h1>

      <div className="bg-white dark:bg-gray-800 border border-gray-200 dark:border-gray-700 rounded-lg p-6 space-y-6">
        {/* Site name */}
        <div>
          <label className="block text-sm font-medium text-gray-700 dark:text-gray-200 mb-1">Site name</label>
          <input
            value={form.site_name}
            onChange={(e) => setForm({ ...form, site_name: e.target.value })}
            className="w-full border border-gray-300 dark:border-gray-600 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
          />
          <p className="text-xs text-gray-400 dark:text-gray-500 mt-1">Displayed in the navbar and emails.</p>
        </div>

        {/* Welcome message */}
        <div>
          <label className="block text-sm font-medium text-gray-700 dark:text-gray-200 mb-1">Welcome message</label>
          <textarea
            value={form.welcome_message}
            onChange={(e) => setForm({ ...form, welcome_message: e.target.value })}
            rows={2}
            className="w-full border border-gray-300 dark:border-gray-600 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
          />
          <p className="text-xs text-gray-400 dark:text-gray-500 mt-1">Shown on the chapter browser page (optional).</p>
        </div>

        {/* Announcement banner */}
        <div>
          <label className="block text-sm font-medium text-gray-700 dark:text-gray-200 mb-1">Announcement banner</label>
          <textarea
            value={form.announcement_banner}
            onChange={(e) => setForm({ ...form, announcement_banner: e.target.value })}
            rows={2}
            className="w-full border border-gray-300 dark:border-gray-600 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
          />
          <p className="text-xs text-gray-400 dark:text-gray-500 mt-1">Shown at the top of all pages. Leave blank to hide.</p>
        </div>

        {/* Toggles */}
        <div className="flex flex-wrap gap-6">
          <label className="flex items-center gap-2 text-sm text-gray-700 dark:text-gray-200">
            <input
              type="checkbox"
              checked={form.registration_enabled}
              onChange={(e) => setForm({ ...form, registration_enabled: e.target.checked })}
              className="rounded"
            />
            Registration enabled
          </label>
          <label className="flex items-center gap-2 text-sm text-gray-700 dark:text-gray-200">
            <input
              type="checkbox"
              checked={form.build_enabled}
              onChange={(e) => setForm({ ...form, build_enabled: e.target.checked })}
              className="rounded"
            />
            Build pipeline enabled
          </label>
        </div>

        {/* Author batch import */}
        <div>
          <label className="flex items-center gap-2 text-sm text-gray-700 dark:text-gray-200">
            <input
              type="checkbox"
              checked={form.author_batch_import_enabled}
              onChange={(e) =>
                setForm({ ...form, author_batch_import_enabled: e.target.checked })
              }
              className="rounded"
            />
            Allow authors to batch-import worked examples
          </label>
          <p className="text-xs text-gray-400 dark:text-gray-500 mt-1 ml-6">
            When on, authenticated users see a "Batch import…" link on the
            Examples page. Author imports land as drafts or in the pending
            review queue — they cannot self-publish.
          </p>
        </div>

        {/* Numeric settings */}
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
          <div>
            <label className="block text-sm font-medium text-gray-700 dark:text-gray-200 mb-1">Max chapters per book</label>
            <input
              type="number"
              min={1}
              value={form.max_chapters_per_book}
              onChange={(e) => setForm({ ...form, max_chapters_per_book: parseInt(e.target.value) || 1 })}
              className="w-full border border-gray-300 dark:border-gray-600 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
            />
          </div>
          <div>
            <label className="block text-sm font-medium text-gray-700 dark:text-gray-200 mb-1">Max concurrent builds</label>
            <input
              type="number"
              min={1}
              value={form.max_concurrent_builds}
              onChange={(e) => setForm({ ...form, max_concurrent_builds: parseInt(e.target.value) || 1 })}
              className="w-full border border-gray-300 dark:border-gray-600 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
            />
          </div>
          <div>
            <label className="block text-sm font-medium text-gray-700 dark:text-gray-200 mb-1">PDF retention (days)</label>
            <input
              type="number"
              min={1}
              value={form.pdf_retention_days}
              onChange={(e) => setForm({ ...form, pdf_retention_days: parseInt(e.target.value) || 1 })}
              className="w-full border border-gray-300 dark:border-gray-600 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
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
          {message && <p className="text-sm text-green-600 dark:text-green-400">{message}</p>}
        </div>
      </div>

      <SplashSection />
    </div>
  );
}


function SplashSection() {
  const queryClient = useQueryClient();
  const [form, setForm] = useState<SplashConfig | null>(null);
  const [imageFile, setImageFile] = useState<File | null>(null);
  const [saving, setSaving] = useState(false);
  const [message, setMessage] = useState('');
  const fileInputRef = useRef<HTMLInputElement>(null);

  const { data } = useQuery({
    queryKey: ['admin-site-config'],
    queryFn: adminApi.splashConfigGet,
  });

  useEffect(() => {
    if (data) setForm(data);
  }, [data]);

  async function handleSave() {
    if (!form) return;
    setSaving(true);
    setMessage('');
    try {
      const result = await adminApi.splashConfigUpdate({
        splash_enabled: form.splash_enabled,
        splash_duration_ms: form.splash_duration_ms,
        splash_caption: form.splash_caption,
        splash_image: imageFile || undefined,
      });
      setForm(result);
      setImageFile(null);
      if (fileInputRef.current) fileInputRef.current.value = '';
      setMessage('Saved.');
      queryClient.invalidateQueries({ queryKey: ['admin-site-config'] });
      queryClient.invalidateQueries({ queryKey: ['siteConfig'] });
    } catch {
      setMessage('Failed to save splash settings.');
    } finally {
      setSaving(false);
    }
  }

  async function handleClearImage() {
    if (!form) return;
    setSaving(true);
    setMessage('');
    try {
      const result = await adminApi.splashConfigUpdate({ clear_image: true });
      setForm(result);
      setImageFile(null);
      if (fileInputRef.current) fileInputRef.current.value = '';
      setMessage('Image cleared — using bundled placeholder.');
      queryClient.invalidateQueries({ queryKey: ['admin-site-config'] });
      queryClient.invalidateQueries({ queryKey: ['siteConfig'] });
    } catch {
      setMessage('Failed to clear image.');
    } finally {
      setSaving(false);
    }
  }

  if (!form) {
    return (
      <div className="mt-8 bg-white dark:bg-gray-800 border border-gray-200 dark:border-gray-700 rounded-lg p-6">
        <p className="text-sm text-gray-500 dark:text-gray-400">Loading splash settings…</p>
      </div>
    );
  }

  return (
    <div className="mt-8 bg-white dark:bg-gray-800 border border-gray-200 dark:border-gray-700 rounded-lg p-6 space-y-6">
      <div className="flex items-center justify-between">
        <h2 className="text-lg font-semibold text-gray-900 dark:text-gray-50">Splash screen</h2>
        <a
          href="/chapters?splash=preview"
          target="_blank"
          rel="noopener noreferrer"
          className="text-sm text-blue-600 dark:text-blue-400 hover:underline"
        >
          Preview in new tab &rarr;
        </a>
      </div>
      <p className="text-xs text-gray-500 dark:text-gray-400 -mt-4">
        A full-screen welcome overlay shown once per browser session on the
        chapter browser. Preview mode bypasses the session and don&apos;t-show-again
        gates without affecting other users.
      </p>

      {/* Toggle */}
      <label className="flex items-center gap-2 text-sm text-gray-700 dark:text-gray-200">
        <input
          type="checkbox"
          checked={form.splash_enabled}
          onChange={(e) => setForm({ ...form, splash_enabled: e.target.checked })}
          className="rounded"
        />
        Splash enabled
      </label>

      {/* Duration */}
      <div>
        <label className="block text-sm font-medium text-gray-700 dark:text-gray-200 mb-1">
          Auto-dismiss after (ms)
        </label>
        <input
          type="number"
          min={2000}
          max={60000}
          step={500}
          value={form.splash_duration_ms}
          onChange={(e) =>
            setForm({ ...form, splash_duration_ms: parseInt(e.target.value) || 10000 })
          }
          className="w-40 border border-gray-300 dark:border-gray-600 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
        />
        <p className="text-xs text-gray-400 dark:text-gray-500 mt-1">
          Between 2000 and 60000 milliseconds (default 10000).
        </p>
      </div>

      {/* Caption */}
      <div>
        <label className="block text-sm font-medium text-gray-700 dark:text-gray-200 mb-1">
          Caption (optional)
        </label>
        <input
          value={form.splash_caption}
          maxLength={200}
          onChange={(e) => setForm({ ...form, splash_caption: e.target.value })}
          className="w-full border border-gray-300 dark:border-gray-600 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
        />
        <p className="text-xs text-gray-400 dark:text-gray-500 mt-1">
          Short line of text overlaid at the bottom of the image.
        </p>
      </div>

      {/* Image */}
      <div>
        <label className="block text-sm font-medium text-gray-700 dark:text-gray-200 mb-1">
          Splash image
        </label>
        {form.splash_image_url ? (
          <div className="mb-3">
            <img
              src={form.splash_image_url}
              alt="Current splash"
              className="max-h-48 rounded border border-gray-200 dark:border-gray-700"
            />
            <p className="text-xs text-gray-400 dark:text-gray-500 mt-1 break-all">
              Current: {form.splash_image_url}
            </p>
          </div>
        ) : (
          <p className="text-xs text-gray-500 dark:text-gray-400 mb-3">
            No image uploaded — using the bundled placeholder SVG.
          </p>
        )}
        <input
          ref={fileInputRef}
          type="file"
          accept="image/png,image/jpeg,image/svg+xml,image/webp"
          onChange={(e) => setImageFile(e.target.files?.[0] || null)}
          className="block text-sm text-gray-700 dark:text-gray-300"
        />
        <p className="text-xs text-gray-400 dark:text-gray-500 mt-1">
          Recommended dimensions: 1600 × 900 (16:9). PNG, JPEG, SVG, or WebP.
        </p>
      </div>

      {/* Actions */}
      <div className="flex items-center gap-3 pt-2">
        <button
          onClick={handleSave}
          disabled={saving}
          className="bg-blue-600 text-white text-sm px-5 py-2 rounded-lg hover:bg-blue-700 disabled:opacity-50"
        >
          {saving ? 'Saving…' : 'Save splash settings'}
        </button>
        {form.splash_image_url && (
          <button
            onClick={handleClearImage}
            disabled={saving}
            className="text-sm text-red-600 dark:text-red-400 hover:underline disabled:opacity-50"
          >
            Clear image
          </button>
        )}
        {message && <p className="text-sm text-green-600 dark:text-green-400">{message}</p>}
      </div>
    </div>
  );
}
