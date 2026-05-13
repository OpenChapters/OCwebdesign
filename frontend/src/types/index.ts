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
  examples_count: number;
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

export type BuildStepStatus =
  | 'pending'
  | 'running'
  | 'succeeded'
  | 'failed'
  | 'skipped';

export interface BuildStep {
  name: string;
  label: string;
  order: number;
  status: BuildStepStatus;
  detail: string;
  started_at: string | null;
  finished_at: string | null;
  log_tail: string;
}

export interface BuildJob {
  celery_task_id: string;
  started_at: string | null;
  finished_at: string | null;
  pdf_path: string;
  error_message: string;
  preview_structure: boolean;
  steps: BuildStep[];
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
  excluded_example_ids: number[];
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

export interface ExampleFigure {
  id: number;
  original_filename: string;
  caption: string;
  order: number;
  file_url: string;
  created_at: string;
}

export interface ExampleDetail extends ExampleListItem {
  solution_tex: string;
  license: string;
  rejection_reason: string;
  is_own: boolean;
  preview_built_at: string | null;
  preview_build_log: string;
  preview_fresh: boolean;
  preview_pdf_url: string | null;
  figures: ExampleFigure[];
}

export interface ExampleWritePayload {
  primary_chapter: number;
  chapters: number[];
  statement_tex: string;
  solution_tex: string;
  difficulty: ExampleDifficulty;
}

export interface ExampleVersionSnapshot {
  statement_tex: string;
  solution_tex: string;
  difficulty: ExampleDifficulty;
  primary_chapter_chabbr: string | null;
  chapters_chabbrs: string[];
  status: ExampleStatus;
  slug: string | null;
}

export interface ExampleVersion {
  version_no: number;
  snapshot: ExampleVersionSnapshot;
  created_at: string;
  editor_display: string | null;
}

export interface PublicSettings {
  site_name: string;
  welcome_message: string;
  announcement_banner: string;
  registration_enabled: boolean;
  author_batch_import_enabled: boolean;
  splash_enabled: boolean;
  splash_duration_ms: number;
  splash_image_url: string | null;
  splash_caption: string;
}
