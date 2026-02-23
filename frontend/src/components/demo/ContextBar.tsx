import type { DemoContext } from '@/data/demoContent';

interface ContextBarProps {
  context: DemoContext;
}

export default function ContextBar({ context }: ContextBarProps) {
  return (
    <div className="rounded-lg border border-blue-500/20 bg-blue-500/5 px-4 py-3">
      <div className="flex items-center gap-2 mb-2">
        <span className="text-lg">{context.emoji}</span>
        <span className="font-syne font-bold text-white/90">{context.label}</span>
        <span className="font-dm-mono text-xs text-white/40">{context.subtitle}</span>
      </div>
      <div className="flex flex-wrap gap-2">
        {context.signals.map((signal) => (
          <span
            key={signal.label}
            className="inline-flex items-center gap-1 rounded-full bg-blue-500/10 border border-blue-500/20 px-2.5 py-0.5 font-dm-mono text-[11px] text-blue-300/80"
          >
            <span>{signal.emoji}</span>
            {signal.label}
          </span>
        ))}
      </div>
    </div>
  );
}
