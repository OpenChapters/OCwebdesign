import { useState, useEffect, FormEvent } from 'react';
import { useParams, useNavigate, Link } from 'react-router-dom';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import {
  DndContext,
  closestCorners,
  KeyboardSensor,
  PointerSensor,
  useSensor,
  useSensors,
  DragEndEvent,
} from '@dnd-kit/core';
import { sortableKeyboardCoordinates, arrayMove } from '@dnd-kit/sortable';
import { booksApi } from '../api/books';
import { chaptersApi } from '../api/chapters';
import ChapterCard from '../components/ChapterCard';
import SortableChapterList from '../components/SortableChapterList';
import type { BookPart, Chapter } from '../types';
import { useToast } from '../components/Toast';

export default function BookEditorPage() {
  const toast = useToast();
  const { id } = useParams<{ id: string }>();
  const bookId = parseInt(id!);
  const navigate = useNavigate();
  const queryClient = useQueryClient();

  const [editingTitle, setEditingTitle] = useState(false);
  const [bookTitle, setBookTitle] = useState('');
  const [newPartTitle, setNewPartTitle] = useState('');
  const [editingPartId, setEditingPartId] = useState<number | null>(null);
  const [editingPartTitle, setEditingPartTitle] = useState('');
  const [activePart, setActivePart] = useState<number | null>(null);
  const [chapterSearch, setChapterSearch] = useState('');
  const [suggestions, setSuggestions] = useState<Chapter[]>([]);
  const [building, setBuilding] = useState(false);
  const [showPreview, setShowPreview] = useState(false);

  const sensors = useSensors(
    useSensor(PointerSensor, { activationConstraint: { distance: 5 } }),
    useSensor(KeyboardSensor, { coordinateGetter: sortableKeyboardCoordinates }),
  );

  const { data: book, isLoading: bookLoading } = useQuery({
    queryKey: ['book', bookId],
    queryFn: () => booksApi.detail(bookId),
  });

  const { data: chaptersData } = useQuery({
    queryKey: ['chapters'],
    queryFn: () => chaptersApi.list(),
  });

  useEffect(() => {
    if (book) {
      setBookTitle(book.title);
      if (book.parts.length > 0 && activePart === null) {
        setActivePart(book.parts[0].id);
      }
    }
  }, [book?.id, book?.title]);

  async function refresh() {
    await queryClient.resetQueries({ queryKey: ['book', bookId] });
  }

  // ── DnD: cross-part and within-part ─────────────────────────────────────

  function findPartForItem(itemId: number | string): BookPart | undefined {
    if (!book) return undefined;
    // Check if it's a part droppable ID
    if (typeof itemId === 'string' && itemId.startsWith('part-')) {
      const partId = parseInt(itemId.replace('part-', ''));
      return book.parts.find((p) => p.id === partId);
    }
    // Otherwise it's a BookChapter ID
    return book.parts.find((p) => p.chapters.some((c) => c.id === itemId));
  }

  async function handleDragEnd(event: DragEndEvent) {
    const { active, over } = event;
    if (!over || !book) return;

    const activeId = active.id as number;
    const sourcePart = findPartForItem(activeId);
    if (!sourcePart) return;

    const destPart = findPartForItem(over.id);
    if (!destPart) return;

    if (sourcePart.id === destPart.id) {
      // Same part → reorder
      if (active.id === over.id) return;
      const oldIndex = sourcePart.chapters.findIndex((c) => c.id === activeId);
      const overIndex = sourcePart.chapters.findIndex((c) => c.id === over.id);
      if (oldIndex === -1 || overIndex === -1) return;
      const newOrder = arrayMove(sourcePart.chapters, oldIndex, overIndex).map((c) => c.id);
      try {
        await booksApi.reorderChapters(bookId, sourcePart.id, newOrder);
        await queryClient.refetchQueries({ queryKey: ['book', bookId] });
      } catch (e) {
        console.error('Reorder failed', e);
      }
    } else {
      // Different part → move chapter
      const bc = sourcePart.chapters.find((c) => c.id === activeId);
      if (!bc) return;
      try {
        // Remove from source
        await booksApi.removeChapter(bookId, sourcePart.id, activeId);
        // Append to destination using a safe order value (max + 1)
        const maxOrder = destPart.chapters.reduce((m, c) => Math.max(m, c.order), -1);
        await booksApi.addChapter(bookId, destPart.id, {
          chapter_id: bc.chapter_detail.id,
          order: maxOrder + 1,
        });
        refresh();
      } catch (e) {
        console.error('Move failed', e);
        refresh();
      }
    }
  }

  // ── Remove chapter ──────────────────────────────────────────────────────

  async function removeChapter(partId: number, bcId: number) {
    try {
      await booksApi.removeChapter(bookId, partId, bcId);
      refresh();
    } catch (e) {
      console.error('Remove failed', e);
    }
  }

  // ── Title editing ───────────────────────────────────────────────────────

  async function saveTitle() {
    if (!bookTitle.trim()) return;
    await booksApi.update(bookId, { title: bookTitle.trim() });
    setEditingTitle(false);
    refresh();
  }

  // ── Parts ───────────────────────────────────────────────────────────────

  async function addPart(e: FormEvent) {
    e.preventDefault();
    if (!newPartTitle.trim()) return;
    const order = book?.parts.length ?? 0;
    await booksApi.addPart(bookId, { title: newPartTitle.trim(), order });
    setNewPartTitle('');
    refresh();
  }

  async function savePart(part: BookPart) {
    if (!editingPartTitle.trim()) return;
    await booksApi.updatePart(bookId, part.id, { title: editingPartTitle.trim() });
    setEditingPartId(null);
    refresh();
  }

  async function deletePart(partId: number) {
    if (!confirm('Remove this part and all its chapters from the book?')) return;
    await booksApi.deletePart(bookId, partId);
    if (activePart === partId) setActivePart(null);
    refresh();
  }

  async function movePartUp(partId: number) {
    if (!book) return;
    const idx = book.parts.findIndex((p) => p.id === partId);
    if (idx <= 0) return;
    const newOrder = book.parts.map((p) => p.id);
    [newOrder[idx - 1], newOrder[idx]] = [newOrder[idx], newOrder[idx - 1]];
    await booksApi.reorderParts(bookId, newOrder);
    refresh();
  }

  async function movePartDown(partId: number) {
    if (!book) return;
    const idx = book.parts.findIndex((p) => p.id === partId);
    if (idx < 0 || idx >= book.parts.length - 1) return;
    const newOrder = book.parts.map((p) => p.id);
    [newOrder[idx], newOrder[idx + 1]] = [newOrder[idx + 1], newOrder[idx]];
    await booksApi.reorderParts(bookId, newOrder);
    refresh();
  }

  // ── Adding chapters ─────────────────────────────────────────────────────

  function computeMissingSuggestions(addedIds: Set<number>) {
    const catalog = chaptersData?.results ?? [];
    const abbrToChapter = new Map(catalog.map((c) => [c.chabbr, c]));
    const neededAbbrs = new Set<string>();
    for (const ch of catalog) {
      if (addedIds.has(ch.id) && ch.depends_on.length > 0) {
        for (const abbr of ch.depends_on) neededAbbrs.add(abbr);
      }
    }
    const missing: Chapter[] = [];
    for (const abbr of neededAbbrs) {
      const dep = abbrToChapter.get(abbr);
      if (dep && dep.chapter_type === 'foundational' && !addedIds.has(dep.id)) {
        missing.push(dep);
      }
    }
    return missing;
  }

  async function addChapter(chapterId: number) {
    if (!activePart) {
      toast('Please select a part first (click a part name on the right).', 'info');
      return;
    }
    const part = book?.parts.find((p) => p.id === activePart);
    const order = part?.chapters.length ?? 0;
    try {
      await booksApi.addChapter(bookId, activePart, { chapter_id: chapterId, order });
      const updatedIds = new Set(addedChapterIds);
      updatedIds.add(chapterId);
      setSuggestions(computeMissingSuggestions(updatedIds));
      refresh();
    } catch (err: any) {
      const msg = err?.response?.data?.non_field_errors?.[0] ?? 'Could not add chapter.';
      toast(msg, 'error');
    }
  }

  const FOUNDATIONAL_PART_TITLE = 'Foundational Material';

  async function getOrCreateFoundationalPart(): Promise<number> {
    // Check if a "Foundational Material" part already exists
    const existing = book?.parts.find((p) => p.title === FOUNDATIONAL_PART_TITLE);
    if (existing) return existing.id;
    // Create it as the last part
    const order = book?.parts.length ?? 0;
    const part = await booksApi.addPart(bookId, { title: FOUNDATIONAL_PART_TITLE, order });
    return part.id;
  }

  async function addSuggestedChapter(chapterId: number) {
    try {
      const partId = await getOrCreateFoundationalPart();
      // Refresh to get the latest part state (may have just been created)
      const freshBook = await booksApi.detail(bookId);
      const part = freshBook.parts.find((p) => p.id === partId);
      const maxOrder = part ? part.chapters.reduce((m, c) => Math.max(m, c.order), -1) : -1;
      await booksApi.addChapter(bookId, partId, { chapter_id: chapterId, order: maxOrder + 1 });
      setSuggestions((prev) => prev.filter((c) => c.id !== chapterId));
      refresh();
    } catch { /* skip duplicates */ }
  }

  async function addAllSuggestions() {
    try {
      const partId = await getOrCreateFoundationalPart();
      const freshBook = await booksApi.detail(bookId);
      const part = freshBook.parts.find((p) => p.id === partId);
      let order = part ? part.chapters.reduce((m, c) => Math.max(m, c.order), -1) + 1 : 0;
      for (const ch of suggestions) {
        try {
          await booksApi.addChapter(bookId, partId, { chapter_id: ch.id, order: order++ });
        } catch { /* skip duplicates */ }
      }
      setSuggestions([]);
      refresh();
    } catch { /* skip */ }
  }

  // ── Build ───────────────────────────────────────────────────────────────

  const [buildStatus, setBuildStatus] = useState<string | null>(null);

  // Poll build status when a build is active
  const { data: buildData } = useQuery({
    queryKey: ['build-poll', bookId],
    queryFn: () => booksApi.getBuildStatus(bookId),
    enabled: buildStatus === 'queued' || buildStatus === 'building',
    refetchInterval: 3000,
  });

  // Update buildStatus from polling data
  useEffect(() => {
    if (buildData?.status) {
      setBuildStatus(buildData.status);
      if (buildData.status === 'complete') {
        toast('Build complete! Your PDF is ready.', 'success');
        refresh();
      } else if (buildData.status === 'failed') {
        toast('Build failed. Check the build status page for details.', 'error');
      }
    }
  }, [buildData?.status]);

  // Also pick up status from the book query
  useEffect(() => {
    if (book && (book.status === 'queued' || book.status === 'building')) {
      setBuildStatus(book.status);
    }
  }, [book?.status]);

  async function triggerBuild() {
    if (!confirm('Start building this book? This may take a few minutes.')) return;
    setBuilding(true);
    try {
      await booksApi.triggerBuild(bookId);
      setBuildStatus('queued');
      toast('Build queued.', 'info');
    } catch (err: any) {
      toast(err?.response?.data?.detail ?? 'Build failed to start.', 'error');
    } finally {
      setBuilding(false);
    }
  }

  // ── Derived data ────────────────────────────────────────────────────────

  const allChapters = chaptersData?.results ?? [];
  const filteredChapters = chapterSearch.trim()
    ? allChapters.filter(
        (c) =>
          c.title.toLowerCase().includes(chapterSearch.toLowerCase()) ||
          c.authors.some((a) => a.toLowerCase().includes(chapterSearch.toLowerCase())),
      )
    : allChapters;

  const addedChapterIds = new Set(
    book?.parts.flatMap((p) => p.chapters.map((bc) => bc.chapter_detail.id)) ?? [],
  );

  // ── Render ──────────────────────────────────────────────────────────────

  if (bookLoading) return <div className="text-center text-gray-500 py-16">Loading…</div>;
  if (!book) return <div className="text-center text-red-600 py-16">Book not found.</div>;

  const chapterCount = book.parts.reduce((sum, p) => sum + p.chapters.length, 0);
  const canBuild = chapterCount > 0 && book.status !== 'building' && book.status !== 'queued';

  return (
    <div className="flex flex-col h-screen overflow-hidden">
      {/* Header */}
      <div className="bg-white border-b border-gray-200 px-6 py-4 flex items-center gap-4">
        <Link to="/books" className="text-sm text-gray-400 hover:text-gray-600">← My Books</Link>
        <div className="flex-1">
          {editingTitle ? (
            <div className="flex items-center gap-2">
              <input
                autoFocus value={bookTitle}
                onChange={(e) => setBookTitle(e.target.value)}
                onKeyDown={(e) => e.key === 'Enter' && saveTitle()}
                className="border border-blue-400 rounded px-2 py-1 text-base font-bold focus:outline-none"
              />
              <button onClick={saveTitle} className="text-sm text-blue-600 hover:underline">Save</button>
              <button onClick={() => { setEditingTitle(false); setBookTitle(book.title); }} className="text-sm text-gray-400 hover:text-gray-600">Cancel</button>
            </div>
          ) : (
            <button onClick={() => setEditingTitle(true)} className="text-base font-bold text-gray-900 hover:text-blue-600 text-left" title="Click to edit book title">
              {book.title} ✎
            </button>
          )}
        </div>
        <span className="text-sm text-gray-500">{chapterCount} chapters</span>

        {/* Build status indicator */}
        {buildStatus === 'queued' && (
          <span className="text-xs bg-yellow-100 text-yellow-800 px-3 py-1.5 rounded-full font-medium animate-pulse">
            Queued…
          </span>
        )}
        {buildStatus === 'building' && (
          <span className="text-xs bg-blue-100 text-blue-800 px-3 py-1.5 rounded-full font-medium animate-pulse">
            Building…
          </span>
        )}
        {buildStatus === 'complete' && (
          <Link to={`/books/${bookId}/status`} className="text-xs bg-green-100 text-green-800 px-3 py-1.5 rounded-full font-medium hover:bg-green-200">
            PDF Ready — View
          </Link>
        )}
        {buildStatus === 'failed' && (
          <Link to={`/books/${bookId}/status`} className="text-xs bg-red-100 text-red-800 px-3 py-1.5 rounded-full font-medium hover:bg-red-200">
            Build Failed — View
          </Link>
        )}

        <button
          onClick={() => setShowPreview(!showPreview)}
          className="text-sm border border-gray-300 text-gray-700 px-4 py-2 rounded-lg hover:bg-gray-50"
        >
          {showPreview ? 'Hide Preview' : 'Preview TOC'}
        </button>
        <button onClick={triggerBuild} disabled={!canBuild || building || buildStatus === 'queued' || buildStatus === 'building'} className="bg-blue-600 text-white text-sm px-5 py-2 rounded-lg hover:bg-blue-700 disabled:opacity-40">
          {building ? 'Starting…' : 'Build PDF'}
        </button>
      </div>

      {/* TOC Preview panel */}
      {showPreview && (
        <div className="bg-white border-b border-gray-200 px-6 py-4 max-h-64 overflow-y-auto">
          <p className="text-xs font-semibold text-gray-500 uppercase tracking-wide mb-3">Book Preview</p>
          <div className="text-sm">
            <p className="font-bold text-gray-900 mb-2">{book.title}</p>
            {book.parts.length === 0 ? (
              <p className="text-gray-400 italic">No parts added yet.</p>
            ) : (
              book.parts.map((part, pi) => (
                <div key={part.id} className="mb-2">
                  <p className="font-semibold text-gray-700">
                    Part {pi + 1}: {part.title}
                  </p>
                  {part.chapters.length === 0 ? (
                    <p className="text-gray-400 italic text-xs ml-4">No chapters</p>
                  ) : (
                    <ol className="ml-4 text-gray-600 list-decimal list-inside">
                      {part.chapters.map((bc) => (
                        <li key={bc.id}>{bc.chapter_detail.title}</li>
                      ))}
                    </ol>
                  )}
                </div>
              ))
            )}
          </div>
        </div>
      )}

      {/* Main content */}
      <div className="flex flex-1 overflow-hidden">
        {/* Left: Chapter catalog */}
        <div className="w-2/5 border-r border-gray-200 flex flex-col overflow-hidden bg-gray-50">
          <div className="px-4 py-3 border-b border-gray-200 bg-white">
            <p className="text-xs font-semibold text-gray-500 uppercase tracking-wide mb-2">Chapter Catalog</p>
            <input
              type="search" placeholder="Search chapters…" value={chapterSearch}
              onChange={(e) => setChapterSearch(e.target.value)}
              className="w-full border border-gray-300 rounded px-3 py-1.5 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
            />
            {activePart && (
              <p className="text-xs text-blue-600 mt-2">
                Adding to: <strong>{book.parts.find((p) => p.id === activePart)?.title}</strong>
              </p>
            )}
          </div>
          <div className="flex-1 overflow-y-auto p-4">
            <div className="grid grid-cols-2 gap-3">
              {filteredChapters.map((chapter) => (
                <ChapterCard
                  key={chapter.id} chapter={chapter}
                  onAdd={addedChapterIds.has(chapter.id) ? undefined : addChapter}
                  addLabel={addedChapterIds.has(chapter.id) ? '✓ Added' : '+ Add'}
                />
              ))}
            </div>
          </div>
        </div>

        {/* Right: Book structure with cross-part DnD */}
        <div className="flex-1 flex flex-col overflow-hidden">
          <div className="px-5 py-3 border-b border-gray-200 bg-white">
            <p className="text-xs font-semibold text-gray-500 uppercase tracking-wide">Book Structure</p>
          </div>

          {/* Cover image upload */}
          <div className="mx-5 mt-4 bg-white border border-gray-200 rounded-lg p-4 flex items-center gap-4">
            <div className="flex-1">
              <p className="text-sm font-medium text-gray-700">Cover Page Image</p>
              <p className="text-xs text-gray-400 mt-0.5">
                {book.has_cover_image
                  ? 'Custom cover image uploaded.'
                  : 'Using default cover. Upload a PDF to customize.'}
              </p>
            </div>
            {book.has_cover_image ? (
              <button
                onClick={async () => {
                  await booksApi.removeCover(bookId);
                  toast('Cover image removed.', 'info');
                  refresh();
                }}
                className="text-xs text-red-600 hover:underline"
              >
                Remove
              </button>
            ) : null}
            <label className="text-xs bg-gray-100 text-gray-700 px-3 py-1.5 rounded cursor-pointer hover:bg-gray-200">
              {book.has_cover_image ? 'Replace' : 'Upload PDF'}
              <input
                type="file"
                accept=".pdf"
                className="hidden"
                onChange={async (e) => {
                  const file = e.target.files?.[0];
                  if (!file) return;
                  try {
                    await booksApi.uploadCover(bookId, file);
                    toast('Cover image uploaded.', 'success');
                    refresh();
                  } catch (err: any) {
                    toast(err?.response?.data?.detail ?? 'Upload failed.', 'error');
                  }
                  e.target.value = '';
                }}
              />
            </label>
          </div>

          {/* DOI field */}
          <div className="mx-5 mt-3 bg-white border border-gray-200 rounded-lg p-4 flex items-center gap-4">
            <p className="text-sm font-medium text-gray-700 shrink-0">DOI</p>
            <input
              type="text"
              placeholder="e.g. 10.1234/openchapters.2026"
              defaultValue={book.doi || ''}
              onBlur={async (e) => {
                const val = e.target.value;
                if (val !== (book.doi || '')) {
                  try {
                    await booksApi.update(bookId, { doi: val });
                    toast('DOI saved.', 'success');
                    refresh();
                  } catch { /* ignore */ }
                }
              }}
              className="flex-1 border border-gray-300 rounded px-3 py-1.5 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500 text-gray-600"
            />
            <p className="text-xs text-gray-400 shrink-0">(optional)</p>
          </div>

          {/* Auto-include suggestions */}
          {suggestions.length > 0 && (
            <div className="mx-5 mt-4 bg-amber-50 border border-amber-200 rounded-lg p-4">
              <div className="flex items-start justify-between gap-3">
                <div className="flex-1">
                  <p className="text-sm font-semibold text-amber-800">Required foundational chapters</p>
                  <p className="text-xs text-amber-700 mt-0.5">
                    The topical chapters you selected reference these foundational chapters.
                  </p>
                  <ul className="mt-2 space-y-1">
                    {suggestions.map((ch) => (
                      <li key={ch.id} className="flex items-center gap-2 text-sm text-amber-900">
                        <span className="flex-1">{ch.title}</span>
                        <button onClick={() => addSuggestedChapter(ch.id)} className="text-xs bg-amber-600 text-white px-2 py-0.5 rounded hover:bg-amber-700">+ Add</button>
                      </li>
                    ))}
                  </ul>
                </div>
                <div className="flex flex-col gap-1 shrink-0">
                  <button onClick={addAllSuggestions} className="text-xs bg-amber-600 text-white px-3 py-1.5 rounded hover:bg-amber-700">Add all</button>
                  <button onClick={() => setSuggestions([])} className="text-xs text-amber-600 hover:underline">Dismiss</button>
                </div>
              </div>
            </div>
          )}

          <div className="flex-1 overflow-y-auto px-5 py-4 space-y-4">
            <DndContext sensors={sensors} collisionDetection={closestCorners} onDragEnd={handleDragEnd}>
              {book.parts.map((part) => (
                <div
                  key={part.id}
                  className={`bg-white border rounded-lg overflow-hidden ${
                    activePart === part.id ? 'border-blue-400 shadow-sm' : 'border-gray-200'
                  }`}
                >
                  {/* Part header */}
                  <div
                    className="flex items-center gap-2 px-4 py-3 bg-gray-50 border-b border-gray-200 cursor-pointer"
                    onClick={() => setActivePart(part.id)}
                  >
                    {editingPartId === part.id ? (
                      <div className="flex items-center gap-2 flex-1" onClick={(e) => e.stopPropagation()}>
                        <input autoFocus value={editingPartTitle}
                          onChange={(e) => setEditingPartTitle(e.target.value)}
                          onKeyDown={(e) => e.key === 'Enter' && savePart(part)}
                          className="flex-1 border border-blue-400 rounded px-2 py-0.5 text-sm font-semibold focus:outline-none"
                        />
                        <button onClick={() => savePart(part)} className="text-xs text-blue-600 hover:underline">Save</button>
                        <button onClick={() => setEditingPartId(null)} className="text-xs text-gray-400">Cancel</button>
                      </div>
                    ) : (
                      <>
                        <span className="flex-1 text-sm font-semibold text-gray-800">
                          {part.title}
                          {activePart === part.id && <span className="ml-2 text-xs text-blue-500 font-normal">(active)</span>}
                        </span>
                        <button onClick={(e) => { e.stopPropagation(); movePartUp(part.id); }}
                          disabled={book.parts.indexOf(part) === 0}
                          className="text-xs text-gray-400 hover:text-gray-600 disabled:opacity-20" title="Move up">▲</button>
                        <button onClick={(e) => { e.stopPropagation(); movePartDown(part.id); }}
                          disabled={book.parts.indexOf(part) === book.parts.length - 1}
                          className="text-xs text-gray-400 hover:text-gray-600 disabled:opacity-20" title="Move down">▼</button>
                        <button onClick={(e) => { e.stopPropagation(); setEditingPartId(part.id); setEditingPartTitle(part.title); }}
                          className="text-xs text-gray-400 hover:text-gray-600" title="Rename part">✎</button>
                        <button onClick={(e) => { e.stopPropagation(); deletePart(part.id); }}
                          className="text-xs text-gray-400 hover:text-red-500" title="Delete part">🗑</button>
                      </>
                    )}
                  </div>

                  {/* Chapters — droppable + sortable */}
                  <div className="p-3">
                    <SortableChapterList
                      partId={part.id}
                      chapters={part.chapters}
                      onRemove={(bcId) => removeChapter(part.id, bcId)}
                    />
                  </div>
                </div>
              ))}
            </DndContext>

            {/* Add part form */}
            <form onSubmit={addPart} className="flex gap-2">
              <input type="text" placeholder="New part title…" value={newPartTitle}
                onChange={(e) => setNewPartTitle(e.target.value)}
                className="flex-1 border border-gray-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
              />
              <button type="submit" disabled={!newPartTitle.trim()}
                className="bg-gray-800 text-white text-sm px-4 py-2 rounded-lg hover:bg-gray-900 disabled:opacity-40">
                Add Part
              </button>
            </form>
          </div>
        </div>
      </div>
    </div>
  );
}