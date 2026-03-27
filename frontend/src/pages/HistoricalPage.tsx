import { useMemo } from 'react';
import { Bar, BarChart, Cell, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts';
import AppShell from '../components/layout/AppShell';
import GlassPanel from '../components/system/GlassPanel';
import StatCard from '../components/system/StatCard';
import StatusBadge from '../components/system/StatusBadge';
import { useCurrentPredictions } from '../hooks/usePredictions';
import { useSystemStats } from '../hooks/useStats';

const aucRows = [
  { label: 'LGBM AUC', value: 0.923 },
  { label: 'XGB AUC', value: 0.917 },
  { label: 'LSTM AUC', value: 0.901 },
];

export default function HistoricalPage() {
  const { data: stats } = useSystemStats();
  const { data: predictions } = useCurrentPredictions();

  const tierCounts = useMemo(() => {
    const counts = { HIGH: 0, MEDIUM: 0, LOW: 0, UNKNOWN: 0 };
    (predictions?.features ?? []).forEach((feature) => {
      const tier = feature.properties?.risk_tier;
      if (tier in counts) {
        counts[tier as keyof typeof counts] += 1;
      } else {
        counts.UNKNOWN += 1;
      }
    });
    return counts;
  }, [predictions]);

  const barData = [
    { tier: 'HIGH', count: tierCounts.HIGH, color: 'rgb(248,113,113)' },
    { tier: 'MEDIUM', count: tierCounts.MEDIUM, color: 'rgb(245,158,11)' },
    { tier: 'LOW', count: tierCounts.LOW, color: 'rgb(52,211,153)' },
    { tier: 'UNKNOWN', count: tierCounts.UNKNOWN, color: 'rgb(148,163,184)' },
  ];

  return (
    <AppShell
      title="Historical Intelligence"
      subtitle="Training lineage, model performance, and tier distribution across live inferences."
    >
      <div className="mb-6 grid grid-cols-1 gap-4 xl:grid-cols-4">
        <StatCard label="Prediction Accuracy" value="92.3%" description="Walk-forward validation across 5 folds." />
        <StatCard label="Ward Coverage" value={stats?.total_wards ?? 250} unit="wards" description="Full Delhi ward map coverage." />
        <StatCard label="Training Span" value="18" unit="years" description="IMD weather and historical flood records." />
        <StatCard label="Rows Processed" value="2.09M" description="Engineered feature rows in training baseline." />
      </div>

      <div className="grid gap-6 xl:grid-cols-[minmax(0,1fr)_360px]">
        <GlassPanel>
          <div className="mb-3">
            <h2 className="ui-headline text-xl">Risk Tier Distribution</h2>
            <p className="ui-body mt-1">Live ward counts by AI risk tier from the latest prediction cycle.</p>
          </div>

          <div className="mb-4 flex flex-wrap gap-2">
            <StatusBadge tone="critical" label={`High ${tierCounts.HIGH}`} />
            <StatusBadge tone="warning" label={`Medium ${tierCounts.MEDIUM}`} />
            <StatusBadge tone="success" label={`Low ${tierCounts.LOW}`} />
            <StatusBadge tone="neutral" label={`Unknown ${tierCounts.UNKNOWN}`} />
          </div>

          <div className="h-[280px] w-full">
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={barData}>
                <XAxis
                  dataKey="tier"
                  tickLine={false}
                  axisLine={{ stroke: 'rgba(148,163,184,0.25)' }}
                  tick={{ fill: 'rgba(148,163,184,1)', fontSize: 11 }}
                />
                <YAxis
                  allowDecimals={false}
                  tickLine={false}
                  axisLine={{ stroke: 'rgba(148,163,184,0.25)' }}
                  tick={{ fill: 'rgba(148,163,184,1)', fontSize: 11 }}
                />
                <Tooltip
                  cursor={{ fill: 'rgba(56,189,248,0.08)' }}
                  contentStyle={{
                    background: 'rgba(14,23,40,0.95)',
                    border: '1px solid rgba(56,189,248,0.35)',
                    borderRadius: '14px',
                    color: 'rgb(226,232,240)',
                  }}
                />
                <Bar dataKey="count" radius={[8, 8, 0, 0]}>
                  {barData.map((entry) => (
                    <Cell key={entry.tier} fill={entry.color} />
                  ))}
                </Bar>
              </BarChart>
            </ResponsiveContainer>
          </div>
        </GlassPanel>

        <GlassPanel>
          <h2 className="ui-headline text-xl">Model Benchmarks</h2>
          <p className="ui-body mt-1">Current champion stack metrics from validation benchmarking.</p>

          <div className="mt-4 space-y-4">
            {aucRows.map((row) => (
              <div key={row.label}>
                <div className="mb-1 flex items-center justify-between">
                  <span className="ui-label">{row.label}</span>
                  <span className="font-mono text-sm text-primary">{row.value.toFixed(3)}</span>
                </div>
                <div className="h-2 w-full rounded-full bg-outline/20">
                  <div className="h-2 rounded-full bg-primary/85" style={{ width: `${row.value * 100}%` }} />
                </div>
              </div>
            ))}
          </div>

          <div className="mt-5">
            <StatusBadge tone="success" label="Confidence 98.4%" pulse />
          </div>
        </GlassPanel>
      </div>
    </AppShell>
  );
}

