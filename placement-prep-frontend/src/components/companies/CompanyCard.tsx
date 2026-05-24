import React from 'react';
import { useNavigate } from 'react-router-dom';
import { Building2, ArrowRight, TrendingUp, Code } from 'lucide-react';
import Card from '../common/Card';
import { Company } from '../../types';

interface CompanyCardProps {
  company: Company;
}

const CompanyCard: React.FC<CompanyCardProps> = ({ company }) => {
  const navigate = useNavigate();

  const getCompanyColor = (name: string) => {
    const colors = [
      'from-ocean-400 to-ocean-600',
      'from-primary-400 to-primary-600',
      'from-cyan-400 to-blue-600',
      'from-teal-400 to-green-600',
    ];
    const index = name.length % colors.length;
    return colors[index];
  };

  return (
    <Card onClick={() => navigate(`/companies/${company.id}`)}>
      <div className="flex items-start justify-between">
        <div className="flex items-center space-x-4">
          <div className={`w-12 h-12 rounded-lg bg-gradient-to-br ${getCompanyColor(company.name)} flex items-center justify-center shadow-md`}>
            <span className="text-white font-bold text-lg">
              {company.name.charAt(0)}
            </span>
          </div>
          <div>
            <h3 className="text-lg font-semibold text-gray-800">{company.name}</h3>
            <p className="text-sm text-gray-500 mt-1">{company.slug}</p>
          </div>
        </div>
        <ArrowRight className="text-gray-400 group-hover:text-primary-500 transition-colors" size={20} />
      </div>
      
      <div className="mt-4 flex items-center justify-between">
        <div className="flex items-center space-x-2 text-sm text-gray-500">
          <Building2 size={16} />
          <span>View experiences</span>
        </div>
        <div className="flex space-x-2">
          <span className="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium bg-ocean-50 text-ocean-700 border border-ocean-200">
            <TrendingUp size={12} className="mr-1" />
            Active
          </span>
          <span className="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium bg-primary-50 text-primary-700 border border-primary-200">
            <Code size={12} className="mr-1" />
            Questions
          </span>
        </div>
      </div>
    </Card>
  );
};

export default CompanyCard;