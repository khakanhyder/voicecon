'use client'

import { Button } from '@/components/ui/button'
import Link from 'next/link'

export default function SettingsPage() {
  return (
    <div className="space-y-6 max-w-5xl">
      <div className="grid gap-6 md:grid-cols-2">
        <Link href="/dashboard/settings/profile">
          <div className="group rounded-2xl border border-slate-200 bg-white p-6 hover:border-[#106959] hover:shadow-[0_4px_20px_-4px_rgba(16,105,89,0.1)] transition-all cursor-pointer h-full relative overflow-hidden">
            <div className="absolute top-0 left-0 w-1 h-full bg-[#106959] opacity-0 group-hover:opacity-100 transition-opacity" />
            <div className="flex items-center gap-4 mb-3">
              <div className="w-12 h-12 rounded-[10px] bg-[#0F6A59]/10 flex items-center justify-center text-[#106959] group-hover:scale-110 transition-transform">
                <svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M19 21v-2a4 4 0 0 0-4-4H9a4 4 0 0 0-4 4v2"/><circle cx="12" cy="7" r="4"/></svg>
              </div>
              <h3 className="text-[18px] font-bold font-poppins text-[#000000]">Profile</h3>
            </div>
            <p className="text-black/60 font-poppins text-[14px] leading-relaxed">
              Update your personal details, adjust preferences, and manage your account security settings.
            </p>
          </div>
        </Link>

        <Link href="/dashboard/settings/billing">
           <div className="group rounded-2xl border border-slate-200 bg-white p-6 hover:border-[#106959] hover:shadow-[0_4px_20px_-4px_rgba(16,105,89,0.1)] transition-all cursor-pointer h-full relative overflow-hidden">
            <div className="absolute top-0 left-0 w-1 h-full bg-[#106959] opacity-0 group-hover:opacity-100 transition-opacity" />
            <div className="flex items-center gap-4 mb-3">
              <div className="w-12 h-12 rounded-[10px] bg-[#0F6A59]/10 flex items-center justify-center text-[#106959] group-hover:scale-110 transition-transform">
                <svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><rect width="20" height="14" x="2" y="5" rx="2"/><line x1="2" x2="22" y1="10" y2="10"/></svg>
              </div>
              <h3 className="text-[18px] font-bold font-poppins text-[#000000]">Billing</h3>
            </div>
            <p className="text-black/60 font-poppins text-[14px] leading-relaxed">
              Manage your subscription plan, view payment methods, and download past invoices.
            </p>
          </div>
        </Link>

        <Link href="/dashboard/settings/team">
           <div className="group rounded-2xl border border-slate-200 bg-white p-6 hover:border-[#106959] hover:shadow-[0_4px_20px_-4px_rgba(16,105,89,0.1)] transition-all cursor-pointer h-full relative overflow-hidden">
            <div className="absolute top-0 left-0 w-1 h-full bg-[#106959] opacity-0 group-hover:opacity-100 transition-opacity" />
            <div className="flex items-center gap-4 mb-3">
              <div className="w-12 h-12 rounded-[10px] bg-[#0F6A59]/10 flex items-center justify-center text-[#106959] group-hover:scale-110 transition-transform">
                <svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M16 21v-2a4 4 0 0 0-4-4H6a4 4 0 0 0-4 4v2"/><circle cx="9" cy="7" r="4"/><path d="M22 21v-2a4 4 0 0 0-3-3.87"/><path d="M16 3.13a4 4 0 0 1 0 7.75"/></svg>
              </div>
              <h3 className="text-[18px] font-bold font-poppins text-[#000000]">Team</h3>
            </div>
            <p className="text-black/60 font-poppins text-[14px] leading-relaxed">
              Invite new team members, manage active user roles, and control workspace permissions.
            </p>
          </div>
        </Link>

        <Link href="/dashboard/settings/workspace">
           <div className="group rounded-2xl border border-slate-200 bg-white p-6 hover:border-[#106959] hover:shadow-[0_4px_20px_-4px_rgba(16,105,89,0.1)] transition-all cursor-pointer h-full relative overflow-hidden">
            <div className="absolute top-0 left-0 w-1 h-full bg-[#106959] opacity-0 group-hover:opacity-100 transition-opacity" />
            <div className="flex items-center gap-4 mb-3">
              <div className="w-12 h-12 rounded-[10px] bg-[#0F6A59]/10 flex items-center justify-center text-[#106959] group-hover:scale-110 transition-transform">
                <svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M6 22V4a2 2 0 0 1 2-2h8a2 2 0 0 1 2 2v18Z"/><path d="M6 12H4a2 2 0 0 0-2 2v6a2 2 0 0 0 2 2h2"/><path d="M18 9h2a2 2 0 0 1 2 2v9a2 2 0 0 1-2 2h-2"/><path d="M10 6h4"/><path d="M10 10h4"/><path d="M10 14h4"/><path d="M10 18h4"/></svg>
              </div>
              <h3 className="text-[18px] font-bold font-poppins text-[#000000]">Workspace</h3>
            </div>
            <p className="text-black/60 font-poppins text-[14px] leading-relaxed">
              Rename this workspace, review its details, or leave and delete it.
            </p>
          </div>
        </Link>

        <Link href="/dashboard/settings/api-keys">
           <div className="group rounded-2xl border border-slate-200 bg-white p-6 hover:border-[#106959] hover:shadow-[0_4px_20px_-4px_rgba(16,105,89,0.1)] transition-all cursor-pointer h-full relative overflow-hidden">
            <div className="absolute top-0 left-0 w-1 h-full bg-[#106959] opacity-0 group-hover:opacity-100 transition-opacity" />
            <div className="flex items-center gap-4 mb-3">
              <div className="w-12 h-12 rounded-[10px] bg-[#0F6A59]/10 flex items-center justify-center text-[#106959] group-hover:scale-110 transition-transform">
                <svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M21 2l-2 2m-7.61 7.61a5.5 5.5 0 1 1-7.778 7.778 5.5 5.5 0 0 1 7.777-7.777zm0 0L15.5 7.5m0 0l3 3L22 7l-3-3m-3.5 3.5L19 4"/></svg>
              </div>
              <h3 className="text-[18px] font-bold font-poppins text-[#000000]">API Keys</h3>
            </div>
            <p className="text-black/60 font-poppins text-[14px] leading-relaxed">
              Generate new API keys and manage existing credentials to integrate with external systems.
            </p>
          </div>
        </Link>
      </div>
    </div>
  )
}
