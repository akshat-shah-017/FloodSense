import { motion } from 'framer-motion';
import type { WardPrediction } from '../../types';
import GlowButton from '../ui/GlowButton';
import RiskBadge from '../ui/RiskBadge';

interface WardPreviewPopupProps {
  ward: WardPrediction;
  onViewDetails: () => void;
}

function summaryForTier(tier: WardPrediction['risk_tier'], score: number): string {
  if (tier === 'HIGH') {
    return `Critical flood probability detected (${Math.round(score)}/100). Immediate response readiness advised.`;
  }
  if (tier === 'MEDIUM') {
    return `Moderate flooding risk (${Math.round(score)}/100). Monitor drainage and low-lying blocks.`;
  }
  if (tier === 'LOW') {
    return `Low near-term risk (${Math.round(score)}/100). Continue routine ward monitoring.`;
  }
  return 'Risk model is currently operating with limited confidence for this ward.';
}

export default function WardPreviewPopup({ ward, onViewDetails }: WardPreviewPopupProps) {
  return (
    <motion.div
      initial={{ opacity: 0, scale: 0.96, y: 6 }}
      animate={{ opacity: 1, scale: 1, y: 0 }}
      transition={{ duration: 0.24, ease: [0.22, 1, 0.36, 1] }}
      className="w-[290px] rounded-2xl border border-primary/30 bg-surface-container/95 p-4 shadow-glass-lg backdrop-blur-xl"
    >
      <div className="mb-2 flex items-center justify-between gap-2">
        <h3 className="ui-headline text-base">{ward.ward_name}</h3>
        <RiskBadge tier={ward.risk_tier} />
      </div>

      <div className="mb-3 flex items-end gap-2">
        <span className="font-mono text-3xl font-semibold text-on-surface">{Math.round(Number(ward.risk_score ?? 0))}</span>
        <span className="ui-label pb-1">/100</span>
      </div>

      <p className="ui-body mb-4">{summaryForTier(ward.risk_tier, Number(ward.risk_score ?? 0))}</p>

      <GlowButton className="w-full" onClick={onViewDetails}>
        View Details
      </GlowButton>
    </motion.div>
  );
}

