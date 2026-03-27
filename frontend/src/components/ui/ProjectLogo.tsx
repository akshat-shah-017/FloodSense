import { useState } from 'react';
import logoJpg from '../../assets/branding/floodsense-logo.jpg';
import logoSvg from '../../assets/branding/floodsense-logo.svg';

interface ProjectLogoProps {
  className?: string;
  alt?: string;
}

export default function ProjectLogo({
  className = 'h-10 w-10 rounded-xl border border-outline/20 object-cover object-[14%_50%]',
  alt = 'FloodSense logo',
}: ProjectLogoProps) {
  const [fallback, setFallback] = useState(false);

  return (
    <img
      src={fallback ? logoJpg : logoSvg}
      alt={alt}
      className={className}
      loading="eager"
      decoding="async"
      onError={() => setFallback(true)}
    />
  );
}
