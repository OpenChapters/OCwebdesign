import client from './client';
import type {
  ExampleDetail,
  ExampleFigure,
  ExampleListItem,
  ExampleStatus,
  ExampleWritePayload,
  PaginatedResponse,
} from '../types';

interface ListParams {
  page?: number;
  chapter?: string;
  difficulty?: string;
  search?: string;
}

export const examplesApi = {
  list: (params: ListParams = {}) =>
    client
      .get<PaginatedResponse<ExampleListItem>>('/examples/', { params })
      .then((r) => r.data),

  detail: (id: number) =>
    client.get<ExampleDetail>(`/examples/${id}/`).then((r) => r.data),

  mine: () =>
    client
      .get<PaginatedResponse<ExampleListItem>>('/examples/mine/')
      .then((r) => r.data),

  manage: (id: number) =>
    client.get<ExampleDetail>(`/examples/${id}/manage/`).then((r) => r.data),

  create: (payload: ExampleWritePayload) =>
    client.post<ExampleDetail>('/examples/', payload).then((r) => r.data),

  update: (id: number, payload: Partial<ExampleWritePayload>) =>
    client
      .patch<ExampleDetail>(`/examples/${id}/manage/`, payload)
      .then((r) => r.data),

  remove: (id: number) =>
    client.delete(`/examples/${id}/manage/`).then((r) => r.data),

  submit: (id: number) =>
    client.post<ExampleDetail>(`/examples/${id}/submit/`).then((r) => r.data),

  preview: (id: number) =>
    client
      .post<{ task_id: string }>(`/examples/${id}/preview/`)
      .then((r) => r.data),

  // ── Figures ──────────────────────────────────────────────────────────────
  uploadFigure: (id: number, file: File, caption = '') => {
    const fd = new FormData();
    fd.append('file', file);
    if (caption) fd.append('caption', caption);
    return client
      .post<ExampleFigure>(`/examples/${id}/figures/`, fd, {
        headers: { 'Content-Type': 'multipart/form-data' },
      })
      .then((r) => r.data);
  },

  deleteFigure: (id: number, figureId: number) =>
    client.delete(`/examples/${id}/figures/${figureId}/`).then((r) => r.data),

  // ── Author batch import (gated on site setting) ──────────────────────────
  importDryRun: (file: File) => {
    const fd = new FormData();
    fd.append('file', file);
    return client
      .post<ImportReport>('/examples/import/dry-run/', fd, {
        headers: { 'Content-Type': 'multipart/form-data' },
      })
      .then((r) => r.data);
  },

  importCommit: (file: File, default_status: 'draft' | 'pending') => {
    const fd = new FormData();
    fd.append('file', file);
    fd.append('default_status', default_status);
    return client
      .post<ImportReport>('/examples/import/commit/', fd, {
        headers: { 'Content-Type': 'multipart/form-data' },
      })
      .then((r) => r.data);
  },

  // ── Admin ────────────────────────────────────────────────────────────────
  adminQueue: (status: ExampleStatus = 'pending') =>
    client
      .get<ExampleDetail[]>('/admin/examples/', { params: { status } })
      .then((r) => r.data),

  adminApprove: (id: number) =>
    client
      .post<ExampleDetail>(`/admin/examples/${id}/approve/`)
      .then((r) => r.data),

  adminReject: (id: number, rejection_reason: string) =>
    client
      .post<ExampleDetail>(`/admin/examples/${id}/reject/`, { rejection_reason })
      .then((r) => r.data),

  adminDelete: (id: number) =>
    client.delete(`/admin/examples/${id}/`).then((r) => r.data),

  adminImportDryRun: (file: File) => {
    const fd = new FormData();
    fd.append('file', file);
    return client
      .post<ImportReport>('/admin/examples/import/dry-run/', fd, {
        headers: { 'Content-Type': 'multipart/form-data' },
      })
      .then((r) => r.data);
  },

  adminImportCommit: (file: File, default_status: 'pending' | 'published') => {
    const fd = new FormData();
    fd.append('file', file);
    fd.append('default_status', default_status);
    return client
      .post<ImportReport>('/admin/examples/import/commit/', fd, {
        headers: { 'Content-Type': 'multipart/form-data' },
      })
      .then((r) => r.data);
  },
};

export interface ImportReportEntry {
  dir: string;
  slug: string | null;
  primary_chapter: string;
  chapters: string[];
  difficulty: string;
  figure_count: number;
  action: 'create' | 'update' | 'skip';
  matched_example_id: number | null;
  persisted_id: number | null;
  errors: string[];
}

export interface ImportReport {
  global_errors: string[];
  summary: {
    total: number;
    create: number;
    update: number;
    errors: number;
  };
  entries: ImportReportEntry[];
}
