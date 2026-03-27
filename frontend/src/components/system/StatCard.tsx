import { ArrowDownRight, ArrowRight, ArrowUpRight } from 'lucide-react';
import { motion } from 'framer-motion';
import type { ReactNode } from 'react';
import { cn } from '../../lib/cn';
import GlassCard from './GlassCard';
import { tapScale } from './motion';

interface StatCardProps {
  label: string;
  value: string | number;
  unit?: string;
  icon?: ReactNode;
  trend?: 'up' | 'down' | 'neutral';
  description?: string;
  highlight?: 'none' | 'warning' | 'critical';
  className?: string;
}

function TrendIcon({ trend }: { trend: 'up' | 'down' | 'neutral' }) {
  if (trend === 'up') {
    return <ArrowUpRight size={14} className="text-secondary" />;
  }
  if (trend === 'down') {
    return <ArrowDownRight size={14} className="text-error" />;
  }
  return <ArrowRight size={14} className="text-on-surface-variant" />;
}

export default function StatCard({
  label,
  value,
  unit,
  icon,
  trend,
  description,
  highlight = 'none',
  className,
}: StatCardProps) {
  const highlightClass =
    highlight === 'critical'
      ? 'border-error/40'
      : highlight === 'warning'
        ? 'border-tertiary/40'
        : 'border-outline/20';

  return (
    <GlassCard className={cn('h-full p-4', highlightClass, className)}>
      <div className="mb-3 flex items-center justify-between gap-2">
        <span className="ui-label">{label}</span>
        {icon ? <span className="text-primary/90">{icon}</span> : null}
      </div>

      <div className="flex items-end gap-2">
        <span className="font-mono text-[30px] font-semibold leading-none text-on-surface">{value}</span>
        {unit ? <span className="ui-label pb-1">{unit}</span> : null}
      </div>

      {description ? <p className="ui-body mt-2">{description}</p> : null}

      {trend ? (
        <motion.div whileTap={tapScale} className="mt-3 inline-flex items-center gap-1">
          <TrendIcon trend={trend} />
          <span className="ui-label">{trend}</span>
        </motion.div>
      ) : null}
    </GlassCard>
  );
}

