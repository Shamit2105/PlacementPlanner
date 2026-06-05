import React, { useEffect, useState } from 'react';
import { ExternalLink } from 'lucide-react';
import { companiesApi, questionsApi, topicsApi } from '../services/api';
import { Company, QuestionStats, QuestionType, ScrapeRequestPayload, TaskStatusResponse, Topic } from '../types';

const QUESTION_TYPES: QuestionType[] = ['DSA_CODING', 'DSA_THEORY', 'OS', 'DBMS', 'NETWORKS', 'SYSTEM_DESIGN'];

const OpsLab: React.FC = () => {
  const [stats, setStats] = useState<QuestionStats | null>(null);
  const [taskStatus, setTaskStatus] = useState<TaskStatusResponse | null>(null);
  const [taskId, setTaskId] = useState('');
  const [companies, setCompanies] = useState<Company[]>([]);
  const [topics, setTopics] = useState<Topic[]>([]);
  const [newCompany, setNewCompany] = useState({ name: '', slug: '' });
  const [newTopic, setNewTopic] = useState({ name: '', question_type: 'DSA_CODING' as QuestionType });
  const [scrapeForm, setScrapeForm] = useState<ScrapeRequestPayload>({ question_type: 'DSA_CODING', target_count: 10 });
  const [message, setMessage] = useState('');

  const load = async () => {
    const [statsRes, companyRes, topicRes] = await Promise.all([
      questionsApi.getStats(),
      companiesApi.list({ page: 1 }),
      topicsApi.list({ page: 1 }),
    ]);
    setStats(statsRes);
    setCompanies(companyRes.results);
    setTopics(topicRes.results);
  };

  useEffect(() => {
    load();
  }, []);

  const createCompany = async () => {
    try {
      await companiesApi.create(newCompany);
      setNewCompany({ name: '', slug: '' });
      setMessage('Company created.');
      await load();
    } catch {
      setMessage('Failed to create company.');
    }
  };

  const createTopic = async () => {
    try {
      await topicsApi.create(newTopic);
      setNewTopic({ name: '', question_type: 'DSA_CODING' });
      setMessage('Topic created.');
      await load();
    } catch {
      setMessage('Failed to create topic.');
    }
  };

  const triggerScrape = async () => {
    try {
      const response = await questionsApi.triggerScrape(scrapeForm);
      setTaskId(response.task_id);
      setMessage(`Scrape queued: ${response.task_id}`);
    } catch {
      setMessage('Scrape trigger failed.');
    }
  };

  const pollStatus = async () => {
    if (!taskId.trim()) return;
    try {
      const response = await questionsApi.getTaskStatus(taskId.trim());
      setTaskStatus(response);
    } catch {
      setMessage('Task status lookup failed.');
    }
  };

  return (
    <div className="space-y-6">
      <header className="surface p-6 sm:p-8">
        <h1 className="text-3xl text-slate-900 sm:text-4xl">Ops Lab</h1>
        <p className="mt-2 text-slate-600">Control panel for stats, scrape, company/topic management, and task polling.</p>
        <div className="mt-4 flex flex-wrap gap-3 text-sm">
          <a
            href="http://localhost:8000/api/docs/"
            target="_blank"
            rel="noreferrer"
            className="inline-flex items-center gap-2 rounded-xl border border-amber-200 bg-white px-3 py-2 font-semibold text-slate-700"
          >
            Swagger docs
            <ExternalLink size={14} />
          </a>
          <a
            href="http://localhost:8000/api/schema/"
            target="_blank"
            rel="noreferrer"
            className="inline-flex items-center gap-2 rounded-xl border border-amber-200 bg-white px-3 py-2 font-semibold text-slate-700"
          >
            OpenAPI schema
            <ExternalLink size={14} />
          </a>
        </div>
      </header>

      <section className="grid gap-4 md:grid-cols-3">
        <article className="surface p-5">
          <p className="text-sm text-slate-500">Total questions</p>
          <p className="text-3xl font-display text-slate-900">{stats?.total ?? 0}</p>
        </article>
        <article className="surface p-5">
          <p className="text-sm text-slate-500">Unique</p>
          <p className="text-3xl font-display text-slate-900">{stats?.unique ?? 0}</p>
        </article>
        <article className="surface p-5">
          <p className="text-sm text-slate-500">Embedded %</p>
          <p className="text-3xl font-display text-slate-900">{stats?.embedded_percent ?? 0}</p>
        </article>
      </section>

      <section className="grid gap-6 lg:grid-cols-2">
        <article className="surface p-5">
          <h2 className="text-xl text-slate-900">Create Company</h2>
          <div className="mt-3 grid gap-2">
            <input
              value={newCompany.name}
              onChange={(event) => setNewCompany((prev) => ({ ...prev, name: event.target.value }))}
              placeholder="Company name"
              className="rounded-xl border border-amber-200 bg-white px-3 py-2 text-sm"
            />
            <input
              value={newCompany.slug}
              onChange={(event) => setNewCompany((prev) => ({ ...prev, slug: event.target.value }))}
              placeholder="company-slug"
              className="rounded-xl border border-amber-200 bg-white px-3 py-2 text-sm"
            />
            <button onClick={createCompany} className="rounded-xl bg-slate-900 px-3 py-2 text-sm font-semibold text-white">
              Create
            </button>
          </div>
          <div className="mt-4 space-y-1 text-sm text-slate-600">
            {companies.map((company) => (
              <p key={company.id}>{company.name} ({company.slug})</p>
            ))}
          </div>
        </article>

        <article className="surface p-5">
          <h2 className="text-xl text-slate-900">Create Topic</h2>
          <div className="mt-3 grid gap-2">
            <input
              value={newTopic.name}
              onChange={(event) => setNewTopic((prev) => ({ ...prev, name: event.target.value }))}
              placeholder="Topic name"
              className="rounded-xl border border-amber-200 bg-white px-3 py-2 text-sm"
            />
            <select
              value={newTopic.question_type}
              onChange={(event) => setNewTopic((prev) => ({ ...prev, question_type: event.target.value as QuestionType }))}
              className="rounded-xl border border-amber-200 bg-white px-3 py-2 text-sm"
            >
              {QUESTION_TYPES.map((type) => (
                <option key={type} value={type}>
                  {type}
                </option>
              ))}
            </select>
            <button onClick={createTopic} className="rounded-xl bg-slate-900 px-3 py-2 text-sm font-semibold text-white">
              Create
            </button>
          </div>
          <div className="mt-4 space-y-1 text-sm text-slate-600">
            {topics.map((topic) => (
              <p key={topic.id}>{topic.name} ({topic.question_type})</p>
            ))}
          </div>
        </article>
      </section>

      <section className="surface p-5">
        <h2 className="text-xl text-slate-900">Scrape & Task Polling</h2>
        <div className="mt-3 grid gap-3 md:grid-cols-4">
          <select
            value={scrapeForm.question_type}
            onChange={(event) => setScrapeForm((prev) => ({ ...prev, question_type: event.target.value as QuestionType }))}
            className="rounded-xl border border-amber-200 bg-white px-3 py-2 text-sm"
          >
            {QUESTION_TYPES.map((type) => (
              <option key={type} value={type}>
                {type}
              </option>
            ))}
          </select>
          <input
            value={scrapeForm.company_name || ''}
            onChange={(event) => setScrapeForm((prev) => ({ ...prev, company_name: event.target.value }))}
            placeholder="company_name"
            className="rounded-xl border border-amber-200 bg-white px-3 py-2 text-sm"
          />
          <input
            value={scrapeForm.topic_name || ''}
            onChange={(event) => setScrapeForm((prev) => ({ ...prev, topic_name: event.target.value }))}
            placeholder="topic_name"
            className="rounded-xl border border-amber-200 bg-white px-3 py-2 text-sm"
          />
          <input
            type="number"
            min={1}
            max={50}
            value={scrapeForm.target_count || 10}
            onChange={(event) => setScrapeForm((prev) => ({ ...prev, target_count: Number(event.target.value) }))}
            className="rounded-xl border border-amber-200 bg-white px-3 py-2 text-sm"
          />
        </div>
        <button onClick={triggerScrape} className="mt-3 rounded-xl bg-slate-900 px-3 py-2 text-sm font-semibold text-white">
          Trigger Scrape
        </button>

        <div className="mt-5 grid gap-3 sm:grid-cols-[1fr_auto]">
          <input
            value={taskId}
            onChange={(event) => setTaskId(event.target.value)}
            placeholder="Paste task id to poll"
            className="rounded-xl border border-amber-200 bg-white px-3 py-2 text-sm"
          />
          <button onClick={pollStatus} className="rounded-xl border border-amber-200 bg-white px-3 py-2 text-sm font-semibold text-slate-700">
            Check Status
          </button>
        </div>

        {taskStatus && (
          <div className="mt-4 rounded-xl border border-sky-200 bg-sky-50/40 p-3 text-sm text-slate-700">
            <p>Task: {taskStatus.task_id}</p>
            <p>Status: {taskStatus.status}</p>
            {taskStatus.error && <p>Error: {taskStatus.error}</p>}
          </div>
        )}
      </section>

      {message && <p className="text-sm font-semibold text-orange-700">{message}</p>}
    </div>
  );
};

export default OpsLab;
