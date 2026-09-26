import { afterEach, beforeEach, describe, expect, it } from 'vitest';
import { cleanup, render, screen, within, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import App from '../App';
import { api } from '../api';

async function signIn(name: RegExp, pin = '1234') {
  const user = userEvent.setup();
  render(<App />);
  await user.click(await screen.findByRole('radio', { name }));
  await user.type(screen.getByLabelText('PIN'), pin);
  await user.click(screen.getByRole('button', { name: 'Sign in' }));
  return user;
}

beforeEach(async () => { await api.logout(); await api.resetDemo(); });
afterEach(() => cleanup());

describe('Login', () => {
  it('rejects a wrong PIN and accepts the right one', async () => {
    const user = await signIn(/Jamie Rivera/, '9999');
    expect(await screen.findByText(/PIN doesn’t match/)).toBeInTheDocument();
    await user.type(screen.getByLabelText('PIN'), '1234');
    await user.click(screen.getByRole('button', { name: 'Sign in' }));
    expect(await screen.findByRole('heading', { name: 'Rosa Martínez' })).toBeInTheDocument();
    expect(screen.getByText('RN Jamie Rivera')).toBeInTheDocument();
  });
});

describe('Roles', () => {
  it('a nurse can check but not order a medication', async () => {
    const user = await signIn(/Jamie Rivera/);
    await user.type(await screen.findByRole('combobox', { name: 'Search a medication' }), 'acetamin');
    await user.click(await screen.findByRole('option', { name: /Acetaminophen/ }));
    expect(await screen.findByText(/Compatible: Acetaminophen/)).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Add order' })).toBeDisabled();
  });
  it('the charge nurse lands on the unit view', async () => {
    await signIn(/Sofia Reyes/);
    expect(await screen.findByText('Unit overview')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /Bed 412A, Rosa Martínez/ })).toBeInTheDocument();
  });
});

describe('Administration', () => {
  it('stop screen requires a reason to give anyway', async () => {
    const user = await signIn(/Jamie Rivera/);
    await user.click(await screen.findByRole('button', { name: /Potassium result/ }));
    await user.click(await screen.findByRole('button', { name: 'Scan and give Lisinopril' }));
    const dialog = await screen.findByRole('dialog');
    expect(within(dialog).getByText(/High potassium/)).toBeInTheDocument();
    await user.click(within(dialog).getByRole('button', { name: 'Give anyway…' }));
    await user.click(within(dialog).getByRole('button', { name: 'Confirm and give' }));
    expect(within(dialog).getByText('Choose a reason.')).toBeInTheDocument();
  });

  it('insulin double-check catches a dose mismatch, then accepts the right dose', async () => {
    const user = await signIn(/Jamie Rivera/);
    await user.click(await screen.findByRole('button', { name: /^412B\s*James Thompson/ }));
    await user.click(await screen.findByRole('button', { name: 'Scan and give Insulin lispro' }));
    const dialog = await screen.findByRole('dialog');
    await user.click(within(dialog).getByRole('button', { name: 'Co-sign and give' }));
    expect(within(dialog).getByText(/Check every item/)).toBeInTheDocument();
    for (const box of within(dialog).getAllByRole('checkbox')) await user.click(box);
    await waitFor(() => expect(within(dialog).getByRole('option', { name: 'RN Maria Chen' })).toBeInTheDocument());
    await user.selectOptions(within(dialog).getByLabelText('Second nurse'), 'mchen');
    await user.type(within(dialog).getByLabelText("Second nurse's PIN"), '1234');
    await user.type(within(dialog).getByLabelText(/Dose calculated/), '4');
    await user.click(within(dialog).getByRole('button', { name: 'Co-sign and give' }));
    expect(await within(dialog).findByText(/Doses don't match/)).toBeInTheDocument();
    await user.type(within(dialog).getByLabelText("Second nurse's PIN"), '1234');
    await user.clear(within(dialog).getByLabelText(/Dose calculated/));
    await user.type(within(dialog).getByLabelText(/Dose calculated/), '2');
    await user.click(within(dialog).getByRole('button', { name: 'Co-sign and give' }));
    await waitFor(() => expect(screen.queryByRole('dialog')).not.toBeInTheDocument());
    expect(screen.getByText(/· 2 RN/)).toBeInTheDocument();
  });
});

describe('Patient form', () => {
  it('validates required fields', async () => {
    const user = await signIn(/Sofia Reyes/);
    await user.click(await screen.findByRole('button', { name: '+ Admit' }));
    const dialog = await screen.findByRole('dialog');
    await user.click(within(dialog).getByRole('button', { name: 'Admit patient' }));
    expect(await within(dialog).findByText('Enter the patient’s name.')).toBeInTheDocument();
  });
});

describe('Safer alternatives and look-alike names', () => {
  it('offers acetaminophen when ibuprofen is not compatible', async () => {
    const user = await signIn(/Samuel Patel/);
    await user.type(await screen.findByRole('combobox', { name: 'Search a medication' }), 'ibupro');
    await user.click(await screen.findByRole('option', { name: /Ibuprofen/ }));
    expect(await screen.findByText(/Not compatible: Ibuprofen/)).toBeInTheDocument();
    expect(screen.getByText(/Safer options for pain relief/)).toBeInTheDocument();
    expect(screen.getAllByText('Acetaminophen').length).toBeGreaterThan(0);
  });
  it('requires confirming a look-alike name before ordering', async () => {
    const user = await signIn(/Samuel Patel/);
    await user.click(await screen.findByRole('button', { name: /^418A\s*Tanya Reed/ }));
    await user.type(await screen.findByRole('combobox', { name: 'Search a medication' }), 'hydrox');
    await user.click(await screen.findByRole('option', { name: /HydrOXYzine/ }));
    expect(await screen.findByText(/Look-alike name: HydrOXYzine vs HydrALAZINE/)).toBeInTheDocument();
    const add = screen.getByRole('button', { name: 'Add order' });
    expect(add).toBeDisabled();
    await user.click(screen.getByRole('checkbox', { name: /I confirm I mean HydrOXYzine/ }));
    expect(add).toBeEnabled();
  });
});
