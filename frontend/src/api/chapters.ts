import client from './client';
import type { Chapter, PaginatedResponse } from '../types';

export const chaptersApi = {
  list: (page = 1) =>
    client
      .get<PaginatedResponse<Chapter>>('/chapters/', { params: { page } })
      .then((r) => r.data),

  detail: (id: number) =>
    client.get<Chapter>(`/chapters/${id}/`).then((r) => r.data),
};
