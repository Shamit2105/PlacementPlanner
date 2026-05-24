import React, { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { motion } from 'framer-motion';
import { 
  GraduationCap, 
  Building2, 
  BookOpen, 
  TrendingUp,
  ArrowRight,
  Star,
  Users,
  Target
} from 'lucide-react';
import { companiesApi, experiencesApi } from '../services/api';
import { Company, Experience } from '../types';
import LoadingSpinner from '../components/common/LoadingSpinner';
import CompanyCard from '../components/companies/CompanyCard';
import ExperienceCard from '../components/experiences/ExperienceCard';

const Home: React.FC = () => {
  const [companies, setCompanies] = useState<Company[]>([]);
  const [experiences, setExperiences] = useState<Experience[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const fetchData = async () => {
      try {
        const [companiesData, experiencesData] = await Promise.all([
          companiesApi.getAll(),
          experiencesApi.getAll({ page: 1 }),
        ]);
        setCompanies(companiesData.results);
        setExperiences(experiencesData.results);
      } catch (error) {
        console.error('Error fetching data:', error);
      } finally {
        setLoading(false);
      }
    };
    fetchData();
  }, []);

  const stats = [
    { icon: <Building2 size={24} />, label: 'Companies', value: '5+', color: 'from-ocean-400 to-ocean-600' },
    { icon: <BookOpen size={24} />, label: 'Experiences', value: '50+', color: 'from-primary-400 to-primary-600' },
    { icon: <Users size={24} />, label: 'Users', value: '100+', color: 'from-cyan-400 to-blue-600' },
    { icon: <Target size={24} />, label: 'Questions', value: '200+', color: 'from-teal-400 to-green-600' },
  ];

  if (loading) return <LoadingSpinner />;

  return (
    <div className="min-h-screen bg-gradient-to-br from-gray-50 via-ocean-50/30 to-primary-50/30">
      {/* Hero Section */}
      <motion.div
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
        className="max-w-7xl mx-auto px-4 py-12"
      >
        <div className="text-center mb-12">
          <motion.div
            initial={{ scale: 0 }}
            animate={{ scale: 1 }}
            className="inline-flex items-center justify-center w-20 h-20 rounded-full bg-gradient-to-br from-ocean-500 to-primary-500 mb-6"
          >
            <GraduationCap className="text-white" size={40} />
          </motion.div>
          <h1 className="text-4xl md:text-5xl font-bold bg-gradient-to-r from-ocean-700 to-primary-700 bg-clip-text text-transparent mb-4">
            Ace Your Placements
          </h1>
          <p className="text-lg text-gray-600 max-w-2xl mx-auto">
            Access curated placement experiences, practice DSA questions, and prepare for your dream company
          </p>
        </div>

        {/* Stats Grid */}
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-12">
          {stats.map((stat, index) => (
            <motion.div
              key={stat.label}
              initial={{ opacity: 0, y: 20 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ delay: index * 0.1 }}
              className={`bg-gradient-to-br ${stat.color} rounded-xl p-6 text-white`}
            >
              <div className="flex items-center justify-between">
                <div>
                  <p className="text-3xl font-bold">{stat.value}</p>
                  <p className="text-sm opacity-90">{stat.label}</p>
                </div>
                {stat.icon}
              </div>
            </motion.div>
          ))}
        </div>

        {/* Recent Companies */}
        <section className="mb-12">
          <div className="flex items-center justify-between mb-6">
            <h2 className="text-2xl font-bold text-gray-800 flex items-center">
              <Building2 className="mr-2 text-ocean-600" size={24} />
              Top Companies
            </h2>
            <Link
              to="/companies"
              className="flex items-center text-primary-600 hover:text-primary-700 font-medium"
            >
              View All <ArrowRight size={16} className="ml-1" />
            </Link>
          </div>
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
            {companies.map((company) => (
              <CompanyCard key={company.id} company={company} />
            ))}
          </div>
        </section>

        {/* Recent Experiences */}
        <section>
          <div className="flex items-center justify-between mb-6">
            <h2 className="text-2xl font-bold text-gray-800 flex items-center">
              <BookOpen className="mr-2 text-primary-600" size={24} />
              Recent Experiences
            </h2>
            <Link
              to="/experiences"
              className="flex items-center text-primary-600 hover:text-primary-700 font-medium"
            >
              View All <ArrowRight size={16} className="ml-1" />
            </Link>
          </div>
          <div className="space-y-4">
            {experiences.slice(0, 3).map((experience) => (
              <ExperienceCard key={experience.id} experience={experience} />
            ))}
          </div>
        </section>
      </motion.div>
    </div>
  );
};

export default Home;