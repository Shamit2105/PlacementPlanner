import React, { useEffect, useMemo, useState } from 'react';
import { Search, Sparkles } from 'lucide-react';
import LoadingSpinner from '../components/common/LoadingSpinner';
import { companiesApi, questionsApi } from '../services/api';
import { Company, QuestionListItem, QuestionType } from '../types';
import QuestionDetailModal from '../components/experiences/QuestionDetailModal';

const QUESTION_TYPES: QuestionType[] = ['DSA_CODING', 'DSA_THEORY', 'OS', 'DBMS', 'NETWORKS', 'SYSTEM_DESIGN'];

const Experiences: React.FC = () => {
  const [questions, setQuestions] = useState<QuestionListItem[]>([]);
  const [companies, setCompanies] = useState<Company[]>([]);
  const [loading, setLoading] = useState(true);
  const [page, setPage] = useState(1);
  const [count, setCount] = useState(0);
  const [selectedType, setSelectedType] = useState<QuestionType | ''>('');
  const [selectedCompany, setSelectedCompany] = useState('');
  const [searchInput, setSearchInput] = useState('');
  const [semanticQuery, setSemanticQuery] = useState('');
  const [semanticResults, setSemanticResults] = useState<QuestionListItem[]>([]);
  const [semanticLoading, setSemanticLoading] = useState(false);
  const [semanticError, setSemanticError] = useState('');
  const [selectedQuestionId, setSelectedQuestionId] = useState<number | null>(null);
  const [isDetailModalOpen, setIsDetailModalOpen] = useState(false);

  useEffect(() => {
    const loadCompanies = async () => {
      const response = await companiesApi.list({ page: 1 });
      setCompanies(response.results);
    };

    loadCompanies();
  }, []);

  useEffect(() => {
    const loadQuestions = async () => {
      setLoading(true);
      try {
        const response = await questionsApi.list({
          page,
          question_type: selectedType || undefined,
          company: selectedCompany || undefined,
          search: searchInput || undefined,
        });
        setQuestions(response.results);
        setCount(response.count);
      } finally {
        setLoading(false);
      }
    };

    loadQuestions();
  }, [page, selectedType, selectedCompany, searchInput]);

  const canNext = useMemo(() => page * 10 < count, [page, count]);

  const runSemanticSearch = async () => {
    if (semanticQuery.trim().length < 3) {
      setSemanticError('Semantic search needs at least 3 characters.');
      return;
    }

    setSemanticLoading(true);
    setSemanticError('');
    try {
      const response = await questionsApi.semanticSearch({
        query: semanticQuery,
        company_slug: selectedCompany || undefined,
        question_type: selectedType || undefined,
        limit: 8,
      });
      setSemanticResults(response.results);
    } catch {
      setSemanticError('Could not run semantic search. Check your API key and backend logs.');
    } finally {
      setSemanticLoading(false);
    }
  };

  const handleDeleteSuccess = (deletedId: number) => {
    setQuestions((prev) => prev.filter((q) => q.id !== deletedId));
    setSemanticResults((prev) => prev.filter((q) => q.id !== deletedId));
    setCount((prev) => Math.max(0, prev - 1));
  };

  return (
    <div className="space-y-6">
      <header className="surface p-6 sm:p-8">
        <h1 className="text-3xl text-slate-900 sm:text-4xl">Question Bank</h1>
        <p className="mt-2 text-slate-600">This page maps to /api/questions list filters and semantic-search endpoints.</p>
        <div className="mt-5 grid gap-3 md:grid-cols-4">
          <label className="relative md:col-span-2">
            <Search size={16} className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-400" />
            <input
              value={searchInput}
              onChange={(event) => {
                setPage(1);
                setSearchInput(event.target.value);
              }}
              placeholder="Keyword search on interview question"
              className="w-full rounded-xl border border-cyan-200 bg-white py-2.5 pl-9 pr-3 text-sm outline-none ring-cyan-200 focus:ring"
            />
          </label>

          <select
            value={selectedType}
            onChange={(event) => {
              setPage(1);
              setSelectedType(event.target.value as QuestionType | '');
            }}
            className="rounded-xl border border-cyan-200 bg-white px-3 py-2.5 text-sm outline-none ring-cyan-200 focus:ring"
          >
            <option value="">All types</option>
            {QUESTION_TYPES.map((type) => (
              <option key={type} value={type}>
                {type}
              </option>
            ))}
          </select>

          <select
            value={selectedCompany}
            onChange={(event) => {
              setPage(1);
              setSelectedCompany(event.target.value);
            }}
            className="rounded-xl border border-cyan-200 bg-white px-3 py-2.5 text-sm outline-none ring-cyan-200 focus:ring"
          >
            <option value="">All companies</option>
            {companies.map((company) => (
              <option key={company.id} value={company.slug}>
                {company.name}
              </option>
            ))}
          </select>
        </div>
      </header>

      <section className="surface p-6">
        <div className="mb-4 flex flex-wrap items-center justify-between gap-2">
          <h2 className="text-xl text-slate-900">Filtered Results</h2>
          <span className="rounded-full bg-slate-100 px-3 py-1 text-xs font-semibold text-slate-700">{count} total</span>
        </div>
        {loading ? (
          <LoadingSpinner label="Querying question bank" />
        ) : (
          <div className="space-y-3">
            {questions.map((question) => (
              <article
                key={question.id}
                onClick={() => {
                  setSelectedQuestionId(question.id);
                  setIsDetailModalOpen(true);
                }}
                className="rounded-xl border border-cyan-200 bg-white p-4 hover:border-cyan-300 hover:shadow-md cursor-pointer transition-all duration-200"
              >
                <div className="flex flex-wrap items-center gap-2 text-xs">
                  <span className="rounded-full bg-cyan-100 px-2 py-1 font-semibold text-cyan-800">
                    {question.question_type_display}
                  </span>
                  <span className="rounded-full bg-sky-100 px-2 py-1 font-semibold text-sky-800">
                    {question.difficulty_display}
                  </span>
                  <span className="rounded-full bg-slate-100 px-2 py-1 font-semibold text-slate-700">{question.status}</span>
                </div>
                <p className="mt-3 text-sm font-semibold text-slate-900">{question.interview_question}</p>
                <p className="mt-2 line-clamp-2 text-sm text-slate-600">{question.answer_preview}</p>
              </article>
            ))}
          </div>
        )}
        <div className="mt-4 flex items-center justify-end gap-2">
          <button
            type="button"
            disabled={page <= 1}
            onClick={() => setPage((prev) => Math.max(1, prev - 1))}
            className="rounded-lg border border-cyan-200 bg-white px-3 py-2 text-sm font-semibold text-slate-700 disabled:cursor-not-allowed disabled:opacity-40"
          >
            Prev
          </button>
          <span className="rounded-lg bg-slate-100 px-3 py-2 text-sm font-semibold text-slate-700">Page {page}</span>
          <button
            type="button"
            disabled={!canNext}
            onClick={() => setPage((prev) => prev + 1)}
            className="rounded-lg border border-cyan-200 bg-white px-3 py-2 text-sm font-semibold text-slate-700 disabled:cursor-not-allowed disabled:opacity-40"
          >
            Next
          </button>
        </div>
      </section>

      <section className="surface p-6">
        <div className="mb-4 flex items-center gap-2">
          <Sparkles className="text-teal-500" size={18} />
          <h2 className="text-xl text-slate-900">Semantic Search</h2>
        </div>
        <p className="text-sm text-slate-600">Uses /api/questions/semantic-search to find conceptually similar questions.</p>
        <div className="mt-3 flex flex-col gap-3 sm:flex-row">
          <input
            value={semanticQuery}
            onChange={(event) => setSemanticQuery(event.target.value)}
            placeholder="Try: design a scalable cache invalidation strategy"
            className="w-full rounded-xl border border-cyan-200 bg-white px-3 py-2.5 text-sm outline-none ring-cyan-200 focus:ring"
          />
          <button
            type="button"
            onClick={runSemanticSearch}
            disabled={semanticLoading}
            className="rounded-xl bg-slate-900 px-4 py-2.5 text-sm font-semibold text-white disabled:opacity-50"
          >
            {semanticLoading ? 'Searching...' : 'Search'}
          </button>
        </div>
        {semanticError && <p className="mt-2 text-sm font-semibold text-red-600">{semanticError}</p>}
        <div className="mt-4 space-y-3">
          {semanticResults.map((question) => (
            <article
              key={`semantic-${question.id}`}
              onClick={() => {
                setSelectedQuestionId(question.id);
                setIsDetailModalOpen(true);
              }}
              className="rounded-xl border border-sky-200 bg-sky-50/40 p-4 hover:border-sky-300 hover:shadow-md cursor-pointer transition-all duration-200"
            >
              <p className="text-sm font-semibold text-slate-900">{question.interview_question}</p>
              <p className="mt-2 text-xs text-slate-600">Similarity: {(question.similarity_score || 0).toFixed(3)}</p>
            </article>
          ))}
        </div>
      </section>

      <QuestionDetailModal
        isOpen={isDetailModalOpen}
        onClose={() => setIsDetailModalOpen(false)}
        questionId={selectedQuestionId}
        onSelectSimilar={(id) => setSelectedQuestionId(id)}
        onDeleteSuccess={handleDeleteSuccess}
      />
    </div>
  );
};

export default Experiences;
