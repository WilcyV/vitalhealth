import type { Permission, Role, User } from '../types';

/**
 * Who can do what. The server enforces this; the UI uses the same table to
 * disable buttons and explain why.
 */
export const PERMISSIONS: Record<Permission, Role[]> = {
  administer: ['nurse', 'charge'],              // give, hold, co-sign
  tasks: ['nurse', 'charge'],                   // mark timed care tasks done
  acknowledge: ['nurse', 'charge', 'pharmacist', 'provider'],
  editPatient: ['nurse', 'charge', 'provider'], // demographics, allergies, conditions
  order: ['provider'],                          // place / discontinue orders
  admit: ['charge', 'provider'],
  discharge: ['charge', 'provider'],
};

export const ROLE_LABEL: Record<Role, string> = { nurse: 'Nurse', charge: 'Charge nurse', pharmacist: 'Pharmacist', provider: 'Provider' };

export function can(user: User | null | undefined, action: Permission): boolean {
  return !!user && PERMISSIONS[action].includes(user.role);
}

/** Tooltip text for a disabled control. */
export function whyNot(action: Permission): string {
  const who = PERMISSIONS[action].map(r => ROLE_LABEL[r].toLowerCase() + 's');
  const list = who.length > 1 ? who.slice(0, -1).join(', ') + ' and ' + who[who.length - 1] : who[0];
  return `Only ${list} can do this.`;
}
