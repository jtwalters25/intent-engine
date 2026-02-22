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
  const lowerBadge = badge.toLowerCase();
  if (lowerBadge.includes('low energy') || lowerBadge.includes('calm')) {
    return 'bg-badge-calm/20 text-badge-calm border-badge-calm/30';
  }
  if (lowerBadge.includes('ages') || lowerBadge.includes('age')) {
    return 'bg-badge-age/20 text-badge-age border-badge-age/30';
  }
  if (lowerBadge.includes('stem') || lowerBadge.includes('science') || lowerBadge.includes('math')) {
    return 'bg-stem/20 text-stem border-stem/30';
  }
  if (lowerBadge.includes('emotional') || lowerBadge.includes('feelings') || lowerBadge.includes('values')) {
    return 'bg-emotional/20 text-emotional border-emotional/30';
  }
  if (lowerBadge.includes('social') || lowerBadge.includes('teamwork')) {
    return 'bg-social/20 text-social border-social/30';
  }
  if (lowerBadge.includes('reading') || lowerBadge.includes('phonics') || lowerBadge.includes('literacy')) {
    return 'bg-literacy/20 text-literacy border-literacy/30';
  }
  return 'bg-muted text-muted-foreground border-border';
};

const ShowCard: React.FC<ShowCardProps> = ({ title, thumbnail, badges, onClick, className }) => {
  return (
    <div
      onClick={onClick}
      className={cn(
        'group cursor-pointer flex-shrink-0 w-[180px] sm:w-[220px] md:w-[260px] transition-all duration-300',
        'hover:scale-105 hover:z-10',
        className
      )}
    >
      <div className="relative overflow-hidden rounded-lg bg-card shadow-lg">
        {/* Thumbnail */}
        <div className="aspect-video overflow-hidden">
          <img
            src={thumbnail}
            alt={title}
            className="h-full w-full object-cover transition-transform duration-500 group-hover:scale-110"
          />
          {/* Hover overlay */}
          <div className="absolute inset-0 bg-gradient-to-t from-background/90 via-background/20 to-transparent opacity-0 group-hover:opacity-100 transition-opacity duration-300" />
        </div>

        {/* Content */}
        <div className="p-3">
          <h3 className="font-semibold text-sm sm:text-base text-foreground truncate mb-2 group-hover:text-primary transition-colors">
            {title}
          </h3>
          
          {/* Badges */}
          <div className="flex flex-wrap gap-1.5">
            {badges.slice(0, 3).map((badge, index) => (
              <span
                key={index}
                className={cn(
                  'text-[10px] sm:text-xs px-2 py-0.5 rounded-full border',
                  getBadgeColor(badge)
                )}
              >
                {badge}
              </span>
            ))}
          </div>
        </div>

        {/* Play button overlay on hover */}
        <div className="absolute inset-0 flex items-center justify-center opacity-0 group-hover:opacity-100 transition-opacity duration-300 pointer-events-none">
          <div className="w-12 h-12 rounded-full bg-primary/90 flex items-center justify-center shadow-lg">
            <svg className="w-5 h-5 text-primary-foreground ml-1" fill="currentColor" viewBox="0 0 24 24">
              <path d="M8 5v14l11-7z" />
            </svg>
          </div>
        </div>
      </div>
    </div>
  );
};

export default ShowCard;
