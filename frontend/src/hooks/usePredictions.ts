import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import {
  fetchCurrentPredictions,
  fetchWardDetail,
  triggerInference,
} from '../api/client';

export function useCurrentPredictions() {
  return useQuery({
    queryKey: ['predictions', 'current'],
    queryFn: fetchCurrentPredictions,
    staleTime: 2 * 60 * 60 * 1000,
    refetchInterval: 3 * 60 * 60 * 1000,
  });
}

export function useWardDetail(wardId: number | null) {
  return useQuery({
    queryKey: ['predictions', 'ward', wardId],
    queryFn: () => fetchWardDetail(wardId as number),
    enabled: wardId !== null,
  });
}

export function useTriggerInference() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationKey: ['inference', 'predict'],
    mutationFn: (payload?: { rainfall_mm?: number; demo_mode?: boolean }) => triggerInference(payload),
    onSuccess: async () => {
      await Promise.all([
        queryClient.invalidateQueries({ queryKey: ['predictions', 'current'] }),
        queryClient.invalidateQueries({ queryKey: ['stats'] }),
        queryClient.invalidateQueries({ queryKey: ['alerts', 'preview'] }),
        queryClient.invalidateQueries({ queryKey: ['alerts', 'log'] }),
      ]);
      await queryClient.refetchQueries({ queryKey: ['predictions', 'current'], type: 'active' });
    },
  });
}
