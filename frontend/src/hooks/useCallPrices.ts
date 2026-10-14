'use client'

import { useEffect } from 'react'

import { formatMoney } from '@/lib/wallet'
import { useEntitlementStore } from '@/store/entitlementStore'

/**
 * Does this workspace see what each call cost?
 *
 * Only Pay As You Go pays per call, so only it is shown a price. The server
 * already blanks the amounts for everyone else (`billing/call_pricing.py`);
 * this decides whether the cost columns and cards appear at all.
 */
export function useShowsCallPrices(): boolean {
  const prepaid = useEntitlementStore((s) => s.entitlements?.prepaid === true)
  const load = useEntitlementStore((s) => s.load)
  useEffect(() => {
    load()
  }, [load])
  return prepaid
}

/** A call's price as billed ("$0.70"), or a dash when none was charged. */
export function formatCallPrice(amount: number | null | undefined): string {
  return amount == null ? '—' : formatMoney(Number(amount))
}
