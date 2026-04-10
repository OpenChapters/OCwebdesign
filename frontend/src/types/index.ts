export interface Discipline {
  id: number;
  name: string;
  slug: string;
  color_primary: string;
}

export interface Chapter {
  id: number;
  title: string;
  authors: string[];
  author_urls: Record<string, string>;
  description: string;
  toc: string[];
  cover_image_url: string;
  keywords: string[];
  chapter_type: 'foundational' | 'topical';
  chabbr: string;
  depends_on: string[];
  discipline: Discipline | null;
  github_repo: string;
  chapter_subdir: string;
  last_updated: string | null;
  cached_at: string;
}

export interface BookChapter {
  id: number;
  order: number;
  chapter_detail: Chapter;
}

export interface BookPart {
  id: number;
  title: string;
  order: number;
  chapters: BookChapter[];
}

export interface BuildJob {
  celery_task_id: string;
  started_at: string | null;
  finished_at: string | null;
  pdf_path: string;
  error_message: string;
}

export interface Book {
  id: number;
  title: string;
  doi: string;
  status: 'draft' | 'queued' | 'building' | 'complete' | 'failed';
  created_at: string;
  updated_at: string;
  parts: BookPart[];
  build_job: BuildJob | null;
  has_cover_image: boolean;
}

export interface BookListItem {
  id: number;
  title: string;
  doi: string;
  status: 'draft' | 'queued' | 'building' | 'complete' | 'failed';
  created_at: string;
  updated_at: string;
}

export interface PaginatedResponse<T> {
  count: number;
  next: string | null;
  previous: string | null;
  results: T[];
}
