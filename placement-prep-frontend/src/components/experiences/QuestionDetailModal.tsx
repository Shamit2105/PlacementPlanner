import React, { useEffect, useState } from 'react';
import { motion } from 'framer-motion';
import { 
  BookOpen, 
  Building2, 
  HelpCircle, 
  Loader2, 
  Tag, 
  Award,
  ExternalLink,
  Code,
  Sparkles
} from 'lucide-react';
import Modal from '../common/Modal';
import { questionsApi } from '../../services/api';
import { QuestionDetail, QuestionListItem } from '../../types';

interface QuestionDetailModalProps {
  isOpen: boolean;
  onClose: () => void;
  questionId: number | null;
  onSelectSimilar?: (id: number) => void;
}

// Markdown parser helper for formatting inline and block markdown elements
export const MarkdownViewer: React.FC<{ text: string }> = ({ text }) => {
  if (!text) return null;

  // Split by code blocks first
  const blocks = text.split(/(```[\s\S]*?```)/g);

  return (
    <div className="space-y-4 text-sm text-slate-700 leading-relaxed">
      {blocks.map((block, idx) => {
        if (block.startsWith('```') && block.endsWith('```')) {
          // Extract language and code
          const codeLines = block.slice(3, -3).trim().split('\n');
          let language = '';
          let code = '';
          if (codeLines[0] && codeLines[0].length < 15 && !codeLines[0].includes(' ') && !codeLines[0].includes('(')) {
            language = codeLines[0];
            code = codeLines.slice(1).join('\n');
          } else {
            code = codeLines.join('\n');
          }
          return (
            <pre key={idx} className="overflow-x-auto rounded-xl bg-slate-950 p-4 font-mono text-xs text-slate-100 border border-slate-800 shadow-inner">
              {language && (
                <div className="mb-2 text-[10px] font-bold uppercase tracking-wider text-slate-400">
                  {language}
                </div>
              )}
              <code>{code}</code>
            </pre>
          );
        }

        // Regular block: split by double newlines into paragraphs or list items
        const paragraphs = block.split(/\n\n+/);
        return paragraphs.map((para, pIdx) => {
          const trimmedPara = para.trim();
          if (!trimmedPara) return null;

          // Check if it is a bullet/numbered list
          if (trimmedPara.startsWith('* ') || trimmedPara.startsWith('- ') || trimmedPara.startsWith('1. ') || trimmedPara.split('\n').every(line => /^\s*([*\-+]|\d+\.)\s+/.test(line))) {
            const listLines = trimmedPara.split('\n');
            const isNumbered = /^\s*\d+\.\s+/.test(listLines[0]);
            
            const listItems = listLines.map((line, lIdx) => {
              const cleanedLine = line.replace(/^\s*([*\-+]|\d+\.)\s+/, '');
              return (
                <li key={lIdx} className="ml-1">
                  {parseInlineMarkdown(cleanedLine)}
                </li>
              );
            });

            if (isNumbered) {
              return <ol key={`${pIdx}-${idx}`} className="list-decimal pl-5 space-y-1.5 my-3 text-slate-700">{listItems}</ol>;
            } else {
              return <ul key={`${pIdx}-${idx}`} className="list-disc pl-5 space-y-1.5 my-3 text-slate-700">{listItems}</ul>;
            }
          }

          // Handle headings: e.g. ### Heading or ## Heading
          if (trimmedPara.startsWith('#')) {
            const level = (trimmedPara.match(/^#+/) || ['#'])[0].length;
            const headingText = trimmedPara.replace(/^#+\s+/, '');
            const parsedText = parseInlineMarkdown(headingText);
            if (level === 1) return <h1 key={`${pIdx}-${idx}`} className="text-xl font-bold text-slate-900 mt-6 mb-2">{parsedText}</h1>;
            if (level === 2) return <h2 key={`${pIdx}-${idx}`} className="text-lg font-bold text-slate-900 mt-5 mb-2">{parsedText}</h2>;
            return <h3 key={`${pIdx}-${idx}`} className="text-base font-bold text-slate-900 mt-4 mb-2">{parsedText}</h3>;
          }

          // Normal paragraph: handle newlines inside it
          const lines = trimmedPara.split('\n');
          return (
            <p key={`${pIdx}-${idx}`} className="my-2.5">
              {lines.map((line, lineIdx) => (
                <React.Fragment key={lineIdx}>
                  {lineIdx > 0 && <br />}
                  {parseInlineMarkdown(line)}
                </React.Fragment>
              ))}
            </p>
          );
        });
      })}
    </div>
  );
};

// Helper function to parse inline formatting: bold, italic, code
function parseInlineMarkdown(text: string): React.ReactNode[] {
  const parts = text.split(/(\*\*.*?\*\*|\*.*?\*|`.*?`)/g);

  return parts.map((part, idx) => {
    if (part.startsWith('**') && part.endsWith('**')) {
      return <strong key={idx} className="font-semibold text-slate-900">{part.slice(2, -2)}</strong>;
    }
    if (part.startsWith('*') && part.endsWith('*')) {
      return <em key={idx} className="italic text-slate-800">{part.slice(1, -1)}</em>;
    }
    if (part.startsWith('`') && part.endsWith('`')) {
      return <code key={idx} className="rounded bg-rose-50 border border-rose-100 px-1 py-0.5 font-mono text-xs text-rose-600">{part.slice(1, -1)}</code>;
    }
    return part;
  });
}

const QuestionDetailModal: React.FC<QuestionDetailModalProps> = ({ isOpen, onClose, questionId, onSelectSimilar }) => {
  const [detail, setDetail] = useState<QuestionDetail | null>(null);
  const [loading, setLoading] = useState(false);
  const [generating, setGenerating] = useState(false);
  const [error, setError] = useState('');
  
  const [similarQuestions, setSimilarQuestions] = useState<QuestionListItem[]>([]);
  const [loadingSimilar, setLoadingSimilar] = useState(false);
  const [errorSimilar, setErrorSimilar] = useState('');

  useEffect(() => {
    if (isOpen && questionId !== null) {
      const fetchDetail = async () => {
        setLoading(true);
        setError('');
        try {
          const res = await questionsApi.getById(questionId);
          setDetail(res);
          
          // Fetch similar questions
          setLoadingSimilar(true);
          setErrorSimilar('');
          try {
            const similarRes = await questionsApi.getSimilar(questionId);
            setSimilarQuestions(similarRes.results);
          } catch (simErr) {
            setErrorSimilar('Failed to load similar questions.');
            console.error(simErr);
          } finally {
            setLoadingSimilar(false);
          }
        } catch (err) {
          setError('Failed to load question details.');
          console.error(err);
        } finally {
          setLoading(false);
        }
      };
      fetchDetail();
    } else {
      setDetail(null);
      setSimilarQuestions([]);
      setErrorSimilar('');
    }
  }, [isOpen, questionId]);

  const handleGenerateAnswer = async () => {
    if (!detail) return;
    setGenerating(true);
    setError('');
    try {
      const res = await questionsApi.generateAnswer(detail.id);
      setDetail(prev => prev ? { ...prev, interview_answer: res.answer } : null);
    } catch (err) {
      setError('Failed to generate answer.');
      console.error(err);
    } finally {
      setGenerating(false);
    }
  };

  return (
    <Modal
      isOpen={isOpen}
      onClose={onClose}
      title="Question Detail"
      size="xl"
    >
      {loading ? (
        <div className="flex flex-col items-center justify-center py-16 space-y-3">
          <Loader2 className="animate-spin text-cyan-600" size={36} />
          <p className="text-sm font-semibold text-slate-600">Retrieving detailed reference answer...</p>
        </div>
      ) : error ? (
        <div className="p-6 text-center text-rose-600 font-medium">
          {error}
        </div>
      ) : detail ? (
        <div className="space-y-6">
          {/* Question Text */}
          <div className="bg-slate-50 border border-slate-200 rounded-xl p-5 shadow-sm">
            <h3 className="text-sm font-semibold text-slate-500 uppercase tracking-wider flex items-center gap-1.5 mb-2">
              <HelpCircle size={16} className="text-slate-400" />
              Interview Question
            </h3>
            <p className="text-base font-semibold text-slate-900 leading-relaxed">
              {detail.interview_question}
            </p>

            {/* Badges / Metadata */}
            <div className="mt-4 flex flex-wrap gap-2">
              <span className="rounded-full bg-cyan-100 border border-cyan-200 px-3 py-1 text-xs font-semibold text-cyan-800">
                {detail.question_type_display}
              </span>
              <span className={`rounded-full px-3 py-1 text-xs font-semibold border ${
                detail.difficulty === 'EASY' 
                  ? 'bg-emerald-50 border-emerald-200 text-emerald-800' 
                  : detail.difficulty === 'MEDIUM' 
                  ? 'bg-amber-50 border-amber-200 text-amber-800' 
                  : 'bg-rose-50 border-rose-200 text-rose-800'
              }`}>
                {detail.difficulty_display}
              </span>
              {detail.source_url && (
                <a
                  href={detail.source_url}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="rounded-full bg-slate-100 hover:bg-slate-200 border border-slate-200 px-3 py-1 text-xs font-semibold text-slate-700 flex items-center gap-1 transition-colors"
                >
                  Source ({detail.source}) <ExternalLink size={12} />
                </a>
              )}
            </div>
          </div>

          {/* Companies & Topics Side-by-Side or Stacked */}
          <div className="grid gap-4 sm:grid-cols-2">
            {/* Companies */}
            <div className="bg-sky-50/40 border border-sky-100/70 rounded-xl p-4">
              <h4 className="text-sm font-bold text-slate-800 flex items-center gap-2 mb-3">
                <Building2 size={16} className="text-sky-600" />
                Featured Companies
              </h4>
              {detail.companies && detail.companies.length > 0 ? (
                <div className="flex flex-wrap gap-2">
                  {detail.companies.map((company) => (
                    <span 
                      key={company.id} 
                      className="px-2.5 py-1 bg-white border border-sky-100 rounded-lg text-xs font-medium text-slate-700 shadow-sm"
                    >
                      {company.name}
                    </span>
                  ))}
                </div>
              ) : (
                <p className="text-xs text-slate-500 italic">No specific company tags assigned.</p>
              )}
            </div>

            {/* Topics */}
            <div className="bg-teal-50/40 border border-teal-100/70 rounded-xl p-4">
              <h4 className="text-sm font-bold text-slate-800 flex items-center gap-2 mb-3">
                <Tag size={16} className="text-teal-600" />
                Topics & Concepts
              </h4>
              {detail.topics && detail.topics.length > 0 ? (
                <div className="flex flex-wrap gap-2">
                  {detail.topics.map((topic) => (
                    <span 
                      key={topic.id} 
                      className="px-2.5 py-1 bg-white border border-teal-100 rounded-lg text-xs font-medium text-slate-700 shadow-sm"
                    >
                      {topic.name}
                    </span>
                  ))}
                </div>
              ) : (
                <p className="text-xs text-slate-500 italic">No specific topics mapped yet.</p>
              )}
            </div>
          </div>

          {/* Reference Answer */}
          <div className="border-t border-slate-100 pt-5">
            <h4 className="text-sm font-bold text-slate-800 flex items-center gap-2 mb-3">
              <BookOpen size={18} className="text-indigo-600" />
              Detailed Model Answer
            </h4>
            {detail.interview_answer ? (
              <div className="bg-white border border-slate-100 rounded-xl p-5 shadow-sm max-h-[40vh] overflow-y-auto">
                <MarkdownViewer text={detail.interview_answer} />
              </div>
            ) : (
              <div className="flex flex-col items-center justify-center p-6 bg-slate-50 border border-slate-200 border-dashed rounded-xl space-y-4">
                <p className="text-sm text-slate-500 italic">No model answer provided yet.</p>
                <button
                  onClick={handleGenerateAnswer}
                  disabled={generating}
                  className="flex items-center gap-2 px-4 py-2 bg-indigo-50 hover:bg-indigo-100 text-indigo-700 border border-indigo-200 rounded-lg text-sm font-semibold transition-colors disabled:opacity-50"
                >
                  {generating ? (
                    <>
                      <Loader2 className="animate-spin" size={16} />
                      Generating...
                    </>
                  ) : (
                    <>
                      <Code size={16} />
                      Generate Reference Answer
                    </>
                  )}
                </button>
              </div>
            )}
          </div>

          {/* Similar Questions Section */}
          <div className="border-t border-slate-100 pt-5">
            <h4 className="text-sm font-bold text-slate-800 flex items-center gap-2 mb-3">
              <Sparkles size={18} className="text-teal-600" />
              Similar Questions
            </h4>
            {loadingSimilar ? (
              <div className="flex flex-col items-center justify-center py-6 space-y-2">
                <Loader2 className="animate-spin text-teal-600" size={24} />
                <p className="text-xs text-slate-500">Finding similar questions...</p>
              </div>
            ) : errorSimilar ? (
              <p className="text-sm text-rose-600">{errorSimilar}</p>
            ) : similarQuestions && similarQuestions.length > 0 ? (
              <div className="grid gap-3 sm:grid-cols-2">
                {similarQuestions.map((sq) => (
                  <div
                    key={sq.id}
                    onClick={() => {
                      if (onSelectSimilar) {
                        onSelectSimilar(sq.id);
                      }
                    }}
                    className={`rounded-xl border border-teal-100 bg-teal-50/30 p-3 hover:border-teal-300 hover:shadow-sm transition-all duration-200 ${onSelectSimilar ? 'cursor-pointer' : ''}`}
                  >
                    <p className="text-sm font-medium text-slate-900 line-clamp-2 mb-2">
                      {sq.interview_question}
                    </p>
                    <div className="flex items-center gap-2 text-[10px]">
                      <span className="rounded bg-teal-100 px-1.5 py-0.5 font-semibold text-teal-800">
                        {sq.question_type_display}
                      </span>
                      {sq.similarity_score !== undefined && (
                        <span className="text-teal-700 font-medium">
                          Sim: {sq.similarity_score.toFixed(3)}
                        </span>
                      )}
                    </div>
                  </div>
                ))}
              </div>
            ) : (
              <p className="text-sm text-slate-500 italic">No similar questions found.</p>
            )}
          </div>
        </div>
      ) : null}
    </Modal>
  );
};

export default QuestionDetailModal;
