import React, { useEffect, useState } from 'react';
import { motion } from 'framer-motion';
import { Search, BookOpen, Filter } from 'lucide-react';
import { experiencesApi } from '../services/api';
import { Experience, ExperienceFilters } from '../types';
import ExperienceCard from '../components/experiences/ExperienceCard';
import LoadingSpinner from '../components/common/LoadingSpinner';

const Experiences: React.FC = () => {
  const [experiences, setExperiences] = useState<Experience[]>([]);
  const [loading, setLoading] = useState(true);
  const [filters, setFilters] = useState<ExperienceFilters>({});
  const [currentPage, setCurrentPage] = useState(1);
  const [totalCount, setTotalCount] = useState(0);

  useEffect(() => {
    const fetchExperiences = async () => {
      setLoading(true);
      try {
        const data = await experiencesApi.getAll({ ...filters, page: currentPage });
        setExperiences(data.results);
        setTotalCount(data.count);
      } catch (error) {
        console.error('Error fetching experiences:', error);
      } finally {
        setLoading(false);
      }
    };
    fetchExperiences();
  }, [filters, currentPage]);

  return (
    <div className="min-h-screen bg-gradient-to-br from-gray-50 via-ocean-50/30 to-primary-50/30 p-6">
      <div className="max-w-7xl mx-auto">
        {/* Header */}
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          className="mb-8"
        >
          <h1 className="text-3xl font-bold text-gray-800 flex items-center mb-2">
            <BookOpen className="mr-3 text-primary-600" size={32} />
            Placement Experiences
          </h1>
          <p className="text-gray-600">Learn from real interview experiences and DSA questions</p>
        </motion.div>

        {/* Filters */}
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          className="mb-6 flex flex-wrap gap-3"
        >
          <button
            onClick={() => setFilters({})}
            className={`px-4 py-2 rounded-lg font-medium transition-all ${
              !filters.round_type
                ? 'bg-primary-500 text-white'
                : 'bg-white text-gray-700 border border-ocean-200 hover:bg-ocean-50'
            }`}
          >
            All
          </button>
          <button
            onClick={() => setFilters({ round_type: 'OA' })}
            className={`px-4 py-2 rounded-lg font-medium transition-all ${
              filters.round_type === 'OA'
                ? 'bg-ocean-500 text-white'
                : 'bg-white text-gray-700 border border-ocean-200 hover:bg-ocean-50'
            }`}
          >
            Online Assessment
          </button>
          <button
            onClick={() => setFilters({ round_type: 'INTERVIEW' })}
            className={`px-4 py-2 rounded-lg font-medium transition-all ${
              filters.round_type === 'INTERVIEW'
                ? 'bg-primary-500 text-white'
                : 'bg-white text-gray-700 border border-ocean-200 hover:bg-ocean-50'
            }`}
          >
            Interviews
          </button>
        </motion.div>

        {/* Experiences List */}
        {loading ? (
          <LoadingSpinner />
        ) : (
          <>
            <div className="space-y-4">
              {experiences.map((experience, index) => (
                <motion.div
                  key={experience.id}
                  initial={{ opacity: 0, x: -20 }}
                  animate={{ opacity: 1, x: 0 }}
                  transition={{ delay: index * 0.1 }}
                >
                  <ExperienceCard experience={experience} />
                </motion.div>
              ))}
            </div>

            {/* Pagination */}
            {totalCount > 5 && (
              <div className="flex justify-center mt-8 space-x-2">
                <button
                  onClick={() => setCurrentPage(p => Math.max(1, p - 1))}
                  disabled={currentPage === 1}
                  className="px-4 py-2 bg-white border border-ocean-200 rounded-lg disabled:opacity-50 hover:bg-ocean-50 transition-colors"
                >
                  Previous
                </button>
                <span className="px-4 py-2 bg-primary-100 text-primary-700 rounded-lg font-medium">
                  {currentPage}
                </span>
                <button
                  onClick={() => setCurrentPage(p => p + 1)}
                  disabled={currentPage * 5 >= totalCount}
                  className="px-4 py-2 bg-white border border-ocean-200 rounded-lg disabled:opacity-50 hover:bg-ocean-50 transition-colors"
                >
                  Next
                </button>
              </div>
            )}
          </>
        )}
      </div>
    </div>
  );
};

export default Experiences;