import React, { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { useExamStore } from '../store/examStore';
import ReactMarkdown from 'react-markdown';
import remarkMath from 'remark-math';
import rehypeKatex from 'rehype-katex';
import 'katex/dist/katex.min.css';

export const MockExamPlayground: React.FC = () => {
  const navigate = useNavigate();
  const { session, questions, answerQuestion, submitExam } = useExamStore();
  const [currentIndex, setCurrentIndex] = useState(0);

  // Redirect if no active session
  useEffect(() => {
    if (!session) navigate('/mock-exam');
    if (session?.isSubmitted) navigate('/mock-exam/result');
  }, [session, navigate]);

  if (!session || questions.length === 0) return null;

  const currentQ = questions[currentIndex];
  const selectedAnswer = session.answers[currentQ.id];

  const handleNext = () => {
    if (currentIndex < questions.length - 1) setCurrentIndex(currentIndex + 1);
  };

  const handlePrev = () => {
    if (currentIndex > 0) setCurrentIndex(currentIndex - 1);
  };

  const handleSubmit = () => {
    if (window.confirm('确定要交卷吗？交卷后将无法修改答案。')) {
      submitExam();
      navigate('/mock-exam/result');
    }
  };

  return (
    <div className="max-w-4xl mx-auto py-8 px-4 flex flex-col md:flex-row gap-6">
      {/* Main Question Area */}
      <div className="flex-1 bg-white p-8 rounded-xl shadow-sm border border-neutral-200">
        <div className="flex justify-between items-center mb-6 pb-4 border-b border-neutral-100">
          <h2 className="text-xl font-bold text-neutral-800">第 {currentIndex + 1} 题 / 共 {questions.length} 题</h2>
        </div>

        <div className="prose prose-slate max-w-none mb-8 text-lg">
          <ReactMarkdown
            remarkPlugins={[remarkMath]}
            rehypePlugins={[rehypeKatex]}
          >
            {currentQ.content}
          </ReactMarkdown>
        </div>

        <div className="space-y-3">
          {currentQ.options.map((opt) => (
            <button
              key={opt.key}
              onClick={() => answerQuestion(currentQ.id, opt.key)}
              className={`w-full text-left p-4 rounded-lg border-2 transition-all ${
                selectedAnswer === opt.key
                  ? 'border-blue-600 bg-blue-50'
                  : 'border-neutral-200 hover:border-blue-300'
              }`}
            >
              <span className="font-bold mr-3">{opt.key}.</span>
              <ReactMarkdown remarkPlugins={[remarkMath]} rehypePlugins={[rehypeKatex]}>
                {opt.text}
              </ReactMarkdown>
            </button>
          ))}
        </div>

        <div className="flex justify-between mt-10">
          <button
            onClick={handlePrev}
            disabled={currentIndex === 0}
            className="px-6 py-2 border border-neutral-300 rounded text-neutral-600 disabled:opacity-50"
          >
            上一题
          </button>
          {currentIndex === questions.length - 1 ? (
            <button onClick={handleSubmit} className="px-6 py-2 bg-blue-700 text-white rounded font-medium">交卷评估</button>
          ) : (
            <button onClick={handleNext} className="px-6 py-2 bg-blue-700 text-white rounded font-medium">下一题</button>
          )}
        </div>
      </div>

      {/* Sidebar Navigation */}
      <div className="w-full md:w-64 bg-white p-6 rounded-xl shadow-sm border border-neutral-200 h-fit">
        <h3 className="font-bold text-neutral-800 mb-4">答题卡</h3>
        <div className="grid grid-cols-5 gap-2">
          {questions.map((q, idx) => (
            <button
              key={q.id}
              onClick={() => setCurrentIndex(idx)}
              className={`w-10 h-10 rounded flex items-center justify-center text-sm font-medium ${
                currentIndex === idx ? 'ring-2 ring-blue-600 ring-offset-2' : ''
              } ${
                session.answers[q.id] ? 'bg-blue-100 text-blue-700' : 'bg-neutral-100 text-neutral-500'
              }`}
            >
              {idx + 1}
            </button>
          ))}
        </div>
        <button onClick={handleSubmit} className="w-full mt-8 py-3 bg-neutral-800 text-white rounded-lg font-medium">交卷</button>
      </div>
    </div>
  );
};