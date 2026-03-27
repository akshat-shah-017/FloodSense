import { motion } from 'framer-motion';
import type { ReactNode } from 'react';
import { cn } from '../../lib/cn';
import { cardHover } from './motion';

interface GlassCardProps {
  children: ReactNode;
  className?: string;
  interactive?: boolean;
}

export default function GlassCard({ children, className, interactive = true }: GlassCardProps) {
  if (!interactive) {
    return <article className={cn('glass-card p-4', className)}>{children}</article>;
  }

  return (
    <motion.article whileHover={cardHover} className={cn('glass-card interactive-card p-4', className)}>
      {children}
    </motion.article>
  );
}

