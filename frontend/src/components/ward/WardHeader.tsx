import { ArrowLeft } from 'lucide-react';
import type { WardPrediction } from '../../types';
import GlowButton from '../ui/GlowButton';
import RiskBadge from '../ui/RiskBadge';

interface WardHeaderProps {
  ward: WardPrediction;
  onBack: () => void;
}

export default function WardHeader({ ward, onBack }: WardHeaderProps) {
  return (
    <header className="mb-6 flex flex-wrap items-start justify-between gap-4">
      <div>
        <GlowButton variant="ghost" className="mb-3" onClick={onBack}>
          <span className="inline-flex items-center gap-2">
            <ArrowLeft size={14} />
            Back
          </span>
        </GlowButton>
        <h1 className="ui-headline text-3xl">Ward Insight: {ward.ward_name}</h1>
        <p className="ui-label mt-2">{`Ward ${ward.ward_id} • Delhi NCR`}</p>
      </div>

      <RiskBadge tier={ward.risk_tier} pulse={ward.risk_tier === 'HIGH'} />
    </header>
  );
}

