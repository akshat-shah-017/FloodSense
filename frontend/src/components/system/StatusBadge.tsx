import { motion } from 'framer-motion';
import { cn } from '../../lib/cn';

export type StatusTone = 'success' | 'warning' | 'critical' | 'neutral';

interface StatusBadgeProps {
  label: string;
  tone?: StatusTone;
  pulse?: boolean;
  className?: string;
}

const toneClasses: Record<StatusTone, string> = {
  success: 'border-secondary/45 bg-secondary/12 text-secondary',
  warning: 'border-tertiary/45 bg-tertiary/12 text-tertiary',
  critical: 'border-error/45 bg-error/12 text-error',
  neutral: 'border-outline/40 bg-outline/10 text-on-surface-variant',
};

export function toneFromTier(tier?: string): StatusTone {
  if (tier === 'HIGH' || tier === 'RED' || tier === 'CRITICAL' || tier === 'FAILED') {
    return 'critical';
  }
  if (tier === 'MEDIUM' || tier === 'YELLOW' || tier === 'WARNING' || tier === 'PENDING') {
    return 'warning';
  }
  if (
    tier === 'LOW' ||
    tier === 'ALL_CLEAR' ||
    tier === 'FRESH' ||
    tier === 'SUCCESS' ||
    tier === 'SENT' ||
    tier === 'ACTIVE'
  ) {
    return 'success';
  }
  return 'neutral';
}

export default function StatusBadge({ label, tone = 'neutral', pulse = false, className }: StatusBadgeProps) {
  return (
    <span
      className={cn(
        'inline-flex items-center gap-2 rounded-full border px-3 py-1 font-mono text-[10px] uppercase tracking-[0.14em]',
        toneClasses[tone],
        className
      )}
    >
      {pulse ? (
        <motion.span
          className={cn(
            'h-1.5 w-1.5 rounded-full',
            tone === 'success' && 'bg-secondary',
            tone === 'warning' && 'bg-tertiary',
            tone === 'critical' && 'bg-error',
            tone === 'neutral' && 'bg-on-surface-variant'
          )}
          animate={{ scale: [1, 1.3, 1], opacity: [0.9, 0.5, 0.9] }}
          transition={{ duration: 1.6, repeat: Infinity }}
        />
      ) : null}
      {label}
    </span>
  );
}
