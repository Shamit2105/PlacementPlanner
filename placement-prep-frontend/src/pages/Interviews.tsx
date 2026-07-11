import React, { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { Mic, MicOff } from 'lucide-react';
import { interviewsApi, questionsApi } from '../services/api';
import { InterviewQuestion, InterviewSession, QuestionListItem, QuestionType } from '../types';
import LoadingSpinner from '../components/common/LoadingSpinner';
import { MarkdownViewer } from '../components/experiences/QuestionDetailModal';

const QUESTION_TYPES: QuestionType[] = ['DSA_CODING', 'DSA_THEORY', 'OS', 'DBMS', 'NETWORKS', 'SYSTEM_DESIGN'];

interface SimilarQuestionState {
  loading: boolean;
  visible: boolean;
  loaded: boolean;
  results: QuestionListItem[];
  error?: string;
}

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
  const [isListening, setIsListening] = useState(false);
  const [isTranscribing, setIsTranscribing] = useState(false);
  const [voiceError, setVoiceError] = useState('');
  const mediaRecorderRef = useRef<MediaRecorder | null>(null);
  const microphoneStreamRef = useRef<MediaStream | null>(null);
  const audioChunksRef = useRef<Blob[]>([]);
  const [similarQuestions, setSimilarQuestions] = useState<Record<number, SimilarQuestionState>>({});

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

  useEffect(() => () => {
    if (mediaRecorderRef.current?.state === 'recording') mediaRecorderRef.current.stop();
    microphoneStreamRef.current?.getTracks().forEach((track) => track.stop());
  }, []);

  const stopListening = () => {
    if (mediaRecorderRef.current?.state === 'recording') {
      mediaRecorderRef.current.stop();
    }
  };

  const toggleVoiceAnswer = async () => {
    if (isListening) {
      stopListening();
      return;
    }
    if (!activeSessionId || !nextQuestion) return;
    if (!navigator.mediaDevices?.getUserMedia || typeof MediaRecorder === 'undefined') {
      setVoiceError('Audio recording is not supported in this browser.');
      return;
    }

    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      const recorder = new MediaRecorder(stream);
      audioChunksRef.current = [];
      microphoneStreamRef.current = stream;
      mediaRecorderRef.current = recorder;
      recorder.ondataavailable = (event) => {
        if (event.data.size > 0) audioChunksRef.current.push(event.data);
      };
      recorder.onstop = async () => {
        setIsListening(false);
        setIsTranscribing(true);
        stream.getTracks().forEach((track) => track.stop());
        microphoneStreamRef.current = null;
        mediaRecorderRef.current = null;
        const audio = new Blob(audioChunksRef.current, { type: recorder.mimeType || 'audio/webm' });
        try {
          const response = await interviewsApi.transcribeAnswer(
            activeSessionId,
            nextQuestion.order,
            audio,
          );
          if (response.transcript.trim()) {
            setAnswer((current) => `${current}${current.trim() ? ' ' : ''}${response.transcript.trim()}`);
          } else {
            setVoiceError('No speech was detected. Please try again.');
          }
        } catch {
          setVoiceError('Could not transcribe the recording. Please try again.');
        } finally {
          setIsTranscribing(false);
          audioChunksRef.current = [];
        }
      };
      recorder.onerror = () => {
        setVoiceError('Audio recording failed. Please try again.');
        setIsListening(false);
        stream.getTracks().forEach((track) => track.stop());
      };

      setVoiceError('');
      recorder.start();
      setIsListening(true);
    } catch {
      setVoiceError('Could not access the microphone. Check browser permission.');
      setIsListening(false);
    }
  };

  const toggleSimilarQuestions = async (interviewQuestionId: number, questionId: number) => {
    const current = similarQuestions[interviewQuestionId];
    if (current?.loaded) {
      setSimilarQuestions((previous) => ({
        ...previous,
        [interviewQuestionId]: { ...current, visible: !current.visible },
      }));
      return;
    }

    setSimilarQuestions((previous) => ({
      ...previous,
      [interviewQuestionId]: { loading: true, visible: true, loaded: false, results: [] },
    }));
    try {
      const response = await questionsApi.getSimilar(questionId, 3);
      setSimilarQuestions((previous) => ({
        ...previous,
        [interviewQuestionId]: {
          loading: false,
          visible: true,
          loaded: true,
          results: response.results.slice(0, 3),
        },
      }));
    } catch {
      setSimilarQuestions((previous) => ({
        ...previous,
        [interviewQuestionId]: {
          loading: false,
          visible: true,
          loaded: true,
          results: [],
          error: 'Could not load similar questions.',
        },
      }));
    }
  };

  const startInterview = async () => {
    setSubmitting(true);
    setMessage('Generating questions and reference answers for your session... This might take up to a minute.');
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

    stopListening();
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

    stopListening();
    setSubmitting(true);
    setMessage('');
    try {
      const evaluated = await interviewsApi.submitAnswer(activeSessionId, {
        question_order: nextQuestion.order,
        candidate_answer: answer,
      });
      setNextQuestion(evaluated);
      setAnswer('');
      setMessage('Answer submitted. Fetch next question to continue.');
      await loadSessions();
    } catch {
      setMessage('Failed to submit answer.');
    } finally {
      setSubmitting(false);
    }
  };

  const skipQuestion = async () => {
    if (!activeSessionId || !nextQuestion) return;

    stopListening();
    setSubmitting(true);
    setMessage('');
    try {
      const skipped = await interviewsApi.skipQuestion(activeSessionId, nextQuestion.order);
      setNextQuestion(skipped);
      setAnswer('');
      setMessage('Question skipped. Fetch next question to continue.');
      await loadSessions();
    } catch {
      setMessage('Failed to skip question.');
    } finally {
      setSubmitting(false);
    }
  };

  const endInterview = async () => {
    if (!activeSessionId) return;

    if (!window.confirm('Are you sure you want to end this interview session early?')) return;

    setSubmitting(true);
    setMessage('');
    try {
      await interviewsApi.endSession(activeSessionId);
      setNextQuestion(null);
      setAnswer('');
      setMessage('Interview ended early.');
      await loadSessions();
    } catch {
      setMessage('Failed to end interview.');
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
            className="mt-4 w-full rounded-xl border border-cyan-200 bg-white px-3 py-2 text-sm outline-none ring-cyan-200 focus:ring"
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
                    : 'border border-cyan-200 bg-white text-slate-700'
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
            className="mt-1 w-full rounded-xl border border-cyan-200 bg-white px-3 py-2 text-sm outline-none ring-cyan-200 focus:ring"
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
                disabled={isListening || isTranscribing}
                onClick={() => {
                  setActiveSessionId(session.id);
                  setNextQuestion(null);
                }}
                className={`w-full rounded-xl border px-3 py-2 text-left disabled:opacity-50 ${
                  activeSessionId === session.id
                    ? 'border-cyan-300 bg-cyan-50'
                    : 'border-cyan-200 bg-white hover:border-cyan-300'
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
          <div className="flex items-center gap-2">
            {activeSession && activeSession.status === 'IN_PROGRESS' && (
              <button
                type="button"
                onClick={endInterview}
                disabled={submitting || isListening || isTranscribing}
                className="rounded-xl border border-rose-200 bg-rose-50 hover:bg-rose-100 px-4 py-2 text-sm font-semibold text-rose-700 disabled:opacity-40 transition-colors"
              >
                End Interview
              </button>
            )}
            <button
              type="button"
              onClick={fetchNext}
              disabled={!activeSession || activeSession.status !== 'IN_PROGRESS' || submitting || isListening || isTranscribing}
              className="rounded-xl border border-cyan-200 bg-white px-4 py-2 text-sm font-semibold text-slate-700 disabled:opacity-40"
            >
              Get Next Question
            </button>
          </div>
        </div>

        {activeSession ? (
          <div className="mt-4 rounded-xl border border-cyan-200 bg-white p-4 text-sm text-slate-700">
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

            {nextQuestion.status === 'PENDING' && (
              <>
                <textarea
                  value={answer}
                  onChange={(event) => setAnswer(event.target.value)}
                  className="mt-4 min-h-36 w-full rounded-xl border border-cyan-200 bg-white p-3 text-sm outline-none ring-cyan-200 focus:ring"
                  placeholder="Write your answer here"
                />

                {nextQuestion.question_type !== 'DSA_CODING' && (
                  <div className="mt-2 flex flex-wrap items-center gap-2">
                    <button
                      type="button"
                      onClick={toggleVoiceAnswer}
                      disabled={submitting || isTranscribing}
                      className={`inline-flex items-center gap-2 rounded-xl border px-3 py-2 text-sm font-semibold transition-colors disabled:opacity-40 ${
                        isListening
                          ? 'border-rose-200 bg-rose-50 text-rose-700'
                          : 'border-cyan-200 bg-white text-slate-700 hover:bg-cyan-50'
                      }`}
                    >
                      {isListening ? <MicOff size={16} /> : <Mic size={16} />}
                      {isTranscribing ? 'Transcribing…' : isListening ? 'Stop and transcribe' : 'Answer with voice'}
                    </button>
                    {isListening && <span className="text-xs font-semibold text-rose-600">Recording… speak naturally</span>}
                    {isTranscribing && <span className="text-xs font-semibold text-cyan-700">Turning your recording into text…</span>}
                    {voiceError && <span className="text-xs text-rose-600">{voiceError}</span>}
                  </div>
                )}

                <div className="mt-3 flex items-center gap-3">
                  <button
                    type="button"
                    onClick={submitAnswer}
                    disabled={submitting || isListening || isTranscribing || !answer.trim()}
                    className="rounded-xl bg-slate-900 px-4 py-2.5 text-sm font-semibold text-white disabled:opacity-40"
                  >
                    Submit Answer
                  </button>
                  <button
                    type="button"
                    onClick={skipQuestion}
                    disabled={submitting || isListening || isTranscribing}
                    className="rounded-xl border border-amber-200 bg-amber-50 hover:bg-amber-100 px-4 py-2.5 text-sm font-semibold text-amber-700 disabled:opacity-40 transition-colors"
                  >
                    Skip Question
                  </button>
                </div>
              </>
            )}

            {nextQuestion.status === 'SKIPPED' && (
              <div className="mt-4 rounded-xl border border-amber-200 bg-amber-50/50 p-4">
                <p className="text-sm font-semibold text-amber-900">Question Skipped</p>
                <p className="mt-1 text-sm text-slate-600">You chose to skip this question. Fetch the next question to continue.</p>
              </div>
            )}

            {nextQuestion.status === 'EVALUATED' && nextQuestion.score !== null && (
              <div className="mt-4 rounded-xl border border-cyan-200 bg-white p-4">
                <p className="text-sm font-semibold text-slate-900">Evaluation</p>
                <p className="mt-1 text-sm text-slate-700">Score: {nextQuestion.score}/10 • Verdict: {nextQuestion.verdict}</p>
                <p className="mt-2 text-sm text-slate-600">{nextQuestion.feedback}</p>
              </div>
            )}
          </article>
        )}

        {message && <p className="mt-4 text-sm font-semibold text-orange-700">{message}</p>}

        {activeSession && activeSession.status !== 'IN_PROGRESS' && (
          <div className="mt-8 border-t border-slate-200 pt-6 space-y-6">
            <div className="flex items-center justify-between">
              <h3 className="text-xl font-bold text-slate-900">
                Session Review & Evaluation
              </h3>
              <button 
                onClick={loadSessions} 
                disabled={loading || submitting}
                className="text-sm font-semibold text-cyan-600 hover:text-cyan-700 disabled:opacity-50"
              >
                Refresh Status
              </button>
            </div>
            <div className="space-y-4">
              {activeSession.questions && activeSession.questions.length > 0 ? (
                activeSession.questions.map((q) => (
                  <div key={q.id} className="rounded-xl border border-slate-200 bg-white p-5 shadow-sm space-y-4">
                    <div className="flex flex-wrap items-center justify-between gap-2 border-b border-slate-100 pb-3">
                      <div className="flex items-center gap-2">
                        <span className="text-sm font-bold text-slate-800">Question {q.order}</span>
                        <span className="rounded-full bg-cyan-100 px-2.5 py-0.5 text-xs font-semibold text-cyan-800">
                          {q.question_type}
                        </span>
                        <span className={`rounded-full px-2.5 py-0.5 text-xs font-semibold border ${
                          q.difficulty === 'EASY'
                            ? 'bg-emerald-50 border-emerald-200 text-emerald-800'
                            : q.difficulty === 'MEDIUM'
                            ? 'bg-amber-50 border-amber-200 text-amber-800'
                            : 'bg-rose-50 border-rose-200 text-rose-800'
                        }`}>
                          {q.difficulty}
                        </span>
                      </div>
                      <div>
                        {q.status === 'SKIPPED' ? (
                          <span className="rounded-full bg-slate-100 px-2.5 py-0.5 text-xs font-semibold text-slate-600">
                            Skipped
                          </span>
                        ) : q.status === 'EVALUATED' && q.score !== null ? (
                          <span className="rounded-full bg-emerald-100 px-2.5 py-0.5 text-xs font-bold text-emerald-800">
                            Grade: {q.score}/10
                          </span>
                        ) : q.status === 'ANSWERED' ? (
                          <span className="rounded-full bg-blue-100 px-2.5 py-0.5 text-xs font-semibold text-blue-800 animate-pulse">
                            Evaluating...
                          </span>
                        ) : (
                          <span className="rounded-full bg-yellow-100 px-2.5 py-0.5 text-xs font-semibold text-yellow-800">
                            {q.status}
                          </span>
                        )}
                      </div>
                    </div>

                    <div>
                      <h4 className="text-xs font-bold text-slate-400 uppercase tracking-wider mb-1">Question Prompt</h4>
                      <p className="text-sm font-semibold text-slate-900">{q.question_text}</p>
                    </div>

                    {q.status !== 'SKIPPED' && q.candidate_answer && (
                      <div className="bg-slate-50 rounded-lg p-3.5 border border-slate-100">
                        <h4 className="text-xs font-bold text-slate-400 uppercase tracking-wider mb-1">Your Answer</h4>
                        <p className="text-sm text-slate-700 whitespace-pre-wrap leading-relaxed">{q.candidate_answer}</p>
                      </div>
                    )}

                    {q.status === 'EVALUATED' && (
                      <div className="bg-emerald-50/30 rounded-lg p-3.5 border border-emerald-100/50 space-y-2">
                        <h4 className="text-xs font-bold text-emerald-700 uppercase tracking-wider">
                          Evaluation & Feedback
                        </h4>
                        <div className="text-sm text-slate-700 space-y-1.5">
                          <p><strong className="text-slate-800">Verdict:</strong> {q.verdict}</p>
                          <p><strong className="text-slate-800">Feedback:</strong> {q.feedback}</p>
                        </div>
                      </div>
                    )}

                    {q.reference_answer && (
                      <div className="bg-indigo-50/20 rounded-lg p-3.5 border border-indigo-100/30">
                        <h4 className="text-xs font-bold text-indigo-700 uppercase tracking-wider mb-2">Reference Answer</h4>
                        <div className="bg-white border border-slate-100 rounded-lg p-3.5 shadow-inner max-h-60 overflow-y-auto">
                          <MarkdownViewer text={q.reference_answer} />
                        </div>
                      </div>
                    )}

                    <div className="border-t border-slate-100 pt-3">
                      <button
                        type="button"
                        onClick={() => toggleSimilarQuestions(q.id, q.question_id)}
                        disabled={similarQuestions[q.id]?.loading}
                        className="text-sm font-semibold text-cyan-700 hover:text-cyan-900 disabled:opacity-50"
                      >
                        {similarQuestions[q.id]?.loading
                          ? 'Finding similar questions…'
                          : similarQuestions[q.id]?.visible
                          ? 'Hide similar questions'
                          : 'Show similar questions (up to 3)'}
                      </button>

                      {similarQuestions[q.id]?.visible && similarQuestions[q.id]?.loaded && (
                        <div className="mt-3 space-y-2">
                          {similarQuestions[q.id].error ? (
                            <p className="text-sm text-rose-600">{similarQuestions[q.id].error}</p>
                          ) : similarQuestions[q.id].results.length === 0 ? (
                            <p className="text-sm text-slate-500">No similar questions found.</p>
                          ) : (
                            similarQuestions[q.id].results.map((similar) => (
                              <div key={similar.id} className="rounded-lg border border-cyan-100 bg-cyan-50/30 p-3">
                                <div className="flex flex-wrap items-center gap-2 text-xs text-slate-500">
                                  <span className="font-semibold text-cyan-800">{similar.question_type_display}</span>
                                  {typeof similar.similarity_score === 'number' && (
                                    <span>{Math.round(similar.similarity_score * 100)}% similar</span>
                                  )}
                                </div>
                                <p className="mt-1 text-sm font-medium text-slate-800">{similar.interview_question}</p>
                              </div>
                            ))
                          )}
                        </div>
                      )}
                    </div>
                  </div>
                ))
              ) : (
                <p className="text-sm text-slate-500 italic">No questions associated with this session.</p>
              )}
            </div>
          </div>
        )}
      </section>
    </div>
  );
};

export default Interviews;
