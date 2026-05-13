import { useQuery } from '@tanstack/react-query';
import { siteConfigApi } from '../api/siteConfig';

export function useSiteConfig() {
  return useQuery({
    queryKey: ['siteConfig'],
    queryFn: siteConfigApi.get,
    staleTime: 60_000,
    gcTime: 5 * 60_000,
  });
}
