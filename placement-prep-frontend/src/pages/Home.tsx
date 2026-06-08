import React, { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { Building2, ChevronRight, Radar, Rocket, ScanSearch, Sparkle } from 'lucide-react';
import LoadingSpinner from '../components/common/LoadingSpinner';
import { companiesApi, questionsApi } from '../services/api';
import { Company, QuestionListItem, QuestionStats } from '../types';

const Home: React.FC = () => {
  const [companies, setCompanies] = useState<Company[]>([]);
  const [latestQuestions, setLatestQuestions] = useState<QuestionListItem[]>([]);
  const [stats, setStats] = useState<QuestionStats | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const load = async () => {
      try {
        const [companyRes, questionRes, statsRes] = await Promise.all([
          companiesApi.list({ page: 1 }),
          questionsApi.list({ page: 1 }),
          questionsApi.getStats(),
        ]);
        setCompanies(companyRes.results.slice(0, 6));
        setLatestQuestions(questionRes.results.slice(0, 5));
        setStats(statsRes);
      } finally {
        setLoading(false);
      }
    };

    load();
  }, []);

  if (loading) {
    return <LoadingSpinner label="Crafting your dashboard" />;
  }

  return (
    <div className="space-y-8">
      <section className="ambient-grid surface relative overflow-hidden p-8 sm:p-10">
        <div className="absolute -right-10 -top-10 h-36 w-36 rounded-full bg-teal-200/50 blur-2xl" />
        <div className="absolute -bottom-10 left-10 h-36 w-36 rounded-full bg-cyan-200/50 blur-2xl" />
        <div className="relative z-10 max-w-3xl">
          <p className="mb-3 inline-flex items-center gap-2 rounded-full border border-cyan-200 bg-white/80 px-3 py-1 text-xs font-semibold uppercase tracking-[0.16em] text-slate-600">
            <Sparkle size={14} />
            Real backend. Real prep.
          </p>
          <h1 className="gradient-text text-4xl leading-tight sm:text-5xl">
            A bright, focused command center for placements.
          </h1>
          <p className="mt-4 max-w-2xl text-base text-slate-700 sm:text-lg">
            Explore the question bank, run semantic search, trigger scraping jobs, and practice AI-evaluated mock interviews from one clean interface.
          </p>
          <div className="mt-6 flex flex-wrap gap-3">
            <Link to="/experiences" className="rounded-xl bg-slate-900 px-5 py-3 text-sm font-semibold text-white hover:bg-slate-700">
              Open Question Bank
            </Link>
            <Link
              to="/ops"
              className="rounded-xl border border-cyan-200 bg-white px-5 py-3 text-sm font-semibold text-slate-700 hover:border-cyan-300"
            >
              Run Ops Lab
            </Link>
          </div>
        </div>
      </section>

      <section className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <article className="surface p-5 stagger-enter">
          <p className="text-sm text-slate-500">Total Questions</p>
          <p className="mt-1 text-3xl font-display text-slate-900">{stats?.total ?? 0}</p>
        </article>
        <article className="surface p-5 stagger-enter" style={{ animationDelay: '80ms' }}>
          <p className="text-sm text-slate-500">Unique Questions</p>
          <p className="mt-1 text-3xl font-display text-slate-900">{stats?.unique ?? 0}</p>
        </article>
        <article className="surface p-5 stagger-enter" style={{ animationDelay: '160ms' }}>
          <p className="text-sm text-slate-500">Embedded</p>
          <p className="mt-1 text-3xl font-display text-slate-900">{stats?.embedded_percent ?? 0}%</p>
        </article>
        <article className="surface p-5 stagger-enter" style={{ animationDelay: '240ms' }}>
          <p className="text-sm text-slate-500">Companies</p>
          <p className="mt-1 text-3xl font-display text-slate-900">{companies.length}</p>
        </article>
      </section>

      <section className="grid gap-5 lg:grid-cols-2">
        <article className="surface p-6">
          <div className="mb-4 flex items-center justify-between">
            <h2 className="text-xl text-slate-900">Companies</h2>
            <Link to="/companies" className="inline-flex items-center gap-1 text-sm font-semibold text-slate-600 hover:text-slate-900">
              View all
              <ChevronRight size={16} />
            </Link>
          </div>
          <div className="grid gap-2">
            {companies.map((company) => (
              <Link
                key={company.id}
                to={`/companies/${company.id}`}
                className="flex items-center justify-between rounded-xl border border-cyan-200 bg-white p-3 hover:border-cyan-300"
              >
                <span className="inline-flex items-center gap-2 text-slate-800">
                  <Building2 size={16} className="text-sky-600" />
                  {company.name}
                </span>
                <span className="text-xs uppercase tracking-[0.16em] text-slate-500">{company.slug}</span>
              </Link>
            ))}
          </div>
        </article>

        <article className="surface p-6">
          <div className="mb-4 flex items-center justify-between">
            <h2 className="text-xl text-slate-900">Latest Questions</h2>
            <Link to="/experiences" className="inline-flex items-center gap-1 text-sm font-semibold text-slate-600 hover:text-slate-900">
              Explore
              <ChevronRight size={16} />
            </Link>
          </div>
          <div className="space-y-3">
            {latestQuestions.map((question) => (
              <div key={question.id} className="rounded-xl border border-cyan-200 bg-white p-3">
                <p className="line-clamp-2 text-sm font-semibold text-slate-800">{question.interview_question}</p>
                <div className="mt-2 flex flex-wrap items-center gap-2 text-xs text-slate-600">
                  <span className="rounded-full bg-cyan-100 px-2 py-1">{question.question_type_display}</span>
                  <span className="rounded-full bg-sky-100 px-2 py-1">{question.difficulty_display}</span>
                </div>
              </div>
            ))}
          </div>
        </article>
      </section>

      <section className="grid gap-4 md:grid-cols-3">
        <Link to="/experiences" className="surface group p-5 hover:border-cyan-300">
          <Radar className="text-cyan-600" />
          <h3 className="mt-3 text-lg text-slate-900">Semantic Search</h3>
          <p className="mt-1 text-sm text-slate-600">Find related questions by intent, not exact keywords.</p>
        </Link>
        <Link to="/interviews" className="surface group p-5 hover:border-teal-300">
          <Rocket className="text-teal-600" />
          <h3 className="mt-3 text-lg text-slate-900">Mock Interviews</h3>
          <p className="mt-1 text-sm text-slate-600">Start sessions, answer live prompts, get scored feedback.</p>
        </Link>
        <Link to="/ops" className="surface group p-5 hover:border-cyan-300">
          <ScanSearch className="text-slate-700" />
          <h3 className="mt-3 text-lg text-slate-900">Ops Lab</h3>
          <p className="mt-1 text-sm text-slate-600">Trigger scrapers, monitor Celery task status, and manage metadata.</p>
        </Link>
      </section>
    </div>
  );
};

export default Home;
