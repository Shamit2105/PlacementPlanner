import React, { useCallback, useEffect, useMemo, useState } from 'react';
import { interviewsApi } from '../services/api';
import { InterviewQuestion, InterviewSession, QuestionType } from '../types';
import LoadingSpinner from '../components/common/LoadingSpinner';

const QUESTION_TYPES: QuestionType[] = ['DSA_CODING', 'DSA_THEORY', 'OS', 'DBMS', 'NETWORKS', 'SYSTEM_DESIGN'];

const Interviews: React.FC = () => {
  const [sessions, setSessions] = useState<InterviewSession[]>([]);
  const [activeSessionId, setActiveSessionId] = useState<number | null>(null);
  const [nextQuestion, setNextQuestion] = useState<InterviewQuestion | null>(null);
  const [answer, setAnswer] = useState('');
  const [companySlug, setCompanySlug] = useState('');
  const [questionTypes, setQuestionTypes] = useState<QuestionType[]>(['DSA_CODING']);
  const [totalQuestions, setTotalQuestions] = useState(5);
  const [loading, setLoading] = useState(true);
  const [submitting, setSubmitting] = useState(false);
  const [message, setMessage] = useState('');

  const activeSession = useMemo(
    () => sessions.find((item) => item.id === activeSessionId) || null,
    [sessions, activeSessionId]
  );

  const loadSessions = useCallback(async () => {
    setLoading(true);
    try {
      const response = await interviewsApi.listSessions();
      setSessions(response.results);
      if (!activeSessionId && response.results.length > 0) {
        setActiveSessionId(response.results[0].id);
      }
    } finally {
      setLoading(false);
    }
  }, [activeSessionId]);

  useEffect(() => {
    loadSessions();
  }, [loadSessions]);

  const startInterview = async () => {
    setSubmitting(true);
    setMessage('');
    try {
      const started = await interviewsApi.startSession({
        company_slug: companySlug || undefined,
        question_types: questionTypes,
        total_questions: totalQuestions,
      });
      setActiveSessionId(started.id);
      setSessions((prev) => [started, ...prev]);
      setNextQuestion(null);
      setAnswer('');
      setMessage('Interview session started. Fetch your next question.');
    } catch {
      setMessage('Could not start interview. Confirm you are logged in and have enough questions in bank.');
    } finally {
      setSubmitting(false);
    }
  };

  const fetchNext = async () => {
    if (!activeSessionId) return;

    setSubmitting(true);
    setMessage('');
    try {
      const response = await interviewsApi.getNextQuestion(activeSessionId);
      if ('message' in response) {
        setNextQuestion(null);
        setMessage(response.message);
      } else {
        setNextQuestion(response);
      }
    } finally {
      setSubmitting(false);
    }
  };

  const submitAnswer = async () => {
    if (!activeSessionId || !nextQuestion || !answer.trim()) return;

    setSubmitting(true);
    setMessage('');
    try {
      const evaluated = await interviewsApi.submitAnswer(activeSessionId, {
        question_order: nextQuestion.order,
        candidate_answer: answer,
      });
      setNextQuestion(evaluated);
      setAnswer('');
      setMessage('Answer evaluated. Fetch next question to continue.');
      await loadSessions();
    } catch {
      setMessage('Failed to submit answer.');
    } finally {
      setSubmitting(false);
    }
  };

  const toggleType = (type: QuestionType) => {
    setQuestionTypes((prev) => {
      if (prev.includes(type)) {
        const next = prev.filter((item) => item !== type);
        return next.length ? next : ['DSA_CODING'];
      }
      return [...prev, type];
    });
  };

  if (loading) return <LoadingSpinner label="Loading interview sessions" />;

  return (
    <div className="grid gap-6 lg:grid-cols-[340px,1fr]">
      <aside className="space-y-4">
        <section className="surface p-5">
          <h1 className="text-2xl text-slate-900">Mock Interviews</h1>
          <p className="mt-2 text-sm text-slate-600">Start new sessions with /api/interviews/sessions/start.</p>

          <input
            value={companySlug}
            onChange={(event) => setCompanySlug(event.target.value)}
            placeholder="company slug (optional)"
            className="mt-4 w-full rounded-xl border border-amber-200 bg-white px-3 py-2 text-sm outline-none ring-orange-200 focus:ring"
          />

          <div className="mt-3 grid grid-cols-2 gap-2">
            {QUESTION_TYPES.map((type) => (
              <button
                type="button"
                key={type}
                onClick={() => toggleType(type)}
                className={`rounded-lg px-2 py-2 text-xs font-semibold ${
                  questionTypes.includes(type)
                    ? 'bg-slate-900 text-white'
                    : 'border border-amber-200 bg-white text-slate-700'
                }`}
              >
                {type}
              </button>
            ))}
          </div>

          <label className="mt-3 block text-xs font-semibold uppercase tracking-[0.12em] text-slate-500">Total Questions</label>
          <input
            type="number"
            min={1}
            max={20}
            value={totalQuestions}
            onChange={(event) => setTotalQuestions(Number(event.target.value))}
            className="mt-1 w-full rounded-xl border border-amber-200 bg-white px-3 py-2 text-sm outline-none ring-orange-200 focus:ring"
          />

          <button
            type="button"
            onClick={startInterview}
            disabled={submitting}
            className="mt-4 w-full rounded-xl bg-slate-900 px-3 py-2.5 text-sm font-semibold text-white disabled:opacity-50"
          >
            Start Interview
          </button>
        </section>

        <section className="surface p-5">
          <h2 className="text-lg text-slate-900">Sessions</h2>
          <div className="mt-3 space-y-2">
            {sessions.map((session) => (
              <button
                type="button"
                key={session.id}
                onClick={() => {
                  setActiveSessionId(session.id);
                  setNextQuestion(null);
                }}
                className={`w-full rounded-xl border px-3 py-2 text-left ${
                  activeSessionId === session.id
                    ? 'border-sky-300 bg-sky-50'
                    : 'border-amber-100 bg-white hover:border-amber-300'
                }`}
              >
                <p className="text-sm font-semibold text-slate-800">Session #{session.id}</p>
                <p className="text-xs text-slate-600">
                  {session.questions_answered}/{session.total_questions} answered • {session.status}
                </p>
              </button>
            ))}
          </div>
        </section>
      </aside>

      <section className="surface p-6">
        <div className="flex flex-wrap items-center justify-between gap-2">
          <h2 className="text-2xl text-slate-900">Active Session Workspace</h2>
          <button
            type="button"
            onClick={fetchNext}
            disabled={!activeSession || submitting}
            className="rounded-xl border border-amber-200 bg-white px-4 py-2 text-sm font-semibold text-slate-700 disabled:opacity-40"
          >
            Get Next Question
          </button>
        </div>

        {activeSession ? (
          <div className="mt-4 rounded-xl border border-amber-100 bg-white p-4 text-sm text-slate-700">
            <p>Company: {activeSession.company_name || 'General pool'}</p>
            <p>Status: {activeSession.status}</p>
            <p>Score: {activeSession.total_score.toFixed(2)} / {activeSession.max_possible_score}</p>
          </div>
        ) : (
          <p className="mt-4 text-sm text-slate-600">No session selected.</p>
        )}

        {nextQuestion && (
          <article className="mt-5 rounded-xl border border-sky-200 bg-sky-50/40 p-5">
            <p className="text-xs font-semibold uppercase tracking-[0.14em] text-sky-700">
              Question {nextQuestion.order} • {nextQuestion.question_type}
            </p>
            <p className="mt-2 text-sm font-semibold text-slate-900">{nextQuestion.question_text}</p>

            <textarea
              value={answer}
              onChange={(event) => setAnswer(event.target.value)}
              className="mt-4 min-h-36 w-full rounded-xl border border-amber-200 bg-white p-3 text-sm outline-none ring-orange-200 focus:ring"
              placeholder="Write your answer here"
            />

            <button
              type="button"
              onClick={submitAnswer}
              disabled={submitting || !answer.trim()}
              className="mt-3 rounded-xl bg-slate-900 px-4 py-2.5 text-sm font-semibold text-white disabled:opacity-40"
            >
              Submit Answer
            </button>

            {nextQuestion.score !== null && (
              <div className="mt-4 rounded-xl border border-amber-200 bg-white p-4">
                <p className="text-sm font-semibold text-slate-900">Evaluation</p>
                <p className="mt-1 text-sm text-slate-700">Score: {nextQuestion.score}/10 • Verdict: {nextQuestion.verdict}</p>
                <p className="mt-2 text-sm text-slate-600">{nextQuestion.feedback}</p>
              </div>
            )}
          </article>
        )}

        {message && <p className="mt-4 text-sm font-semibold text-orange-700">{message}</p>}
      </section>
    </div>
  );
};

export default Interviews;
