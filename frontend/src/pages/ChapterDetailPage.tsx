import { useState, useEffect, useCallback } from 'react';
import { useParams, Link, useNavigate, useLocation } from 'react-router-dom';
import { useQuery } from '@tanstack/react-query';
import { chaptersApi } from '../api/chapters';
import { booksApi } from '../api/books';
import { useAuth } from '../contexts/AuthContext';
import type { BookListItem } from '../types';
import { useToast } from '../components/Toast';

export default function ChapterDetailPage() {
  const toast = useToast();
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const { isAuthenticated } = useAuth();

  const location = useLocation();
  const openAddOnLoad = !!(location.state as any)?.addToBook;

  const { data: chapter, isLoading } = useQuery({
    queryKey: ['chapter', id],
    queryFn: () => chaptersApi.detail(parseInt(id!)),
  });

  const { data: books = [] } = useQuery({
    queryKey: ['books'],
    queryFn: booksApi.list,
    enabled: isAuthenticated,
  });

  const [showAdd, setShowAdd] = useState(false);
  const [adding, setAdding] = useState(false);
  const [imgFailed, setImgFailed] = useState(false);

  useEffect(() => {
    if (openAddOnLoad && isAuthenticated && chapter) setShowAdd(true);
  }, [openAddOnLoad, isAuthenticated, chapter?.id]);

  const draftBooks = books.filter((b: BookListItem) => b.status === 'draft');

  async function addToBook(bookId: number) {
    if (!chapter) return;
    setAdding(true);
    try {
      const book = await booksApi.detail(bookId);
      if (book.parts.length === 0) {
        await booksApi.addPart(bookId, { title: 'Part I', order: 0 });
        const updated = await booksApi.detail(bookId);
        await booksApi.addChapter(bookId, updated.parts[0].id, {
          chapter_id: chapter.id,
          order: 0,
        });
      } else {
        const firstPart = book.parts[0];
        await booksApi.addChapter(bookId, firstPart.id, {
          chapter_id: chapter.id,
          order: firstPart.chapters.length,
        });
      }
      navigate(`/books/${bookId}`);
    } catch {
      toast('Could not add chapter. It may already be in this book.', 'error');
    } finally {
      setAdding(false);
      setShowAdd(false);
    }
  }

  async function createBookAndAdd() {
    if (!chapter) return;
    setAdding(true);
    try {
      const book = await booksApi.create('Untitled Book');
      await booksApi.addPart(book.id, { title: 'Part I', order: 0 });
      const updated = await booksApi.detail(book.id);
      await booksApi.addChapter(book.id, updated.parts[0].id, {
        chapter_id: chapter.id,
        order: 0,
      });
      navigate(`/books/${book.id}`);
    } catch {
      toast('Could not create book.', 'error');
    } finally {
      setAdding(false);
    }
  }

  if (isLoading) {
    return <div className="text-center text-gray-500 py-16">Loading…</div>;
  }
  if (!chapter) {
    return <div className="text-center text-red-600 py-16">Chapter not found.</div>;
  }

  return (
    <div className="max-w-3xl mx-auto px-6 py-8">
      <Link to="/chapters" className="text-sm text-gray-400 hover:text-gray-600">
        ← Back to browser
      </Link>

      <div className="mt-6 bg-white border border-gray-200 rounded-xl shadow-sm overflow-hidden">
        {chapter.cover_image_url && !imgFailed ? (
          <img
            src={`/api/chapters/${chapter.id}/cover/?v=${new Date(chapter.cached_at).getTime()}`}
            alt={chapter.title}
            className="w-full h-48 object-cover"
            onError={() => setImgFailed(true)}
          />
        ) : (
          <div className="w-full h-48 bg-gradient-to-br from-blue-50 to-blue-100 flex items-center justify-center">
            <span className="text-6xl">📖</span>
          </div>
        )}

        <div className="p-6">
          <div className="flex items-start justify-between gap-4">
            <div>
              <h1 className="text-2xl font-bold text-gray-900">{chapter.title}</h1>
              {chapter.authors.length > 0 && (
                <p className="text-sm text-gray-500 mt-1">{chapter.authors.join(', ')}</p>
              )}
            </div>
            <span
              className={`shrink-0 text-xs px-2.5 py-1 rounded-full font-medium ${
                chapter.chapter_type === 'foundational'
                  ? 'bg-blue-100 text-blue-800'
                  : 'bg-purple-100 text-purple-800'
              }`}
            >
              {chapter.chapter_type}
            </span>
          </div>

          {chapter.description && (
            <p className="text-sm text-gray-600 mt-4 leading-relaxed">{chapter.description}</p>
          )}

          {chapter.keywords.length > 0 && (
            <div className="flex flex-wrap gap-1.5 mt-4">
              {chapter.keywords.map((kw) => (
                <span
                  key={kw}
                  className="text-xs bg-gray-100 text-gray-600 px-2 py-0.5 rounded"
                >
                  {kw}
                </span>
              ))}
            </div>
          )}

          {chapter.toc.length > 0 && (
            <div className="mt-6">
              <h2 className="text-sm font-semibold text-gray-700 mb-2">Table of Contents</h2>
              <ol className="list-decimal list-inside text-sm text-gray-600 space-y-1">
                {chapter.toc.map((item, i) => (
                  <li key={i}>{item}</li>
                ))}
              </ol>
            </div>
          )}

          {chapter.depends_on.length > 0 && (
            <div className="mt-6">
              <h2 className="text-sm font-semibold text-gray-700 mb-1">
                Depends on foundational chapters
              </h2>
              <p className="text-xs text-gray-500">
                {chapter.depends_on.join(', ')}
              </p>
            </div>
          )}

          {/* Add to Book */}
          <div className="mt-8 pt-6 border-t border-gray-100">
            {isAuthenticated ? (
              <div className="relative">
                <button
                  onClick={() => setShowAdd(!showAdd)}
                  className="bg-blue-600 text-white text-sm px-5 py-2 rounded-lg hover:bg-blue-700"
                >
                  + Add to Book
                </button>

                {showAdd && (
                  <div className="absolute left-0 top-full mt-2 bg-white border border-gray-200 rounded-lg shadow-lg p-3 z-10 w-72">
                    <p className="text-xs font-semibold text-gray-500 uppercase tracking-wide mb-2">
                      Choose a book
                    </p>
                    {draftBooks.length > 0 && (
                      <div className="space-y-1 mb-3">
                        {draftBooks.map((b: BookListItem) => (
                          <button
                            key={b.id}
                            onClick={() => addToBook(b.id)}
                            disabled={adding}
                            className="w-full text-left text-sm text-gray-800 hover:bg-gray-50 rounded px-2 py-1.5 disabled:opacity-50"
                          >
                            {b.title}
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
            ) : (
              <Link
                to="/login"
                className="text-sm text-blue-600 hover:underline"
              >
                Sign in to add this chapter to a book
              </Link>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}