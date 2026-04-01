import client from './client';
import type { Chapter, Discipline, PaginatedResponse } from '../types';

export const chaptersApi = {
  list: (page = 1, discipline?: string) =>
    client
      .get<PaginatedResponse<Chapter>>('/chapters/', {
        params: { page, ...(discipline ? { discipline } : {}) },
      })
      .then((r) => r.data),

  detail: (id: number) =>
    client.get<Chapter>(`/chapters/${id}/`).then((r) => r.data),

  disciplines: () =>
    client.get<Discipline[]>('/disciplines/').then((r) => r.data),
};
