import { z } from 'zod';
import type { PlatformItem } from './demoPlatforms';

const number = z.number().finite();
const step = z.object({
  step_id: z.string(), offset_minutes: number.nonnegative(),
  intent: z.record(z.unknown()), transition_reason: z.string(),
});
const planSchema = z.object({
  plan_id: z.string(), domain: z.literal('streaming'), objective: z.string(),
  current_state: z.record(z.unknown()), desired_state: z.record(z.unknown()),
  constraints: z.array(z.object({ type: z.string(), value: z.unknown(), hard: z.boolean(), source: z.string() })),
  steps: z.array(step).min(1).max(5), assumptions: z.array(z.string()),
  confidence: number.min(0).max(1), created_at: z.string().datetime({ offset: true }),
  expires_at: z.string().datetime({ offset: true }).nullable(), planner_version: z.string(),
});
const executionSchema = z.object({
  trace_id: z.string(), active_step: step,
  ranking: z.array(z.object({
    item: z.object({ item_id: z.string(), title: z.string() }), rank: number,
    final_score: number, status: z.enum(['boosted', 'neutral', 'demoted', 'blocked']), explanation: z.string(),
    score_breakdown: z.object({
      base_score: number, final_score: number, diversity_penalty: number,
      blocked: z.boolean(), block_reason: z.string().nullable(),
      multipliers: z.object({ context: number, profile: number, urgency: number, cost: number, prophecy: number }),
    }),
  })),
  explanation: z.object({ plan_reason: z.string(), ranking_reason: z.string() }),
});

export type IntentPlan = z.infer<typeof planSchema>;
export type PlanExecution = z.infer<typeof executionSchema>;
export const EXAMPLE_GOALS = [
  'The kids are wired and bedtime is in an hour.',
  'Family movie night.', 'Something educational to help us focus.',
  'A quick session under 20 minutes.', 'Something high-energy.',
];

export function catalogCandidates(catalog: PlatformItem[]) {
  return catalog.map(item => ({
    item_id: item.id, title: item.title, category: item.genre,
    base_score: item.engagementScore,
    attributes: { maturity: item.maturity, calm_score: item.calmScore, complexity: item.complexity },
  }));
}

async function post<T>(path: string, body: unknown, schema: z.ZodType<T>, signal?: AbortSignal): Promise<T> {
  const controller = new AbortController();
  const cancel = () => controller.abort();
  signal?.addEventListener('abort', cancel, { once: true });
  if (signal?.aborted) controller.abort();
  const timer = setTimeout(cancel, 15000);
  try {
    const base = (import.meta.env.VITE_API_BASE_URL ?? '').replace(/\/$/, '');
    const response = await fetch(`${base}/v4/${path}`, {
      method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body), signal: controller.signal,
    });
    if (!response.ok) {
      if (response.status === 404 && path === 'execute') throw new Error('This plan is unavailable or expired. Create a new plan.');
      if (response.status === 409) throw new Error('This plan cannot run now. Create a new plan.');
      if (response.status === 422) throw new Error('The goal or catalog is unsupported. Try one of the example goals.');
      throw new Error('The intent service is unavailable. Please try again.');
    }
    const checked = schema.safeParse(await response.json());
    if (!checked.success) throw new Error('The intent service returned an invalid response.');
    return checked.data;
  } catch (error) {
    if (controller.signal.aborted && !signal?.aborted) throw new Error('The intent service timed out. Please try again.');
    if (error instanceof TypeError) throw new Error('Cannot reach the intent service. Please try again.');
    throw error;
  } finally {
    clearTimeout(timer);
    signal?.removeEventListener('abort', cancel);
  }
}

export const createPlan = (text: string, signal?: AbortSignal) => post('plan', { text, domain: 'streaming', context: {} }, planSchema, signal);
export const executePlan = (planId: string, catalog: PlatformItem[], signal?: AbortSignal) => post('execute', { plan_id: planId, candidates: catalogCandidates(catalog) }, executionSchema, signal);
