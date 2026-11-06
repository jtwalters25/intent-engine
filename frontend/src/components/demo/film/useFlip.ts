import { useCallback, useEffect, useLayoutEffect, useRef } from 'react';

type Pos = { x: number; y: number };

/**
 * FLIP reorder animation. Attach `register(id)` as the ref of each item's wrapper.
 * When `order` changes, each wrapper slides from its old slot to its new one,
 * staggered by its new position. Instant under prefers-reduced-motion.
 */
export function useFlip(order: string[], staggerMs = 45) {
  const nodes = useRef(new Map<string, HTMLElement>());
  const prev = useRef(new Map<string, Pos>());
  const key = order.join('|');

  const measure = useCallback(() => {
    const next = new Map<string, Pos>();
    nodes.current.forEach((el, id) => next.set(id, { x: el.offsetLeft, y: el.offsetTop }));
    return next;
  }, []);

  useLayoutEffect(() => {
    const reduce = window.matchMedia('(prefers-reduced-motion: reduce)').matches;
    const next = measure();
    if (!reduce) {
      order.forEach((id, i) => {
        const el = nodes.current.get(id);
        const from = prev.current.get(id);
        const to = next.get(id);
        if (!el || !from || !to || (from.x === to.x && from.y === to.y)) return;
        el.style.transition = 'none';
        el.style.transform = `translate(${from.x - to.x}px, ${from.y - to.y}px)`;
        requestAnimationFrame(() => {
          el.style.transition = '';
          el.style.transitionDelay = `${i * staggerMs}ms`;
          el.style.transform = '';
        });
      });
    }
    prev.current = next;
    // `key` captures every change to `order`
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [key, measure, staggerMs]);

  // Keep remembered positions current when the layout reflows (e.g. resize)
  useEffect(() => {
    const onResize = () => { prev.current = measure(); };
    window.addEventListener('resize', onResize);
    return () => window.removeEventListener('resize', onResize);
  }, [measure]);

  return useCallback(
    (id: string) => (el: HTMLElement | null) => {
      if (el) nodes.current.set(id, el);
      else nodes.current.delete(id);
    },
    [],
  );
}
