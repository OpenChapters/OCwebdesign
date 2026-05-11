import {
  SortableContext,
  useSortable,
  verticalListSortingStrategy,
} from '@dnd-kit/sortable';
import { useDroppable } from '@dnd-kit/core';
import { CSS } from '@dnd-kit/utilities';
import type { BookChapter } from '../types';

export function SortableItem({
  bookChapter,
  onRemove,
}: {
  bookChapter: BookChapter;
  onRemove: () => void;
}) {
  const { attributes, listeners, setNodeRef, transform, transition, isDragging } = useSortable({
    id: bookChapter.id,
    data: { type: 'chapter', partId: bookChapter.id },
  });
  const style = {
    transform: CSS.Transform.toString(transform),
    transition,
    opacity: isDragging ? 0.4 : 1,
  };
  return (
    <div
      ref={setNodeRef}
      style={style}
      className="flex items-center gap-2 bg-white dark:bg-gray-800 border border-gray-200 dark:border-gray-700 rounded px-3 py-2 text-sm"
    >
      <span
        {...attributes}
        {...listeners}
        role="button"
        tabIndex={0}
        aria-label={`Drag handle for ${bookChapter.chapter_detail.title} — use the keyboard to reorder or move between parts`}
        className="cursor-grab text-gray-300 hover:text-gray-500 dark:hover:text-gray-400 select-none focus:outline-none focus:ring-2 focus:ring-blue-500 rounded"
      >
        <span aria-hidden="true">⠿</span>
      </span>
      <span className="flex-1 truncate text-gray-800 dark:text-gray-100">{bookChapter.chapter_detail.title}</span>
      <button
        onClick={onRemove}
        aria-label={`Remove chapter "${bookChapter.chapter_detail.title}" from this part`}
        className="text-gray-300 hover:text-red-500 dark:hover:text-red-400 transition-colors font-bold text-base leading-none focus:outline-none focus:ring-2 focus:ring-red-500 rounded px-1"
      >
        <span aria-hidden="true">×</span>
      </button>
    </div>
  );
}

interface Props {
  partId: number;
  chapters: BookChapter[];
  onRemove: (bcId: number) => void;
}

export default function SortableChapterList({ partId, chapters, onRemove }: Props) {
  // Make the part itself a drop target so chapters can be dropped into empty parts
  const { setNodeRef, isOver } = useDroppable({ id: `part-${partId}` });

  return (
    <div
      ref={setNodeRef}
      className={`flex flex-col gap-1 min-h-[2rem] rounded transition-colors ${
        isOver ? 'bg-blue-50 dark:bg-blue-950/40' : ''
      }`}
    >
      <SortableContext items={chapters.map((c) => c.id)} strategy={verticalListSortingStrategy}>
        {chapters.length === 0 ? (
          <p className="text-xs text-gray-400 dark:text-gray-500 italic py-2 text-center">
            Drop chapters here, or add from the catalog.
          </p>
        ) : (
          chapters.map((bc) => (
            <SortableItem key={bc.id} bookChapter={bc} onRemove={() => onRemove(bc.id)} />
          ))
        )}
      </SortableContext>
    </div>
  );
}
