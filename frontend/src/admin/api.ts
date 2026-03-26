import client from '../api/client';
import type { PaginatedResponse } from '../types';

// ── Dashboard ────────────────────────────────────────────────────────────────

export interface DashboardData {
  users: { total: number; new_this_week: number };
  chapters: { published: number; unpublished: number };
  books: { draft: number; queued: number; building: number; complete: number; failed: number };
  builds_today: { total: number; success: number; failed: number };
  storage: { pdf_count: number; pdf_size_mb: number };
  recent_builds: {
    id: number;
    book_title: string;
    user_email: string;
    status: string;
    started_at: string | null;
    finished_at: string | null;
    error: boolean;
  }[];
}

export interface Worker {
  name: string;
  status: string;
  active_tasks: number;
  total_tasks: Record<string, number>;
  pool: string;
  concurrency: number;
}

// ── Users ────────────────────────────────────────────────────────────────────

export interface AdminUser {
  id: number;
  email: string;
  is_active: boolean;
  is_staff: boolean;
  is_superuser: boolean;
  date_joined: string;
  last_login: string | null;
  book_count: number;
}

export interface AdminUserDetail {
  id: number;
  email: string;
  is_active: boolean;
  is_staff: boolean;
  is_superuser: boolean;
  date_joined: string;
  last_login: string | null;
}

export interface UserBook {
  id: number;
  title: string;
  status: string;
  created_at: string;
  updated_at: string;
}

// ── Audit Log ────────────────────────────────────────────────────────────────

export interface AuditLogEntry {
  id: number;
  timestamp: string;
  user_email: string | null;
  action: string;
  target_type: string;
  target_id: number | null;
  detail: Record<string, any>;
  ip_address: string | null;
}

// ── System ───────────────────────────────────────────────────────────────────

export interface HealthCheck {
  status: 'ok' | 'warning' | 'error';
  detail?: string;
  [key: string]: any;
}

export interface SystemHealth {
  overall: 'ok' | 'warning' | 'error';
  checks: Record<string, HealthCheck>;
}

export interface GitHubStatus {
  status: string;
  detail?: string;
  rate_limit?: number;
  remaining?: number;
  reset_at?: string;
}

// ── Settings ─────────────────────────────────────────────────────────────────

export interface SiteSettings {
  site_name: string;
  welcome_message: string;
  announcement_banner: string;
  registration_enabled: boolean;
  build_enabled: boolean;
  max_chapters_per_book: number;
  max_concurrent_builds: number;
  pdf_retention_days: number;
}

// ── Builds ───────────────────────────────────────────────────────────────────

export interface AdminBuild {
  id: number;
  book_id: number;
  book_title: string;
  user_email: string;
  status: string;
  celery_task_id: string;
  started_at: string | null;
  finished_at: string | null;
  has_error: boolean;
  pdf_size_mb: number | null;
}

export interface AdminBuildDetail extends AdminBuild {
  log_output: string;
  error_message: string;
  pdf_path: string;
}

// ── Chapters ─────────────────────────────────────────────────────────────────

export interface AdminChapter {
  id: number;
  title: string;
  authors: string[];
  description: string;
  toc: string[];
  cover_image_url: string;
  keywords: string[];
  chapter_type: 'foundational' | 'topical';
  chabbr: string;
  depends_on: string[];
  published: boolean;
  github_repo: string;
  chapter_subdir: string;
  latex_entry_file: string;
  cached_at: string;
}

// ── API ──────────────────────────────────────────────────────────────────────

export const adminApi = {
  // Dashboard
  dashboard: () =>
    client.get<DashboardData>('/admin/dashboard/').then((r) => r.data),
  workers: () =>
    client.get<{ workers: Worker[]; error?: string }>('/admin/workers/').then((r) => r.data),

  // Users
  userList: (params?: { search?: string; page?: number }) =>
    client.get<PaginatedResponse<AdminUser>>('/admin/users/', { params }).then((r) => r.data),
  userCreate: (data: { email: string; password: string; is_staff?: boolean }) =>
    client.post('/admin/users/', data).then((r) => r.data),
  userDetail: (id: number) =>
    client.get<AdminUserDetail>(`/admin/users/${id}/`).then((r) => r.data),
  userUpdate: (id: number, data: Partial<AdminUserDetail>) =>
    client.patch<AdminUserDetail>(`/admin/users/${id}/`, data).then((r) => r.data),
  userDelete: (id: number) =>
    client.delete(`/admin/users/${id}/`),
  userBooks: (id: number) =>
    client.get<UserBook[]>(`/admin/users/${id}/books/`).then((r) => r.data),

  // Builds
  buildList: (params?: { search?: string; status?: string; page?: number }) =>
    client.get('/admin/builds/', { params }).then((r) => r.data as {
      count: number; page: number; page_size: number; results: AdminBuild[];
    }),
  buildDetail: (id: number) =>
    client.get<AdminBuildDetail>(`/admin/builds/${id}/`).then((r) => r.data),
  buildCancel: (id: number) =>
    client.post(`/admin/builds/${id}/cancel/`).then((r) => r.data),
  buildRetry: (id: number) =>
    client.post(`/admin/builds/${id}/retry/`).then((r) => r.data),
  buildDownload: (id: number) =>
    client.get(`/admin/builds/${id}/download/`, { responseType: 'blob' }).then((r) => {
      const disposition = r.headers['content-disposition'] || '';
      const match = disposition.match(/filename="?([^"]+)"?/);
      const filename = match ? match[1] : `build_${id}.pdf`;
      const url = window.URL.createObjectURL(r.data);
      const a = document.createElement('a');
      a.href = url;
      a.download = filename;
      document.body.appendChild(a);
      a.click();
      a.remove();
      window.URL.revokeObjectURL(url);
    }),

  // System
  systemHealth: () =>
    client.get<SystemHealth>('/admin/system/health/').then((r) => r.data),
  systemGitHub: () =>
    client.get<GitHubStatus>('/admin/system/github/').then((r) => r.data),

  // Settings
  settingsGet: () =>
    client.get<SiteSettings>('/admin/settings/').then((r) => r.data),
  settingsUpdate: (data: Partial<SiteSettings>) =>
    client.patch<{ detail: string; settings: SiteSettings }>('/admin/settings/', data).then((r) => r.data),

  // Audit log
  auditLog: (params?: { action?: string; target_type?: string; user?: string; page?: number }) =>
    client.get('/admin/audit/', { params }).then((r) => r.data as {
      count: number; page: number; page_size: number; results: AuditLogEntry[];
    }),

  // Analytics
  analyticsBuilds: (days = 30) =>
    client.get<{ date: string; total: number; success: number; failed: number }[]>(
      '/admin/analytics/builds/', { params: { days } }
    ).then((r) => r.data),
  analyticsChapters: () =>
    client.get<{ title: string; chabbr: string; count: number }[]>(
      '/admin/analytics/chapters/'
    ).then((r) => r.data),
  analyticsUsers: (days = 90) =>
    client.get<{ date: string; count: number }[]>(
      '/admin/analytics/users/', { params: { days } }
    ).then((r) => r.data),

  // Chapters
  chapterList: (params?: { search?: string; page?: number }) =>
    client.get<PaginatedResponse<AdminChapter>>('/admin/chapters/', { params }).then((r) => r.data),
  chapterDetail: (id: number) =>
    client.get<AdminChapter>(`/admin/chapters/${id}/`).then((r) => r.data),
  chapterUpdate: (id: number, data: Partial<AdminChapter>) =>
    client.patch<AdminChapter>(`/admin/chapters/${id}/`, data).then((r) => r.data),
  chapterSync: () =>
    client.post<{ detail: string; output: string }>('/admin/chapters/sync/').then((r) => r.data),
};
