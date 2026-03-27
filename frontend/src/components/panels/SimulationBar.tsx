import { CloudRain, Sparkles } from 'lucide-react';
import { useEffect, useMemo, useRef, useState } from 'react';
import { useTriggerInference } from '../../hooks/usePredictions';
import { useOpenWeatherStatus } from '../../hooks/useWeather';
import { relativeTime } from '../../lib/format';
import GlassPanel from '../system/GlassPanel';
import StatusBadge from '../system/StatusBadge';
import GlowButton from '../ui/GlowButton';

function scenarioTone(rainfall: number): 'success' | 'warning' | 'critical' {
  if (rainfall >= 170) {
    return 'critical';
  }
  if (rainfall >= 90) {
    return 'warning';
  }
  return 'success';
}

export default function SimulationBar() {
  const [rainfall, setRainfall] = useState(60);
  const [demoMode, setDemoMode] = useState(true);
  const [showComplete, setShowComplete] = useState(false);
  const latestRainfallRef = useRef(rainfall);
  const triggerInference = useTriggerInference();
  const weatherStatus = useOpenWeatherStatus();

  const presets = [40, 80, 120, 180];
  const tone = scenarioTone(rainfall);

  useEffect(() => {
    if (!weatherStatus.data?.forecast?.max_6hr_mm) {
      return;
    }
    const inferredRain = Math.round(Number(weatherStatus.data.forecast.max_6hr_mm));
    if (Number.isFinite(inferredRain) && inferredRain > 0) {
      setRainfall(Math.max(0, Math.min(200, inferredRain)));
    }
  }, [weatherStatus.data?.forecast?.max_6hr_mm]);

  useEffect(() => {
    if (!triggerInference.isSuccess) {
      return;
    }

    setShowComplete(true);
    const timer = window.setTimeout(() => setShowComplete(false), 3500);
    return () => window.clearTimeout(timer);
  }, [triggerInference.isSuccess]);

  useEffect(() => {
    latestRainfallRef.current = rainfall;
  }, [rainfall]);

  const handleToggleDemoMode = () => {
    setDemoMode((prev) => {
      const next = !prev;
      const payload = { rainfall_mm: latestRainfallRef.current, demo_mode: next };
      if (import.meta.env.DEV) {
        console.info('[Inference Trigger]', { reason: 'demo_mode_toggled', ...payload });
      }
      triggerInference.mutate(payload);
      return next;
    });
  };

  const scenarioLabel = useMemo(() => {
    if (rainfall >= 170) {
      return 'Extreme Burst';
    }
    if (rainfall >= 90) {
      return 'Heavy Monsoon';
    }
    return 'Managed Rain';
  }, [rainfall]);

  const weatherBadgeTone =
    weatherStatus.data?.status === 'live'
      ? 'success'
      : weatherStatus.data?.status === 'error'
        ? 'critical'
        : 'neutral';

  const weatherLabel =
    weatherStatus.data?.status === 'live'
      ? `OpenWeather Live • 24h ${weatherStatus.data.forecast?.total_24h_mm?.toFixed(1) ?? '—'} mm`
      : weatherStatus.data?.status === 'error'
        ? 'OpenWeather Error'
        : 'OpenWeather Not Configured';

  return (
    <GlassPanel className="mt-6 p-4">
      <div className="mb-3 flex flex-wrap items-center justify-between gap-2">
        <StatusBadge label={weatherLabel} tone={weatherBadgeTone} />
        <GlowButton
          variant={demoMode ? 'primary' : 'ghost'}
          loading={triggerInference.isPending}
          onClick={handleToggleDemoMode}
        >
          {demoMode ? 'Demo Mode On' : 'Demo Mode Off'}
        </GlowButton>
      </div>

      <div className="grid gap-4 lg:grid-cols-[220px_minmax(0,1fr)_320px] lg:items-center">
        <div>
          <div className="mb-1 flex items-center gap-2">
            <Sparkles size={14} className="text-primary" />
            <span className="ui-label">Inference Engine</span>
          </div>
          <h3 className="ui-headline text-lg">Scenario Simulation</h3>
          <p className="ui-body mt-1">
            {demoMode
              ? 'Scattered-risk demo mode using rainfall + ward vulnerability factors.'
              : 'Run flood forecasting under synthetic rainfall stress.'}
          </p>
        </div>

        <div className="rounded-2xl border border-outline/20 bg-surface-container/65 p-3">
          <div className="mb-2 flex items-center justify-between">
            <div className="flex items-center gap-2">
              <CloudRain size={14} className="text-primary" />
              <span className="ui-label">Rainfall</span>
            </div>
            <StatusBadge label={`${scenarioLabel} / ${rainfall} mm`} tone={tone} />
          </div>

          <input
            type="range"
            min={0}
            max={200}
            value={rainfall}
            onChange={(event) => setRainfall(Number(event.target.value))}
            className="rain-slider"
            aria-label="Rainfall intensity"
          />

          <div className="mt-3 flex flex-wrap gap-2">
            {presets.map((preset) => (
              <GlowButton
                key={preset}
                variant={rainfall === preset ? 'primary' : 'ghost'}
                className="min-h-8 px-3 py-1 text-[10px]"
                onClick={() => setRainfall(preset)}
              >
                {preset}mm
              </GlowButton>
            ))}
          </div>
        </div>

        <div className="flex flex-col items-end gap-2">
          {showComplete && triggerInference.data ? (
            <StatusBadge
              tone="success"
              label={`Updated ${triggerInference.data.wards_predicted} Wards`}
              pulse
            />
          ) : null}
          {triggerInference.data ? (
            <div className="ui-label">
              Last run: {triggerInference.data.demo_mode ? 'DEMO' : 'LIVE'} •{' '}
              {relativeTime(triggerInference.data.completed_at)}
            </div>
          ) : null}
          {triggerInference.isError ? <StatusBadge tone="critical" label="Inference Failed" /> : null}
          <GlowButton
            variant="primary"
            loading={triggerInference.isPending}
            onClick={() => {
              const payload = { rainfall_mm: rainfall, demo_mode: demoMode };
              if (import.meta.env.DEV) {
                console.info('[Inference Trigger]', { reason: 'manual_click', ...payload });
              }
              triggerInference.mutate(payload);
            }}
          >
            Run Inference
          </GlowButton>
        </div>
      </div>
    </GlassPanel>
  );
}
