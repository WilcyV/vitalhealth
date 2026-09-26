import { useSyncExternalStore } from 'react';
import { api } from '../api';
import type { Connection, User } from '../types';

/** The signed-in user (null when signed out). */
export function useUser(): User | null {
  return useSyncExternalStore(l => api.subscribe(l), () => api.getUser());
}

/** WebSocket connection state (always "online" in demo mode). */
export function useConnection(): Connection {
  return useSyncExternalStore(l => api.subscribe(l), () => api.getConnection());
}
