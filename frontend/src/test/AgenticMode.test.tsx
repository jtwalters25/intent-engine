import { act, cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { afterEach, expect, it, vi } from 'vitest';
import AgenticMode from '@/components/demo/AgenticMode';
import { plan, execution, lifecycle } from './agenticFixtures';

afterEach(() => { cleanup(); vi.unstubAllGlobals(); vi.restoreAllMocks(); });

it('cancels in-flight work when the mode is unmounted', async () => {
  const fetch = vi.fn().mockImplementation(() => new Promise(() => {}));
  vi.stubGlobal('fetch', fetch);
  const view = render(<AgenticMode />);
  fireEvent.click(screen.getByRole('button', { name: 'Create plan' }));
  expect(screen.getByRole('button', { name: 'Working…' })).toBeDisabled();
  const signal = fetch.mock.calls[0][1].signal;
  view.unmount();
  expect(signal.aborted).toBe(true);
});

it('renders backend plan, ranking, safety evidence, and execution reference', async () => {
  const fetch = vi.fn().mockResolvedValueOnce({ ok: true, json: async () => plan }).mockResolvedValueOnce({ ok: true, json: async () => execution }).mockResolvedValue({ ok: true, json: async () => lifecycle });
  vi.stubGlobal('fetch', fetch);
  render(<AgenticMode />);
  fireEvent.click(screen.getByRole('button', { name: 'Create plan' }));
  await screen.findByText('Intent ranking');
  expect(screen.getByText(/Dark Season 3 · Blocked/)).toBeInTheDocument();
  expect(screen.getByText(/Execution reference: trace_test/)).toBeInTheDocument();
  await screen.findByText(/Plan: ACTIVE/);
  expect(fetch.mock.calls.map(call => call[0])).toEqual(['/v4/plan', '/v4/execute', '/v4/advance']);
  expect(screen.getByText('Now · Active')).toBeInTheDocument();
});

it('refreshes server execution without creating another plan', async () => {
  const fetch = vi.fn().mockImplementation(async (url: string) => ({ ok: true, json: async () => url.endsWith('/plan') ? plan : url.endsWith('/execute') ? execution : lifecycle }));
  vi.stubGlobal('fetch', fetch);
  render(<AgenticMode />);
  fireEvent.click(screen.getByRole('button', { name: 'Create plan' }));
  await screen.findByText('Intent ranking');
  await screen.findByText(/Plan: ACTIVE/);
  fireEvent.click(screen.getByRole('button', { name: 'Refresh ranking' }));
  await waitFor(() => expect(fetch).toHaveBeenCalledTimes(5));
  expect(fetch.mock.calls[3][0]).toBe('/v4/execute');
});

it('shows service failures without ranking a local fallback', async () => {
  vi.stubGlobal('fetch', vi.fn().mockRejectedValue(new TypeError('offline')));
  render(<AgenticMode />);
  fireEvent.click(screen.getByRole('button', { name: 'Create plan' }));
  expect(await screen.findByRole('alert')).toHaveTextContent('Cannot reach');
  expect(screen.queryByText('Intent ranking')).not.toBeInTheDocument();
});

it('retains a plan after execution failure and permits retry', async () => {
  const fetch = vi.fn().mockResolvedValueOnce({ ok: true, json: async () => plan }).mockResolvedValueOnce({ ok: false, status: 500 }).mockResolvedValueOnce({ ok: true, json: async () => execution }).mockResolvedValue({ ok: true, json: async () => lifecycle });
  vi.stubGlobal('fetch', fetch);
  render(<AgenticMode />);
  fireEvent.click(screen.getByRole('button', { name: 'Create plan' }));
  await screen.findByRole('alert');
  fireEvent.click(screen.getByRole('button', { name: 'Refresh ranking' }));
  await screen.findByText('Intent ranking');
  await screen.findByText(/Plan: ACTIVE/);
  expect(screen.queryByRole('alert')).not.toBeInTheDocument();
});

it('records a playback report and stops interaction after terminal completion', async () => {
  const allowed = { ...execution.ranking[0], item: { item_id: 'calm', title: 'Calm Show' }, status: 'neutral' };
  const fetch = vi.fn().mockImplementation(async (url: string) => ({ ok: true, json: async () =>
    url.endsWith('/plan') ? plan : url.endsWith('/execute') ? { ...execution, ranking: [allowed] } :
    url.endsWith('/observe') ? { ...lifecycle, plan_status: 'COMPLETE', evaluation: 'COMPLETE', event_count: 1, next_transition_minutes: null } : lifecycle }));
  vi.stubGlobal('fetch', fetch);
  render(<AgenticMode />);
  await act(async () => { fireEvent.click(screen.getByRole('button', { name: 'Create plan' })); });
  fireEvent.click(screen.getByRole('button', { name: 'Report finished: Calm Show' }));
  await screen.findByText(/Plan: COMPLETE/);
  const observation = fetch.mock.calls.find(call => call[0] === '/v4/observe');
  expect(JSON.parse(observation![1].body)).toEqual({ plan_id: 'plan_test', step_id: 'step_one', event_type: 'CONTENT_COMPLETED', metadata: { candidate_id: 'calm' } });
  expect(screen.getByRole('button', { name: 'Refresh ranking' })).toBeDisabled();
  expect(screen.getByRole('button', { name: 'Report finished: Calm Show' })).toBeDisabled();
});

it('polls server progression and refreshes ranking only when the active step changes', async () => {
  let tick: () => Promise<void>;
  vi.spyOn(globalThis, 'setInterval').mockImplementation(callback => { tick = callback as () => Promise<void>; return 1 as unknown as ReturnType<typeof setInterval>; });
  const nextStep = { ...plan.steps[0], step_id: 'step_two', offset_minutes: 25 };
  let advanced = false;
  const fetch = vi.fn().mockImplementation(async (url: string) => ({ ok: true, json: async () =>
    url.endsWith('/plan') ? { ...plan, steps: [...plan.steps, nextStep] } : url.endsWith('/execute') ?
    { ...execution, active_step: advanced ? nextStep : execution.active_step } :
    { ...lifecycle, active_step_id: advanced ? 'step_two' : 'step_one' } }));
  vi.stubGlobal('fetch', fetch);
  render(<AgenticMode />);
  await act(async () => { fireEvent.click(screen.getByRole('button', { name: 'Create plan' })); });
  await act(async () => { await tick!(); });
  expect(fetch.mock.calls.filter(call => call[0] === '/v4/execute')).toHaveLength(1);
  advanced = true;
  await act(async () => { await tick!(); });
  expect(screen.getByText('After 25 minutes · Active')).toBeInTheDocument();
  expect(fetch.mock.calls.filter(call => call[0] === '/v4/execute')).toHaveLength(2);
});

it('cancels via the observe endpoint and exposes no report controls for blocked items', async () => {
  const fetch = vi.fn().mockImplementation(async (url: string) => ({ ok: true, json: async () =>
    url.endsWith('/plan') ? plan : url.endsWith('/execute') ? execution : url.endsWith('/observe') ?
    { ...lifecycle, plan_status: 'CANCELLED', next_transition_minutes: null } : lifecycle }));
  vi.stubGlobal('fetch', fetch);
  render(<AgenticMode />);
  await act(async () => { fireEvent.click(screen.getByRole('button', { name: 'Create plan' })); });
  expect(screen.queryByRole('button', { name: /Report started/ })).not.toBeInTheDocument();
  fireEvent.click(screen.getByRole('button', { name: 'Cancel plan' }));
  await screen.findByText(/Plan: CANCELLED/);
  expect(screen.getByRole('button', { name: 'Cancel plan' })).toBeDisabled();
});
