import type { PlatformContext } from '@/data/demoPlatforms';

interface ContextSwitcherProps {
  contexts: Record<string, PlatformContext>;
  contextKeys: string[];
  activeContext: string;
  onSelect: (key: string) => void;
}

export default function ContextSwitcher({ contexts, contextKeys, activeContext, onSelect }: ContextSwitcherProps) {
  return (
    <div className="flex flex-col gap-1.5">
      {contextKeys.map((key) => {
        const ctx = contexts[key];
        const isActive = key === activeContext;
        return (
          <button
            key={key}
            onClick={() => onSelect(key)}
            className={`
              flex items-start gap-2.5 rounded-lg border px-3 py-2.5 text-left
              transition-all duration-200 cursor-pointer w-full
              ${isActive
                ? 'border-blue-500/40 bg-blue-500/10 shadow-[0_0_10px_rgba(59,130,246,0.1)]'
                : 'border-white/5 bg-white/[0.01] hover:border-white/15 hover:bg-white/[0.03]'
              }
            `}
          >
            <span className="text-base mt-0.5 flex-shrink-0">{ctx.emoji}</span>
            <div className="min-w-0">
              <div className={`font-syne text-sm font-semibold ${isActive ? 'text-blue-300' : 'text-white/50'}`}>
                {ctx.label}
              </div>
              <div className="font-dm-mono text-[10px] text-white/30 mt-0.5 leading-snug">
                {ctx.subtitle}
              </div>
            </div>
          </button>
        );
      })}
    </div>
  );
}
