import { useState } from 'react';
import { Link } from 'react-router-dom';
import { useQuery } from '@tanstack/react-query';
import axios from 'axios';
import { examplesApi } from '../api/examples';
import { chaptersApi } from '../api/chapters';
import { useAuth } from '../contexts/AuthContext';
import type { ExampleDifficulty } from '../types';

const DIFFICULTY_LABEL: Record<ExampleDifficulty, string> = {
  introductory: 'Introductory',
  standard: 'Standard',
  advanced: 'Advanced',
};

const DIFFICULTY_BADGE: Record<ExampleDifficulty, string> = {
  introductory: 'bg-emerald-100 text-emerald-800',
  standard: 'bg-blue-100 text-blue-800',
  advanced: 'bg-amber-100 text-amber-800',
};

function StatementPreview({ tex }: { tex: string }) {
  const trimmed = tex.length > 240 ? tex.slice(0, 240) + '…' : tex;
  return (
    <pre className="font-mono text-xs text-gray-700 whitespace-pre-wrap leading-relaxed">
      {trimmed}
    </pre>
  );
}

export default function ExamplesPage() {
  const { isAuthenticated } = useAuth();
  const [chapter, setChapter] = useState('');
  const [difficulty, setDifficulty] = useState('');
  const [search, setSearch] = useState('');

  const { data: chapters = [] } = useQuery({
    queryKey: ['chapters-all-for-examples'],
    queryFn: () => chaptersApi.listAll(),
    staleTime: 300_000,
  });

  const { data: publicSettings } = useQuery({
    queryKey: ['public-settings'],
    queryFn: () => axios.get('/api/settings/public/').then((r) => r.data),
    staleTime: 60_000,
  });
  const batchImportEnabled = Boolean(publicSettings?.author_batch_import_enabled);

  const { data, isLoading } = useQuery({
    queryKey: ['examples', chapter, difficulty, search],
    queryFn: () =>
      examplesApi.list({
        chapter: chapter || undefined,
        difficulty: difficulty || undefined,
        search: search || undefined,
      }),
  });

  const examples = data?.results ?? [];

  return (
    <div className="max-w-6xl mx-auto px-6 py-8">
      <div className="flex items-start justify-between mb-6 gap-4">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">Worked examples</h1>
          <p className="text-sm text-gray-600 mt-1 max-w-2xl">
            Community-contributed examples with full solutions, tagged to one
            or more chapters. Browse here, or include them at book build time.
          </p>
        </div>
        {isAuthenticated && (
          <div className="flex flex-wrap gap-2 shrink-0">
            {batchImportEnabled && (
              <Link
                to="/examples/import"
                className="text-sm bg-gray-800 text-white px-4 py-2 rounded-lg hover:bg-gray-900"
              >
                Batch import…
              </Link>
            )}
            <Link
              to="/examples/new"
              className="text-sm bg-blue-600 text-white px-4 py-2 rounded-lg hover:bg-blue-700"
            >
              Submit an example
            </Link>
          </div>
        )}
      </div>

      <div className="flex flex-wrap gap-3 mb-6">
        <select
          value={chapter}
          onChange={(e) => setChapter(e.target.value)}
          className="border border-gray-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
        >
          <option value="">All chapters</option>
          {chapters
            .filter((c) => c.chabbr)
            .map((c) => (
              <option key={c.id} value={c.chabbr}>
                {c.title} ({c.chabbr})
              </option>
            ))}
        </select>
        <select
          value={difficulty}
          onChange={(e) => setDifficulty(e.target.value)}
          className="border border-gray-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
        >
          <option value="">All difficulties</option>
          <option value="introductory">Introductory</option>
          <option value="standard">Standard</option>
          <option value="advanced">Advanced</option>
        </select>
        <input
          type="search"
          placeholder="Search statement / solution…"
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          className="flex-1 min-w-[200px] border border-gray-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
        />
      </div>

      {isLoading && <p className="text-gray-500 py-12 text-center">Loading…</p>}

      {!isLoading && examples.length === 0 && (
        <div className="text-center py-16 bg-white border border-gray-200 rounded-lg">
          <p className="text-lg font-semibold text-gray-700 mb-1">
            No examples yet
          </p>
          <p className="text-sm text-gray-400">
            {isAuthenticated
              ? 'Be the first to submit one.'
              : 'Sign in to contribute.'}
          </p>
        </div>
      )}

      <div className="space-y-3">
        {examples.map((ex) => (
          <Link
            key={ex.id}
            to={`/examples/${ex.id}`}
            className="block bg-white border border-gray-200 rounded-lg p-4 hover:border-blue-300 hover:shadow-sm transition"
          >
            <div className="flex items-start justify-between gap-3 mb-2">
              <div className="flex flex-wrap items-center gap-2">
                <span
                  className={`text-xs font-medium px-2 py-0.5 rounded-full ${DIFFICULTY_BADGE[ex.difficulty]}`}
                >
                  {DIFFICULTY_LABEL[ex.difficulty]}
                </span>
                {ex.chapters.map((ch) => (
                  <span
                    key={ch.id}
                    className="text-xs font-mono bg-gray-100 text-gray-700 px-2 py-0.5 rounded"
                  >
                    {ch.chabbr}
                  </span>
                ))}
              </div>
              <span className="text-xs text-gray-400 shrink-0">
                by {ex.author_display}
              </span>
            </div>
            <StatementPreview tex={ex.statement_tex} />
          </Link>
        ))}
      </div>
    </div>
  );
}
