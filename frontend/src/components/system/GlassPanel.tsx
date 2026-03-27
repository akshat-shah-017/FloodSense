import { motion } from 'framer-motion';
import type { ReactNode } from 'react';
import { cn } from '../../lib/cn';

interface GlassPanelProps {
  children: ReactNode;
  className?: string;
}

export default function GlassPanel({ children, className }: GlassPanelProps) {
  return <section className={cn('glass-panel p-6', className)}>{children}</section>;
}

export function AnimatedGlassPanel({ children, className }: GlassPanelProps) {
  return (
    <motion.section
      whileHover={{ y: -2, transition: { duration: 0.22 } }}
      className={cn('glass-panel p-6', className)}
    >
      {children}
    </motion.section>
  );
}

