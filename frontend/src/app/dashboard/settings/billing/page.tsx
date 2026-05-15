'use client';

import React, { useState } from 'react';
import {
  CreditCard,
  DollarSign,
  Calendar,
  Download,
  AlertCircle,
  CheckCircle,
  TrendingUp,
  Clock,
  Phone,
  Zap,
} from 'lucide-react';
import { Button } from '@/components/ui/button';

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

export default function BillingPage() {
  const [billingPeriod, setBillingPeriod] = useState<'monthly' | 'yearly'>('monthly');

  // Sample data - In production, fetch from API
  const availablePlans: SubscriptionPlan[] = [
    {
      id: '1',
      name: 'Starter',
      description: 'Perfect for trying out voice AI',
      price_monthly: 29,
      price_yearly: 290,
      included_minutes: 1000,
      included_calls: 100,
      max_agents: 1,
      max_phone_numbers: 1,
      max_knowledge_bases: 1,
      overage_rate_per_minute: 0.015,
      overage_rate_per_call: 0.05,
      features: {
        'Voice calls': true,
        'SMS support': true,
        'Basic analytics': true,
        'Email support': true,
      },
      is_active: true,
      is_public: true,
    },
    {
      id: '2',
      name: 'Professional',
      description: 'For growing businesses',
      price_monthly: 99,
      price_yearly: 990,
      included_minutes: 5000,
      included_calls: 500,
      max_agents: 5,
      max_phone_numbers: 5,
      max_knowledge_bases: 10,
      overage_rate_per_minute: 0.012,
      overage_rate_per_call: 0.04,
      features: {
        'Voice calls': true,
        'SMS support': true,
        'Advanced analytics': true,
        'Priority support': true,
        'Custom workflows': true,
        'API access': true,
      },
      is_active: true,
      is_public: true,
    },
    {
      id: '3',
      name: 'Enterprise',
      description: 'For large organizations',
      price_monthly: 299,
      price_yearly: 2990,
      included_minutes: 20000,
      included_calls: 2000,
      max_agents: 20,
      max_phone_numbers: 20,
      max_knowledge_bases: 50,
      overage_rate_per_minute: 0.01,
      overage_rate_per_call: 0.03,
      features: {
        'Voice calls': true,
        'SMS support': true,
        'Advanced analytics': true,
        'Dedicated support': true,
        'Custom workflows': true,
        'API access': true,
        'White-label': true,
        'SLA guarantee': true,
      },
      is_active: true,
      is_public: true,
    },
  ];

  const currentSubscription: Subscription = {
    id: '1',
    plan_id: '2',
    plan_name: 'Professional',
    status: 'active',
    billing_period: 'monthly',
    current_period_start: '2024-01-01T00:00:00Z',
    current_period_end: '2024-02-01T00:00:00Z',
    trial_end: null,
    canceled_at: null,
    current_period_minutes: 3245,
    current_period_calls: 289,
  };

  const currentUsage: Usage = {
    minutes_used: 3245,
    minutes_included: 5000,
    minutes_overage: 0,
    calls_used: 289,
    calls_included: 500,
    calls_overage: 0,
    estimated_overage_cost: 0,
  };

  const invoices: Invoice[] = [
    {
      id: '1',
      invoice_number: 'INV-2024-001',
      status: 'paid',
      amount_due: 99.0,
      amount_paid: 99.0,
      total: 99.0,
      period_start: '2024-01-01T00:00:00Z',
      period_end: '2024-02-01T00:00:00Z',
      due_date: '2024-01-07T00:00:00Z',
      paid_at: '2024-01-05T00:00:00Z',
      invoice_pdf: '#',
      hosted_invoice_url: '#',
    },
    {
      id: '2',
      invoice_number: 'INV-2023-012',
      status: 'paid',
      amount_due: 99.0,
      amount_paid: 99.0,
      total: 99.0,
      period_start: '2023-12-01T00:00:00Z',
      period_end: '2024-01-01T00:00:00Z',
      due_date: '2023-12-07T00:00:00Z',
      paid_at: '2023-12-05T00:00:00Z',
      invoice_pdf: '#',
      hosted_invoice_url: '#',
    },
  ];

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

  const formatDate = (dateString: string) => {
    return new Date(dateString).toLocaleDateString('en-US', {
      year: 'numeric',
      month: 'short',
      day: 'numeric',
    });
  };

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
            <span
              className={`px-3 py-1 text-sm font-semibold rounded ${getStatusColor(
                currentSubscription.status
              )}`}
            >
              {currentSubscription.status.toUpperCase()}
            </span>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-3 gap-6 mb-6">
            <div>
              <div className="text-sm text-gray-600 mb-1">Plan</div>
              <div className="text-2xl font-bold text-indigo-600">
                {currentSubscription.plan_name}
              </div>
              <div className="text-sm text-gray-500">
                ${availablePlans.find((p) => p.id === currentSubscription.plan_id)?.price_monthly}
                /month
              </div>
            </div>

            <div>
              <div className="text-sm text-gray-600 mb-1">Current Period</div>
              <div className="text-sm font-medium text-gray-900">
                {formatDate(currentSubscription.current_period_start)} -{' '}
                {formatDate(currentSubscription.current_period_end)}
              </div>
              <div className="text-xs text-gray-500 mt-1">
                Renews on {formatDate(currentSubscription.current_period_end)}
              </div>
            </div>

            <div>
              <div className="text-sm text-gray-600 mb-1">Payment Method</div>
              <div className="flex items-center gap-2">
                <CreditCard className="w-4 h-4 text-gray-400" />
                <span className="text-sm font-medium text-gray-900">•••• 4242</span>
              </div>
              <button className="text-xs text-indigo-600 hover:text-indigo-700 mt-1">
                Update payment method
              </button>
            </div>
          </div>

          <div className="flex gap-3">
            <Button variant="outline">Change Plan</Button>
            <Button variant="outline" className="text-red-600 border-red-200 hover:bg-red-50">
              Cancel Subscription
            </Button>
          </div>
        </div>

        {/* Usage This Period */}
        <div className="bg-white border rounded-lg p-6">
          <h2 className="text-xl font-bold text-gray-900 mb-6">Usage This Period</h2>

          <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
            {/* Minutes Usage */}
            <div>
              <div className="flex items-center justify-between mb-2">
                <div className="flex items-center gap-2">
                  <Clock className="w-5 h-5 text-blue-600" />
                  <span className="font-medium text-gray-900">Call Minutes</span>
                </div>
                <span className="text-sm font-semibold text-gray-900">
                  {currentUsage.minutes_used} / {currentUsage.minutes_included}
                </span>
              </div>

              <div className="w-full bg-gray-200 rounded-full h-2 mb-2">
                <div
                  className="bg-blue-600 h-2 rounded-full"
                  style={{
                    width: `${Math.min(
                      100,
                      (currentUsage.minutes_used / currentUsage.minutes_included) * 100
                    )}%`,
                  }}
                />
              </div>

              <div className="flex items-center justify-between text-xs text-gray-600">
                <span>
                  {Math.round((currentUsage.minutes_used / currentUsage.minutes_included) * 100)}%
                  used
                </span>
                {currentUsage.minutes_overage > 0 && (
                  <span className="text-red-600 font-semibold">
                    +{currentUsage.minutes_overage} overage
                  </span>
                )}
              </div>
            </div>

            {/* Calls Usage */}
            <div>
              <div className="flex items-center justify-between mb-2">
                <div className="flex items-center gap-2">
                  <Phone className="w-5 h-5 text-green-600" />
                  <span className="font-medium text-gray-900">Total Calls</span>
                </div>
                <span className="text-sm font-semibold text-gray-900">
                  {currentUsage.calls_used} / {currentUsage.calls_included}
                </span>
              </div>

              <div className="w-full bg-gray-200 rounded-full h-2 mb-2">
                <div
                  className="bg-green-600 h-2 rounded-full"
                  style={{
                    width: `${Math.min(
                      100,
                      (currentUsage.calls_used / currentUsage.calls_included) * 100
                    )}%`,
                  }}
                />
              </div>

              <div className="flex items-center justify-between text-xs text-gray-600">
                <span>
                  {Math.round((currentUsage.calls_used / currentUsage.calls_included) * 100)}% used
                </span>
                {currentUsage.calls_overage > 0 && (
                  <span className="text-red-600 font-semibold">
                    +{currentUsage.calls_overage} overage
                  </span>
                )}
              </div>
            </div>
          </div>

          {currentUsage.estimated_overage_cost > 0 && (
            <div className="mt-6 p-4 bg-yellow-50 border border-yellow-200 rounded-lg">
              <div className="flex items-start gap-3">
                <AlertCircle className="w-5 h-5 text-yellow-600 flex-shrink-0 mt-0.5" />
                <div>
                  <h4 className="text-sm font-semibold text-yellow-900 mb-1">
                    Estimated Overage Charges
                  </h4>
                  <p className="text-sm text-yellow-800">
                    Your usage has exceeded the included limits. Estimated additional charges: $
                    {currentUsage.estimated_overage_cost.toFixed(2)}
                  </p>
                </div>
              </div>
            </div>
          )}
        </div>

        {/* Available Plans */}
        <div className="bg-white border rounded-lg p-6">
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

          <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
            {availablePlans.map((plan) => (
              <div
                key={plan.id}
                className={`border-2 rounded-lg p-6 ${
                  plan.id === currentSubscription.plan_id
                    ? 'border-indigo-600 bg-indigo-50'
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
                      ${billingPeriod === 'monthly' ? plan.price_monthly : (plan.price_yearly || 0) / 12}
                    </span>
                    <span className="text-gray-600">/month</span>
                  </div>
                  {billingPeriod === 'yearly' && (
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
                  {Object.entries(plan.features).map(([feature, enabled]) =>
                    enabled ? (
                      <div key={feature} className="flex items-center gap-2 text-sm text-gray-600">
                        <CheckCircle className="w-4 h-4 text-green-600" />
                        <span>{feature}</span>
                      </div>
                    ) : null
                  )}
                </div>

                {plan.id === currentSubscription.plan_id ? (
                  <Button disabled className="w-full">
                    Current Plan
                  </Button>
                ) : (
                  <Button className="w-full bg-indigo-600 hover:bg-indigo-700">
                    {parseInt(plan.id) > parseInt(currentSubscription.plan_id)
                      ? 'Upgrade'
                      : 'Downgrade'}
                  </Button>
                )}

                <div className="mt-4 pt-4 border-t text-xs text-gray-500">
                  <div>Overage: ${plan.overage_rate_per_minute}/min</div>
                  <div>Extra calls: ${plan.overage_rate_per_call}/call</div>
                </div>
              </div>
            ))}
          </div>
        </div>

        {/* Invoice History */}
        <div className="bg-white border rounded-lg overflow-hidden">
          <div className="px-6 py-4 border-b">
            <h2 className="text-xl font-bold text-gray-900">Invoice History</h2>
            <p className="text-sm text-gray-600 mt-1">Download and view past invoices</p>
          </div>

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
                    {formatDate(invoice.period_start)} - {formatDate(invoice.period_end)}
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
                    <button className="text-indigo-600 hover:text-indigo-900 text-sm font-medium flex items-center gap-1 ml-auto">
                      <Download className="w-4 h-4" />
                      Download
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}
