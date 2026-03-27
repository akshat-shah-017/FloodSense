import { motion } from 'framer-motion';
import { cn } from '../../lib/cn';

interface StatusDotProps {
  color?: 'success' | 'warning' | 'critical' | 'neutral' | 'primary';
  pulse?: boolean;
  className?: string;
}

const colorClasses: Record<NonNullable<StatusDotProps['color']>, string> = {
  success: 'bg-secondary',
  warning: 'bg-tertiary',
  critical: 'bg-error',
  neutral: 'bg-on-surface-variant',
  primary: 'bg-primary',
};

export default function StatusDot({ color = 'success', pulse = false, className }: StatusDotProps) {
  if (!pulse) {
    return <span className={cn('inline-flex h-2 w-2 rounded-full', colorClasses[color], className)} />;
  }

  return (
    <motion.span
      className={cn('inline-flex h-2 w-2 rounded-full', colorClasses[color], className)}
      animate={{ scale: [1, 1.35, 1], opacity: [1, 0.45, 1] }}
      transition={{ duration: 1.6, repeat: Infinity }}
    />
  );
}

