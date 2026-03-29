import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import type { Chapter } from '../types';

interface Props {
  chapter: Chapter;
  onAdd?: (chapterId: number) => void;
  addLabel?: string;
  addDisabled?: boolean;
  showBrowserButtons?: boolean;
  onAddToBook?: (chapterId: number) => void;
}

export default function ChapterCard({
  chapter,
  onAdd,
  addLabel = '+ Add to Part',
  addDisabled = false,
  showBrowserButtons = false,
  onAddToBook,
}: Props) {
  const navigate = useNavigate();
  const [imgStatus, setImgStatus] = useState<'loading' | 'loaded' | 'error'>('loading');
  const cacheBust = chapter.cached_at ? `?v=${new Date(chapter.cached_at).getTime()}` : '';
  const coverUrl = chapter.cover_image_url ? `/api/chapters/${chapter.id}/cover/${cacheBust}` : '';
  const hasUrl = !!coverUrl;

  return (
    <div className="relative group flex flex-col">
      {/* TOC popover on hover */}
      {chapter.toc.length > 0 && (
        <div className="absolute z-20 left-0 right-0 bottom-full mb-2 bg-white border border-gray-200 rounded-lg shadow-lg p-3 hidden group-hover:block pointer-events-none">
          <p className="text-xs font-semibold text-gray-700 mb-1">Contents</p>
          <ul className="text-xs text-gray-600 space-y-0.5">
            {chapter.toc.map((item, i) => (
              <li key={i} className="truncate">· {item}</li>
            ))}
          </ul>
        </div>
      )}

      <div className="bg-white rounded-lg border border-gray-200 shadow-sm hover:shadow-md transition-shadow flex flex-col h-full">
        <div className="relative w-full h-28 rounded-t-lg overflow-hidden bg-gradient-to-br from-blue-50 to-blue-100">
          {hasUrl && imgStatus !== 'error' && (
            <img
              src={coverUrl}
              alt={chapter.title}
              loading="eager"
              className={`absolute inset-0 w-full h-full object-cover transition-opacity duration-300 ${
                imgStatus === 'loaded' ? 'opacity-100' : 'opacity-0'
              }`}
              onLoad={() => setImgStatus('loaded')}
              onError={() => setImgStatus('error')}
            />
          )}
          {(imgStatus !== 'loaded' || !hasUrl) && (
            <div className="absolute inset-0 flex items-center justify-center">
              <span className="text-4xl">📖</span>
            </div>
          )}
        </div>

        <div className="p-3 flex flex-col flex-1 gap-1">
          <h3 className="font-semibold text-sm text-gray-900 line-clamp-2 leading-snug">
            {chapter.title}
          </h3>
          {chapter.authors.length > 0 && (
            <p className="text-xs text-gray-500 truncate">{chapter.authors.join(', ')}</p>
          )}
          {chapter.keywords.length > 0 && (
            <div className="flex flex-wrap gap-1 mt-1">
              {chapter.keywords.slice(0, 3).map((kw) => (
                <span
                  key={kw}
                  className="text-xs bg-gray-100 text-gray-600 px-1.5 py-0.5 rounded"
                >
                  {kw}
                </span>
              ))}
            </div>
          )}
        </div>

        {/* Book Editor mode: single Add button */}
        {onAdd && (
          <div className="px-3 pb-3">
            <button
              onClick={() => !addDisabled && onAdd(chapter.id)}
              disabled={addDisabled}
              className={`w-full text-xs px-2 py-1.5 rounded transition-colors ${
                addDisabled
                  ? 'bg-green-100 text-green-700 cursor-default'
                  : 'bg-blue-600 text-white hover:bg-blue-700'
              }`}
            >
              {addLabel}
            </button>
          </div>
        )}

        {/* Browser mode: View + Add to Book buttons */}
        {showBrowserButtons && !onAdd && (
          <div className="px-3 pb-3 flex gap-2">
            <button
              onClick={() => navigate(`/chapters/${chapter.id}`)}
              className="flex-1 text-xs border border-gray-300 text-gray-700 px-2 py-1.5 rounded hover:bg-gray-50 transition-colors"
            >
              View
            </button>
            <button
              onClick={() =>
                onAddToBook
                  ? onAddToBook(chapter.id)
                  : navigate(`/chapters/${chapter.id}`, { state: { addToBook: true } })
              }
              className="flex-1 text-xs bg-blue-600 text-white px-2 py-1.5 rounded hover:bg-blue-700 transition-colors"
            >
              + Add to Book
            </button>
          </div>
        )}
      </div>
    </div>
  );
}
