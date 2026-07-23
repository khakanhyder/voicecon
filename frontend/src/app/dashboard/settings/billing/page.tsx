'use client';

import React, { useState, useEffect } from 'react';
import {
  CreditCard,
  Calendar,
  Download,
  AlertCircle,
  CheckCircle,
  Clock,
  Phone,
} from 'lucide-react';
import { toast } from 'sonner';
import { Button } from '@/components/ui/button';
import { apiClient, getErrorMessage } from '@/lib/api';
import { API_ENDPOINTS } from '@/lib/constants';
import { CheckoutModal, type CheckoutPlan } from '@/components/billing/CheckoutModal';

interface SubscriptionPlan {
  id: string;
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
  features: Record<string, boolean>;
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

  const fetchAll = async () => {
    setLoading(true);
    const [plansRes, subRes, usageRes, invRes] = await Promise.allSettled([
      apiClient.get<SubscriptionPlan[]>(API_ENDPOINTS.BILLING_PLANS),
      apiClient.get<Subscription | null>(API_ENDPOINTS.BILLING_SUBSCRIPTION),
      apiClient.get<Usage>(API_ENDPOINTS.BILLING_USAGE),
      apiClient.get<Invoice[]>(API_ENDPOINTS.BILLING_INVOICES),
    ]);

    if (plansRes.status === 'fulfilled') setPlans(plansRes.value.data);
    setSubscription(subRes.status === 'fulfilled' ? subRes.value.data : null);
    setUsage(usageRes.status === 'fulfilled' ? usageRes.value.data : null);
    if (invRes.status === 'fulfilled') setInvoices(invRes.value.data);
    setLoading(false);
  };

  useEffect(() => {
    fetchAll();
  }, []);

  // Switch an existing subscription to a different plan (no new card needed).
  const switchPlan = async (planId: string) => {
    setActionBusy(true);
    try {
      await apiClient.put(API_ENDPOINTS.BILLING_SUBSCRIPTION, { plan_id: planId, prorate: true });
      toast.success('Plan updated');
      await fetchAll();
    } catch (err) {
      toast.error(getErrorMessage(err));
    } finally {
      setActionBusy(false);
    }
  };

  const cancelSubscription = async () => {
    if (!confirm('Cancel your subscription at the end of the current period?')) return;
    setActionBusy(true);
    try {
      await apiClient.delete(API_ENDPOINTS.BILLING_SUBSCRIPTION);
      toast.success('Subscription canceled');
      await fetchAll();
    } catch (err) {
      toast.error(getErrorMessage(err));
    } finally {
      setActionBusy(false);
    }
  };

  // Choosing a plan: switch in place if subscribed, otherwise open checkout.
  const choosePlan = (plan: SubscriptionPlan) => {
    if (subscription) {
      switchPlan(plan.id);
    } else {
      setCheckoutPlan({
        id: plan.id,
        name: plan.name,
        price_monthly: plan.price_monthly,
        price_yearly: plan.price_yearly,
      });
    }
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
        return 'text-red-600 bg-red-100';
      case 'canceled':
        return 'text-gray-600 bg-gray-100';
      default:
        return 'text-gray-600 bg-gray-100';
    }
  };

  const formatDate = (dateString: string) =>
    new Date(dateString).toLocaleDateString('en-US', {
      year: 'numeric',
      month: 'short',
      day: 'numeric',
    });

  const currentPlan = plans.find((p) => p.id === subscription?.plan_id);

  return (
    <div className="min-h-screen bg-gray-50 p-6">
      <div className="max-w-7xl mx-auto space-y-6">
        {/* Header */}
        <div>
          <h1 className="text-3xl font-bold text-gray-900">Billing & Subscription</h1>
          <p className="text-gray-600 mt-1">Manage your subscription, usage, and invoices</p>
        </div>

        {/* Current Subscription */}
        <div className="bg-white border rounded-lg p-6">
          <div className="flex items-center justify-between mb-4">
            <div>
              <h2 className="text-xl font-bold text-gray-900">Current Plan</h2>
              <p className="text-sm text-gray-600">Your active subscription</p>
            </div>
            {loading ? (
              <Skeleton className="w-20 h-7" />
            ) : subscription ? (
              <span
                className={`px-3 py-1 text-sm font-semibold rounded ${getStatusColor(
                  subscription.status
                )}`}
              >
                {subscription.status.toUpperCase()}
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
                <div className="text-sm text-gray-600 mb-1">Plan</div>
                <div className="text-2xl font-bold text-blue-600">{subscription.plan_name}</div>
                {currentPlan && (
                  <div className="text-sm text-gray-500">
                    ${currentPlan.price_monthly}/month
                  </div>
                )}
              </div>
              <div>
                <div className="text-sm text-gray-600 mb-1">Current Period</div>
                <div className="text-sm font-medium text-gray-900">
                  {formatDate(subscription.current_period_start)} -{' '}
                  {formatDate(subscription.current_period_end)}
                </div>
                <div className="text-xs text-gray-500 mt-1 flex items-center gap-1">
                  <Calendar className="w-3 h-3" />
                  Renews {formatDate(subscription.current_period_end)}
                </div>
              </div>
              <div>
                <div className="text-sm text-gray-600 mb-1">Billing Period</div>
                <div className="flex items-center gap-2">
                  <CreditCard className="w-4 h-4 text-gray-400" />
                  <span className="text-sm font-medium text-gray-900 capitalize">
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

          {subscription && !subscription.canceled_at && (
            <div className="flex gap-3">
              <Button variant="outline" onClick={scrollToPlans} disabled={actionBusy}>
                Change Plan
              </Button>
              <Button
                variant="outline"
                className="text-red-600 border-red-200 hover:bg-red-50"
                onClick={cancelSubscription}
                disabled={actionBusy}
              >
                Cancel Subscription
              </Button>
            </div>
          )}
        </div>

        {/* Usage This Period */}
        <div className="bg-white border rounded-lg p-6">
          <h2 className="text-xl font-bold text-gray-900 mb-6">Usage This Period</h2>

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
            <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
              {/* Minutes */}
              <div>
                <div className="flex items-center justify-between mb-2">
                  <div className="flex items-center gap-2">
                    <Clock className="w-5 h-5 text-blue-600" />
                    <span className="font-medium text-gray-900">Call Minutes</span>
                  </div>
                  <span className="text-sm font-semibold text-gray-900">
                    {usage.minutes_used} / {usage.minutes_included}
                  </span>
                </div>
                <div className="w-full bg-gray-200 rounded-full h-2 mb-2">
                  <div
                    className="bg-blue-600 h-2 rounded-full"
                    style={{
                      width: `${Math.min(
                        100,
                        usage.minutes_included > 0
                          ? (usage.minutes_used / usage.minutes_included) * 100
                          : 0
                      )}%`,
                    }}
                  />
                </div>
                <div className="flex items-center justify-between text-xs text-gray-600">
                  <span>
                    {usage.minutes_included > 0
                      ? Math.round((usage.minutes_used / usage.minutes_included) * 100)
                      : 0}
                    % used
                  </span>
                  {usage.minutes_overage > 0 && (
                    <span className="text-red-600 font-semibold">
                      +{usage.minutes_overage} overage
                    </span>
                  )}
                </div>
              </div>

              {/* Calls */}
              <div>
                <div className="flex items-center justify-between mb-2">
                  <div className="flex items-center gap-2">
                    <Phone className="w-5 h-5 text-green-600" />
                    <span className="font-medium text-gray-900">Total Calls</span>
                  </div>
                  <span className="text-sm font-semibold text-gray-900">
                    {usage.calls_used} / {usage.calls_included}
                  </span>
                </div>
                <div className="w-full bg-gray-200 rounded-full h-2 mb-2">
                  <div
                    className="bg-green-600 h-2 rounded-full"
                    style={{
                      width: `${Math.min(
                        100,
                        usage.calls_included > 0
                          ? (usage.calls_used / usage.calls_included) * 100
                          : 0
                      )}%`,
                    }}
                  />
                </div>
                <div className="flex items-center justify-between text-xs text-gray-600">
                  <span>
                    {usage.calls_included > 0
                      ? Math.round((usage.calls_used / usage.calls_included) * 100)
                      : 0}
                    % used
                  </span>
                  {usage.calls_overage > 0 && (
                    <span className="text-red-600 font-semibold">
                      +{usage.calls_overage} overage
                    </span>
                  )}
                </div>
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
        <div id="available-plans" className="bg-white border rounded-lg p-6">
          <div className="flex items-center justify-between mb-6">
            <div>
              <h2 className="text-xl font-bold text-gray-900">Available Plans</h2>
              <p className="text-sm text-gray-600">Choose the plan that fits your needs</p>
            </div>
            <div className="flex items-center gap-2 bg-gray-100 rounded-lg p-1">
              <button
                onClick={() => setBillingPeriod('monthly')}
                className={`px-4 py-2 rounded-md text-sm font-medium transition-colors ${
                  billingPeriod === 'monthly'
                    ? 'bg-white text-gray-900 shadow-sm'
                    : 'text-gray-600 hover:text-gray-900'
                }`}
              >
                Monthly
              </button>
              <button
                onClick={() => setBillingPeriod('yearly')}
                className={`px-4 py-2 rounded-md text-sm font-medium transition-colors ${
                  billingPeriod === 'yearly'
                    ? 'bg-white text-gray-900 shadow-sm'
                    : 'text-gray-600 hover:text-gray-900'
                }`}
              >
                Yearly
                <span className="ml-1 text-xs text-green-600">(Save 15%)</span>
              </button>
            </div>
          </div>

          {loading ? (
            <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
              {[1, 2, 3].map((i) => (
                <div key={i} className="border-2 rounded-lg p-6 space-y-4">
                  <Skeleton className="h-6 w-28" />
                  <Skeleton className="h-4 w-40" />
                  <Skeleton className="h-12 w-24" />
                  <div className="space-y-2">
                    {[1, 2, 3, 4].map((j) => (
                      <Skeleton key={j} className="h-4 w-full" />
                    ))}
                  </div>
                  <Skeleton className="h-10 w-full" />
                </div>
              ))}
            </div>
          ) : plans.length > 0 ? (
            <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
              {plans
                .filter((p) => p.is_active && p.is_public)
                .map((plan) => (
                  <div
                    key={plan.id}
                    className={`border-2 rounded-lg p-6 ${
                      plan.id === subscription?.plan_id
                        ? 'border-blue-600 bg-blue-50'
                        : 'border-gray-200 hover:border-gray-300'
                    }`}
                  >
                    <div className="mb-4">
                      <h3 className="text-lg font-bold text-gray-900">{plan.name}</h3>
                      <p className="text-sm text-gray-600 mt-1">{plan.description}</p>
                    </div>

                    <div className="mb-6">
                      <div className="flex items-baseline gap-2">
                        <span className="text-4xl font-bold text-gray-900">
                          $
                          {billingPeriod === 'monthly'
                            ? plan.price_monthly
                            : Math.round(((plan.price_yearly ?? plan.price_monthly * 10) / 12) * 10) /
                              10}
                        </span>
                        <span className="text-gray-600">/month</span>
                      </div>
                      {billingPeriod === 'yearly' && plan.price_yearly && (
                        <p className="text-xs text-gray-500 mt-1">
                          Billed ${plan.price_yearly} annually
                        </p>
                      )}
                    </div>

                    <div className="space-y-3 mb-6">
                      <div className="flex items-center gap-2 text-sm text-gray-600">
                        <CheckCircle className="w-4 h-4 text-green-600" />
                        <span>{plan.included_minutes.toLocaleString()} minutes/month</span>
                      </div>
                      <div className="flex items-center gap-2 text-sm text-gray-600">
                        <CheckCircle className="w-4 h-4 text-green-600" />
                        <span>{plan.included_calls.toLocaleString()} calls/month</span>
                      </div>
                      <div className="flex items-center gap-2 text-sm text-gray-600">
                        <CheckCircle className="w-4 h-4 text-green-600" />
                        <span>Up to {plan.max_agents} agents</span>
                      </div>
                      <div className="flex items-center gap-2 text-sm text-gray-600">
                        <CheckCircle className="w-4 h-4 text-green-600" />
                        <span>Up to {plan.max_phone_numbers} phone numbers</span>
                      </div>
                      {Object.entries(plan.features || {}).map(([feature, enabled]) =>
                        enabled ? (
                          <div
                            key={feature}
                            className="flex items-center gap-2 text-sm text-gray-600"
                          >
                            <CheckCircle className="w-4 h-4 text-green-600" />
                            <span>{feature}</span>
                          </div>
                        ) : null
                      )}
                    </div>

                    {plan.id === subscription?.plan_id ? (
                      <Button disabled className="w-full">
                        Current Plan
                      </Button>
                    ) : (
                      <Button
                        className="w-full bg-blue-600 hover:bg-blue-700"
                        onClick={() => choosePlan(plan)}
                        disabled={actionBusy}
                      >
                        {subscription ? 'Switch Plan' : 'Get Started'}
                      </Button>
                    )}

                    <div className="mt-4 pt-4 border-t text-xs text-gray-500">
                      <div>Overage: ${plan.overage_rate_per_minute}/min</div>
                      <div>Extra calls: ${plan.overage_rate_per_call}/call</div>
                    </div>
                  </div>
                ))}
            </div>
          ) : (
            <p className="text-gray-500 text-sm">No plans available.</p>
          )}
        </div>

        {/* Invoice History */}
        <div className="bg-white border rounded-lg overflow-hidden">
          <div className="px-6 py-4 border-b">
            <h2 className="text-xl font-bold text-gray-900">Invoice History</h2>
            <p className="text-sm text-gray-600 mt-1">Download and view past invoices</p>
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
