import type { LucideIcon } from 'lucide-react';
import { motion } from 'framer-motion';
import { NavLink } from 'react-router-dom';
import { cn } from '../../lib/cn';

interface SidebarItemProps {
  to: string;
  label: string;
  icon: LucideIcon;
  disabled?: boolean;
}

export default function SidebarItem({ to, label, icon: Icon, disabled = false }: SidebarItemProps) {
  if (disabled) {
    return (
      <div className="flex cursor-not-allowed items-center gap-3 rounded-2xl border border-outline/10 px-3 py-2.5 text-sm text-on-surface-variant/60">
        <Icon size={16} />
        <span>{label}</span>
      </div>
    );
  }

  return (
    <NavLink
      to={to}
      end={to === '/'}
      className={({ isActive }) =>
        cn(
          'group flex items-center gap-3 rounded-2xl border px-3 py-2.5 text-sm transition-all duration-300 ease-premium',
          isActive
            ? 'border-primary/45 bg-primary/12 text-primary'
            : 'border-outline/15 text-on-surface-variant hover:border-outline/40 hover:bg-surface-container/60 hover:text-on-surface'
        )
      }
    >
      {({ isActive }) => (
        <motion.div whileHover={{ x: 1 }} className="flex items-center gap-3">
          <Icon size={16} className={isActive ? 'opacity-100' : 'opacity-80'} />
          <span>{label}</span>
        </motion.div>
      )}
    </NavLink>
  );
}

