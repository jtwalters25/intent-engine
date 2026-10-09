import { afterEach, describe, expect, it, vi } from 'vitest';
import { catalogCandidates, createPlan, executePlan } from '@/data/agenticApi';
import { platforms } from '@/data/demoPlatforms';

import { plan, execution } from './agenticFixtures';

afterEach(() => { vi.unstubAllGlobals(); vi.unstubAllEnvs(); vi.useRealTimers(); });

describe('V4 transport', () => {
  it('sends only goal text/domain/context to plan and parses the backend plan', async () => {
    const fetch = vi.fn().mockResolvedValue({ ok: true, json: async () => plan });
    vi.stubGlobal('fetch', fetch);
    expect((await createPlan('Bedtime')).plan_id).toBe('plan_test');
    const [url, options] = fetch.mock.calls[0];
    expect(url).toBe('/v4/plan');
    expect(JSON.parse(options.body)).toEqual({ text: 'Bedtime', domain: 'streaming', context: {} });
  });
  it('maps the catalog to backend attributes and executes the stored ID', async () => {
    const fetch = vi.fn().mockResolvedValue({ ok: true, json: async () => execution });
    vi.stubGlobal('fetch', fetch);
    await executePlan('plan_test', platforms.streaming.catalog);
    expect(JSON.parse(fetch.mock.calls[0][1].body)).toEqual({ plan_id: 'plan_test', candidates: catalogCandidates(platforms.streaming.catalog) });
    const candidate = catalogCandidates(platforms.streaming.catalog)[0];
    expect(candidate.attributes).toEqual({ maturity: 'adult', calm_score: platforms.streaming.catalog[0].calmScore, complexity: platforms.streaming.catalog[0].complexity });
    expect(candidate.base_score).toBe(platforms.streaming.catalog[0].engagementScore);
  });
  it('uses the configured backend URL', async () => {
    vi.stubEnv('VITE_API_BASE_URL', 'https://api.example.test/');
    const fetch = vi.fn().mockResolvedValue({ ok: true, json: async () => plan });
    vi.stubGlobal('fetch', fetch);
    await createPlan('Bedtime');
    expect(fetch.mock.calls[0][0]).toBe('https://api.example.test/v4/plan');
  });
  it.each([404, 409, 422, 500])('reports HTTP %s without fabricated results', async status => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue({ ok: false, status }));
    await expect(executePlan('plan_test', platforms.streaming.catalog)).rejects.toThrow();
  });
  it('rejects malformed successful responses', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue({ ok: true, json: async () => ({ plan_id: 'broken' }) }));
    await expect(createPlan('Bedtime')).rejects.toThrow('invalid response');
  });
  it('reports a network failure', async () => {
    vi.stubGlobal('fetch', vi.fn().mockRejectedValue(new TypeError('network')));
    await expect(createPlan('Bedtime')).rejects.toThrow('Cannot reach');
  });
  it('aborts after the request deadline', async () => {
    vi.useFakeTimers();
    vi.stubGlobal('fetch', vi.fn().mockImplementation((_url, options) => new Promise((_resolve, reject) => options.signal.addEventListener('abort', () => reject(new DOMException('Aborted', 'AbortError'))))));
    const pending = expect(createPlan('Bedtime')).rejects.toThrow('timed out');
    await vi.advanceTimersByTimeAsync(15000);
    await pending;
  });
});
