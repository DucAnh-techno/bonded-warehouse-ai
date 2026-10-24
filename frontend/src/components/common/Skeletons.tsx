import React from 'react';

export const Skeleton: React.FC<{ className?: string }> = ({ className = '' }) => (
  <div className={`animate-pulse bg-slate-200/80 rounded ${className}`} />
);

// 1. Dashboard Page Skeletons
export const DashboardSkeleton: React.FC = () => (
  <div className="space-y-6 animate-pulse">
    {/* Header banner skeleton */}
    <div className="bg-white border border-slate-200 rounded-xl p-6 shadow-sm">
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
        <div className="space-y-2">
          <div className="h-6 w-48 bg-slate-200 rounded" />
          <div className="h-4 w-72 bg-slate-100 rounded" />
        </div>
        <div className="flex gap-2">
          <div className="h-9 w-28 bg-slate-200 rounded-lg" />
          <div className="h-9 w-36 bg-slate-300 rounded-lg" />
        </div>
      </div>
    </div>

    {/* 5 KPI Cards skeleton */}
    <div className="grid grid-cols-2 md:grid-cols-4 lg:grid-cols-5 gap-3">
      {[...Array(5)].map((_, i) => (
        <div key={i} className="bg-white p-4 rounded-xl border border-slate-200 shadow-sm space-y-2.5">
          <div className="flex justify-between items-center">
            <div className="h-3.5 w-24 bg-slate-200 rounded" />
            <div className="h-4 w-4 bg-slate-200 rounded-full" />
          </div>
          <div className="h-7 w-16 bg-slate-300 rounded" />
          <div className="h-3 w-28 bg-slate-100 rounded" />
        </div>
      ))}
    </div>

    {/* Search & Filter Bar skeleton */}
    <div className="bg-white p-4 rounded-xl border border-slate-200 shadow-sm flex flex-col md:flex-row gap-3">
      <div className="h-10 flex-1 bg-slate-100 rounded-lg" />
      <div className="h-10 w-40 bg-slate-100 rounded-lg" />
      <div className="h-10 w-40 bg-slate-100 rounded-lg" />
    </div>

    {/* Table skeleton */}
    <div className="bg-white rounded-xl border border-slate-200 shadow-sm overflow-hidden p-4 space-y-3">
      <div className="h-8 bg-slate-100 rounded mb-2" />
      {[...Array(6)].map((_, i) => (
        <div key={i} className="flex items-center justify-between py-2 border-b border-slate-100">
          <div className="h-4 w-32 bg-slate-200 rounded" />
          <div className="h-4 w-20 bg-slate-100 rounded" />
          <div className="h-4 w-28 bg-slate-200 rounded" />
          <div className="h-4 w-36 bg-slate-100 rounded" />
          <div className="h-4 w-16 bg-slate-200 rounded" />
          <div className="h-6 w-20 bg-slate-200 rounded-full" />
          <div className="h-4 w-24 bg-slate-100 rounded" />
          <div className="h-7 w-20 bg-slate-200 rounded" />
        </div>
      ))}
    </div>
  </div>
);

// 2. Documents Page Skeletons
export const DocumentsPageSkeleton: React.FC = () => (
  <div className="space-y-6 animate-pulse">
    {/* Top Bar Skeleton */}
    <div className="bg-white border border-slate-200 rounded-xl p-4 shadow-sm flex flex-col md:flex-row justify-between gap-4">
      <div className="flex items-center gap-3">
        <div className="h-4 w-32 bg-slate-200 rounded" />
        <div className="h-9 w-64 bg-slate-200 rounded-lg" />
      </div>
      <div className="flex gap-2">
        <div className="h-9 w-44 bg-slate-300 rounded-lg" />
        <div className="h-9 w-28 bg-slate-200 rounded-lg" />
      </div>
    </div>

    {/* Document checklist pills */}
    <div className="bg-slate-50 border border-slate-200 rounded-xl p-4 space-y-3">
      <div className="h-4 w-48 bg-slate-200 rounded" />
      <div className="grid grid-cols-2 sm:grid-cols-4 lg:grid-cols-7 gap-2">
        {[...Array(7)].map((_, i) => (
          <div key={i} className="h-14 bg-slate-200/80 rounded-lg" />
        ))}
      </div>
    </div>

    {/* Document tabs pills */}
    <div className="flex gap-2 items-center">
      <div className="h-4 w-24 bg-slate-200 rounded mr-2" />
      {[...Array(4)].map((_, i) => (
        <div key={i} className="h-8 w-36 bg-slate-200 rounded-lg" />
      ))}
    </div>

    {/* Document Viewer 2-column skeleton */}
    <div className="grid grid-cols-1 lg:grid-cols-12 gap-5">
      {/* Left PDF preview skeleton */}
      <div className="lg:col-span-7 bg-white rounded-xl border border-slate-200 shadow-sm p-4 min-h-[500px] flex flex-col justify-between">
        <div className="h-8 bg-slate-100 rounded mb-4" />
        <div className="flex-1 bg-slate-100/60 rounded flex items-center justify-center">
          <div className="h-32 w-32 bg-slate-200/70 rounded-lg" />
        </div>
        <div className="h-8 bg-slate-100 rounded mt-4" />
      </div>

      {/* Right Extracted Fields skeleton */}
      <div className="lg:col-span-5 bg-white rounded-xl border border-slate-200 shadow-sm p-4 space-y-4">
        <div className="h-6 w-48 bg-slate-200 rounded" />
        <div className="space-y-3">
          {[...Array(6)].map((_, i) => (
            <div key={i} className="space-y-1">
              <div className="h-3 w-28 bg-slate-200 rounded" />
              <div className="h-8 bg-slate-100 rounded-lg" />
            </div>
          ))}
        </div>
        <div className="h-24 bg-slate-50 border border-slate-200 rounded-lg" />
      </div>
    </div>
  </div>
);

// 3. Reconciliation Page Skeletons
export const ReconciliationSkeleton: React.FC = () => (
  <div className="space-y-6 animate-pulse">
    {/* Top Header Card */}
    <div className="bg-white border border-slate-200 rounded-xl p-5 shadow-sm space-y-4">
      <div className="flex flex-col lg:flex-row justify-between gap-4">
        <div className="space-y-2">
          <div className="h-6 w-60 bg-slate-200 rounded" />
          <div className="h-4 w-80 bg-slate-100 rounded" />
        </div>
        <div className="flex flex-wrap gap-2">
          <div className="h-9 w-48 bg-slate-100 rounded-lg" />
          <div className="h-9 w-40 bg-slate-300 rounded-lg" />
          <div className="h-9 w-28 bg-slate-200 rounded-lg" />
        </div>
      </div>
      {/* 5 KPI mini-bars */}
      <div className="grid grid-cols-2 sm:grid-cols-5 gap-3 pt-3 border-t border-slate-100">
        {[...Array(5)].map((_, i) => (
          <div key={i} className="h-12 bg-slate-100 rounded-lg" />
        ))}
      </div>
    </div>

    {/* Cross-document matrix skeleton table */}
    <div className="bg-white border border-slate-200 rounded-xl shadow-sm overflow-hidden p-5 space-y-3">
      <div className="flex justify-between items-center pb-2 border-b border-slate-200">
        <div className="h-5 w-44 bg-slate-200 rounded" />
        <div className="h-8 w-32 bg-slate-200 rounded-lg" />
      </div>
      <div className="h-8 bg-slate-100 rounded" />
      {[...Array(7)].map((_, i) => (
        <div key={i} className="grid grid-cols-8 gap-2 py-2 border-b border-slate-100">
          <div className="h-4 bg-slate-200 rounded col-span-2" />
          <div className="h-4 bg-slate-100 rounded" />
          <div className="h-4 bg-slate-100 rounded" />
          <div className="h-4 bg-slate-100 rounded" />
          <div className="h-4 bg-slate-100 rounded" />
          <div className="h-4 bg-slate-100 rounded" />
          <div className="h-5 bg-slate-200 rounded-full" />
        </div>
      ))}
    </div>

    {/* General transport card skeleton */}
    <div className="bg-white border border-slate-200 rounded-xl p-5 shadow-sm space-y-3">
      <div className="h-5 w-52 bg-slate-200 rounded" />
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        {[...Array(4)].map((_, i) => (
          <div key={i} className="h-36 bg-slate-50 border border-slate-200 rounded-xl p-3 space-y-2">
            <div className="h-4 w-36 bg-slate-200 rounded" />
            <div className="h-4 w-full bg-slate-100 rounded" />
            <div className="h-4 w-3/4 bg-slate-100 rounded" />
          </div>
        ))}
      </div>
    </div>
  </div>
);

// 4. SKU Matrix Table Skeleton (Used within Reconciliation Accordion)
export const SkuMatrixSkeleton: React.FC = () => (
  <div className="space-y-3 animate-pulse p-4">
    <div className="flex justify-between items-center mb-3">
      <div className="h-8 w-64 bg-slate-100 rounded-lg" />
      <div className="h-8 w-44 bg-slate-100 rounded-lg" />
    </div>
    <div className="h-8 bg-slate-100 rounded" />
    {[...Array(6)].map((_, i) => (
      <div key={i} className="grid grid-cols-7 gap-3 py-3 border-b border-slate-100 items-center">
        <div className="h-4 bg-slate-200 rounded col-span-2" />
        <div className="h-4 bg-slate-100 rounded text-right" />
        <div className="h-4 bg-slate-100 rounded text-right" />
        <div className="h-4 bg-slate-100 rounded text-right" />
        <div className="h-4 bg-slate-100 rounded text-center" />
        <div className="h-6 bg-slate-200 rounded-full mx-auto w-16" />
      </div>
    ))}
  </div>
);

// 5. WMS Gateway Skeleton
export const WMSGatewaySkeleton: React.FC = () => (
  <div className="space-y-6 animate-pulse">
    {/* Header */}
    <div className="bg-white border border-slate-200 rounded-xl p-6 shadow-sm flex flex-col md:flex-row justify-between gap-4">
      <div className="space-y-2">
        <div className="h-6 w-64 bg-slate-200 rounded" />
        <div className="h-4 w-96 bg-slate-100 rounded" />
      </div>
      <div className="h-9 w-60 bg-slate-200 rounded-lg" />
    </div>

    {/* Gatekeeper Check Card Skeleton */}
    <div className="bg-white border border-slate-200 rounded-xl p-6 shadow-sm space-y-4">
      <div className="flex justify-between items-center pb-3 border-b border-slate-100">
        <div className="h-5 w-48 bg-slate-200 rounded" />
        <div className="h-6 w-28 bg-slate-200 rounded-full" />
      </div>
      <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
        {[...Array(3)].map((_, i) => (
          <div key={i} className="h-20 bg-slate-50 border border-slate-200 rounded-lg p-3 space-y-2">
            <div className="h-4 w-32 bg-slate-200 rounded" />
            <div className="h-3 w-44 bg-slate-100 rounded" />
          </div>
        ))}
      </div>
    </div>

    {/* Action cards: Excel & Transmission */}
    <div className="grid grid-cols-1 lg:grid-cols-2 gap-5">
      <div className="bg-white border border-slate-200 rounded-xl p-5 shadow-sm space-y-3">
        <div className="h-5 w-40 bg-slate-200 rounded" />
        <div className="h-16 bg-slate-50 border border-slate-200 rounded-lg" />
        <div className="h-10 w-full bg-slate-200 rounded-lg" />
      </div>
      <div className="bg-white border border-slate-200 rounded-xl p-5 shadow-sm space-y-3">
        <div className="h-5 w-40 bg-slate-200 rounded" />
        <div className="h-16 bg-slate-50 border border-slate-200 rounded-lg" />
        <div className="h-10 w-full bg-slate-300 rounded-lg" />
      </div>
    </div>
  </div>
);
