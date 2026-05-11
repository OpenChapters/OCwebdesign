import { useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { useQuery } from '@tanstack/react-query';
import { booksApi } from '../api/books';
import { useAuth } from '../contexts/AuthContext';
import { useToast } from '../components/Toast';

export default function CommunityPage() {
  const navigate = useNavigate();
  const toast = useToast();
  const { isAuthenticated } = useAuth();
  const [cloningId, setCloningId] = useState<number | null>(null);

  const { data: books = [], isLoading } = useQuery({
    queryKey: ['library-public'],
    queryFn: () => booksApi.publicLibrary(),
    staleTime: 60_000,
  });

  async function handleClone(bookId: number) {
    setCloningId(bookId);
    try {
      const result = await booksApi.clonePublicBook(bookId);
      toast('Book cloned to your drafts.', 'success');
      navigate(`/books/${result.id}`);
    } catch (err: any) {
      toast(err?.response?.data?.detail || 'Could not clone book.', 'error');
    } finally {
      setCloningId(null);
    }
  }

  return (
    <div className="max-w-4xl mx-auto px-4 sm:px-6 py-6 sm:py-8">
      <div className="mb-6">
        <h1 className="text-2xl font-bold text-gray-900 dark:text-gray-50 mb-2">Community library</h1>
        <p className="text-sm text-gray-600 dark:text-gray-300">
          Books built by other contributors who chose to share them. Each entry shows
          the book's structure and chapters; PDFs and HTML readers are private to the
          original author. To share your own builds, enable visibility on your{' '}
          <Link to="/profile" className="text-blue-600 dark:text-blue-400 hover:underline">profile</Link>.
        </p>
      </div>

      {isLoading ? (
        <p className="text-gray-500 dark:text-gray-400 py-8 text-center">Loading…</p>
      ) : books.length === 0 ? (
        <div className="text-center py-16">
          <p className="text-4xl mb-3">📚</p>
          <p className="text-lg font-semibold text-gray-700 dark:text-gray-200 mb-1">Nothing here yet</p>
          <p className="text-sm text-gray-400 dark:text-gray-500">
            No one has chosen to share their builds at this time.
          </p>
        </div>
      ) : (
        <div className="flex flex-col gap-4">
          {books.map((book) => (
            <article
              key={book.id}
              className="bg-white dark:bg-gray-800 border border-gray-200 dark:border-gray-700 rounded-lg p-5"
            >
              <div className="flex items-start justify-between gap-4 mb-3">
                <div>
                  <h2 className="text-lg font-semibold text-gray-900 dark:text-gray-50">{book.title}</h2>
                  <p className="text-xs text-gray-500 dark:text-gray-400 mt-0.5">
                    by {book.author_display} · built{' '}
                    {new Date(book.updated_at).toLocaleDateString()}
                  </p>
                </div>
                {isAuthenticated ? (
                  <button
                    onClick={() => handleClone(book.id)}
                    disabled={cloningId === book.id}
                    className="shrink-0 text-sm bg-blue-600 text-white px-4 py-2 rounded-lg hover:bg-blue-700 disabled:opacity-50"
                    title="Copy this book's parts and chapters into a new draft you can edit and rebuild as your own."
                  >
                    {cloningId === book.id ? 'Cloning…' : 'Clone to my books'}
                  </button>
                ) : (
                  <Link
                    to="/login"
                    className="shrink-0 text-sm text-blue-600 dark:text-blue-400 hover:underline"
                  >
                    Sign in to clone
                  </Link>
                )}
              </div>

              {book.parts.length > 0 && (
                <div className="space-y-3">
                  {book.parts.map((part) => (
                    <div key={part.order}>
                      <p className="text-xs font-semibold text-gray-500 dark:text-gray-400 uppercase tracking-wide mb-1">
                        {part.title}
                      </p>
                      <ul className="text-sm text-gray-700 dark:text-gray-200 space-y-0.5 pl-3">
                        {part.chapters.map((ch) => (
                          <li key={ch.id} className="flex items-baseline gap-2">
                            <Link
                              to={`/chapters/${ch.id}`}
                              className="text-blue-600 dark:text-blue-400 hover:underline"
                            >
                              {ch.title}
                            </Link>
                            {ch.chabbr && (
                              <span className="text-xs font-mono text-gray-400 dark:text-gray-500">
                                {ch.chabbr}
                              </span>
                            )}
                          </li>
                        ))}
                      </ul>
                    </div>
                  ))}
                </div>
              )}
            </article>
          ))}
        </div>
      )}
    </div>
  );
}
