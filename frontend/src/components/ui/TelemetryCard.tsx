import type { ReactNode } from 'react';
import StatCard from '../system/StatCard';

interface TelemetryCardProps {
  label: string;
  value: string | number;
  unit?: string;
  trend?: 'up' | 'down' | 'neutral';
  icon?: ReactNode;
  alert?: boolean;
  description?: string;
  compact?: boolean;
  className?: string;
}

export default function TelemetryCard({
  label,
  value,
  unit,
  trend,
  icon,
  alert = false,
  description,
  compact = false,
  className = '',
}: TelemetryCardProps) {
  return (
    <StatCard
      label={label}
      value={value}
      unit={unit}
      trend={trend}
      icon={icon}
      description={description}
      highlight={alert ? 'critical' : 'none'}
      className={`${compact ? 'p-3' : ''} ${className}`}
    />
  );
}

