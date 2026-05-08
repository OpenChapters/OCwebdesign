import client from './client';
import type {
  ExampleDetail,
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
};
