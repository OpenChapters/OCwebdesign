export type BuildFormat = 'pdf' | 'html' | 'both';

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
  reviewer_name: string;
  reviewed_at: string | null;
  html_built_at: string | null;
  cached_at: string;
  has_pdf_labels: boolean;
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
  html_built_at: string | null;
  has_pdf: boolean;
  has_html: boolean;
  last_build_format: BuildFormat;
  include_examples: boolean;
  include_solutions: boolean;
  examples_count: number;
}

export interface BookListItem {
  id: number;
  title: string;
  doi: string;
  status: 'draft' | 'queued' | 'building' | 'complete' | 'failed';
  created_at: string;
  updated_at: string;
  html_built_at: string | null;
  has_pdf: boolean;
  has_html: boolean;
}


export interface PaginatedResponse<T> {
  count: number;
  next: string | null;
  previous: string | null;
  results: T[];
}

export type ExampleDifficulty = 'introductory' | 'standard' | 'advanced';
export type ExampleStatus = 'draft' | 'pending' | 'published' | 'rejected';

export interface ExampleChapterRef {
  id: number;
  title: string;
  chabbr: string;
}

export interface ExampleListItem {
  id: number;
  primary_chapter: ExampleChapterRef;
  chapters: ExampleChapterRef[];
  statement_tex: string;
  difficulty: ExampleDifficulty;
  status: ExampleStatus;
  author_display: string;
  created_at: string;
  updated_at: string;
}

export interface ExampleDetail extends ExampleListItem {
  solution_tex: string;
  license: string;
  rejection_reason: string;
  preview_built_at: string | null;
  preview_build_log: string;
  preview_fresh: boolean;
  preview_pdf_url: string | null;
}

export interface ExampleWritePayload {
  primary_chapter: number;
  chapters: number[];
  statement_tex: string;
  solution_tex: string;
  difficulty: ExampleDifficulty;
}
