'use client';

import React from 'react';
import { AlertCircle, XCircle } from 'lucide-react';

interface FlowValidationProps {
  errors: string[];
}

export const FlowValidation: React.FC<FlowValidationProps> = ({ errors }) => {
  if (errors.length === 0) return null;

  return (
    <div className="bg-white border-2 border-red-200 rounded-lg shadow-lg max-w-md">
      <div className="flex items-center gap-3 px-4 py-3 bg-red-50 border-b border-red-100 rounded-t-lg">
        <AlertCircle className="w-5 h-5 text-red-600" />
        <div>
          <h4 className="text-sm font-semibold text-red-900">Validation Errors</h4>
          <p className="text-xs text-red-700">{errors.length} {errors.length === 1 ? 'issue' : 'issues'} found</p>
        </div>
      </div>
      <div className="px-4 py-3 max-h-64 overflow-y-auto">
        <ul className="space-y-2">
          {errors.map((error, index) => (
            <li key={index} className="flex items-start gap-2 text-sm text-red-800">
              <XCircle className="w-4 h-4 mt-0.5 flex-shrink-0" />
              <span>{error}</span>
            </li>
          ))}
        </ul>
      </div>
    </div>
  );
};
