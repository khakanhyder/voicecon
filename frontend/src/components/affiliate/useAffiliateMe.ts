'use client'

import { useQuery } from '@tanstack/react-query'
import { affiliateApi } from '@/lib/affiliate'

export const AFFILIATE_ME_KEY = ['affiliate', 'me'] as const

/**
 * The signed-in partner's profile, links, rules, balance and payout setup.
 * The portal shell loads it first, so pages read it from the cache.
 */
export function useAffiliateMe(enabled = true) {
  return useQuery({
    queryKey: AFFILIATE_ME_KEY,
    queryFn: affiliateApi.me,
    enabled,
    retry: false,
    staleTime: 60 * 1000,
  })
}
