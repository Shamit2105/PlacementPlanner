import React, { useState } from 'react';
import { motion } from 'framer-motion';
import { Calendar, ExternalLink, Code, Brain, Target, Eye, ChevronDown, ChevronUp } from 'lucide-react';
import Badge from '../common/Badge';
import QuestionModal from './QuestionModal';
import { Experience } from '../../types';

interface ExperienceCardProps {
  experience: Experience;
}

const ExperienceCard: React.FC<ExperienceCardProps> = ({ experience }) => {
  const [isModalOpen, setIsModalOpen] = useState(false);
  const [showAllQuestions, setShowAllQuestions] = useState(false);

  const displayQuestions = showAllQuestions 
    ? experience.extracted_dsa_questions 
    : experience.extracted_dsa_questions.slice(0, 3);

  return (
    <>
      <motion.div
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
        className="bg-white rounded-xl border border-ocean-100 p-6 hover:shadow-lg transition-all duration-300"
      >
        {/* Header */}
        <div className="flex items-start justify-between mb-4">
          <div>
            <h3 className="text-lg font-semibold text-gray-800">{experience.company_name}</h3>
            <div className="flex items-center space-x-2 mt-1">
              <Badge 
                text={experience.round_type_display} 
                variant={experience.round_type === 'OA' ? 'ocean' : 'primary'} 
              />
              <Badge text={experience.target_role} variant="success" />
            </div>
          </div>
          <div className="text-right">
            <span className="text-xs text-gray-500 flex items-center">
              <Calendar size={14} className="mr-1" />
              {new Date(experience.created_at).toLocaleDateString()}
            </span>
            <a
              href={experience.source_url}
              target="_blank"
              rel="noopener noreferrer"
              className="text-xs text-ocean-600 hover:text-ocean-700 flex items-center mt-1"
            >
              <ExternalLink size={14} className="mr-1" />
              {experience.source_platform}
            </a>
          </div>
        </div>

        {/* DSA Questions */}
        {experience.extracted_dsa_questions.length > 0 && (
          <div className="mt-4">
            <h4 className="text-sm font-semibold text-gray-700 flex items-center mb-3">
              <Code size={16} className="mr-2 text-primary-500" />
              DSA Questions ({experience.extracted_dsa_questions.length})
            </h4>
            <div className="space-y-2">
              {displayQuestions.map((question, index) => (
                <div
                  key={index}
                  className="p-3 bg-gradient-to-r from-primary-50/50 to-ocean-50/50 rounded-lg border border-primary-100/50 hover:border-primary-300 transition-all"
                >
                  <p className="text-sm text-gray-700 leading-relaxed">
                    <span className="font-semibold text-primary-600 mr-1">Q{index + 1}.</span>
                    {question}
                  </p>
                </div>
              ))}
            </div>
            
            {/* Show More/Less Button */}
            {experience.extracted_dsa_questions.length > 3 && (
              <div className="mt-3 flex space-x-2">
                <button
                  onClick={() => setShowAllQuestions(!showAllQuestions)}
                  className="text-xs text-primary-600 hover:text-primary-700 font-medium flex items-center transition-colors"
                >
                  {showAllQuestions ? (
                    <>
                      <ChevronUp size={14} className="mr-1" />
                      Show Less
                    </>
                  ) : (
                    <>
                      <ChevronDown size={14} className="mr-1" />
                      Show {experience.extracted_dsa_questions.length - 3} More Questions
                    </>
                  )}
                </button>
                
                <button
                  onClick={() => setIsModalOpen(true)}
                  className="text-xs text-ocean-600 hover:text-ocean-700 font-medium flex items-center ml-4 transition-colors"
                >
                  <Eye size={14} className="mr-1" />
                  View All in Detail
                </button>
              </div>
            )}
          </div>
        )}

        {/* Core Topics */}
        {experience.extracted_core_topics.length > 0 && (
          <div className="mt-4">
            <h4 className="text-sm font-semibold text-gray-700 flex items-center mb-2">
              <Brain size={16} className="mr-2 text-ocean-500" />
              Core Topics
            </h4>
            <div className="flex flex-wrap gap-2">
              {experience.extracted_core_topics.map((topic, index) => (
                <span
                  key={index}
                  className="px-2.5 py-1 bg-ocean-50 text-ocean-700 rounded-md text-xs font-medium border border-ocean-200 hover:bg-ocean-100 transition-colors"
                >
                  {topic}
                </span>
              ))}
            </div>
          </div>
        )}

        {/* No Questions Message */}
        {experience.extracted_dsa_questions.length === 0 && experience.extracted_core_topics.length === 0 && (
          <div className="mt-4 p-4 bg-gray-50 rounded-lg text-center">
            <p className="text-sm text-gray-500">
              No questions or topics extracted yet. Check the source for more details.
            </p>
            <a
              href={experience.source_url}
              target="_blank"
              rel="noopener noreferrer"
              className="text-xs text-ocean-600 hover:text-ocean-700 mt-2 inline-flex items-center"
            >
              <ExternalLink size={12} className="mr-1" />
              View Original Post
            </a>
          </div>
        )}
      </motion.div>

      {/* Question Detail Modal */}
      <QuestionModal
        isOpen={isModalOpen}
        onClose={() => setIsModalOpen(false)}
        experience={experience}
      />
    </>
  );
};

export default ExperienceCard;