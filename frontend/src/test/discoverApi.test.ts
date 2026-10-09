import { afterEach, describe, expect, it, vi } from 'vitest';
import { searchDiscover, sendDiscoverFeedback } from '@/data/discoverApi';

afterEach(() => { vi.unstubAllGlobals(); vi.unstubAllEnvs(); });

const sampleResponse = {
  results: [{
    candidate_id: 'ticketmaster:1', rank: 1, title: 'Science Museum',
    source_url: 'https://example.com/e', provider: 'ticketmaster',
    category: 'Museum', location_name: null, start_time: null,
    price_min: null, price_max: null, currency: null,
    final_score: 1.23, status: 'boosted', needs_verification: false,
    signals: { family_friendly: 0.9, educational_value: 0.9 },
    constraints: { budget: 'PASS' },
    explanation: {
      text: 'Recommended because it matches your educational value.',
      claims: [{ text: 'matches your educational value', kind: 'match', attribute: 'educational value', evidence_status: 'VERIFIED', signal: 'educational_value' }],
    },
  }],
  needs_verification_ids: [],
  excluded_count: 2,
  warnings: [],
  ranking_fingerprint: 'abc123def456',
  engine_version: 'discover-ranker-0.1.0',
  config_version: 'default',
};

describe('discoverApi', () => {
  it('posts the search request and parses the response', async () => {
    const fetch = vi.fn().mockResolvedValue({ ok: true, json: async () => sampleResponse });
    vi.stubGlobal('fetch', fetch);
    const resp = await searchDiscover({ query: 'museum', location: 'Seattle', budgetTotal: 100 });
    expect(resp.results[0].title).toBe('Science Museum');
    const [url, options] = fetch.mock.calls[0];
    expect(url).toBe('/discover/search');
    expect(JSON.parse(options.body)).toEqual({ query: 'museum', location: 'Seattle', budget_total: 100 });
  });

  it('uses the configured backend URL', async () => {
    vi.stubEnv('VITE_API_BASE_URL', 'https://api.example.test/');
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue({ ok: true, json: async () => sampleResponse }));
    await searchDiscover({ query: 'museum' });
    expect((globalThis.fetch as any).mock.calls[0][0]).toBe('https://api.example.test/discover/search');
  });

  it.each([422, 502, 500])('reports HTTP %s without fabricating results', async (status) => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue({ ok: false, status }));
    await expect(searchDiscover({ query: 'museum' })).rejects.toThrow();
  });

  it('rejects a malformed success response', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue({ ok: true, json: async () => ({ results: 'nope' }) }));
    await expect(searchDiscover({ query: 'museum' })).rejects.toThrow('invalid response');
  });

  it('reports a network failure', async () => {
    vi.stubGlobal('fetch', vi.fn().mockRejectedValue(new TypeError('network')));
    await expect(searchDiscover({ query: 'museum' })).rejects.toThrow('Cannot reach');
  });

  it('posts feedback with the expected body', async () => {
    const fetch = vi.fn().mockResolvedValue({ ok: true, json: async () => ({ status: 'recorded', request_id: 'r1' }) });
    vi.stubGlobal('fetch', fetch);
    await sendDiscoverFeedback({ requestId: 'r1', helpfulness: 'very_helpful', wouldUseAgain: true });
    const [url, options] = fetch.mock.calls[0];
    expect(url).toBe('/discover/feedback');
    expect(JSON.parse(options.body).helpfulness).toBe('very_helpful');
  });
});
