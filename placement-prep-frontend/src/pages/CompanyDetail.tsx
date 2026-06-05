import React, { useEffect, useMemo, useState } from 'react';
import { Link, useParams } from 'react-router-dom';
import { ArrowLeft, BookText, Layers3, Search } from 'lucide-react';
import LoadingSpinner from '../components/common/LoadingSpinner';
import { companiesApi, questionsApi } from '../services/api';
import { Company, QuestionListItem } from '../types';

const CompanyDetail: React.FC = () => {
  const { id } = useParams();
  const [company, setCompany] = useState<Company | null>(null);
  const [questions, setQuestions] = useState<QuestionListItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [searchText, setSearchText] = useState('');

  useEffect(() => {
    const load = async () => {
      setLoading(true);
      try {
        const companiesRes = await companiesApi.list({ page: 1 });
        const selected = companiesRes.results.find((item) => item.id === Number(id)) || null;
        setCompany(selected);

        if (selected) {
          const questionsRes = await questionsApi.list({ company: selected.slug, page: 1 });
          setQuestions(questionsRes.results);
        } else {
          setQuestions([]);
        }
      } finally {
        setLoading(false);
      }
    };

    if (id) {
      load();
    }
  }, [id]);

  const filteredQuestions = useMemo(() => {
    const normalized = searchText.trim().toLowerCase();
    if (!normalized) return questions;
    return questions.filter((item) => item.interview_question.toLowerCase().includes(normalized));
  }, [questions, searchText]);

  if (loading) return <LoadingSpinner label="Loading company board" />;

  if (!company) {
    return (
      <div className="surface p-8 text-center">
        <p className="text-lg font-semibold text-slate-800">Company not found.</p>
        <Link to="/companies" className="mt-3 inline-flex text-sm font-semibold text-sky-700 hover:text-sky-800">
          Back to companies
        </Link>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <Link to="/companies" className="inline-flex items-center gap-2 text-sm font-semibold text-slate-600 hover:text-slate-900">
        <ArrowLeft size={16} />
        Back to companies
      </Link>

      <section className="surface p-6 sm:p-8">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div>
            <h1 className="text-3xl text-slate-900">{company.name}</h1>
            <p className="mt-2 text-sm uppercase tracking-[0.14em] text-slate-500">slug: {company.slug}</p>
          </div>
          <div className="rounded-xl border border-amber-200 bg-white px-4 py-3 text-right">
            <p className="text-xs uppercase tracking-[0.14em] text-slate-500">Question hits</p>
            <p className="text-2xl font-display text-slate-900">{questions.length}</p>
          </div>
        </div>

        <label className="relative mt-5 block max-w-lg">
          <Search size={16} className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-400" />
          <input
            value={searchText}
            onChange={(event) => setSearchText(event.target.value)}
            placeholder="Search questions in this company"
            className="w-full rounded-xl border border-amber-200 bg-white py-2.5 pl-9 pr-3 text-sm outline-none ring-orange-200 focus:ring"
          />
        </label>
      </section>

      <section className="grid gap-3">
        {filteredQuestions.map((question) => (
          <article key={question.id} className="surface p-5">
            <div className="flex flex-wrap items-center gap-2 text-xs">
              <span className="rounded-full bg-amber-100 px-2 py-1 font-semibold text-amber-800">
                {question.question_type_display}
              </span>
              <span className="rounded-full bg-sky-100 px-2 py-1 font-semibold text-sky-800">
                {question.difficulty_display}
              </span>
              <span className="rounded-full bg-slate-100 px-2 py-1 font-semibold text-slate-700">{question.status}</span>
            </div>
            <p className="mt-3 text-sm font-semibold text-slate-900">{question.interview_question}</p>
            <p className="mt-2 line-clamp-2 text-sm text-slate-600">{question.answer_preview}</p>
            <div className="mt-4 flex flex-wrap gap-2 text-xs text-slate-500">
              <span className="inline-flex items-center gap-1">
                <BookText size={13} />
                Source: {question.source}
              </span>
              <span className="inline-flex items-center gap-1">
                <Layers3 size={13} />
                Used: {question.times_used}
              </span>
            </div>
          </article>
        ))}
      </section>

      {filteredQuestions.length === 0 && (
        <div className="surface p-8 text-center text-slate-600">No questions match your search inside this company.</div>
      )}
    </div>
  );
};

export default CompanyDetail;
