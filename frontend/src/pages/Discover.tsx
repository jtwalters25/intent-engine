import { useCallback, useState } from 'react';
import {
  searchDiscover,
  type DiscoveryResponse,
  type DiscoveryResult,
  type DiscoveryClaim,
} from '@/data/discoverApi';

const EXAMPLE_QUERIES = [
  'Something educational and fun for my kids this Saturday',
  'Live music downtown this weekend',
  'A rainy-day activity for a family of four',
];

export default function Discover() {
  const [query, setQuery] = useState(EXAMPLE_QUERIES[0]);
  const [location, setLocation] = useState('');
  const [budget, setBudget] = useState('');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [response, setResponse] = useState<DiscoveryResponse | null>(null);

  const runSearch = useCallback(async (q: string) => {
    const trimmed = q.trim();
    if (!trimmed) return;
    setLoading(true);
    setError(null);
    try {
      const budgetTotal = budget.trim() ? Number(budget) : undefined;
      const result = await searchDiscover({
        query: trimmed,
        location: location.trim() || undefined,
        budgetTotal: Number.isFinite(budgetTotal) ? budgetTotal : undefined,
      });
      setResponse(result);
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Something went wrong.');
      setResponse(null);
    } finally {
      setLoading(false);
    }
  }, [budget, location]);

  return (
    <div className="min-h-screen bg-[#0a0a0a] text-white">
      <div className="mx-auto max-w-5xl px-4 py-6 sm:px-6 lg:px-8">
        <header className="mb-6">
          <h1 className="font-syne text-3xl sm:text-4xl font-extrabold tracking-tight text-white/95">
            Intent Engine — Discover
          </h1>
          <p className="font-dm-mono text-sm text-white/40 mt-1">
            Real activities, ranked against your intent — with every claim grounded in verified evidence.
          </p>
        </header>

        {/* Search form */}
        <section className="rounded-lg border border-blue-500/20 bg-blue-500/5 p-5 mb-6">
          <label className="block font-dm-mono text-[11px] uppercase tracking-wider text-white/40 mb-1">
            What are you looking for?
          </label>
          <textarea
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            rows={2}
            className="w-full resize-none rounded-md border border-white/10 bg-black/40 px-3 py-2 font-dm-mono text-sm text-white/80 placeholder:text-white/25 focus:border-blue-500/50 focus:outline-none"
            placeholder="e.g. Something educational and fun for my kids this Saturday"
          />
          <div className="mt-3 grid grid-cols-1 gap-3 sm:grid-cols-2">
            <input
              value={location}
              onChange={(e) => setLocation(e.target.value)}
              placeholder="Location (e.g. Seattle, WA)"
              className="rounded-md border border-white/10 bg-black/40 px-3 py-2 font-dm-mono text-sm text-white/80 placeholder:text-white/25 focus:border-blue-500/50 focus:outline-none"
            />
            <input
              value={budget}
              onChange={(e) => setBudget(e.target.value)}
              inputMode="decimal"
              placeholder="Budget total (optional)"
              className="rounded-md border border-white/10 bg-black/40 px-3 py-2 font-dm-mono text-sm text-white/80 placeholder:text-white/25 focus:border-blue-500/50 focus:outline-none"
            />
          </div>
          <div className="mt-3 flex flex-wrap gap-1.5">
            {EXAMPLE_QUERIES.map((q) => (
              <button
                key={q}
                type="button"
                onClick={() => { setQuery(q); runSearch(q); }}
                className="rounded-full border border-white/10 bg-white/[0.02] px-2.5 py-1 font-dm-mono text-[10px] text-white/50 transition-colors hover:border-blue-500/40 hover:text-white/80"
              >
                {q.length > 46 ? `${q.slice(0, 46)}…` : q}
              </button>
            ))}
          </div>
          <button
            type="button"
            onClick={() => runSearch(query)}
            disabled={loading}
            className="mt-4 rounded-md bg-blue-600/90 px-4 py-2 font-syne text-sm font-bold text-white transition-colors hover:bg-blue-600 disabled:opacity-50"
          >
            {loading ? 'Searching…' : 'Discover'}
          </button>
        </section>

        {error && (
          <div className="rounded-lg border border-red-600/30 bg-red-600/5 px-4 py-3 mb-6 font-dm-mono text-sm text-red-300/90">
            {error}
          </div>
        )}

        {response && <Results response={response} />}
      </div>
    </div>
  );
}

function Results({ response }: { response: DiscoveryResponse }) {
  const verified = response.results.filter((r) => !r.needs_verification);
  const needs = response.results.filter((r) => r.needs_verification);

  return (
    <section className="space-y-6">
      {response.warnings.length > 0 && (
        <div className="rounded-md border border-amber-500/30 bg-amber-500/5 px-3 py-2 font-dm-mono text-[11px] text-amber-300/80">
          {response.warnings.join(' · ')}
        </div>
      )}

      {response.results.length === 0 && (
        <p className="font-dm-mono text-sm text-white/40">No eligible results. Try broadening your search.</p>
      )}

      {verified.length > 0 && (
        <div>
          <h2 className="font-syne text-lg font-bold text-green-400/80 mb-3">Recommended</h2>
          <div className="space-y-3">
            {verified.map((r) => <ResultCard key={r.candidate_id} result={r} />)}
          </div>
        </div>
      )}

      {needs.length > 0 && (
        <div>
          <h2 className="font-syne text-lg font-bold text-amber-300/80 mb-1">Needs verification</h2>
          <p className="font-dm-mono text-[11px] text-white/40 mb-3">
            Shown separately — some eligibility facts could not be verified.
          </p>
          <div className="space-y-3">
            {needs.map((r) => <ResultCard key={r.candidate_id} result={r} />)}
          </div>
        </div>
      )}

      <footer className="pt-2 font-dm-mono text-[10px] text-white/20">
        {response.results.length} ranked · {response.excluded_count} excluded by hard constraints · fingerprint {response.ranking_fingerprint.slice(0, 12)}…
      </footer>
    </section>
  );
}

function ResultCard({ result }: { result: DiscoveryResult }) {
  return (
    <article className="rounded-lg border border-white/10 bg-white/[0.02] p-4">
      <div className="flex items-start gap-3">
        <span className="font-dm-mono text-sm text-white/40 w-6">{result.rank}</span>
        <div className="min-w-0 flex-1">
          <div className="flex items-center gap-2 flex-wrap">
            <a
              href={result.source_url}
              target="_blank"
              rel="noopener noreferrer"
              className="font-syne font-bold text-white/90 hover:text-blue-300 truncate"
            >
              {result.title}
            </a>
            <StatusBadge status={result.status} />
            {result.needs_verification && (
              <span className="font-dm-mono text-[10px] rounded-full border border-amber-500/40 bg-amber-500/10 text-amber-300/90 px-2 py-0.5">
                needs verification
              </span>
            )}
          </div>
          <div className="font-dm-mono text-[11px] text-white/40 mt-0.5">
            {[result.category, result.location_name, result.provider].filter(Boolean).join(' · ')}
          </div>
          <p className="font-dm-mono text-[12px] text-white/70 mt-2 leading-relaxed">{result.explanation.text}</p>
          <div className="mt-2 flex flex-wrap gap-1.5">
            {result.explanation.claims.map((c, i) => <ClaimBadge key={i} claim={c} />)}
          </div>
        </div>
        <span className="font-dm-mono text-xs text-white/60">{result.final_score.toFixed(2)}</span>
      </div>
    </article>
  );
}

function StatusBadge({ status }: { status: DiscoveryResult['status'] }) {
  const style =
    status === 'boosted' ? 'border-green-400/40 bg-green-400/10 text-green-300/90'
    : status === 'demoted' ? 'border-orange-400/40 bg-orange-400/10 text-orange-300/90'
    : 'border-white/15 bg-white/5 text-white/50';
  return <span className={`font-dm-mono text-[10px] rounded-full border px-2 py-0.5 ${style}`}>{status}</span>;
}

function ClaimBadge({ claim }: { claim: DiscoveryClaim }) {
  const tone =
    claim.evidence_status === 'VERIFIED' ? 'border-green-500/30 bg-green-500/10 text-green-300/80'
    : claim.evidence_status === 'EXTRACTED' ? 'border-sky-500/30 bg-sky-500/10 text-sky-300/80'
    : 'border-amber-500/30 bg-amber-500/10 text-amber-300/80';
  return (
    <span className={`font-dm-mono text-[10px] rounded border px-1.5 py-0.5 ${tone}`} title={`${claim.kind} · ${claim.evidence_status}`}>
      {claim.text}
    </span>
  );
}
