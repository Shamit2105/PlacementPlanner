import React from 'react';

interface BadgeProps {
  text: string;
  variant?: 'primary' | 'ocean' | 'success' | 'warning';
  size?: 'sm' | 'md';
}

const Badge: React.FC<BadgeProps> = ({ text, variant = 'primary', size = 'sm' }) => {
  const variants = {
    primary: 'bg-primary-100 text-primary-700 border-primary-200',
    ocean: 'bg-ocean-100 text-ocean-700 border-ocean-200',
    success: 'bg-green-100 text-green-700 border-green-200',
    warning: 'bg-yellow-100 text-yellow-700 border-yellow-200',
  };

  const sizes = {
    sm: 'px-2 py-0.5 text-xs',
    md: 'px-3 py-1 text-sm',
  };

  return (
    <span className={`inline-flex items-center font-medium rounded-full border ${variants[variant]} ${sizes[size]}`}>
      {text}
    </span>
  );
};

export default Badge;