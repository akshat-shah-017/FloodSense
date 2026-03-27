import { useQuery } from '@tanstack/react-query';
import { fetchOpenWeatherStatus } from '../api/client';

export function useOpenWeatherStatus() {
  return useQuery({
    queryKey: ['weather', 'openweather'],
    queryFn: fetchOpenWeatherStatus,
    staleTime: 2 * 60 * 1000,
    refetchInterval: 3 * 60 * 1000,
  });
}

