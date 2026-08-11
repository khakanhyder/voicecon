'use client';

import React, { useState, useEffect } from 'react';
import {
  CreditCard,
  Calendar,
  Download,
  AlertCircle,
  CheckCircle,
  XCircle,
  Clock,
  Phone,
} from 'lucide-react';
import { toast } from 'sonner';
import { Button } from '@/components/ui/button';
import { apiClient, getErrorMessage } from '@/lib/api';
import { API_ENDPOINTS } from '@/lib/constants';
import { CheckoutModal, type CheckoutPlan } from '@/components/billing/CheckoutModal';
import { entitlementService, FEATURE_LABELS } from '@/lib/entitlements';
import { useEntitlementStore } from '@/store/entitlementStore';

interface SubscriptionPlan {
  id: string;
  slug: string | null;
  tier: number;
  name: string;
  description: string;
  price_monthly: number;
  price_yearly: number | null;
  included_minutes: number;
  included_calls: number;
  max_agents: number;
  max_phone_numbers: number;
  max_knowledge_bases: number;
  overage_rate_per_minute: number;
  overage_rate_per_call: number;
  features: Record<string, any>;
  entitlements: {
    features?: Record<string, boolean>;
    limits?: Record<string, number>;
  };
  trial_days: number;
  is_trialable: boolean;
  is_active: boolean;
  is_public: boolean;
}

interface Subscription {
  id: string;
  plan_id: string;
  plan_name: string;
  status: string;
  billing_period: string;
  current_period_start: string;
  current_period_end: string;
  trial_end: string | null;
  canceled_at: string | null;
  current_period_minutes: number;
  current_period_calls: number;
}

interface Usage {
  minutes_used: number;
  minutes_included: number;
  minutes_overage: number;
  calls_used: number;
  calls_included: number;
  calls_overage: number;
  estimated_overage_cost: number;
}

interface Invoice {
  id: string;
  invoice_number: string;
  status: string;
  amount_due: number;
  amount_paid: number;
  total: number;
  period_start: string;
  period_end: string;
  due_date: string | null;
  paid_at: string | null;
  invoice_pdf: string | null;
  hosted_invoice_url: string | null;
}

function Skeleton({ className }: { className?: string }) {
  return <div className={`animate-pulse bg-gray-200 rounded ${className}`} />;
}

export default function BillingPage() {
  const [billingPeriod, setBillingPeriod] = useState<'monthly' | 'yearly'>('monthly');
  const [loading, setLoading] = useState(true);
  const [plans, setPlans] = useState<SubscriptionPlan[]>([]);
  const [subscription, setSubscription] = useState<Subscription | null>(null);
  const [usage, setUsage] = useState<Usage | null>(null);
  const [invoices, setInvoices] = useState<Invoice[]>([]);
  const [actionBusy, setActionBusy] = useState(false);
  const [checkoutPlan, setCheckoutPlan] = useState<CheckoutPlan | null>(null);

  const entitlements = useEntitlementStore((s) => s.entitlements);
  const refreshEntitlements = useEntitlementStore((s) => s.refresh);

  const fetchAll = async () => {
    setLoading(true);
    const [plansRes, subRes, usageRes, invRes] = await Promise.allSettled([
      apiClient.get<SubscriptionPlan[]>(API_ENDPOINTS.BILLING_PLANS),
      apiClient.get<Subscription | null>(API_ENDPOINTS.BILLING_SUBSCRIPTION),
      apiClient.get<Usage>(API_ENDPOINTS.BILLING_USAGE),
      apiClient.get<Invoice[]>(API_ENDPOINTS.BILLING_INVOICES),
      refreshEntitlements(),
    ]);

    if (plansRes.status === 'fulfilled') setPlans(plansRes.value.data);
    setSubscription(subRes.status === 'fulfilled' ? subRes.value.data : null);
    setUsage(usageRes.status === 'fulfilled' ? usageRes.value.data : null);
    if (invRes.status === 'fulfilled') setInvoices(invRes.value.data);
    setLoading(false);
  };

  useEffect(() => {
    fetchAll();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  /**
   * Move an existing *paid* subscription to a different plan.
   *
   * Upgrades apply immediately; downgrades are scheduled for the end of the
   * period the customer already paid for. A downgrade the workspace doesn't fit
   * comes back as a 409 listing what's over the limit — we surface that rather
   * than deleting anything to make it fit.
   */
  const switchPlan = async (planId: string) => {
    setActionBusy(true);
    try {
      const updated = await entitlementService.changePlan(planId);
      const target = plans.find((p) => p.id === planId);
      const isUpgrade = (target?.tier ?? 0) >= (currentPlan?.tier ?? 0);
      toast.success(
        isUpgrade
          ? 'Plan upgraded — the new limits are active now'
          : `Downgrade scheduled for ${formatDate(updated.current_period_end)}`
      );
      await fetchAll();
    } catch (err: any) {
      const body = err?.response?.data;
      if (body?.code === 'downgrade_blocked' || body?.detail?.code === 'downgrade_blocked') {
        const payload = body.code ? body : body.detail;
        const lines = (payload.conflicts ?? [])
          .map((c: any) => `${c.current} ${c.label} (max ${c.allowed})`)
          .join(', ');
        toast.error(`${payload.detail} You have ${lines}.`, { duration: 8000 });
      } else {
        toast.error(getErrorMessage(err));
      }
    } finally {
      setActionBusy(false);
    }
  };

  const cancelSubscription = async () => {
    if (!confirm('Cancel your subscription at the end of the current period?')) return;
    setActionBusy(true);
    try {
      await entitlementService.cancel();
      toast.success('Subscription cancelled — you keep access until the period ends');
      await fetchAll();
    } catch (err) {
      toast.error(getErrorMessage(err));
    } finally {
      setActionBusy(false);
    }
  };

  const reactivateSubscription = async () => {
    setActionBusy(true);
    try {
      await entitlementService.reactivate();
      toast.success('Subscription reactivated');
      await fetchAll();
    } catch (err) {
      toast.error(getErrorMessage(err));
    } finally {
      setActionBusy(false);
    }
  };

  /**
   * Choosing a plan.
   *
   * A workspace on a *paid* plan switches in place — the card is already on
   * file. A trial, a lapsed trial or an expired subscription has no card, so it
   * goes through checkout; the backend converts the existing subscription
   * rather than creating a second one.
   */
  const needsCheckout = !subscription || entitlements?.source !== 'stripe';

  const choosePlan = (plan: SubscriptionPlan) => {
    if (!needsCheckout) {
      switchPlan(plan.id);
      return;
    }
    setCheckoutPlan({
      id: plan.id,
      name: plan.name,
      price_monthly: plan.price_monthly,
      price_yearly: plan.price_yearly,
    });
  };

  const scrollToPlans = () =>
    document.getElementById('available-plans')?.scrollIntoView({ behavior: 'smooth' });

  const getStatusColor = (status: string) => {
    switch (status) {
      case 'active':
      case 'paid':
        return 'text-green-600 bg-green-100';
      case 'trialing':
        return 'text-blue-600 bg-blue-100';
      case 'past_due':
      case 'grace':
        return 'text-amber-700 bg-amber-100';
      case 'expired':
        return 'text-red-600 bg-red-100';
      case 'canceled':
        return 'text-gray-600 bg-gray-100';
      default:
        return 'text-gray-600 bg-gray-100';
    }
  };

  const STATUS_LABELS: Record<string, string> = {
    trialing: 'FREE TRIAL',
    active: 'ACTIVE',
    past_due: 'PAYMENT FAILED',
    grace: 'TRIAL ENDED',
    expired: 'EXPIRED',
    canceled: 'CANCELLED',
  };

  const formatDate = (dateString: string) =>
    new Date(dateString).toLocaleDateString('en-US', {
      year: 'numeric',
      month: 'short',
      day: 'numeric',
    });

  const currentPlan = plans.find((p) => p.id === subscription?.plan_id);

  return (
    <div className="space-y-6">
        {/* Header */}


        {/* Current Subscription */}
        <div className="rounded-[10px] border border-black/10 bg-white p-6 shadow-[0_4px_20px_-4px_rgba(16,105,89,0.1)]">
          <div className="flex items-center justify-between mb-6">
            <div>
              <h2 className="text-[20px] font-bold font-poppins text-[#000000]">Current Plan</h2>
              <p className="text-[14px] font-poppins text-black/60 mt-1">Your active subscription</p>
            </div>
            {loading ? (
              <Skeleton className="w-20 h-7" />
            ) : entitlements?.has_subscription ? (
              // The *effective* status, which accounts for a trial that has
              // ended since the row was last written.
              <span
                className={`px-3 py-1 text-sm font-semibold rounded ${getStatusColor(
                  entitlements.status
                )}`}
              >
                {STATUS_LABELS[entitlements.status] ?? entitlements.status.toUpperCase()}
              </span>
            ) : null}
          </div>

          {loading ? (
            <div className="grid grid-cols-1 md:grid-cols-3 gap-6 mb-6">
              {[1, 2, 3].map((i) => (
                <div key={i} className="space-y-2">
                  <Skeleton className="h-4 w-24" />
                  <Skeleton className="h-8 w-32" />
                  <Skeleton className="h-4 w-20" />
                </div>
              ))}
            </div>
          ) : subscription ? (
            <div className="grid grid-cols-1 md:grid-cols-3 gap-6 mb-6">
              <div>
                <div className="text-[14px] font-poppins text-black/60 mb-1">Plan</div>
                <div className="text-[24px] font-bold font-poppins text-[#106959]">{subscription.plan_name}</div>
                {currentPlan && (
                  <div className="text-[14px] font-poppins text-black/60">
                    ${currentPlan.price_monthly}/month
                  </div>
                )}
              </div>
              <div>
                <div className="text-[14px] font-poppins text-black/60 mb-1">
                  {entitlements?.is_trial ? 'Trial period' : 'Current Period'}
                </div>
                <div className="text-[14px] font-medium font-poppins text-[#000000]">
                  {formatDate(subscription.current_period_start)} -{' '}
                  {formatDate(subscription.current_period_end)}
                </div>
                <div className="text-[12px] font-poppins text-black/50 mt-1 flex items-center gap-1">
                  <Calendar className="w-3 h-3" />
                  {entitlements?.is_trial
                    ? `${entitlements.days_remaining ?? 0} ${
                        entitlements.days_remaining === 1 ? 'day' : 'days'
                      } left`
                    : entitlements?.status === 'expired'
                      ? 'Ended'
                      : entitlements?.cancel_at_period_end
                        ? `Ends ${formatDate(subscription.current_period_end)}`
                        : `Renews ${formatDate(subscription.current_period_end)}`}
                </div>
              </div>
              <div>
                <div className="text-[14px] font-poppins text-black/60 mb-1">Billing Period</div>
                <div className="flex items-center gap-2">
                  <CreditCard className="w-4 h-4 text-black/40" />
                  <span className="text-[14px] font-medium font-poppins text-[#000000] capitalize">
                    {subscription.billing_period}
                  </span>
                </div>
                {subscription.canceled_at && (
                  <div className="text-xs text-red-600 mt-1">
                    Cancels {formatDate(subscription.current_period_end)}
                  </div>
                )}
              </div>
            </div>
          ) : (
            <div className="py-8 text-center text-gray-500">
              <p className="mb-4">No active subscription found.</p>
              <p className="text-sm">Choose a plan below to get started.</p>
            </div>
          )}

          {subscription && (
            <div className="flex flex-wrap gap-3">
              <Button variant="outline" onClick={scrollToPlans} disabled={actionBusy}>
                {needsCheckout ? 'Choose a plan' : 'Change Plan'}
              </Button>

              {entitlements?.cancel_at_period_end ? (
                <Button onClick={reactivateSubscription} disabled={actionBusy}>
                  Reactivate subscription
                </Button>
              ) : (
                entitlements?.is_live && (
                  <Button
                    variant="outline"
                    className="text-red-600 border-red-200 hover:bg-red-50"
                    onClick={cancelSubscription}
                    disabled={actionBusy}
                  >
                    {entitlements.is_trial ? 'End trial' : 'Cancel Subscription'}
                  </Button>
                )
              )}
            </div>
          )}

          {/* Read-only accounts keep every screen — this explains why nothing
              can be changed, instead of leaving buttons that silently fail. */}
          {entitlements?.is_read_only && entitlements.has_subscription && (
            <div className="mt-4 flex items-start gap-3 rounded-lg border border-red-200 bg-red-50 p-4">
              <AlertCircle className="mt-0.5 h-5 w-5 flex-shrink-0 text-red-600" />
              <div className="text-sm text-red-900">
                <p className="font-semibold">This workspace is read-only</p>
                <p className="mt-1 text-red-800">
                  Your agents are paused and calls aren&apos;t being answered. Everything
                  you built is kept and stays exportable — choose a plan below to switch
                  it back on.
                </p>
              </div>
            </div>
          )}
        </div>

        {/* Usage This Period */}
        <div className="rounded-[10px] border border-black/10 bg-white p-6 shadow-[0_4px_20px_-4px_rgba(16,105,89,0.1)]">
          <div className="mb-6">
            <h2 className="text-[20px] font-bold font-poppins text-[#000000]">Usage This Period</h2>
            <p className="text-[14px] font-poppins text-black/60 mt-1">Calls and minutes are unlimited — this is what you have used</p>
          </div>

          {loading ? (
            <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
              {[1, 2].map((i) => (
                <div key={i} className="space-y-3">
                  <div className="flex justify-between">
                    <Skeleton className="h-5 w-28" />
                    <Skeleton className="h-5 w-20" />
                  </div>
                  <Skeleton className="h-2 w-full rounded-full" />
                </div>
              ))}
            </div>
          ) : usage ? (
            /* Counts only — no bars. Minutes and calls are unlimited on every
               plan, so a progress bar would have no denominator to fill and an
               "x / unlimited" ratio is not a thing anyone can read. */
            <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
              <div className="rounded-[8px] border border-black/10 bg-[#0F6A590A] p-4">
                <div className="flex items-center gap-2">
                  <Clock className="w-5 h-5 text-[#106959]" />
                  <span className="font-medium font-poppins text-[#000000]">Call Minutes</span>
                </div>
                <p className="mt-2 text-[26px] font-bold font-poppins leading-none text-[#000000]">
                  {usage.minutes_used}
                </p>
                <p className="mt-1.5 text-[12px] font-poppins text-black/50">
                  used this period &middot; unlimited on your plan
                </p>
              </div>

              <div className="rounded-[8px] border border-black/10 bg-[#0F6A590A] p-4">
                <div className="flex items-center gap-2">
                  <Phone className="w-5 h-5 text-[#106959]" />
                  <span className="font-medium font-poppins text-[#000000]">Total Calls</span>
                </div>
                <p className="mt-2 text-[26px] font-bold font-poppins leading-none text-[#000000]">
                  {usage.calls_used}
                </p>
                <p className="mt-1.5 text-[12px] font-poppins text-black/50">
                  used this period &middot; unlimited on your plan
                </p>
              </div>
            </div>
          ) : (
            <p className="text-gray-500 text-sm">No usage data available.</p>
          )}

          {usage && usage.estimated_overage_cost > 0 && (
            <div className="mt-6 p-4 bg-yellow-50 border border-yellow-200 rounded-lg">
              <div className="flex items-start gap-3">
                <AlertCircle className="w-5 h-5 text-yellow-600 flex-shrink-0 mt-0.5" />
                <div>
                  <h4 className="text-sm font-semibold text-yellow-900 mb-1">
                    Estimated Overage Charges
                  </h4>
                  <p className="text-sm text-yellow-800">
                    Your usage has exceeded the included limits. Estimated additional charges: $
                    {usage.estimated_overage_cost.toFixed(2)}
                  </p>
                </div>
              </div>
            </div>
          )}
        </div>

        {/* Available Plans */}
        <div id="available-plans" className="rounded-[10px] border border-black/10 bg-white p-6 shadow-[0_4px_20px_-4px_rgba(16,105,89,0.1)]">
          <div className="flex flex-col items-center justify-center mb-8 pt-4 gap-5 text-center">
            <div>
              <h2 className="text-[24px] font-bold font-poppins text-[#000000]">Available Plans</h2>
              <p className="text-[14px] font-poppins text-black/60 mt-1">Choose the plan that fits your needs</p>
            </div>
            <div className="flex items-center justify-center gap-2 bg-[#0F6A590A] border border-black/10 rounded-lg p-1">
              <button
                onClick={() => setBillingPeriod('monthly')}
                className={`px-6 py-2.5 rounded-md text-sm font-semibold transition-all ${
                  billingPeriod === 'monthly'
                    ? 'bg-white text-[#106959] shadow-sm ring-1 ring-black/5'
                    : 'text-gray-600 hover:text-gray-900'
                }`}
              >
                Monthly
              </button>
              <button
                onClick={() => setBillingPeriod('yearly')}
                className={`px-6 py-2.5 rounded-md text-sm font-semibold transition-all flex items-center gap-1.5 ${
                  billingPeriod === 'yearly'
                    ? 'bg-white text-[#106959] shadow-sm ring-1 ring-black/5'
                    : 'text-gray-600 hover:text-gray-900'
                }`}
              >
                Yearly
                <span className="text-[10px] font-bold tracking-wide uppercase px-2 py-0.5 rounded-full bg-green-100 text-green-700">Save 15%</span>
              </button>
            </div>
          </div>

          {loading ? (
            <div className="flex flex-col md:flex-row flex-wrap justify-center gap-6">
              {[1, 2, 3].map((i) => (
                <div key={i} className="w-full md:w-[350px] border border-black/10 rounded-[10px] p-6 space-y-4">
                  <Skeleton className="h-6 w-28" />
                  <Skeleton className="h-4 w-40" />
                  <Skeleton className="h-12 w-24" />
                  <div className="space-y-2">
                    {[1, 2, 3, 4].map((j) => (
                      <Skeleton key={j} className="h-4 w-full" />
                    ))}
                  </div>
                  <Skeleton className="h-10 w-full mt-auto" />
                </div>
              ))}
            </div>
          ) : plans.length > 0 ? (
            <div className="flex flex-col md:flex-row flex-wrap justify-center gap-6">
              {plans
                .filter((p) => p.is_active && p.is_public)
                .map((plan) => (
                  <div
                    key={plan.id}
                    className={`w-full md:w-[350px] flex flex-col rounded-[10px] border p-6 transition-all bg-white relative top-0 hover:-top-1 ${
                      plan.id === subscription?.plan_id
                        ? 'border-[#106959] bg-[#0F6A590A] shadow-sm'
                        : 'border-black/10 hover:border-[#106959] hover:shadow-[0_4px_20px_-4px_rgba(16,105,89,0.1)]'
                    }`}
                  >
                    <div className="mb-4">
                      <h3 className="text-[20px] font-bold font-poppins text-[#000000]">{plan.name}</h3>
                      <p className="text-[13px] font-poppins text-black/60 mt-2">{plan.description}</p>
                    </div>

                    <div className="mb-6">
                      <div className="flex items-baseline gap-2">
                        <span className="text-[40px] font-bold text-[#000000] font-poppins">
                          $
                          {billingPeriod === 'monthly'
                            ? plan.price_monthly
                            : Math.round(((plan.price_yearly ?? plan.price_monthly * 10) / 12) * 10) /
                              10}
                        </span>
                        <span className="text-gray-500 font-medium text-sm">/month</span>
                      </div>
                      {billingPeriod === 'yearly' && plan.price_yearly && (
                        <p className="text-[12px] font-medium text-[#106959] mt-1 bg-green-50 w-fit px-2 py-0.5 rounded">
                          Billed ${plan.price_yearly} annually
                        </p>
                      )}
                    </div>

                    <div className="space-y-3.5 mb-8 flex-1">
                      {/* Driven by code, not by `included_minutes`: that column
                          is legacy pricing data and no longer caps anything, so
                          rendering it would advertise a limit that is not real. */}
                      <div className="flex items-center gap-2.5 text-[14px] text-gray-700 font-poppins">
                        <CheckCircle className="w-[18px] h-[18px] text-[#106959]" />
                        <span><strong className="font-semibold">Unlimited</strong> calls &amp; minutes</span>
                      </div>
                      <div className="flex items-center gap-2.5 text-[14px] text-gray-700 font-poppins">
                        <CheckCircle className="w-[18px] h-[18px] text-[#106959]" />
                        <span>Up to <strong className="font-semibold">{plan.max_agents}</strong> agents</span>
                      </div>
                      <div className="flex items-center gap-2.5 text-[14px] text-gray-700 font-poppins">
                        <CheckCircle className="w-[18px] h-[18px] text-[#106959]" />
                        <span>Up to <strong className="font-semibold">{plan.max_phone_numbers}</strong> phone numbers</span>
                      </div>
                      {/* Marketing bullets from the plan's `features` copy. */}
                      {(plan.features?.highlights ?? []).map((highlight: string) => (
                        <div
                          key={highlight}
                          className="flex items-start gap-2.5 text-[14px] text-gray-700 font-poppins"
                        >
                          <CheckCircle className="w-[18px] h-[18px] text-[#106959] mt-0.5" />
                          <span className="leading-tight">{highlight}</span>
                        </div>
                      ))}

                      {/* Capabilities this plan does NOT include, shown greyed
                          out rather than hidden — a feature nobody can see is a
                          feature nobody upgrades for. */}
                      {Object.entries(plan.entitlements?.features ?? {})
                        .filter(([, enabled]) => !enabled)
                        .filter(([key]) => FEATURE_LABELS[key])
                        .map(([key]) => (
                          <div
                            key={key}
                            className="flex items-start gap-2.5 text-[14px] text-gray-400 font-poppins"
                          >
                            <XCircle className="w-[18px] h-[18px] text-gray-300 mt-0.5" />
                            <span className="leading-tight line-through decoration-gray-300">
                              {FEATURE_LABELS[key]}
                            </span>
                          </div>
                        ))}
                    </div>

                    {plan.id === subscription?.plan_id && entitlements?.is_live ? (
                      <Button disabled className="w-full h-[45px] font-poppins text-sm rounded-[8px]">
                        {entitlements.is_trial ? 'Currently trialling' : 'Current Plan'}
                      </Button>
                    ) : (
                      <Button
                        className="w-full h-[45px] font-poppins text-sm rounded-[8px] bg-[#106959] hover:bg-[#0c5044] text-white shadow-sm"
                        onClick={() => choosePlan(plan)}
                        disabled={actionBusy}
                      >
                        {needsCheckout
                          ? entitlements?.is_trial
                            ? `Upgrade to ${plan.name}`
                            : 'Get Started'
                          : (plan.tier ?? 0) >= (currentPlan?.tier ?? 0)
                            ? 'Upgrade'
                            : 'Downgrade'}
                      </Button>
                    )}

                    {plan.id === subscription?.plan_id && entitlements?.is_trial && (
                      <p className="mt-2 text-center text-[12px] text-black/50 font-poppins">
                        Your trial includes every feature — usage is capped until you
                        upgrade.
                      </p>
                    )}

                    <div className="mt-5 pt-4 border-t border-black/5 text-[12px] text-gray-500 font-poppins flex flex-col gap-1">
                      <div>Overage minutes: <span className="font-medium text-gray-900">${plan.overage_rate_per_minute}/min</span></div>
                      <div>Extra calls: <span className="font-medium text-gray-900">${plan.overage_rate_per_call}/call</span></div>
                    </div>
                  </div>
                ))}
            </div>
          ) : (
            <p className="text-gray-500 text-sm text-center">No plans available.</p>
          )}
        </div>

        {/* Invoice History */}
        <div className="rounded-[10px] border border-black/10 bg-white overflow-hidden shadow-[0_4px_20px_-4px_rgba(16,105,89,0.1)]">
          <div className="px-6 py-5 border-b border-black/10">
            <h2 className="text-[20px] font-bold font-poppins text-[#000000]">Invoice History</h2>
            <p className="text-[14px] font-poppins text-black/60 mt-1">Download and view past invoices</p>
          </div>

          {loading ? (
            <div className="p-6 space-y-3">
              {[1, 2, 3].map((i) => (
                <div key={i} className="flex items-center justify-between py-2">
                  <Skeleton className="h-4 w-32" />
                  <Skeleton className="h-4 w-40" />
                  <Skeleton className="h-6 w-16" />
                  <Skeleton className="h-4 w-16" />
                  <Skeleton className="h-4 w-20" />
                </div>
              ))}
            </div>
          ) : invoices.length > 0 ? (
            <table className="w-full">
              <thead className="bg-gray-50 border-b">
                <tr>
                  <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">
                    Invoice
                  </th>
                  <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">
                    Period
                  </th>
                  <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">
                    Status
                  </th>
                  <th className="px-6 py-3 text-right text-xs font-medium text-gray-500 uppercase">
                    Amount
                  </th>
                  <th className="px-6 py-3 text-right text-xs font-medium text-gray-500 uppercase">
                    Actions
                  </th>
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-200">
                {invoices.map((invoice) => (
                  <tr key={invoice.id} className="hover:bg-gray-50">
                    <td className="px-6 py-4 whitespace-nowrap">
                      <div className="text-sm font-medium text-gray-900">
                        {invoice.invoice_number}
                      </div>
                      {invoice.paid_at && (
                        <div className="text-xs text-gray-500">
                          Paid {formatDate(invoice.paid_at)}
                        </div>
                      )}
                    </td>
                    <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-900">
                      {formatDate(invoice.period_start)} — {formatDate(invoice.period_end)}
                    </td>
                    <td className="px-6 py-4 whitespace-nowrap">
                      <span
                        className={`px-2 py-1 text-xs font-semibold rounded ${getStatusColor(
                          invoice.status
                        )}`}
                      >
                        {invoice.status.toUpperCase()}
                      </span>
                    </td>
                    <td className="px-6 py-4 whitespace-nowrap text-right text-sm font-semibold text-gray-900">
                      ${invoice.total.toFixed(2)}
                    </td>
                    <td className="px-6 py-4 whitespace-nowrap text-right">
                      {invoice.invoice_pdf ? (
                        <a
                          href={invoice.invoice_pdf}
                          target="_blank"
                          rel="noopener noreferrer"
                          className="text-blue-600 hover:text-blue-800 text-sm font-medium flex items-center gap-1 ml-auto"
                        >
                          <Download className="w-4 h-4" />
                          Download
                        </a>
                      ) : (
                        <span className="text-gray-400 text-sm">—</span>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          ) : (
            <div className="px-6 py-12 text-center text-gray-500">
              <p>No invoices yet.</p>
            </div>
          )}
        </div>
      
      {checkoutPlan && (
        <CheckoutModal
          plan={checkoutPlan}
          billingPeriod={billingPeriod}
          onClose={() => setCheckoutPlan(null)}
          onSuccess={async () => {
            setCheckoutPlan(null);
            await fetchAll();
          }}
        />
      )}
    </div>
  );
}
