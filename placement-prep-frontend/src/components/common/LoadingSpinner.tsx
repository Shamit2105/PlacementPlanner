import React from 'react';

const LoadingSpinner: React.FC<{ label?: string }> = ({ label = 'Loading' }) => {
  return (
    <div className="flex flex-col items-center justify-center gap-3 py-12">
      <div className="relative h-12 w-12">
        <div className="absolute inset-0 rounded-full border-4 border-cyan-200" />
        <div className="absolute inset-0 animate-spin rounded-full border-4 border-transparent border-t-teal-500 border-r-cyan-500" />
      </div>
      <p className="text-sm font-semibold text-slate-600">{label}</p>
    </div>
  );
};

export default LoadingSpinner;
