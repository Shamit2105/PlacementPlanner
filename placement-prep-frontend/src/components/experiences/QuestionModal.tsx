import React from 'react';
import { motion } from 'framer-motion';
import { 
  Code, 
  ExternalLink, 
  Copy, 
  CheckCircle2,
  GraduationCap,
  BookOpen,
  Lightbulb,
  ChevronRight
} from 'lucide-react';
import Modal from '../common/Modal';
import Badge from '../common/Badge';
import { Experience } from '../../types';

interface QuestionModalProps {
  isOpen: boolean;
  onClose: () => void;
  experience: Experience;
}

const QuestionModal: React.FC<QuestionModalProps> = ({ isOpen, onClose, experience }) => {
  const [copiedIndex, setCopiedIndex] = React.useState<number | null>(null);

  const handleCopyQuestion = async (question: string, index: number) => {
    await navigator.clipboard.writeText(question);
    setCopiedIndex(index);
    setTimeout(() => setCopiedIndex(null), 2000);
  };

  return (
    <Modal
      isOpen={isOpen}
      onClose={onClose}
      title="DSA Questions"
      size="xl"
    >
      <div className="space-y-6">
        {/* Company Info */}
        <div className="bg-gradient-to-r from-ocean-50 to-primary-50 rounded-xl p-4 border border-ocean-200">
          <div className="flex items-center justify-between">
            <div>
              <h3 className="text-lg font-semibold text-gray-800">
                {experience.company_name}
              </h3>
              <div className="flex items-center space-x-2 mt-2">
                <Badge 
                  text={experience.round_type_display} 
                  variant={experience.round_type === 'OA' ? 'ocean' : 'primary'} 
                />
                <Badge text={experience.target_role} variant="success" />
              </div>
            </div>
            <a
              href={experience.source_url}
              target="_blank"
              rel="noopener noreferrer"
              className="flex items-center text-sm text-ocean-600 hover:text-ocean-700 transition-colors"
            >
              <ExternalLink size={16} className="mr-1" />
              View Source
            </a>
          </div>
        </div>

        {/* Questions List */}
        <div>
          <h3 className="text-lg font-semibold text-gray-800 flex items-center mb-4">
            <Code className="mr-2 text-primary-500" size={20} />
            All Questions ({experience.extracted_dsa_questions.length})
          </h3>
          
          <div className="space-y-4">
            {experience.extracted_dsa_questions.map((question, index) => (
              <motion.div
                key={index}
                initial={{ opacity: 0, x: -20 }}
                animate={{ opacity: 1, x: 0 }}
                transition={{ delay: index * 0.05 }}
                className="group relative"
              >
                <div className="p-4 bg-gradient-to-r from-primary-50/30 to-ocean-50/30 rounded-xl border border-primary-100/50 hover:border-primary-300 hover:shadow-md transition-all">
                  <div className="flex items-start space-x-3">
                    {/* Question Number */}
                    <div className="flex-shrink-0 w-8 h-8 rounded-full bg-gradient-to-br from-ocean-400 to-primary-500 flex items-center justify-center">
                      <span className="text-white text-sm font-semibold">
                        {index + 1}
                      </span>
                    </div>
                    
                    {/* Question Content */}
                    <div className="flex-1 min-w-0">
                      <p className="text-gray-800 leading-relaxed">
                        {question}
                      </p>
                      
                      {/* Question Tags */}
                      <div className="flex flex-wrap gap-2 mt-3">
                        {/* Auto-detect difficulty based on keywords */}
                        {question.toLowerCase().includes('time complexity') && (
                          <span className="inline-flex items-center px-2 py-0.5 rounded-md text-xs font-medium bg-yellow-50 text-yellow-700 border border-yellow-200">
                            <Lightbulb size={12} className="mr-1" />
                            Complexity Analysis
                          </span>
                        )}
                        {question.toLowerCase().includes('tree') && (
                          <span className="inline-flex items-center px-2 py-0.5 rounded-md text-xs font-medium bg-green-50 text-green-700 border border-green-200">
                            Tree
                          </span>
                        )}
                        {question.toLowerCase().includes('dp') || question.toLowerCase().includes('dynamic') && (
                          <span className="inline-flex items-center px-2 py-0.5 rounded-md text-xs font-medium bg-purple-50 text-purple-700 border border-purple-200">
                            Dynamic Programming
                          </span>
                        )}
                        {question.toLowerCase().includes('graph') && (
                          <span className="inline-flex items-center px-2 py-0.5 rounded-md text-xs font-medium bg-blue-50 text-blue-700 border border-blue-200">
                            Graph
                          </span>
                        )}
                        {question.toLowerCase().includes('array') || question.toLowerCase().includes('sum') && (
                          <span className="inline-flex items-center px-2 py-0.5 rounded-md text-xs font-medium bg-orange-50 text-orange-700 border border-orange-200">
                            Array
                          </span>
                        )}
                      </div>
                    </div>
                    
                    {/* Copy Button */}
                    <button
                      onClick={() => handleCopyQuestion(question, index)}
                      className="flex-shrink-0 p-2 rounded-lg hover:bg-white/80 transition-colors opacity-0 group-hover:opacity-100"
                      title="Copy question"
                    >
                      {copiedIndex === index ? (
                        <CheckCircle2 size={18} className="text-green-500" />
                      ) : (
                        <Copy size={18} className="text-gray-400" />
                      )}
                    </button>
                  </div>
                </div>
              </motion.div>
            ))}
          </div>
        </div>

        {/* Core Topics Section */}
        {experience.extracted_core_topics.length > 0 && (
          <div className="pt-4 border-t border-gray-200">
            <h3 className="text-lg font-semibold text-gray-800 flex items-center mb-3">
              <BookOpen className="mr-2 text-ocean-500" size={20} />
              Core Topics Covered
            </h3>
            <div className="flex flex-wrap gap-2">
              {experience.extracted_core_topics.map((topic, index) => (
                <span
                  key={index}
                  className="px-3 py-1.5 bg-ocean-50 text-ocean-700 rounded-lg text-sm font-medium border border-ocean-200 hover:bg-ocean-100 transition-colors"
                >
                  {topic}
                </span>
              ))}
            </div>
          </div>
        )}

        {/* Study Tips */}
        <div className="bg-gradient-to-r from-yellow-50 to-amber-50 rounded-xl p-4 border border-yellow-200">
          <h3 className="text-sm font-semibold text-yellow-800 flex items-center mb-2">
            <GraduationCap size={16} className="mr-2" />
            Study Tips
          </h3>
          <ul className="space-y-2">
            <li className="flex items-start text-sm text-yellow-700">
              <ChevronRight size={14} className="mr-2 mt-0.5 flex-shrink-0" />
              Practice these questions on LeetCode or similar platforms
            </li>
            <li className="flex items-start text-sm text-yellow-700">
              <ChevronRight size={14} className="mr-2 mt-0.5 flex-shrink-0" />
              Focus on understanding the patterns rather than memorizing solutions
            </li>
            <li className="flex items-start text-sm text-yellow-700">
              <ChevronRight size={14} className="mr-2 mt-0.5 flex-shrink-0" />
              Time yourself while solving to simulate interview conditions
            </li>
          </ul>
        </div>
      </div>
    </Modal>
  );
};

export default QuestionModal;