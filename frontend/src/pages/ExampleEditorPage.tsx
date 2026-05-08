import { useEffect, useMemo, useRef, useState } from 'react';
import { Link, useNavigate, useParams } from 'react-router-dom';
import { useQuery } from '@tanstack/react-query';
import { examplesApi } from '../api/examples';
import { chaptersApi } from '../api/chapters';
import { useToast } from '../components/Toast';
import type { ExampleDifficulty, ExampleWritePayload } from '../types';

interface FormState {
  primary_chapter: number | null;
  chapters: number[];
  statement_tex: string;
  solution_tex: string;
  difficulty: ExampleDifficulty;
}

const EMPTY: FormState = {
  primary_chapter: null,
  chapters: [],
  statement_tex: '',
  solution_tex: '',
  difficulty: 'standard',
};

export default function ExampleEditorPage() {
  const { id } = useParams<{ id?: string }>();
  const isEdit = id !== undefined;
  const exampleId = isEdit ? Number(id) : null;
  const navigate = useNavigate();
  const toast = useToast();

  const [form, setForm] = useState<FormState>(EMPTY);
  const [saving, setSaving] = useState(false);
  const [rejectionReason, setRejectionReason] = useState('');

  // Preview state. `previewPdfUrl` is the signed URL minted by the
  // serializer — the iframe and "Open in new tab" link both consume it
  // directly. `previewFresh` reflects the live state from polling and
  // `previewBuildLog` surfaces compile errors when a build fails.
  const [previewing, setPreviewing] = useState(false);
  const [previewExampleId, setPreviewExampleId] = useState<number | null>(null);
  const [previewFresh, setPreviewFresh] = useState(false);
  const [previewBuiltAt, setPreviewBuiltAt] = useState<string | null>(null);
  const [previewBuildLog, setPreviewBuildLog] = useState('');
  const [previewPdfUrl, setPreviewPdfUrl] = useState<string | null>(null);
  const pollAbortRef = useRef<{ cancelled: boolean } | null>(null);

  const { data: chapters = [] } = useQuery({
    queryKey: ['chapters-all-for-example-editor'],
    queryFn: () => chaptersApi.listAll(),
    staleTime: 300_000,
  });

  const { data: existing } = useQuery({
    queryKey: ['example-edit', exampleId],
    queryFn: () => examplesApi.manage(exampleId as number),
    enabled: isEdit && exampleId !== null && !Number.isNaN(exampleId),
  });

  useEffect(() => {
    if (existing) {
      setForm({
        primary_chapter: existing.primary_chapter.id,
        chapters: existing.chapters.map((c) => c.id),
        statement_tex: existing.statement_tex,
        solution_tex: existing.solution_tex,
        difficulty: existing.difficulty,
      });
      if (existing.status === 'rejected' && existing.rejection_reason) {
        setRejectionReason(existing.rejection_reason);
      }
      setPreviewExampleId(existing.id);
      setPreviewFresh(existing.preview_fresh);
      setPreviewBuiltAt(existing.preview_built_at);
      setPreviewBuildLog(existing.preview_build_log || '');
      setPreviewPdfUrl(existing.preview_pdf_url);
    }
  }, [existing]);

  // Cancel any in-flight poll when the page unmounts.
  useEffect(() => () => { if (pollAbortRef.current) pollAbortRef.current.cancelled = true; }, []);

  // Editing the form invalidates any prior fresh preview signal locally;
  // the freshness gate on submit is enforced server-side too.
  function markPreviewStale() {
    setPreviewFresh(false);
  }

  const validChapters = useMemo(
    () => chapters.filter((c) => c.chabbr),
    [chapters],
  );

  function toggleChapter(chapterId: number) {
    setForm((f) => {
      const has = f.chapters.includes(chapterId);
      const next = has ? f.chapters.filter((x) => x !== chapterId) : [...f.chapters, chapterId];
      let primary = f.primary_chapter;
      if (has && primary === chapterId) primary = next[0] ?? null;
      if (!has && primary === null) primary = chapterId;
      return { ...f, chapters: next, primary_chapter: primary };
    });
  }

  function validateForm(): string | null {
    if (form.chapters.length === 0) return 'Tag at least one chapter.';
    if (form.primary_chapter === null) return 'Pick a primary chapter.';
    if (!form.statement_tex.trim() || !form.solution_tex.trim()) {
      return 'Statement and solution cannot be empty.';
    }
    return null;
  }

  function buildPayload(): ExampleWritePayload {
    return {
      primary_chapter: form.primary_chapter as number,
      chapters: form.chapters,
      statement_tex: form.statement_tex,
      solution_tex: form.solution_tex,
      difficulty: form.difficulty,
    };
  }

  function errorMessage(err: any, fallback: string): string {
    const detail = err?.response?.data;
    if (typeof detail === 'string') return detail;
    return (
      detail?.detail ||
      Object.values(detail || {})[0]?.toString() ||
      fallback
    );
  }

  async function handleSubmit(e: React.FormEvent, action: 'save' | 'submit') {
    e.preventDefault();
    const err = validateForm();
    if (err) { toast(err, 'error'); return; }
    setSaving(true);
    try {
      if (action === 'submit') {
        // The Preview button already saved the draft and produced a
        // fresh preview. Saving again here would bump updated_at past
        // preview_built_at and trip the server's freshness gate.
        // Submit is only enabled when previewFresh is True, so the
        // persisted content already matches the previewed snapshot.
        if (previewExampleId === null) {
          toast('Run Preview first, then submit.', 'error');
          return;
        }
        const submitted = await examplesApi.submit(previewExampleId);
        toast('Submitted for review.', 'success');
        navigate(`/examples/${submitted.id}`);
        return;
      }
      const payload = buildPayload();
      const saved = isEdit
        ? await examplesApi.update(exampleId as number, payload)
        : await examplesApi.create(payload);
      toast(isEdit ? 'Draft updated.' : 'Draft saved.', 'success');
      navigate(`/examples/${saved.id}`);
    } catch (e: any) {
      toast(errorMessage(e, 'Could not save.'), 'error');
    } finally {
      setSaving(false);
    }
  }

  async function handlePreview() {
    const err = validateForm();
    if (err) { toast(err, 'error'); return; }
    setPreviewing(true);
    setPreviewBuildLog('');
    if (pollAbortRef.current) pollAbortRef.current.cancelled = true;
    const abort = { cancelled: false };
    pollAbortRef.current = abort;
    try {
      const payload = buildPayload();
      const saved = isEdit
        ? await examplesApi.update(exampleId as number, payload)
        : await examplesApi.create(payload);
      // For new examples, the URL changes to /examples/<id>/edit so a
      // refresh keeps the preview state intact.
      if (!isEdit) {
        navigate(`/examples/${saved.id}/edit`, { replace: true });
      }
      setPreviewExampleId(saved.id);
      const baselineBuiltAt = saved.preview_built_at;
      await examplesApi.preview(saved.id);
      // Poll the manage endpoint until preview_built_at advances or a
      // non-empty preview_build_log appears (= build failed). Cap at ~2 min.
      const start = Date.now();
      while (!abort.cancelled && Date.now() - start < 120_000) {
        await new Promise((r) => setTimeout(r, 1500));
        if (abort.cancelled) return;
        const fresh = await examplesApi.manage(saved.id);
        if (fresh.preview_build_log) {
          setPreviewBuildLog(fresh.preview_build_log);
          setPreviewFresh(false);
          toast('Preview build failed — see error log below.', 'error');
          return;
        }
        if (fresh.preview_built_at && fresh.preview_built_at !== baselineBuiltAt) {
          setPreviewBuiltAt(fresh.preview_built_at);
          setPreviewFresh(fresh.preview_fresh);
          setPreviewPdfUrl(fresh.preview_pdf_url);
          toast('Preview ready.', 'success');
          return;
        }
      }
      if (!abort.cancelled) {
        toast('Preview is taking longer than expected — try again or check the worker.', 'error');
      }
    } catch (e: any) {
      toast(errorMessage(e, 'Could not start preview.'), 'error');
    } finally {
      setPreviewing(false);
    }
  }

  // Any form edit invalidates the local fresh signal (server enforces this
  // via the preview_built_at vs updated_at gate).
  function updateField<K extends keyof FormState>(key: K, value: FormState[K]) {
    setForm((f) => ({ ...f, [key]: value }));
    markPreviewStale();
  }

  return (
    <div className="max-w-4xl mx-auto px-6 py-8">
      <Link to="/examples" className="text-sm text-blue-600 hover:underline">
        ← Back to examples
      </Link>
      <h1 className="mt-3 text-2xl font-bold text-gray-900">
        {isEdit ? 'Edit example' : 'New example'}
      </h1>
      <p className="text-sm text-gray-600 mt-1">
        Paste your LaTeX directly. The compile-preview button arrives in a
        later iteration; for now, please verify your snippet locally before
        submitting.
      </p>

      {isEdit && rejectionReason && (
        <div className="mt-4 bg-red-50 border border-red-200 rounded-lg px-4 py-3">
          <p className="text-xs font-semibold text-red-800 uppercase tracking-wide mb-1">
            Previous rejection reason
          </p>
          <p className="text-sm text-red-900 whitespace-pre-wrap">{rejectionReason}</p>
        </div>
      )}

      <form className="mt-6 space-y-5" onSubmit={(e) => handleSubmit(e, 'save')}>
        <div>
          <label className="block text-sm font-medium text-gray-700 mb-1">
            Tagged chapters <span className="text-red-500">*</span>
          </label>
          <p className="text-xs text-gray-500 mb-2">
            Select every chapter this example is relevant to. The primary
            chapter (chosen below) drives which preamble is used when the
            preview compile lands in Phase 2.
          </p>
          <div className="border border-gray-300 rounded-lg max-h-48 overflow-y-auto p-2">
            {validChapters.map((c) => (
              <label
                key={c.id}
                className="flex items-center gap-2 px-2 py-1 hover:bg-gray-50 rounded cursor-pointer"
              >
                <input
                  type="checkbox"
                  checked={form.chapters.includes(c.id)}
                  onChange={() => toggleChapter(c.id)}
                  className="rounded"
                />
                <span className="text-sm">{c.title}</span>
                <span className="text-xs font-mono text-gray-400 ml-auto">{c.chabbr}</span>
              </label>
            ))}
          </div>
        </div>

        <div>
          <label className="block text-sm font-medium text-gray-700 mb-1">
            Primary chapter <span className="text-red-500">*</span>
          </label>
          <select
            value={form.primary_chapter ?? ''}
            onChange={(e) => {
              updateField('primary_chapter', e.target.value ? Number(e.target.value) : null);
            }}
            disabled={form.chapters.length === 0}
            className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500 disabled:bg-gray-50"
          >
            <option value="">— Select primary chapter —</option>
            {validChapters
              .filter((c) => form.chapters.includes(c.id))
              .map((c) => (
                <option key={c.id} value={c.id}>
                  {c.title} ({c.chabbr})
                </option>
              ))}
          </select>
        </div>

        <div>
          <label className="block text-sm font-medium text-gray-700 mb-1">
            Difficulty
          </label>
          <div className="flex gap-3">
            {(['introductory', 'standard', 'advanced'] as ExampleDifficulty[]).map((d) => (
              <label key={d} className="flex items-center gap-1.5 text-sm">
                <input
                  type="radio"
                  name="difficulty"
                  value={d}
                  checked={form.difficulty === d}
                  onChange={() => updateField('difficulty', d)}
                />
                {d.charAt(0).toUpperCase() + d.slice(1)}
              </label>
            ))}
          </div>
        </div>

        <div>
          <label className="block text-sm font-medium text-gray-700 mb-1">
            Statement (LaTeX) <span className="text-red-500">*</span>
          </label>
          <textarea
            value={form.statement_tex}
            onChange={(e) => updateField('statement_tex', e.target.value)}
            rows={10}
            required
            className="w-full font-mono text-sm border border-gray-300 rounded-lg px-3 py-2 focus:outline-none focus:ring-2 focus:ring-blue-500"
            placeholder={'Find the rotation matrix that...'}
          />
        </div>

        <div>
          <label className="block text-sm font-medium text-gray-700 mb-1">
            Solution (LaTeX) <span className="text-red-500">*</span>
          </label>
          <textarea
            value={form.solution_tex}
            onChange={(e) => updateField('solution_tex', e.target.value)}
            rows={14}
            required
            className="w-full font-mono text-sm border border-gray-300 rounded-lg px-3 py-2 focus:outline-none focus:ring-2 focus:ring-blue-500"
            placeholder={'Begin by noting that...'}
          />
        </div>

        <div className="flex flex-wrap gap-2 pt-2 border-t border-gray-200 items-center">
          <button
            type="submit"
            disabled={saving || previewing}
            className="text-sm bg-gray-800 text-white px-4 py-2 rounded-lg hover:bg-gray-900 disabled:opacity-50"
          >
            {saving ? 'Saving…' : isEdit ? 'Save changes' : 'Save draft'}
          </button>
          <button
            type="button"
            onClick={handlePreview}
            disabled={saving || previewing}
            className="text-sm bg-amber-600 text-white px-4 py-2 rounded-lg hover:bg-amber-700 disabled:opacity-50"
          >
            {previewing ? 'Building preview…' : 'Preview'}
          </button>
          <button
            type="button"
            onClick={(e) => handleSubmit(e, 'submit')}
            disabled={saving || previewing || !previewFresh}
            title={!previewFresh ? 'Click Preview and wait for a successful build before submitting.' : undefined}
            className="text-sm bg-blue-600 text-white px-4 py-2 rounded-lg hover:bg-blue-700 disabled:opacity-50"
          >
            {saving ? 'Working…' : 'Save & submit for review'}
          </button>
          <Link
            to="/examples"
            className="text-sm text-gray-600 px-4 py-2 rounded-lg hover:bg-gray-100"
          >
            Cancel
          </Link>
          {!previewFresh && previewBuiltAt && !previewing && (
            <span className="text-xs text-amber-700">
              Preview is stale — click Preview again before submitting.
            </span>
          )}
        </div>
      </form>

      {previewBuildLog && (
        <section className="mt-6">
          <h2 className="text-sm font-semibold text-red-800 uppercase tracking-wide mb-2">
            Last build failed
          </h2>
          <pre className="font-mono text-xs text-red-900 bg-red-50 border border-red-200 rounded-lg p-3 whitespace-pre-wrap leading-relaxed max-h-64 overflow-y-auto">
            {previewBuildLog}
          </pre>
        </section>
      )}

      {previewExampleId !== null && previewPdfUrl && !previewBuildLog && (
        <section className="mt-6">
          <div className="flex items-center justify-between mb-2">
            <h2 className="text-sm font-semibold text-gray-700 uppercase tracking-wide">
              Preview
            </h2>
            <a
              href={previewPdfUrl}
              target="_blank"
              rel="noopener noreferrer"
              className="text-xs text-blue-600 hover:underline"
            >
              Open in new tab ↗
            </a>
          </div>
          <iframe
            key={previewPdfUrl}
            src={previewPdfUrl}
            title="Example preview"
            className="w-full h-[640px] border border-gray-200 rounded-lg bg-white"
          />
        </section>
      )}
    </div>
  );
}
