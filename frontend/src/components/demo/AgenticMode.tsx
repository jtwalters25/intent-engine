import { useEffect, useRef, useState } from 'react';
import { platforms, type PlatformItem } from '@/data/demoPlatforms';
import { advancePlan, createPlan, executePlan, observePlan, EXAMPLE_GOALS, type IntentPlan, type PlanExecution, type PlanLifecycle, type OutcomeType } from '@/data/agenticApi';

export default function AgenticMode({ catalog = platforms.streaming.catalog }: { catalog?: PlatformItem[] }) {
  const [text, setText] = useState(EXAMPLE_GOALS[0]);
  const [submittedGoal, setSubmittedGoal] = useState('');
  const [plan, setPlan] = useState<IntentPlan | null>(null);
  const [execution, setExecution] = useState<PlanExecution | null>(null);
  const [lifecycle, setLifecycle] = useState<PlanLifecycle | null>(null);
  const [pending, setPending] = useState(false);
  const [error, setError] = useState('');
  const request = useRef<AbortController | null>(null);
  useEffect(() => () => request.current?.abort(), []);
  const terminal = lifecycle !== null && lifecycle.plan_status !== 'ACTIVE';

  useEffect(() => {
    if (!plan || pending || terminal || error) return;
    const controller = new AbortController();
    let inFlight = false;
    const timer = setInterval(async () => {
      if (inFlight) return;
      inFlight = true;
      try {
        const status = await advancePlan(plan.plan_id, controller.signal);
        if (controller.signal.aborted) return;
        setLifecycle(status);
        if (status.plan_status === 'ACTIVE' && status.active_step_id !== execution?.active_step.step_id) {
          const ranked = await executePlan(plan.plan_id, catalog, controller.signal);
          if (!controller.signal.aborted) setExecution(ranked);
        }
      } catch (failure) {
        if (!controller.signal.aborted) setError(failure instanceof Error ? failure.message : 'Lifecycle refresh failed.');
      } finally { inFlight = false; }
    }, 15000);
    return () => { clearInterval(timer); controller.abort(); };
  }, [plan, pending, terminal, error, execution?.active_step.step_id, catalog]);

  async function run(goal?: string) {
    request.current?.abort();
    const controller = new AbortController();
    request.current = controller;
    setPending(true); setError(''); setExecution(null);
    if (goal !== undefined) { setPlan(null); setLifecycle(null); }
    try {
      const next = goal !== undefined ? await createPlan(goal.trim(), controller.signal) : plan;
      if (!next || controller.signal.aborted) return;
      setPlan(next);
      if (goal !== undefined) setSubmittedGoal(goal.trim());
      const ranked = await executePlan(next.plan_id, catalog, controller.signal);
      if (!controller.signal.aborted) setExecution(ranked);
      const status = await advancePlan(next.plan_id, controller.signal);
      if (!controller.signal.aborted) setLifecycle(status);
    } catch (failure) {
      if (!controller.signal.aborted) setError(failure instanceof Error ? failure.message : 'The request failed. Please try again.');
    } finally {
      if (!controller.signal.aborted) setPending(false);
    }
  }

  async function report(eventType: OutcomeType, candidateId?: string) {
    if (!plan || !execution || terminal) return;
    request.current?.abort();
    const controller = new AbortController(); request.current = controller;
    setPending(true); setError('');
    try {
      const status = await observePlan(plan.plan_id, execution.active_step.step_id, eventType, candidateId, controller.signal);
      if (!controller.signal.aborted) setLifecycle(status);
    } catch (failure) {
      if (!controller.signal.aborted) setError(failure instanceof Error ? failure.message : 'Outcome report failed.');
    } finally { if (!controller.signal.aborted) setPending(false); }
  }

  return <div className="space-y-6">
    <section className="rounded-lg border border-red-600/30 bg-red-600/5 p-5">
      <h2 className="font-syne text-lg font-bold">What are you trying to accomplish?</h2>
      <p className="my-2 text-sm text-white/60">Streaming pilot · Kids safety profile</p>
      <label htmlFor="agentic-goal" className="sr-only">Your goal</label>
      <textarea id="agentic-goal" value={text} onChange={event => setText(event.target.value)} maxLength={4096} rows={2} className="w-full rounded border border-white/20 bg-black/40 p-3" />
      <div className="my-3 flex flex-wrap gap-2">{EXAMPLE_GOALS.map(goal => <button key={goal} type="button" disabled={pending} onClick={() => setText(goal)} className="rounded border border-white/20 px-2 py-1 text-xs disabled:opacity-50">{goal}</button>)}</div>
      <button type="button" disabled={pending || !text.trim()} onClick={() => void run(text)} className="rounded bg-red-600 px-4 py-2 disabled:opacity-50">{pending ? 'Working…' : 'Create plan'}</button>
      <p role="status" className="mt-2 text-sm text-white/60">{pending ? 'Preparing your plan and ranking…' : ''}</p>
      {error && <p role="alert" className="mt-3 text-red-300">{error}</p>}
    </section>
    {plan && <>
      <section className="rounded-lg border border-white/10 p-5">
        <h2 className="font-syne text-lg font-bold">Understood</h2>
        <p className="mt-2">{submittedGoal}</p>
        <p className="mt-2 text-white/70">Goal: {plan.objective.replace(/_/g, ' ')} · Viewer: {String(plan.current_state.viewer)} · Confidence: {Math.round(plan.confidence * 100)}%</p>
        <div className="my-3 flex flex-wrap gap-2">{plan.constraints.map((constraint, index) => <span className="rounded border border-white/20 px-2 py-1 text-xs" key={index}>{constraint.hard ? '🔒 ' : ''}{constraint.type}: {String(constraint.value)}</span>)}</div>
        <ul className="space-y-1 text-xs text-white/60">{plan.assumptions.map(assumption => <li key={assumption}>{assumption}</li>)}</ul>
      </section>
      <section className="rounded-lg border border-white/10 p-5">
        <h2 className="font-syne text-lg font-bold">Plan timeline</h2>
        <div className="mt-3 grid gap-3 sm:grid-cols-3">{plan.steps.map(step => <div key={step.step_id} className={`rounded border p-3 ${step.step_id === execution?.active_step.step_id ? 'border-green-400' : 'border-white/20'}`}>
          <p>{step.offset_minutes === 0 ? 'Now' : `After ${step.offset_minutes} minutes`}{step.step_id === execution?.active_step.step_id ? ' · Active' : ''}</p>
          <p className="mt-2 text-sm text-white/60">Energy: {String(step.intent.energy ?? 'unspecified')} · {String(step.intent.tone ?? '')}</p>
          <p className="mt-2 text-sm">{step.transition_reason}</p>
        </div>)}</div>
        <p className="my-3 text-sm text-white/60">Steps follow server time. Status refreshes every 15 seconds; new steps refresh ranking automatically.</p>
        {lifecycle && <div role="status" className="my-3 text-sm">
          <p>Plan: {lifecycle.plan_status} · Evaluation: {lifecycle.evaluation} · Reports: {lifecycle.event_count}</p>
          {lifecycle.next_transition_minutes !== null && <p>Next transition in {Math.ceil(lifecycle.next_transition_minutes)} minutes</p>}
          <p className="mt-1 text-white/60">{lifecycle.explanation}</p>
        </div>}
        <button type="button" disabled={pending || terminal} onClick={() => void run()} className="rounded border border-white/30 px-3 py-2 disabled:opacity-50">Refresh ranking</button>
        <button type="button" disabled={pending || terminal || !execution} onClick={() => void report('PLAN_CANCELLED')} className="ml-2 rounded border border-white/30 px-3 py-2 disabled:opacity-50">Cancel plan</button>
      </section>
    </>}
    {execution && <section className="rounded-lg border border-white/10 p-5">
      <h2 className="font-syne text-lg font-bold text-green-300">Intent ranking</h2>
      <p className="my-3 text-sm text-white/60">{execution.explanation.plan_reason}</p>
      <ol className="space-y-3">{execution.ranking.map(row => <li key={row.item.item_id} className={`rounded border border-white/10 p-3 ${row.status === 'blocked' ? 'text-red-300' : ''}`}>
        <p>{row.rank}. {row.item.title} · {row.status === 'blocked' ? 'Blocked' : row.final_score.toFixed(3)}</p>
        <p className="mt-1 text-sm text-white/60">{row.explanation}</p>
        {row.status !== 'blocked' && <div className="mt-2 flex flex-wrap gap-2">
          <button type="button" disabled={pending || terminal} onClick={() => void report('CONTENT_STARTED', row.item.item_id)} className="rounded border border-white/20 px-2 py-1 text-xs disabled:opacity-50">Report started: {row.item.title}</button>
          <button type="button" disabled={pending || terminal} onClick={() => void report('CONTENT_COMPLETED', row.item.item_id)} className="rounded border border-white/20 px-2 py-1 text-xs disabled:opacity-50">Report finished: {row.item.title}</button>
        </div>}
        <details className="mt-2 text-xs"><summary>Why this ranking?</summary>
          <p className="mt-2">Base {row.score_breakdown.base_score.toFixed(3)} · Multipliers: {Object.entries(row.score_breakdown.multipliers).map(([key, value]) => `${key} ${value.toFixed(3)}`).join(' · ')} · Diversity adjustment {row.score_breakdown.diversity_penalty.toFixed(3)}</p>
          {row.score_breakdown.block_reason && <p>{row.score_breakdown.block_reason}</p>}
        </details>
      </li>)}</ol>
      <p className="mt-4 text-sm text-white/60">{execution.explanation.ranking_reason}</p>
      <p className="mt-2 break-all text-xs text-white/40">Execution reference: {execution.trace_id}</p>
    </section>}
  </div>;
}
