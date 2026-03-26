import { useState, useRef, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { useQuery } from '@tanstack/react-query';
import axios from 'axios';
import { chaptersApi } from '../api/chapters';
import { booksApi } from '../api/books';
import { useAuth } from '../contexts/AuthContext';
import ChapterCard from '../components/ChapterCard';
import type { Chapter, BookListItem } from '../types';
import { useToast } from '../components/Toast';

export default function ChapterBrowserPage() {
  const toast = useToast();
  const [search, setSearch] = useState('');
  const { isAuthenticated } = useAuth();
  const navigate = useNavigate();

  // Book picker state
  const [pickerChapterId, setPickerChapterId] = useState<number | null>(null);
  const [adding, setAdding] = useState(false);
  const pickerRef = useRef<HTMLDivElement>(null);

  const { data: publicSettings } = useQuery({
    queryKey: ['public-settings'],
    queryFn: () => axios.get('/api/settings/public/').then((r) => r.data),
    staleTime: 60_000,
  });

  const { data, isLoading, error } = useQuery({
    queryKey: ['chapters'],
    queryFn: () => chaptersApi.list(),
  });

  const { data: books = [] } = useQuery({
    queryKey: ['books'],
    queryFn: booksApi.list,
    enabled: isAuthenticated,
  });

  // Close picker when clicking outside
  useEffect(() => {
    function handleClick(e: MouseEvent) {
      if (pickerRef.current && !pickerRef.current.contains(e.target as Node)) {
        setPickerChapterId(null);
      }
    }
    if (pickerChapterId !== null) {
      document.addEventListener('mousedown', handleClick);
      return () => document.removeEventListener('mousedown', handleClick);
    }
  }, [pickerChapterId]);

  const chapters = data?.results ?? [];
  const lastBookId = parseInt(localStorage.getItem('last_book_id') ?? '0');
  const draftBooks = books
    .filter((b: BookListItem) => b.status === 'draft')
    .sort((a: BookListItem, b: BookListItem) => (a.id === lastBookId ? -1 : b.id === lastBookId ? 1 : 0));

  const filtered = search.trim()
    ? chapters.filter(
        (c) =>
          c.title.toLowerCase().includes(search.toLowerCase()) ||
          c.authors.some((a) => a.toLowerCase().includes(search.toLowerCase())) ||
          c.keywords.some((k) => k.toLowerCase().includes(search.toLowerCase())),
      )
    : chapters;

  const topical = filtered.filter((c) => c.chapter_type !== 'foundational');
  const foundational = filtered.filter((c) => c.chapter_type === 'foundational');

  function handleAddToBook(chapterId: number) {
    if (!isAuthenticated) {
      navigate('/login');
      return;
    }
    setPickerChapterId(chapterId);
  }

  async function addToExistingBook(bookId: number) {
    if (pickerChapterId === null) return;
    setAdding(true);
    try {
      const book = await booksApi.detail(bookId);
      if (book.parts.length === 0) {
        await booksApi.addPart(bookId, { title: 'Part I', order: 0 });
        const updated = await booksApi.detail(bookId);
        await booksApi.addChapter(bookId, updated.parts[0].id, {
          chapter_id: pickerChapterId,
          order: 0,
        });
      } else {
        const firstPart = book.parts[0];
        await booksApi.addChapter(bookId, firstPart.id, {
          chapter_id: pickerChapterId,
          order: firstPart.chapters.length,
        });
      }
      localStorage.setItem('last_book_id', String(bookId));
      setPickerChapterId(null);
      navigate(`/books/${bookId}`);
    } catch {
      toast('Could not add chapter. It may already be in this book.', 'error');
    } finally {
      setAdding(false);
    }
  }

  async function createBookAndAdd() {
    if (pickerChapterId === null) return;
    setAdding(true);
    try {
      const book = await booksApi.create('Untitled Book');
      await booksApi.addPart(book.id, { title: 'Part I', order: 0 });
      const updated = await booksApi.detail(book.id);
      await booksApi.addChapter(book.id, updated.parts[0].id, {
        chapter_id: pickerChapterId,
        order: 0,
      });
      localStorage.setItem('last_book_id', String(book.id));
      setPickerChapterId(null);
      navigate(`/books/${book.id}`);
    } catch {
      toast('Could not create book.', 'error');
    } finally {
      setAdding(false);
    }
  }

  function renderGrid(chapters: Chapter[]) {
    return (
      <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 lg:grid-cols-5 gap-4">
        {chapters.map((chapter) => (
          <div key={chapter.id} className="relative">
            <ChapterCard
              chapter={chapter}
              showBrowserButtons
              onAddToBook={handleAddToBook}
            />
            {pickerChapterId === chapter.id && (
              <div
                ref={pickerRef}
                className="absolute z-30 left-0 right-0 top-full mt-1 bg-white border border-gray-200 rounded-lg shadow-lg p-3"
              >
                <p className="text-xs font-semibold text-gray-500 uppercase tracking-wide mb-2">
                  Choose a book
                </p>
                {draftBooks.length > 0 && (
                  <div className="space-y-1 mb-2">
                    {draftBooks.map((b: BookListItem) => (
                      <button
                        key={b.id}
                        onClick={() => addToExistingBook(b.id)}
                        disabled={adding}
                        className="w-full text-left text-sm text-gray-800 hover:bg-gray-50 rounded px-2 py-1.5 disabled:opacity-50 truncate"
                      >
                        {b.title}
                        {b.id === lastBookId && (
                          <span className="ml-1 text-xs text-blue-500">(last used)</span>
                        )}
                      </button>
                    ))}
                  </div>
                )}
                <button
                  onClick={createBookAndAdd}
                  disabled={adding}
                  className="w-full text-sm text-blue-600 hover:bg-blue-50 rounded px-2 py-1.5 text-left font-medium disabled:opacity-50"
                >
                  + Create new book
                </button>
              </div>
            )}
          </div>
        ))}
      </div>
    );
  }

  const welcomeMessage = publicSettings?.welcome_message || '';
  const announcementBanner = publicSettings?.announcement_banner || '';

  return (
    <div className="max-w-7xl mx-auto px-6 py-8">
      {/* Announcement banner */}
      {announcementBanner && (
        <div className="mb-6 bg-amber-50 border border-amber-200 rounded-lg px-4 py-3 text-sm text-amber-800">
          {announcementBanner}
        </div>
      )}

      {/* Welcome banner */}
      {welcomeMessage && (
        <div className="mb-8 bg-gradient-to-r from-blue-50 to-indigo-50 border border-blue-100 rounded-xl px-6 py-5">
          <p className="text-gray-700 leading-relaxed">{welcomeMessage}</p>
        </div>
      )}

      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">Chapter Browser</h1>
          <p className="text-sm text-gray-500 mt-0.5">
            {data ? `${data.count} chapters available` : ''}
          </p>
        </div>
        <input
          type="search"
          placeholder="Search chapters…"
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          className="border border-gray-300 rounded-lg px-3 py-2 text-sm w-64 focus:outline-none focus:ring-2 focus:ring-blue-500"
        />
      </div>

      {isLoading && (
        <div className="text-center text-gray-500 py-16">Loading chapters…</div>
      )}

      {error && (
        <div className="text-center text-red-600 py-16">Failed to load chapters.</div>
      )}

      {!isLoading && filtered.length === 0 && (
        <div className="text-center text-gray-400 py-16">No chapters found.</div>
      )}

      {topical.length > 0 && (
        <section className="mb-10">
          <h2 className="text-lg font-semibold text-gray-800 mb-1">Topical Chapters</h2>
          <p className="text-sm text-gray-500 mb-4">
            Specialized topics in materials science and engineering.
          </p>
          {renderGrid(topical)}
        </section>
      )}

      {foundational.length > 0 && (
        <section>
          <h2 className="text-lg font-semibold text-gray-800 mb-1">Foundational Chapters</h2>
          <p className="text-sm text-gray-500 mb-4">
            Core mathematical and scientific background.
          </p>
          {renderGrid(foundational)}
        </section>
      )}
    </div>
  );
}