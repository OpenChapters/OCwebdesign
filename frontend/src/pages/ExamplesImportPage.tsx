import { useState } from 'react';
import { Link } from 'react-router-dom';
import { useQueryClient } from '@tanstack/react-query';
import { examplesApi } from '../api/examples';
import type { ImportReport } from '../api/examples';
import { useToast } from '../components/Toast';

type DefaultStatus = 'draft' | 'pending';

export default function ExamplesImportPage() {
  const toast = useToast();
  const queryClient = useQueryClient();
  const [file, setFile] = useState<File | null>(null);
  const [defaultStatus, setDefaultStatus] = useState<DefaultStatus>('pending');
  const [report, setReport] = useState<ImportReport | null>(null);
  const [loading, setLoading] = useState(false);
  const [committed, setCommitted] = useState(false);

  function reset() {
    setReport(null);
    setCommitted(false);
  }

  async function handleValidate() {
    if (file === null) return;
    setLoading(true);
    setCommitted(false);
    try {
      const r = await examplesApi.importDryRun(file);
      setReport(r);
      if (r.global_errors.length === 0 && r.summary.errors === 0) {
        toast(
          `Validated: ${r.summary.create} to create, ${r.summary.update} to update.`,
          'success',
        );
      } else {
        toast('Validation found errors — see report below.', 'error');
      }
    } catch (err: any) {
      const data = err?.response?.data;
      if (data && typeof data === 'object' && 'entries' in data) {
        setReport(data as ImportReport);
      }
      toast(err?.response?.data?.detail || 'Validation failed.', 'error');
    } finally {
      setLoading(false);
    }
  }

  async function handleCommit() {
    if (file === null || report === null) return;
    if (report.summary.errors > 0 || report.global_errors.length > 0) return;
    setLoading(true);
    try {
      const r = await examplesApi.importCommit(file, defaultStatus);
      setReport(r);
      setCommitted(true);
      queryClient.invalidateQueries({ queryKey: ['examples'] });
      queryClient.invalidateQueries({ queryKey: ['my-examples'] });
      toast(
        `Imported: ${r.summary.create} created, ${r.summary.update} updated.`,
        'success',
      );
    } catch (err: any) {
      const data = err?.response?.data;
      if (data && typeof data === 'object' && 'entries' in data) {
        setReport(data as ImportReport);
      }
      toast(err?.response?.data?.detail || 'Import failed.', 'error');
    } finally {
      setLoading(false);
    }
  }

  const cleanReport =
    report !== null &&
    report.global_errors.length === 0 &&
    report.summary.errors === 0;

  return (
    <div className="p-8 max-w-5xl mx-auto">
      <div className="flex items-center justify-between mb-1">
        <h1 className="text-2xl font-bold text-gray-900">Batch import examples</h1>
        <Link to="/examples" className="text-sm text-blue-600 hover:underline">
          ← Back to examples
        </Link>
      </div>
      <p className="text-sm text-gray-600 mb-6">
        Upload a zip with a <code className="bg-gray-100 px-1 rounded">manifest.json</code> at
        the root and one directory per example holding{' '}
        <code className="bg-gray-100 px-1 rounded">statement.tex</code>,{' '}
        <code className="bg-gray-100 px-1 rounded">solution.tex</code>, and an optional{' '}
        <code className="bg-gray-100 px-1 rounded">figures/</code> subdirectory. Use the
        same file structure as the admin import; you become the author of every
        row in the batch.
      </p>

      <div className="bg-white border border-gray-200 rounded-lg p-5 mb-4 space-y-4">
        <div>
          <label className="block text-sm font-medium text-gray-700 mb-1">
            Batch zip
          </label>
          <input
            type="file"
            accept=".zip,application/zip"
            onChange={(e) => {
              setFile(e.target.files?.[0] ?? null);
              reset();
            }}
            className="text-sm"
          />
          <p className="text-xs text-gray-500 mt-1">
            Cap: 50 MB total · 5 MB per figure · max 200 entries per batch.
          </p>
        </div>

        <div>
          <label className="block text-sm font-medium text-gray-700 mb-1">
            Default status for newly created examples
          </label>
          <div className="flex gap-3">
            {(['pending', 'draft'] as DefaultStatus[]).map((s) => (
              <label key={s} className="flex items-center gap-1.5 text-sm">
                <input
                  type="radio"
                  name="default_status"
                  value={s}
                  checked={defaultStatus === s}
                  onChange={() => setDefaultStatus(s)}
                />
                {s === 'pending' ? 'Submit for review (Pending)' : 'Save as Draft'}
              </label>
            ))}
          </div>
          <p className="text-xs text-gray-500 mt-1">
            <strong>Pending</strong> sends new examples to the admin review
            queue. <strong>Draft</strong> keeps them private so you can edit
            before submitting. Existing examples (matched by slug) keep their
            current status.
          </p>
        </div>

        <div className="flex gap-2 pt-2 border-t border-gray-100">
          <button
            onClick={handleValidate}
            disabled={file === null || loading}
            className="text-sm bg-amber-600 text-white px-4 py-2 rounded-lg hover:bg-amber-700 disabled:opacity-50"
          >
            {loading && !committed ? 'Validating…' : 'Validate'}
          </button>
          <button
            onClick={handleCommit}
            disabled={!cleanReport || loading || committed}
            title={
              committed
                ? 'Already imported — pick a new file to start over.'
                : !cleanReport
                ? 'Validate first; resolve any errors before importing.'
                : undefined
            }
            className="text-sm bg-blue-600 text-white px-4 py-2 rounded-lg hover:bg-blue-700 disabled:opacity-50"
          >
            {committed ? 'Imported ✓' : loading ? 'Importing…' : 'Confirm and import'}
          </button>
        </div>
      </div>

      {report && <ReportView report={report} committed={committed} />}
    </div>
  );
}

function ReportView({ report, committed }: { report: ImportReport; committed: boolean }) {
  return (
    <div className="bg-white border border-gray-200 rounded-lg p-5">
      {report.global_errors.length > 0 && (
        <div className="mb-4 bg-red-50 border border-red-200 rounded-lg px-4 py-3">
          <p className="text-xs font-semibold text-red-800 uppercase tracking-wide mb-1">
            Cannot import this batch
          </p>
          <ul className="text-sm text-red-900 list-disc pl-5 space-y-0.5">
            {report.global_errors.map((e, i) => (
              <li key={i}>{e}</li>
            ))}
          </ul>
        </div>
      )}

      <div className="flex flex-wrap gap-4 mb-3 text-sm">
        <span className="text-gray-600">
          Total: <span className="font-semibold">{report.summary.total}</span>
        </span>
        <span className="text-emerald-700">
          Create: <span className="font-semibold">{report.summary.create}</span>
        </span>
        <span className="text-blue-700">
          Update: <span className="font-semibold">{report.summary.update}</span>
        </span>
        <span className={report.summary.errors > 0 ? 'text-red-700' : 'text-gray-400'}>
          Errors: <span className="font-semibold">{report.summary.errors}</span>
        </span>
        {committed && (
          <span className="ml-auto text-xs text-emerald-700 font-medium">
            ✓ Persisted to database
          </span>
        )}
      </div>

      <div className="overflow-x-auto">
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b border-gray-200 text-left text-xs text-gray-500 uppercase tracking-wide">
              <th className="py-2 pr-3">Dir</th>
              <th className="py-2 pr-3">Slug</th>
              <th className="py-2 pr-3">Primary</th>
              <th className="py-2 pr-3">Tagged</th>
              <th className="py-2 pr-3">Difficulty</th>
              <th className="py-2 pr-3">Figs</th>
              <th className="py-2 pr-3">Action</th>
              <th className="py-2 pr-3">Errors</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-gray-100">
            {report.entries.map((e) => (
              <tr key={e.dir} className="align-top">
                <td className="py-2 pr-3 font-mono text-xs text-gray-700">{e.dir}</td>
                <td className="py-2 pr-3 font-mono text-xs text-gray-500">{e.slug || '—'}</td>
                <td className="py-2 pr-3 font-mono text-xs">{e.primary_chapter || '—'}</td>
                <td className="py-2 pr-3 font-mono text-xs text-gray-600">
                  {e.chapters.join(', ') || '—'}
                </td>
                <td className="py-2 pr-3 text-xs">{e.difficulty}</td>
                <td className="py-2 pr-3 text-xs text-gray-600">{e.figure_count}</td>
                <td className="py-2 pr-3">
                  <ActionBadge action={e.action} />
                  {e.persisted_id && (
                    <Link
                      to={`/examples/${e.persisted_id}`}
                      className="ml-2 text-xs text-blue-600 hover:underline"
                    >
                      #{e.persisted_id}
                    </Link>
                  )}
                </td>
                <td className="py-2 pr-3">
                  {e.errors.length > 0 ? (
                    <ul className="text-xs text-red-700 list-disc pl-4 space-y-0.5">
                      {e.errors.map((msg, i) => (
                        <li key={i}>{msg}</li>
                      ))}
                    </ul>
                  ) : (
                    <span className="text-xs text-gray-300">—</span>
                  )}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}

function ActionBadge({ action }: { action: 'create' | 'update' | 'skip' }) {
  const cls =
    action === 'create'
      ? 'bg-emerald-100 text-emerald-800'
      : action === 'update'
      ? 'bg-blue-100 text-blue-800'
      : 'bg-red-100 text-red-700';
  return (
    <span className={`text-xs font-medium px-1.5 py-0.5 rounded ${cls}`}>{action}</span>
  );
}
