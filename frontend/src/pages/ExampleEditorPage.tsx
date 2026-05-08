import { useEffect, useMemo, useState } from 'react';
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
    }
  }, [existing]);

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

  async function handleSubmit(e: React.FormEvent, action: 'save' | 'submit') {
    e.preventDefault();
    if (form.chapters.length === 0) {
      toast('Tag at least one chapter.', 'error');
      return;
    }
    if (form.primary_chapter === null) {
      toast('Pick a primary chapter.', 'error');
      return;
    }
    if (!form.statement_tex.trim() || !form.solution_tex.trim()) {
      toast('Statement and solution cannot be empty.', 'error');
      return;
    }
    setSaving(true);
    try {
      const payload: ExampleWritePayload = {
        primary_chapter: form.primary_chapter,
        chapters: form.chapters,
        statement_tex: form.statement_tex,
        solution_tex: form.solution_tex,
        difficulty: form.difficulty,
      };
      const saved = isEdit
        ? await examplesApi.update(exampleId as number, payload)
        : await examplesApi.create(payload);
      if (action === 'submit') {
        await examplesApi.submit(saved.id);
        toast('Submitted for review.', 'success');
      } else {
        toast(isEdit ? 'Draft updated.' : 'Draft saved.', 'success');
      }
      navigate(`/examples/${saved.id}`);
    } catch (err: any) {
      const detail = err?.response?.data;
      const msg =
        typeof detail === 'string'
          ? detail
          : detail?.detail ||
            Object.values(detail || {})[0]?.toString() ||
            'Could not save.';
      toast(msg, 'error');
    } finally {
      setSaving(false);
    }
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
            onChange={(e) =>
              setForm((f) => ({ ...f, primary_chapter: e.target.value ? Number(e.target.value) : null }))
            }
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
                  onChange={() => setForm((f) => ({ ...f, difficulty: d }))}
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
            onChange={(e) => setForm((f) => ({ ...f, statement_tex: e.target.value }))}
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
            onChange={(e) => setForm((f) => ({ ...f, solution_tex: e.target.value }))}
            rows={14}
            required
            className="w-full font-mono text-sm border border-gray-300 rounded-lg px-3 py-2 focus:outline-none focus:ring-2 focus:ring-blue-500"
            placeholder={'Begin by noting that...'}
          />
        </div>

        <div className="flex flex-wrap gap-2 pt-2 border-t border-gray-200">
          <button
            type="submit"
            disabled={saving}
            className="text-sm bg-gray-800 text-white px-4 py-2 rounded-lg hover:bg-gray-900 disabled:opacity-50"
          >
            {saving ? 'Saving…' : isEdit ? 'Save changes' : 'Save draft'}
          </button>
          <button
            type="button"
            onClick={(e) => handleSubmit(e, 'submit')}
            disabled={saving}
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
        </div>
      </form>
    </div>
  );
}
