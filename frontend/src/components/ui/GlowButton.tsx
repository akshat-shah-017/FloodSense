import { Loader2 } from 'lucide-react';
import { motion } from 'framer-motion';
import type { ReactNode } from 'react';
import { cn } from '../../lib/cn';
import { tapScale } from '../system/motion';

interface GlowButtonProps {
  children: ReactNode;
  onClick?: () => void;
  variant?: 'primary' | 'danger' | 'ghost';
  loading?: boolean;
  disabled?: boolean;
  className?: string;
  type?: 'button' | 'submit' | 'reset';
}

const variantClasses: Record<NonNullable<GlowButtonProps['variant']>, string> = {
  primary:
    'border border-primary/50 bg-primary/16 text-primary hover:border-primary/65 hover:bg-primary/22',
  danger: 'border border-error/50 bg-error/14 text-error hover:border-error/65 hover:bg-error/20',
  ghost:
    'border border-outline/35 bg-surface-container/55 text-on-surface hover:border-outline/50 hover:bg-surface-container/85',
};

export default function GlowButton({
  children,
  onClick,
  variant = 'primary',
  loading = false,
  disabled = false,
  className,
  type = 'button',
}: GlowButtonProps) {
  return (
    <motion.button
      whileTap={tapScale}
      type={type}
      onClick={onClick}
      disabled={disabled || loading}
      className={cn(
        'focus-ring inline-flex min-h-10 items-center justify-center gap-2 rounded-2xl px-4 font-mono text-[11px] uppercase tracking-[0.12em] shadow-glass transition-all duration-300 ease-premium disabled:cursor-not-allowed disabled:opacity-55',
        variantClasses[variant],
        className
      )}
    >
      {loading ? <Loader2 size={14} className="animate-spin" /> : null}
      <span>{children}</span>
    </motion.button>
  );
}

