import { useState, useMemo } from 'react';
import { catalog, contexts, rankForContext, type ContextKey } from '@/data/demoContent';
import ContentCard from '@/components/demo/ContentCard';
import ContextBar from '@/components/demo/ContextBar';
import ContextSwitcher from '@/components/demo/ContextSwitcher';

export default function Demo() {
  const [activeContext, setActiveContext] = useState<ContextKey>('bedtime');
  const [transitioning, setTransitioning] = useState(false);

  const rankedItems = useMemo(
    () => rankForContext(catalog, activeContext),
    [activeContext],
  );

  const activeCtx = contexts[activeContext];

  const handleContextSwitch = (key: ContextKey) => {
    if (key === activeContext) return;
    setTransitioning(true);
    setTimeout(() => {
      setActiveContext(key);
      setTransitioning(false);
    }, 150);
  };

  return (
    <div className="min-h-screen bg-[#0a0a0a] text-white">
      <div className="mx-auto max-w-6xl px-4 py-8 sm:px-6 lg:px-8">
        {/* Header */}
        <header className="mb-8">
          <h1 className="font-syne text-3xl sm:text-4xl font-extrabold tracking-tight text-white/95">
            Intent Engine
          </h1>
          <p className="font-dm-mono text-sm text-white/40 mt-1">
            Context-aware re-ranking — same catalog, different intent, different order
          </p>
        </header>

        {/* Context Switcher */}
        <section className="mb-6">
          <ContextSwitcher activeContext={activeContext} onSelect={handleContextSwitch} />
        </section>

        {/* Active Context Bar */}
        <section className="mb-8">
          <ContextBar context={activeCtx} />
        </section>

        {/* Before / After columns */}
        <div
          className={`transition-opacity duration-150 ${transitioning ? 'opacity-0' : 'opacity-100'}`}
        >
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
            {/* Before column */}
            <div>
              <div className="flex items-center gap-2 mb-4">
                <h2 className="font-syne text-lg font-bold text-white/70">Before</h2>
                <span className="font-dm-mono text-[11px] text-white/30">Engagement score only</span>
              </div>
              <div className="space-y-2">
                {catalog.map((item, i) => (
                  <ContentCard key={item.id} item={item} rank={i + 1} variant="before" />
                ))}
              </div>
            </div>

            {/* Movement arrows (desktop) */}
            <div className="hidden lg:block relative">
              {/* After column header */}
              <div className="flex items-center gap-2 mb-4">
                <h2 className="font-syne text-lg font-bold text-green-400/80">After</h2>
                <span className="font-dm-mono text-[11px] text-white/30">Intent-adjusted</span>
              </div>

              {/* Movement indicators between columns */}
              <div className="space-y-2">
                {rankedItems.map((item, i) => (
                  <div key={item.id} className="relative">
                    {/* Movement arrow indicator */}
                    {item.movement !== 0 && (
                      <div className="absolute -left-6 top-1/2 -translate-y-1/2 font-dm-mono text-[10px]">
                        {item.movement > 0 ? (
                          <span className="text-green-400">+{item.movement}</span>
                        ) : (
                          <span className="text-red-400">{item.movement}</span>
                        )}
                      </div>
                    )}
                    <ContentCard item={item} rank={i + 1} variant="after" />
                  </div>
                ))}
              </div>
            </div>

            {/* After column (mobile — no movement arrows) */}
            <div className="lg:hidden">
              <div className="flex items-center gap-2 mb-4">
                <h2 className="font-syne text-lg font-bold text-green-400/80">After</h2>
                <span className="font-dm-mono text-[11px] text-white/30">Intent-adjusted</span>
              </div>
              <div className="space-y-2">
                {rankedItems.map((item, i) => (
                  <ContentCard key={item.id} item={item} rank={i + 1} variant="after" />
                ))}
              </div>
            </div>
          </div>
        </div>

        {/* Footer */}
        <footer className="mt-12 pt-6 border-t border-white/5">
          <p className="font-dm-mono text-xs text-white/20 text-center">
            Intent Engine — context-aware content re-ranking demo
          </p>
        </footer>
      </div>
    </div>
  );
}
