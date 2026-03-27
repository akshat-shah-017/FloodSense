import { useQuery } from '@tanstack/react-query';
import { fetchStats } from '../api/client';

export function useSystemStats() {
  return useQuery({
    queryKey: ['stats'],
    queryFn: fetchStats,
    staleTime: 30 * 1000,
    refetchInterval: 60 * 1000,
  });
}
