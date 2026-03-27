import StatusBadge, { toneFromTier } from '../system/StatusBadge';

interface RiskBadgeProps {
  tier: string;
  pulse?: boolean;
}

export default function RiskBadge({ tier, pulse = false }: RiskBadgeProps) {
  return <StatusBadge label={tier} tone={toneFromTier(tier)} pulse={pulse} />;
}

