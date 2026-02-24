import type { ScoringBreakdown, RankedPlatformItem } from '@/data/demoPlatforms';

interface ScoringFormulaProps {
  item: RankedPlatformItem | null;
}

function fmtMul(val: number): string {
  return val.toFixed(2);
}

function mulColor(val: number): string {
  if (val >= 1.1) return 'text-green-400';
  if (val >= 0.9) return 'text-white/70';
  if (val >= 0.5) return 'text-amber-400';
  return 'text-red-400';
}

export default function ScoringFormula({ item }: ScoringFormulaProps) {
  if (!item) {
    return (
      <div className="rounded-lg border border-white/10 bg-[#0d0d0d] p-4">
        <h3 className="font-syne text-sm font-bold text-white/80 mb-3">Scoring Formula</h3>
        <p className="font-dm-mono text-[11px] text-white/30">Select or hover an item to see its breakdown</p>
      </div>
    );
  }

  const b: ScoringBreakdown = item.breakdown;

  return (
    <div className="rounded-lg border border-white/10 bg-[#0d0d0d] p-4">
      <div className="flex items-center justify-between mb-3">
        <h3 className="font-syne text-sm font-bold text-white/80">Scoring Formula</h3>
        <span className="font-dm-mono text-[10px] text-white/30">{item.emoji} {item.title}</span>
      </div>

      <pre className="font-dm-mono text-[11px] leading-relaxed overflow-x-auto">
        <code>
          <span className="text-white/40">{'// Multiplier-based scoring\n'}</span>
          <span className="text-white/60">{'final_score = '}</span>
          <span className="text-white/80">base</span>
          <span className="text-white/40">(</span>
          <span className="text-blue-300">{fmtMul(b.baseScore)}</span>
          <span className="text-white/40">)</span>
          {'\n'}

          <span className="text-white/40">{'  × '}</span>
          <span className="text-white/80">time</span>
          <span className="text-white/40">(</span>
          <span className={mulColor(b.timeMultiplier)}>{fmtMul(b.timeMultiplier)}</span>
          <span className="text-white/40">)</span>
          {'\n'}

          <span className="text-white/40">{'  × '}</span>
          <span className="text-white/80">viewer</span>
          <span className="text-white/40">(</span>
          <span className={mulColor(b.viewerMultiplier)}>{fmtMul(b.viewerMultiplier)}</span>
          <span className="text-white/40">)</span>
          {'\n'}

          <span className="text-white/40">{'  × '}</span>
          <span className="text-white/80">energy</span>
          <span className="text-white/40">(</span>
          <span className={mulColor(b.energyMultiplier)}>{fmtMul(b.energyMultiplier)}</span>
          <span className="text-white/40">)</span>
          {'\n'}

          <span className="text-white/40">{'  × '}</span>
          <span className="text-white/80">device</span>
          <span className="text-white/40">(</span>
          <span className={mulColor(b.deviceMultiplier)}>{fmtMul(b.deviceMultiplier)}</span>
          <span className="text-white/40">)</span>
          {'\n'}

          <span className="text-white/40">{'  × '}</span>
          <span className="text-white/80">prophecy</span>
          <span className="text-white/40">(</span>
          <span className={mulColor(b.prophecyBoost)}>{fmtMul(b.prophecyBoost)}</span>
          <span className="text-white/40">)</span>
          {'\n'}

          <span className="text-white/40">{'  + '}</span>
          <span className="text-white/80">diversity</span>
          <span className="text-white/40">(</span>
          <span className={b.diversityPenalty < 0 ? 'text-red-400' : 'text-white/50'}>{b.diversityPenalty >= 0 ? '+' : ''}{fmtMul(b.diversityPenalty)}</span>
          <span className="text-white/40">)</span>
          {'\n\n'}

          <span className="text-white/40">{'  = '}</span>
          <span className="text-green-300 font-bold">{fmtMul(b.finalScore)}</span>
          {'\n'}

          {b.blocked && (
            <>
              {'\n'}
              <span className="text-red-400">{'// '}{b.blockReason || 'BLOCKED'}</span>
              {'\n'}
              <span className="text-red-400/70">{'if (maturity === "adult" && viewer === "kids") → BLOCKED'}</span>
            </>
          )}
        </code>
      </pre>
    </div>
  );
}
