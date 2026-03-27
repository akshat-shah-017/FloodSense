import type { WardPrediction } from '../../types';
import GlassPanel from '../system/GlassPanel';
import RiskBadge from '../ui/RiskBadge';

interface RiskScoreCardProps {
  ward: WardPrediction;
}

const toneColor: Record<string, string> = {
  HIGH: 'text-error',
  MEDIUM: 'text-tertiary',
  LOW: 'text-secondary',
  UNKNOWN: 'text-on-surface-variant',
};

export default function RiskScoreCard({ ward }: RiskScoreCardProps) {
  const score = Math.max(0, Math.min(100, Math.round(Number(ward.risk_score ?? 0))));
  const radius = 68;
  const circumference = 2 * Math.PI * radius;
  const strokeOffset = circumference - (score / 100) * circumference;
  const colorClass = toneColor[ward.risk_tier] ?? toneColor.UNKNOWN;

  return (
    <GlassPanel className="h-full">
      <div className="mb-4 flex items-center justify-between">
        <h2 className="ui-headline text-xl">Risk Score</h2>
        <RiskBadge tier={ward.risk_tier} />
      </div>

      <div className="mx-auto mb-4 flex w-full max-w-[220px] justify-center">
        <div className="relative h-[170px] w-[170px]">
          <svg width="170" height="170" viewBox="0 0 170 170">
            <circle cx="85" cy="85" r={radius} stroke="rgba(148,163,184,0.2)" strokeWidth="10" fill="none" />
            <circle
              cx="85"
              cy="85"
              r={radius}
              stroke={ward.risk_tier === 'HIGH' ? 'rgb(248,113,113)' : ward.risk_tier === 'MEDIUM' ? 'rgb(245,158,11)' : ward.risk_tier === 'LOW' ? 'rgb(52,211,153)' : 'rgb(148,163,184)'}
              strokeWidth="10"
              fill="none"
              strokeLinecap="round"
              strokeDasharray={circumference}
              strokeDashoffset={strokeOffset}
              transform="rotate(-90 85 85)"
            />
          </svg>
          <div className="absolute inset-0 flex flex-col items-center justify-center">
            <span className={`font-mono text-[42px] font-semibold leading-none ${colorClass}`}>{score}</span>
            <span className="ui-label mt-1">/100 Risk</span>
          </div>
        </div>
      </div>

      <div className="grid grid-cols-2 gap-3">
        <div className="rounded-2xl border border-outline/20 bg-surface-container/55 p-3">
          <div className="ui-label">CI Lower</div>
          <div className="mt-1 font-mono text-base text-on-surface">{Number(ward.ci_lower ?? 0).toFixed(1)}</div>
        </div>
        <div className="rounded-2xl border border-outline/20 bg-surface-container/55 p-3">
          <div className="ui-label">CI Upper</div>
          <div className="mt-1 font-mono text-base text-on-surface">{Number(ward.ci_upper ?? 0).toFixed(1)}</div>
        </div>
      </div>
    </GlassPanel>
  );
}

