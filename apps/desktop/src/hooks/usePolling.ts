import { useEffect } from "react";

export function usePolling(fn: () => void | Promise<void>, ms: number, deps: unknown[]) {
  useEffect(() => {
    let mounted = true;
    const tick = async () => {
      if (!mounted) return;
      await fn();
    };

    tick();
    const id = window.setInterval(tick, ms);
    return () => {
      mounted = false;
      window.clearInterval(id);
    };
  }, deps);
}
