import { motion } from 'framer-motion';

interface RainLoaderProps {
  label?: string;
  mode?: 'full' | 'compact';
  className?: string;
}

const drops = [
  { x: '-34%', delay: 0.0, duration: 1.65 },
  { x: '-22%', delay: 0.14, duration: 1.8 },
  { x: '-10%', delay: 0.22, duration: 1.7 },
  { x: '2%', delay: 0.34, duration: 1.9 },
  { x: '14%', delay: 0.48, duration: 1.76 },
  { x: '26%', delay: 0.6, duration: 1.84 },
  { x: '38%', delay: 0.76, duration: 1.74 },
];

export default function RainLoader({
  label = 'FloodSense',
  mode = 'full',
  className,
}: RainLoaderProps) {
  const isFull = mode === 'full';

  return (
    <div
      className={`${
        isFull
          ? 'flex min-h-screen w-full items-center justify-center bg-surface/94 backdrop-blur-xl'
          : 'flex items-center gap-3'
      } ${className ?? ''}`}
    >
      <div className={`${isFull ? 'flex flex-col items-center gap-6' : 'flex items-center gap-3'}`}>
        <div className="relative h-[84px] w-[168px]">
          <motion.div
            className="absolute left-1/2 top-1/2 h-14 w-14 -translate-x-1/2 -translate-y-1/2 rounded-full bg-primary/18 blur-2xl"
            animate={{ opacity: [0.4, 0.72, 0.4], scale: [0.9, 1.08, 0.9] }}
            transition={{ duration: 2.2, repeat: Infinity, ease: [0.22, 1, 0.36, 1] }}
          />
          {drops.map((drop, index) => (
            <motion.span
              key={`${drop.x}-${index}`}
              className="absolute left-1/2 top-2 h-2.5 w-1.5 rounded-full bg-primary shadow-[0_0_18px_rgba(56,189,248,0.8)]"
              style={{ marginLeft: drop.x }}
              initial={{ y: -10, opacity: 0 }}
              animate={{ y: [0, 44], opacity: [0, 1, 0] }}
              transition={{
                duration: drop.duration,
                repeat: Infinity,
                delay: drop.delay,
                ease: 'linear',
              }}
            />
          ))}
          <motion.div
            className="absolute inset-x-[36px] bottom-2 h-[2px] rounded-full bg-secondary/65"
            animate={{ opacity: [0.2, 0.75, 0.2], scaleX: [0.92, 1.06, 0.92] }}
            transition={{ duration: 1.8, repeat: Infinity, ease: [0.22, 1, 0.36, 1] }}
          />
        </div>

        <div className={`${isFull ? 'text-center' : ''}`}>
          <div className="ui-headline text-[30px] leading-none text-on-surface">{label}</div>
          {isFull ? <div className="ui-label mt-2">Calibrating Rain Intelligence</div> : null}
        </div>
      </div>
    </div>
  );
}
