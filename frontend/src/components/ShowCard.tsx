import React from 'react';
import { cn } from '@/lib/utils';

interface ShowCardProps {
  title: string;
  thumbnail: string;
  badges: string[];
  onClick?: () => void;
  className?: string;
}

const getBadgeColor = (badge: string): string => {
  const b = badge.toLowerCase();
  if (b.includes('low energy') || b.includes('calm'))
    return 'bg-badge-calm/20 text-badge-calm border-badge-calm/30';
  if (b.includes('high energy'))
    return 'bg-energy-high/20 text-energy-high border-energy-high/30';
  if (b.includes('medium energy'))
    return 'bg-muted/60 text-foreground/70 border-border';
  if (b.includes('ages'))
    return 'bg-badge-age/20 text-badge-age border-badge-age/30';
  if (b.includes('stem') || b.includes('science') || b.includes('math'))
    return 'bg-stem/20 text-stem border-stem/30';
  if (b.includes('emotional') || b.includes('feelings') || b.includes('values'))
    return 'bg-emotional/20 text-emotional border-emotional/30';
  if (b.includes('social') || b.includes('teamwork'))
    return 'bg-social/20 text-social border-social/30';
  if (b.includes('reading') || b.includes('phonics') || b.includes('literacy'))
    return 'bg-literacy/20 text-literacy border-literacy/30';
  return 'bg-muted text-muted-foreground border-border';
};

const ShowCard: React.FC<ShowCardProps> = ({ title, thumbnail, badges, onClick, className }) => {
  return (
    <div
      onClick={onClick}
      className={cn(
        'group cursor-pointer flex-shrink-0 w-[180px] sm:w-[220px] md:w-[260px]',
        'transition-transform duration-300 ease-out',
        'hover:scale-105 hover:z-10',
        'motion-reduce:transition-none motion-reduce:hover:scale-100',
        className,
      )}
    >
      <div className="relative overflow-hidden rounded-xl bg-card shadow-lg ring-1 ring-white/5">
        {/* Thumbnail */}
        <div className="aspect-video overflow-hidden">
          <img
            src={thumbnail}
            alt={title}
            loading="lazy"
            className="h-full w-full object-cover transition-transform duration-500 group-hover:scale-110 motion-reduce:group-hover:scale-100"
          />
          {/* Hover gradient */}
          <div className="absolute inset-0 bg-gradient-to-t from-background/80 via-transparent to-transparent opacity-0 group-hover:opacity-100 transition-opacity duration-300" />
        </div>

        {/* Content */}
        <div className="p-3">
          <h3 className="font-semibold text-sm sm:text-base text-foreground truncate mb-1.5 group-hover:text-primary transition-colors">
            {title}
          </h3>
          <div className="flex flex-wrap gap-1.5">
            {badges.slice(0, 2).map((badge, index) => (
              <span
                key={index}
                className={cn(
                  'text-xs px-2 py-0.5 rounded-full border font-medium',
                  getBadgeColor(badge),
                )}
              >
                {badge}
              </span>
            ))}
          </div>
        </div>

        {/* Play button on hover */}
        <div className="absolute inset-0 flex items-center justify-center opacity-0 group-hover:opacity-100 transition-opacity duration-300 pointer-events-none">
          <div className="w-12 h-12 rounded-full bg-primary/90 backdrop-blur-sm flex items-center justify-center shadow-xl">
            <svg className="w-5 h-5 text-primary-foreground ml-0.5" fill="currentColor" viewBox="0 0 24 24">
              <path d="M8 5v14l11-7z" />
            </svg>
          </div>
        </div>
      </div>
    </div>
  );
};

export default ShowCard;
