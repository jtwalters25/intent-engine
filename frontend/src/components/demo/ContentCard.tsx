import type { DemoItem, RankedDemoItem } from '@/data/demoContent';

interface ContentCardProps {
  item: DemoItem | RankedDemoItem;
  rank: number;
  variant: 'before' | 'after';
}

function isRanked(item: DemoItem | RankedDemoItem): item is RankedDemoItem {
  return 'intentScore' in item;
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

export default function ContentCard({ item, rank, variant }: ContentCardProps) {
  const ranked = variant === 'after' && isRanked(item) ? item : null;
  const score = ranked ? ranked.intentScore : item.engagementScore;
  const isBoosted = ranked?.status === 'boosted';
  const isBlocked = ranked?.status === 'blocked';
  const isDemoted = ranked?.status === 'demoted';

  return (
    <div
      className={`
        relative flex items-center gap-3 rounded-lg border p-3 transition-all duration-300
        ${isBoosted ? 'border-green-500/40 bg-green-500/5 shadow-[0_0_15px_rgba(34,197,94,0.1)]' : 'border-white/5 bg-white/[0.02]'}
        ${isBlocked || isDemoted ? 'opacity-50' : ''}
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
          background: `linear-gradient(135deg, ${item.thumbnail ? 'rgba(255,255,255,0.05)' : '#1a1a2e'}, rgba(255,255,255,0.02))`,
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
        {ranked && ranked.reason && (
          <div className="font-dm-mono text-[10px] text-green-400/70 mt-1 leading-tight line-clamp-2">
            {ranked.reason}
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
