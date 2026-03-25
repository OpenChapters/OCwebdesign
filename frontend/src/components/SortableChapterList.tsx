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
      className="flex items-center gap-2 bg-white border border-gray-200 rounded px-3 py-2 text-sm"
    >
      <span
        {...attributes}
        {...listeners}
        className="cursor-grab text-gray-300 hover:text-gray-500 select-none"
        title="Drag to reorder or move to another part"
      >
        ⠿
      </span>
      <span className="flex-1 truncate text-gray-800">{bookChapter.chapter_detail.title}</span>
      <button
        onClick={onRemove}
        className="text-gray-300 hover:text-red-500 transition-colors font-bold text-base leading-none"
        title="Remove chapter"
      >
        ×
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
        isOver ? 'bg-blue-50' : ''
      }`}
    >
      <SortableContext items={chapters.map((c) => c.id)} strategy={verticalListSortingStrategy}>
        {chapters.length === 0 ? (
          <p className="text-xs text-gray-400 italic py-2 text-center">
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
