import React, { useEffect, useState } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { motion } from 'framer-motion';
import { 
  Building2, 
  ArrowLeft, 
  Filter,
  BookOpen,
  Code,
  Brain,
  Users,
  TrendingUp,
  Calendar,
  ExternalLink,
  ChevronDown,
  ChevronUp,
  Search,
  SlidersHorizontal
} from 'lucide-react';
import { companiesApi, experiencesApi } from '../services/api';
import { Company, Experience } from '../types';
import ExperienceCard from '../components/experiences/ExperienceCard';
import LoadingSpinner from '../components/common/LoadingSpinner';
import Badge from '../components/common/Badge';

const CompanyDetail: React.FC = () => {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  
  const [company, setCompany] = useState<Company | null>(null);
  const [experiences, setExperiences] = useState<Experience[]>([]);
  const [loading, setLoading] = useState(true);
  const [currentPage, setCurrentPage] = useState(1);
  const [totalCount, setTotalCount] = useState(0);
  const [activeFilter, setActiveFilter] = useState<'ALL' | 'OA' | 'INTERVIEW'>('ALL');
  const [searchTerm, setSearchTerm] = useState('');

  useEffect(() => {
    if (id) {
      fetchCompanyData();
    }
  }, [id, currentPage, activeFilter]);

  const fetchCompanyData = async () => {
    if (!id) return;
    
    setLoading(true);
    try {
      const companyId = parseInt(id);
      
      // Fetch company details and experiences in parallel
      const [companyData, experiencesData] = await Promise.all([
        companiesApi.getById(companyId),
        companiesApi.getExperiences(
          companyId, 
          currentPage, 
          activeFilter !== 'ALL' ? activeFilter as 'OA' | 'INTERVIEW' : undefined
        ),
      ]);
      
      setCompany(companyData);
      setExperiences(experiencesData.results);
      setTotalCount(experiencesData.count);
    } catch (error) {
      console.error('Error fetching company data:', error);
    } finally {
      setLoading(false);
    }
  };

  const handleFilterChange = (filter: 'ALL' | 'OA' | 'INTERVIEW') => {
    setActiveFilter(filter);
    setCurrentPage(1); // Reset to first page when filter changes
  };

  const filteredExperiences = experiences.filter(exp => 
    searchTerm === '' || 
    exp.target_role.toLowerCase().includes(searchTerm.toLowerCase()) ||
    exp.extracted_dsa_questions.some(q => q.toLowerCase().includes(searchTerm.toLowerCase()))
  );

  // Calculate stats
  const oaCount = experiences.filter(e => e.round_type === 'OA').length;
  const interviewCount = experiences.filter(e => e.round_type === 'INTERVIEW').length;
  const totalQuestions = experiences.reduce((sum, exp) => sum + exp.extracted_dsa_questions.length, 0);

  if (loading && !company) return <LoadingSpinner />;
  if (!company) return <div>Company not found</div>;

  return (
    <div className="min-h-screen bg-gradient-to-br from-gray-50 via-ocean-50/30 to-primary-50/30">
      {/* Header Section */}
      <div className="bg-white border-b border-ocean-100">
        <div className="max-w-7xl mx-auto px-4 py-8">
          {/* Back Button */}
          <button
            onClick={() => navigate('/companies')}
            className="flex items-center text-gray-600 hover:text-ocean-700 mb-6 transition-colors"
          >
            <ArrowLeft size={20} className="mr-2" />
            Back to Companies
          </button>

          {/* Company Hero */}
          <motion.div
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            className="flex flex-col md:flex-row items-start md:items-center justify-between"
          >
            <div className="flex items-center space-x-4 mb-4 md:mb-0">
              <div className="w-20 h-20 rounded-2xl bg-gradient-to-br from-ocean-400 to-primary-500 flex items-center justify-center shadow-lg">
                <span className="text-white text-3xl font-bold">
                  {company.name.charAt(0)}
                </span>
              </div>
              <div>
                <h1 className="text-3xl font-bold text-gray-800">{company.name}</h1>
                <p className="text-gray-600 mt-1">{company.slug}</p>
                <div className="flex items-center space-x-4 mt-2">
                  <Badge text={`${totalCount} Experiences`} variant="primary" size="md" />
                  <Badge text={`${totalQuestions} Questions`} variant="ocean" size="md" />
                </div>
              </div>
            </div>
          </motion.div>

          {/* Stats Cards */}
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mt-8">
            <motion.div
              initial={{ opacity: 0, y: 20 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ delay: 0.1 }}
              className="bg-gradient-to-br from-ocean-50 to-ocean-100 rounded-xl p-4 border border-ocean-200"
            >
              <BookOpen className="text-ocean-600 mb-2" size={24} />
              <p className="text-2xl font-bold text-ocean-700">{totalCount}</p>
              <p className="text-sm text-ocean-600">Total Experiences</p>
            </motion.div>

            <motion.div
              initial={{ opacity: 0, y: 20 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ delay: 0.2 }}
              className="bg-gradient-to-br from-primary-50 to-primary-100 rounded-xl p-4 border border-primary-200"
            >
              <Code className="text-primary-600 mb-2" size={24} />
              <p className="text-2xl font-bold text-primary-700">{totalQuestions}</p>
              <p className="text-sm text-primary-600">DSA Questions</p>
            </motion.div>

            <motion.div
              initial={{ opacity: 0, y: 20 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ delay: 0.3 }}
              className="bg-gradient-to-br from-green-50 to-green-100 rounded-xl p-4 border border-green-200"
            >
              <TrendingUp className="text-green-600 mb-2" size={24} />
              <p className="text-2xl font-bold text-green-700">{oaCount}</p>
              <p className="text-sm text-green-600">Online Assessments</p>
            </motion.div>

            <motion.div
              initial={{ opacity: 0, y: 20 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ delay: 0.4 }}
              className="bg-gradient-to-br from-purple-50 to-purple-100 rounded-xl p-4 border border-purple-200"
            >
              <Users className="text-purple-600 mb-2" size={24} />
              <p className="text-2xl font-bold text-purple-700">{interviewCount}</p>
              <p className="text-sm text-purple-600">Interviews</p>
            </motion.div>
          </div>
        </div>
      </div>

      {/* Content Section */}
      <div className="max-w-7xl mx-auto px-4 py-8">
        {/* Filters and Search */}
        <div className="bg-white rounded-xl border border-ocean-100 p-4 mb-6">
          <div className="flex flex-col md:flex-row md:items-center justify-between space-y-4 md:space-y-0">
            {/* Round Type Filters */}
            <div className="flex flex-wrap gap-2">
              <button
                onClick={() => handleFilterChange('ALL')}
                className={`px-4 py-2 rounded-lg text-sm font-medium transition-all ${
                  activeFilter === 'ALL'
                    ? 'bg-gradient-to-r from-ocean-500 to-primary-500 text-white shadow-sm'
                    : 'bg-gray-50 text-gray-700 hover:bg-gray-100 border border-gray-200'
                }`}
              >
                All Experiences
              </button>
              <button
                onClick={() => handleFilterChange('OA')}
                className={`px-4 py-2 rounded-lg text-sm font-medium transition-all ${
                  activeFilter === 'OA'
                    ? 'bg-ocean-500 text-white shadow-sm'
                    : 'bg-gray-50 text-gray-700 hover:bg-gray-100 border border-gray-200'
                }`}
              >
                Online Assessment
              </button>
              <button
                onClick={() => handleFilterChange('INTERVIEW')}
                className={`px-4 py-2 rounded-lg text-sm font-medium transition-all ${
                  activeFilter === 'INTERVIEW'
                    ? 'bg-primary-500 text-white shadow-sm'
                    : 'bg-gray-50 text-gray-700 hover:bg-gray-100 border border-gray-200'
                }`}
              >
                Interviews
              </button>
            </div>

            {/* Search */}
            <div className="relative max-w-xs w-full">
              <Search className="absolute left-3 top-1/2 transform -translate-y-1/2 text-gray-400" size={18} />
              <input
                type="text"
                placeholder="Search experiences..."
                value={searchTerm}
                onChange={(e) => setSearchTerm(e.target.value)}
                className="w-full pl-10 pr-4 py-2 bg-gray-50 border border-ocean-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-primary-500 focus:border-transparent transition-all text-sm"
              />
            </div>
          </div>
        </div>

        {/* Experiences List */}
        {loading ? (
          <LoadingSpinner />
        ) : filteredExperiences.length > 0 ? (
          <div className="space-y-4">
            {filteredExperiences.map((experience, index) => (
              <motion.div
                key={experience.id}
                initial={{ opacity: 0, y: 20 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ delay: index * 0.1 }}
              >
                <ExperienceCard experience={experience} />
              </motion.div>
            ))}
          </div>
        ) : (
          <motion.div
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            className="text-center py-12"
          >
            <BookOpen className="mx-auto text-gray-300 mb-4" size={48} />
            <h3 className="text-lg font-semibold text-gray-600 mb-2">No experiences found</h3>
            <p className="text-gray-500">
              {searchTerm 
                ? 'No experiences match your search criteria. Try different keywords.'
                : `No ${activeFilter !== 'ALL' ? activeFilter + ' ' : ''}experiences available for ${company.name} yet.`}
            </p>
          </motion.div>
        )}

        {/* Pagination */}
        {totalCount > 5 && (
          <div className="flex justify-center mt-8 space-x-2">
            <button
              onClick={() => setCurrentPage(p => Math.max(1, p - 1))}
              disabled={currentPage === 1}
              className="px-4 py-2 bg-white border border-ocean-200 rounded-lg disabled:opacity-50 disabled:cursor-not-allowed hover:bg-ocean-50 transition-colors text-sm font-medium"
            >
              Previous
            </button>
            
            {/* Page Numbers */}
            {Array.from({ length: Math.min(5, Math.ceil(totalCount / 5)) }, (_, i) => i + 1).map(page => (
              <button
                key={page}
                onClick={() => setCurrentPage(page)}
                className={`px-4 py-2 rounded-lg text-sm font-medium transition-all ${
                  currentPage === page
                    ? 'bg-primary-500 text-white'
                    : 'bg-white border border-ocean-200 hover:bg-ocean-50 text-gray-700'
                }`}
              >
                {page}
              </button>
            ))}
            
            <button
              onClick={() => setCurrentPage(p => p + 1)}
              disabled={currentPage * 5 >= totalCount}
              className="px-4 py-2 bg-white border border-ocean-200 rounded-lg disabled:opacity-50 disabled:cursor-not-allowed hover:bg-ocean-50 transition-colors text-sm font-medium"
            >
              Next
            </button>
          </div>
        )}
      </div>
    </div>
  );
};

export default CompanyDetail;