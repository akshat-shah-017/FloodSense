import { useMemo } from 'react';
import { useQuery } from '@tanstack/react-query';
import { fetchAlertLog, fetchAlertPreview } from '../api/client';

export function useAlertPreview() {
  return useQuery({
    queryKey: ['alerts', 'preview'],
    queryFn: fetchAlertPreview,
    refetchInterval: 5 * 60 * 1000,
  });
}

export function useAlertLog() {
  return useQuery({
    queryKey: ['alerts', 'log'],
    queryFn: fetchAlertLog,
    staleTime: 5 * 60 * 1000,
    refetchInterval: 5 * 60 * 1000,
  });
}

export function useWardAlertHistory(wardId: number | null) {
  const query = useAlertLog();

  const wardAlerts = useMemo(() => {
    if (!wardId || !query.data) {
      return [];
    }
    return query.data
      .filter((row) => row.ward_id === wardId)
      .sort((a, b) => {
        const left = new Date(a.dispatched_at).getTime();
        const right = new Date(b.dispatched_at).getTime();
        return right - left;
      });
  }, [query.data, wardId]);

  return {
    ...query,
    data: wardAlerts,
  };
}
