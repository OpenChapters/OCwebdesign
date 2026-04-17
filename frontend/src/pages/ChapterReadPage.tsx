import { useParams, Link } from 'react-router-dom';
import { useQuery } from '@tanstack/react-query';
import client from '../api/client';
import type { Chapter } from '../types';

export default function ChapterReadPage() {
  const { id } = useParams<{ id: string }>();

  const { data: chapter, isLoading } = useQuery({
    queryKey: ['chapter', id],
    queryFn: () => client.get<Chapter>(`/chapters/${id}/`).then((r) => r.data),
  });

  if (isLoading) {
    return (
      <div className="flex items-center justify-center min-h-screen bg-gray-50">
        <p className="text-gray-500">Loading...</p>
      </div>
    );
  }

  if (!chapter || !chapter.html_built_at) {
    return (
      <div className="flex items-center justify-center min-h-screen bg-gray-50">
        <div className="text-center">
          <p className="text-gray-500 mb-4">HTML version not available for this chapter.</p>
          <Link to={`/chapters/${id}`} className="text-blue-600 hover:underline text-sm">
            Back to chapter info
          </Link>
        </div>
      </div>
    );
  }

  return (
    <div className="flex flex-col h-screen bg-gray-50">
      {/* Top bar */}
      <div className="bg-white border-b border-gray-200 px-4 py-2 flex items-center gap-4 shrink-0">
        <Link
          to={`/chapters/${id}`}
          className="text-sm text-gray-500 hover:text-gray-700"
        >
          &larr; Chapter Info
        </Link>
        <h1 className="text-sm font-semibold text-gray-900 truncate">
          {chapter.title}
        </h1>
        {chapter.discipline && (
          <span
            className="text-xs px-1.5 py-0.5 rounded text-white shrink-0"
            style={{ backgroundColor: chapter.discipline.color_primary }}
          >
            {chapter.discipline.name}
          </span>
        )}
      </div>

      {/* iframe containing lwarp HTML */}
      <iframe
        src={`/api/chapters/${id}/html/node-1.html`}
        title={chapter.title}
        style={{ width: '100%', height: 'calc(100vh - 48px)', border: 'none' }}
      />
    </div>
  );
}
