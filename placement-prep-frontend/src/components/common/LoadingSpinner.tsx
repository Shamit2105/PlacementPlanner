import React from 'react';

const LoadingSpinner: React.FC = () => {
  return (
    <div className="flex justify-center items-center py-12">
      <div className="relative">
        <div className="w-12 h-12 rounded-full border-4 border-ocean-100"></div>
        <div className="w-12 h-12 rounded-full border-4 border-t-primary-500 border-r-ocean-500 animate-spin absolute top-0"></div>
      </div>
    </div>
  );
};

export default LoadingSpinner;