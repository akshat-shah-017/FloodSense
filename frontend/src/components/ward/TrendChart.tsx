import { CartesianGrid, Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts';
import GlassPanel from '../system/GlassPanel';
import { formatChartDate } from '../../lib/format';

interface TrendChartProps {
  points: Array<{ predicted_at: string; risk_score: number }>;
}

export default function TrendChart({ points }: TrendChartProps) {
  const chartData = points.map((point) => ({
    risk_score: Number(point.risk_score ?? 0),
    predicted_at: point.predicted_at,
    label: formatChartDate(point.predicted_at),
  }));

  return (
    <GlassPanel>
      <div className="mb-2">
        <h2 className="ui-headline text-xl">Trend Chart</h2>
        <p className="ui-body mt-1">30-day forecast progression from latest model outputs.</p>
      </div>

      {chartData.length < 2 ? (
        <div className="flex h-[240px] items-center justify-center rounded-2xl border border-outline/20 bg-surface-container/55 text-sm text-on-surface-variant">
          Run inference cycles to populate trend history.
        </div>
      ) : (
        <div className="h-[240px] w-full">
          <ResponsiveContainer width="100%" height="100%">
            <LineChart data={chartData}>
              <CartesianGrid vertical={false} stroke="rgba(148,163,184,0.16)" />
              <XAxis
                dataKey="label"
                tickLine={false}
                axisLine={{ stroke: 'rgba(148,163,184,0.2)' }}
                tick={{ fill: 'rgba(148,163,184,1)', fontSize: 11 }}
              />
              <YAxis
                domain={[0, 100]}
                ticks={[0, 25, 50, 75, 100]}
                tickLine={false}
                axisLine={{ stroke: 'rgba(148,163,184,0.2)' }}
                tick={{ fill: 'rgba(148,163,184,1)', fontSize: 11 }}
              />
              <Tooltip
                cursor={{ stroke: 'rgba(56,189,248,0.35)' }}
                contentStyle={{
                  background: 'rgba(14,23,40,0.95)',
                  border: '1px solid rgba(56,189,248,0.35)',
                  borderRadius: '14px',
                  color: 'rgb(226,232,240)',
                }}
                formatter={(value: number) => [`${Number(value).toFixed(1)}`, 'Risk Score']}
              />
              <Line type="monotone" dataKey="risk_score" stroke="rgb(56,189,248)" strokeWidth={2.5} dot={false} />
            </LineChart>
          </ResponsiveContainer>
        </div>
      )}
    </GlassPanel>
  );
}

