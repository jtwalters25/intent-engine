import { useState, useMemo, useCallback, useEffect, useRef } from 'react';
import {
  platforms,
  platformKeys,
  rankWithSignals,
  type PlatformKey,
  type SignalKey,
  type SignalValues,
} from '@/data/demoPlatforms';
import SignalSliders from '@/components/demo/SignalSliders';
import ScoringFormula from '@/components/demo/ScoringFormula';
import ProphecyAgent from '@/components/demo/ProphecyAgent';
import PosterGrid, { HeldStrip, type OrderView } from '@/components/demo/film/PosterGrid';

const SHELF_SIZE = 9;
import FocusPanel from '@/components/demo/film/FocusPanel';

/** Context subtitles read "8:45 PM — winding down for sleep"; split into the time and the description. */
function splitSubtitle(subtitle: string): { when: string; what: string } {
  const i = subtitle.indexOf(' — ');
  return i === -1 ? { when: '', what: subtitle } : { when: subtitle.slice(0, i), what: subtitle.slice(i + 3) };
}

export default function Demo() {
  const [calm, setCalm] = useState<boolean>(() => {
    try { return localStorage.getItem('demo-calm') === '1'; } catch { return false; }
  });
  const toggleCalm = useCallback(() => {
    setCalm((v) => {
      const next = !v;
      try { localStorage.setItem('demo-calm', next ? '1' : '0'); } catch { /* ignore */ }
      return next;
    });
  }, []);
  const [activePlatform, setActivePlatform] = useState<PlatformKey>('streaming');
  const [activeContextMap, setActiveContextMap] = useState<Record<PlatformKey, string>>({
    streaming: 'bedtime',
    music: 'wind-down',
    ecommerce: 'baby-shower',
    ride_matching: 'morning-commute',
    food_delivery: 'sunday-comfort',
  });
  const [signalOverrides, setSignalOverrides] = useState<Partial<SignalValues>>({});
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [view, setView] = useState<OrderView>('moment');
  const [whyOpen, setWhyOpen] = useState(false);
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

  // A shelf shows the top picks, like a real app's row. Held-back titles sort last
  // (score 0), so the shelf keeps each title's rank from the full ranking.
  const heldItems = useMemo(() => rankedItems.filter((r) => r.breakdown.blocked), [rankedItems]);
  const displayItems = useMemo(() => {
    if (view === 'moment') return rankedItems.filter((r) => !r.breakdown.blocked).slice(0, SHELF_SIZE);
    // Engagement view: the catalog's own order, same ranked objects so details stay available
    const byId = new Map(rankedItems.map((r) => [r.id, r]));
    return platform.catalog.slice(0, SHELF_SIZE).map((c) => byId.get(c.id)!);
  }, [view, rankedItems, platform.catalog]);

  // Focus: the selected tile, else the #1 pick for this moment
  const focusItem = rankedItems.find((r) => r.id === selectedId) ?? rankedItems[0] ?? null;
  const focusRank = focusItem ? rankedItems.indexOf(focusItem) + 1 : 0;

  // On one-column layouts the focus panel sits below the grid; bring it into view on select
  const sideRef = useRef<HTMLElement>(null);
  const handleSelect = useCallback((id: string) => {
    setSelectedId((cur) => (cur === id ? null : id));
    const el = sideRef.current;
    if (el && window.matchMedia('(max-width: 1023px)').matches) {
      const reduce = window.matchMedia('(prefers-reduced-motion: reduce)').matches;
      requestAnimationFrame(() => el.scrollIntoView({ behavior: reduce ? 'auto' : 'smooth', block: 'start' }));
    }
  }, []);

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => { if (e.key === 'Escape') setSelectedId(null); };
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, []);

  const handlePlatformSwitch = useCallback((key: PlatformKey) => {
    if (key === activePlatform) return;
    setTransitioning(true);
    setSignalOverrides({});
    setSelectedId(null);
    setTimeout(() => {
      setActivePlatform(key);
      setTransitioning(false);
    }, 150);
  }, [activePlatform]);

  // No fade on context change: the tiles slide into their new order instead
  const handleContextSwitch = useCallback((key: string) => {
    if (key === activeContext) return;
    setSignalOverrides({});
    setView('moment');
    setActiveContextMap((prev) => ({ ...prev, [activePlatform]: key }));
  }, [activeContext, activePlatform]);

  const handleSignalChange = useCallback((key: SignalKey, value: number) => {
    setSignalOverrides((prev) => ({ ...prev, [key]: value }));
  }, []);

  const handleSignalReset = useCallback(() => {
    setSignalOverrides({});
  }, []);

  const { when, what } = splitSubtitle(activeCtx.subtitle);

  return (
    <div className={`demo-root film min-h-screen bg-[var(--demo-bg)] text-white transition-colors duration-500 ${calm ? 'demo-calm' : ''}`}>
      <div className="film-wrap">
        {/* Header */}
        <header className="film-header">
          <div className="min-w-0">
            <h1 className="film-wordmark">Intent Engine</h1>
            <p className="film-tagline">Same catalog. Different moment. Different order.</p>
          </div>
          <div className="film-header-actions">
            <button type="button" aria-pressed={calm} onClick={toggleCalm} title="Warm, low-stimulation palette" className="film-chip-btn">
              {calm ? 'Calm: on' : 'Calm: off'}
            </button>
          </div>
        </header>

        {/* Platforms */}
        <nav className="film-platforms" aria-label="Platform">
          {platformKeys.map((key) => (
            <button key={key} type="button" aria-pressed={key === activePlatform} onClick={() => handlePlatformSwitch(key)}>
              {platforms[key].label}
              {key === 'streaming' && <span className="film-tag">pilot</span>}
            </button>
          ))}
        </nav>

        <div className={`film-layout transition-opacity duration-150 ${transitioning ? 'opacity-0' : 'opacity-100'}`}>
          <div className="min-w-0">
            {/* Moment hero */}
            <section className="film-hero" aria-live="polite">
              <p className="film-when">{when || activeCtx.label}</p>
              {when && <p className="film-moment">{activeCtx.label}</p>}
              <p className="film-what">{what}</p>
              <ul className="film-signals" aria-label="Signals in this moment">
                {activeCtx.signals.map((s) => <li key={s.label}>{s.label}</li>)}
              </ul>
            </section>

            {/* Moment picker */}
            <div className="film-picker" role="group" aria-label="Choose a moment">
              {platform.contextKeys.map((key) => (
                <button key={key} type="button" aria-pressed={key === activeContext} onClick={() => handleContextSwitch(key)}>
                  {platform.contexts[key].label}
                </button>
              ))}
            </div>

            {/* Order toggle */}
            <div className="film-order">
              <div className="film-segment" role="group" aria-label="Order">
                <button type="button" aria-pressed={view === 'moment'} onClick={() => setView('moment')}>For this moment</button>
                <button type="button" aria-pressed={view === 'engagement'} onClick={() => setView('engagement')}>Engagement</button>
              </div>
              <p className="film-order-note">
                {view === 'moment'
                  ? `Top ${displayItems.length} of ${platform.catalog.length} for this moment.`
                  : `Top ${displayItems.length} of ${platform.catalog.length} by engagement alone.`}
              </p>
            </div>

            <PosterGrid items={displayItems} view={view} selectedId={selectedId} onSelect={handleSelect} />
            {view === 'moment' && <HeldStrip items={heldItems} selectedId={selectedId} onSelect={handleSelect} />}
          </div>

          {/* Focus + Why */}
          <aside className="film-side" ref={sideRef}>
            {focusItem && (
              <FocusPanel item={focusItem} rank={focusRank} total={rankedItems.length} signalConfigs={platform.signalConfigs} />
            )}
            <button type="button" className="film-why-btn" aria-expanded={whyOpen} aria-controls="film-why" onClick={() => setWhyOpen((v) => !v)}>
              {whyOpen ? 'Hide the math' : 'Why this order?'}
            </button>
            <div id="film-why" hidden={!whyOpen} className="film-why">
              <ScoringFormula item={focusItem} />
              <SignalSliders
                configs={platform.signalConfigs}
                values={signals}
                defaults={activeCtx.defaults}
                onChange={handleSignalChange}
                onReset={handleSignalReset}
              />
              <ProphecyAgent prophecyValue={signals.prophecy} />
            </div>
          </aside>
        </div>

        <footer className="film-footer">
          Deterministic ranking. Every result explained. Sample data: titles are real, but engagement and stimulation values are estimates, not measurements of any title.
        </footer>
      </div>
    </div>
  );
}
