import { useSyncExternalStore } from 'react';
import { api } from '../api';
import type { Snapshot } from '../types';

/** Live snapshot of the unit. Re-renders whenever the backend pushes a change. */
export function useVital(): Snapshot | null {
  return useSyncExternalStore(l => api.subscribe(l), () => api.getSnapshot());
}
