import type { PlatformItem, RankedPlatformItem } from '@/data/demoPlatforms';

interface ContentCardProps {
  item: PlatformItem | RankedPlatformItem;
  rank: number;
  variant: 'before' | 'after';
  onHover?: (item: RankedPlatformItem | null) => void;
}

function isRanked(item: PlatformItem | RankedPlatformItem): item is RankedPlatformItem {
  return 'breakdown' in item;
}

function scoreColor(score: number): string {
  if (score >= 0.8) return 'text-green-400';
  if (score >= 0.5) return 'text-amber-400';
  return 'text-neutral-500';
}

function scoreBg(score: number): string {
  if (score >= 0.8) return 'bg-green-400/10 border-green-400/30';
  if (score >= 0.5) return 'bg-amber-400/10 border-amber-400/30';
  return 'bg-neutral-500/10 border-neutral-500/30';
}

export default function ContentCard({ item, rank, variant, onHover }: ContentCardProps) {
  const ranked = variant === 'after' && isRanked(item) ? item : null;
  const score = ranked ? ranked.breakdown.finalScore : item.engagementScore;
  const isBoosted = ranked?.status === 'boosted';
  const isBlocked = ranked?.status === 'blocked';
  const isDemoted = ranked?.status === 'demoted';

  const handleMouseEnter = () => {
    if (ranked && onHover) onHover(ranked);
  };

  const handleMouseLeave = () => {
    if (onHover) onHover(null);
  };

  // Build a brief reason string from the breakdown
  const reason = ranked
    ? ranked.breakdown.blocked
      ? ranked.breakdown.blockReason || 'Blocked'
      : `time ×${ranked.breakdown.timeMultiplier} · viewer ×${ranked.breakdown.viewerMultiplier} · energy ×${ranked.breakdown.energyMultiplier}`
    : null;

  return (
    <div
      onMouseEnter={handleMouseEnter}
      onMouseLeave={handleMouseLeave}
      className={`
        relative flex items-center gap-3 rounded-lg border p-3 transition-all duration-300
        ${isBoosted ? 'border-green-500/40 bg-green-500/5 shadow-[0_0_15px_rgba(34,197,94,0.1)]' : 'border-white/5 bg-white/[0.02]'}
        ${isBlocked || isDemoted ? 'opacity-50' : ''}
        ${onHover ? 'cursor-pointer' : ''}
      `}
    >
      {/* Rank number */}
      <div className="font-fraunces flex-shrink-0 w-8 text-center text-2xl italic text-white/30">
        {rank}
      </div>

      {/* Emoji thumbnail */}
      <div
        className="flex-shrink-0 w-14 h-14 rounded-md flex items-center justify-center text-2xl"
        style={{
          background: `linear-gradient(135deg, rgba(255,255,255,0.05), rgba(255,255,255,0.02))`,
        }}
      >
        {item.emoji}
      </div>

      {/* Info */}
      <div className="flex-1 min-w-0">
        <div className="font-syne font-bold text-sm text-white/90 truncate">
          {item.title}
        </div>
        <div className="font-dm-mono text-[11px] text-white/40 mt-0.5">
          {item.genre} · {item.rating} · {item.runtime}
        </div>
        {reason && variant === 'after' && (
          <div className="font-dm-mono text-[10px] text-green-400/70 mt-1 leading-tight line-clamp-2">
            {reason}
          </div>
        )}
      </div>

      {/* Score badge */}
      <div className={`flex-shrink-0 px-2 py-1 rounded border font-dm-mono text-xs font-medium ${scoreBg(score)} ${scoreColor(score)}`}>
        {score.toFixed(2)}
      </div>

      {/* Blocked overlay */}
      {isBlocked && (
        <div className="absolute inset-0 rounded-lg flex items-center justify-center bg-black/40">
          <span className="font-dm-mono text-xs text-red-400/80 bg-red-400/10 px-2 py-0.5 rounded border border-red-400/20">
            BLOCKED
          </span>
        </div>
      )}
    </div>
  );
}
