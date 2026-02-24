import { useState, useMemo, useCallback } from 'react';
import {
  platforms,
  platformKeys,
  rankWithSignals,
  type PlatformKey,
  type SignalKey,
  type SignalValues,
  type RankedPlatformItem,
} from '@/data/demoPlatforms';
import ContentCard from '@/components/demo/ContentCard';
import ContextSwitcher from '@/components/demo/ContextSwitcher';
import PlatformTabs from '@/components/demo/PlatformTabs';
import SignalSliders from '@/components/demo/SignalSliders';
import ScoringFormula from '@/components/demo/ScoringFormula';
import ProphecyAgent from '@/components/demo/ProphecyAgent';

export default function Demo() {
  const [activePlatform, setActivePlatform] = useState<PlatformKey>('streaming');
  const [activeContextMap, setActiveContextMap] = useState<Record<PlatformKey, string>>({
    streaming: 'bedtime',
    music: 'wind-down',
    ecommerce: 'baby-shower',
  });
  const [signalOverrides, setSignalOverrides] = useState<Partial<SignalValues>>({});
  const [hoveredItem, setHoveredItem] = useState<RankedPlatformItem | null>(null);
  const [transitioning, setTransitioning] = useState(false);

  const platform = platforms[activePlatform];
  const activeContext = activeContextMap[activePlatform];
  const activeCtx = platform.contexts[activeContext];

  // Merge defaults with overrides
  const signals: SignalValues = useMemo(() => {
    return { ...activeCtx.defaults, ...signalOverrides };
  }, [activeCtx.defaults, signalOverrides]);

  // Rank with current signals
  const rankedItems = useMemo(
    () => rankWithSignals(platform.catalog, signals),
    [platform.catalog, signals],
  );

  // Focus item for ScoringFormula: hovered item or #1 ranked
  const focusItem = hoveredItem ?? rankedItems[0] ?? null;

  const handlePlatformSwitch = useCallback((key: PlatformKey) => {
    if (key === activePlatform) return;
    setTransitioning(true);
    setSignalOverrides({});
    setHoveredItem(null);
    setTimeout(() => {
      setActivePlatform(key);
      setTransitioning(false);
    }, 150);
  }, [activePlatform]);

  const handleContextSwitch = useCallback((key: string) => {
    if (key === activeContext) return;
    setTransitioning(true);
    setSignalOverrides({});
    setHoveredItem(null);
    setTimeout(() => {
      setActiveContextMap((prev) => ({ ...prev, [activePlatform]: key }));
      setTransitioning(false);
    }, 150);
  }, [activeContext, activePlatform]);

  const handleSignalChange = useCallback((key: SignalKey, value: number) => {
    setSignalOverrides((prev) => ({ ...prev, [key]: value }));
  }, []);

  const handleSignalReset = useCallback(() => {
    setSignalOverrides({});
  }, []);

  const handleHover = useCallback((item: RankedPlatformItem | null) => {
    setHoveredItem(item);
  }, []);

  return (
    <div className="min-h-screen bg-[#0a0a0a] text-white">
      <div className="mx-auto max-w-7xl px-4 py-6 sm:px-6 lg:px-8">
        {/* Header */}
        <header className="mb-6">
          <h1 className="font-syne text-3xl sm:text-4xl font-extrabold tracking-tight text-white/95">
            Intent Engine
          </h1>
          <p className="font-dm-mono text-sm text-white/40 mt-1">
            Context-aware re-ranking — same catalog, different intent, different order
          </p>
        </header>

        {/* Platform Tabs */}
        <section className="mb-6">
          <PlatformTabs active={activePlatform} onSelect={handlePlatformSwitch} />
        </section>

        {/* Main layout: sidebar + content + right panel */}
        <div className="flex flex-col xl:flex-row gap-6">
          {/* Left Sidebar: Context Switcher + Prophecy Agent */}
          <div className="xl:w-56 flex-shrink-0 space-y-4">
            <ContextSwitcher
              contexts={platform.contexts}
              contextKeys={platform.contextKeys}
              activeContext={activeContext}
              onSelect={handleContextSwitch}
            />
            <ProphecyAgent prophecyValue={signals.prophecy} />
          </div>

          {/* Center: Before / After columns */}
          <div
            className={`flex-1 min-w-0 transition-opacity duration-150 ${transitioning ? 'opacity-0' : 'opacity-100'}`}
          >
            {/* Active context bar */}
            <div className="rounded-lg border border-blue-500/20 bg-blue-500/5 px-4 py-3 mb-5">
              <div className="flex items-center gap-2 mb-1.5">
                <span className="text-lg">{activeCtx.emoji}</span>
                <span className="font-syne font-bold text-white/90">{activeCtx.label}</span>
                <span className="font-dm-mono text-xs text-white/40">{activeCtx.subtitle}</span>
              </div>
              <div className="flex flex-wrap gap-1.5">
                {activeCtx.signals.map((signal) => (
                  <span
                    key={signal.label}
                    className="inline-flex items-center gap-1 rounded-full bg-blue-500/10 border border-blue-500/20 px-2 py-0.5 font-dm-mono text-[10px] text-blue-300/80"
                  >
                    <span>{signal.emoji}</span>
                    {signal.label}
                  </span>
                ))}
              </div>
            </div>

            <div className="grid grid-cols-1 lg:grid-cols-2 gap-5">
              {/* Before column */}
              <div>
                <div className="flex items-center gap-2 mb-3">
                  <h2 className="font-syne text-lg font-bold text-white/70">Before</h2>
                  <span className="font-dm-mono text-[11px] text-white/30">Engagement score only</span>
                </div>
                <div className="space-y-2">
                  {platform.catalog.map((item, i) => (
                    <ContentCard key={item.id} item={item} rank={i + 1} variant="before" />
                  ))}
                </div>
              </div>

              {/* After column */}
              <div>
                <div className="flex items-center gap-2 mb-3">
                  <h2 className="font-syne text-lg font-bold text-green-400/80">After</h2>
                  <span className="font-dm-mono text-[11px] text-white/30">Intent-adjusted</span>
                </div>
                <div className="space-y-2">
                  {rankedItems.map((item, i) => (
                    <div key={item.id} className="relative">
                      {/* Movement indicator */}
                      {item.movement !== 0 && (
                        <div className="absolute -left-5 top-1/2 -translate-y-1/2 font-dm-mono text-[10px] hidden lg:block">
                          {item.movement > 0 ? (
                            <span className="text-green-400">+{item.movement}</span>
                          ) : (
                            <span className="text-red-400">{item.movement}</span>
                          )}
                        </div>
                      )}
                      <ContentCard item={item} rank={i + 1} variant="after" onHover={handleHover} />
                    </div>
                  ))}
                </div>
              </div>
            </div>
          </div>

          {/* Right Sidebar: Signal Sliders + Scoring Formula */}
          <div className="xl:w-72 flex-shrink-0 space-y-4">
            <SignalSliders
              configs={platform.signalConfigs}
              values={signals}
              defaults={activeCtx.defaults}
              onChange={handleSignalChange}
              onReset={handleSignalReset}
            />
            <ScoringFormula item={focusItem} />
          </div>
        </div>

        {/* Footer */}
        <footer className="mt-10 pt-4 border-t border-white/5">
          <p className="font-dm-mono text-xs text-white/20 text-center">
            Intent Engine — context-aware content re-ranking demo
          </p>
        </footer>
      </div>
    </div>
  );
}
