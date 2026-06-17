import React, { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useExamStore } from '../store/examStore';

export const MockExamResult: React.FC = () => {
  const navigate = useNavigate();
  const { session, questions, unlockReport, resetExam } = useExamStore();
  const [phone, setPhone] = useState('');

  if (!session || !session.isSubmitted) {
    return (
      <div className="text-center py-20">
        <p>没有正在进行的模考</p>
        <button onClick={() => navigate('/mock-exam')} className="mt-4 text-blue-600">返回首页</button>
      </div>
    );
  }

  // Calculate score (AMC scoring: 6 for correct, 1.5 for blank, 0 for wrong)
  const score = questions.reduce((acc, q) => {
    const ans = session.answers[q.id];
    if (!ans) return acc + 1.5; // blank
    if (ans === q.correctAnswer) return acc + 6; // correct
    return acc; // wrong
  }, 0);

  const maxScore = questions.length * 6;

  const handleUnlock = (e: React.FormEvent) => {
    e.preventDefault();
    if (phone.length >= 11) {
      // In real app, submit to backend
      unlockReport();
    } else {
      alert("请输入有效的手机号");
    }
  };

  if (!session.isLeadCaptured) {
    return (
      <div className="max-w-xl mx-auto py-16 px-4">
        <div className="bg-white p-8 rounded-xl shadow-md border border-neutral-200 text-center">
          <div className="w-16 h-16 bg-green-100 text-green-600 rounded-full flex items-center justify-center mx-auto mb-6">
            <svg className="w-8 h-8" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" /></svg>
          </div>
          <h2 className="text-2xl font-bold text-neutral-800 mb-2">试卷批改完成！</h2>
          <p className="text-neutral-600 mb-8">系统已完成评分并生成排位预估报告。</p>

          <form onSubmit={handleUnlock} className="max-w-sm mx-auto space-y-4">
            <input
              type="tel"
              placeholder="请输入手机号解锁完整报告"
              value={phone}
              onChange={(e) => setPhone(e.target.value)}
              className="w-full px-4 py-3 border border-neutral-300 rounded-lg focus:ring-2 focus:ring-blue-600 focus:outline-none"
              required
            />
            <button type="submit" className="w-full py-3 bg-blue-700 text-white font-medium rounded-lg hover:bg-blue-800">
              免费解锁我的成绩
            </button>
          </form>
        </div>
      </div>
    );
  }

  return (
    <div className="max-w-3xl mx-auto py-12 px-4">
      <div className="bg-white p-8 rounded-xl shadow-sm border border-neutral-200 text-center">
        <h2 className="text-2xl font-bold text-neutral-800 mb-6">模考成绩单</h2>

        <div className="flex justify-center items-center space-x-12 mb-10">
          <div>
            <p className="text-sm text-neutral-500 mb-1">总分</p>
            <p className="text-5xl font-bold text-blue-700">{score}</p>
            <p className="text-sm text-neutral-400 mt-1">满分 {maxScore}</p>
          </div>
          <div className="h-16 w-px bg-neutral-200"></div>
          <div>
            <p className="text-sm text-neutral-500 mb-1">预估排位</p>
            <p className="text-3xl font-bold text-green-600">前 15%</p>
            <p className="text-sm text-neutral-400 mt-1">击败同龄人</p>
          </div>
        </div>

        <div className="bg-neutral-50 p-6 rounded-lg text-left mb-8">
          <h3 className="font-bold text-neutral-800 mb-2">提升建议</h3>
          <p className="text-neutral-600">
            您的代数基础较好，但在几何与数论部分失分较多。想知道具体的错题解析与提分路径？
          </p>
        </div>

        <div className="flex flex-col md:flex-row gap-4 justify-center">
          <button onClick={() => { resetExam(); navigate('/mock-exam'); }} className="px-6 py-3 border border-neutral-300 text-neutral-700 font-medium rounded-lg">
            再测一次
          </button>
          <a href="#" className="px-6 py-3 bg-blue-700 text-white font-medium rounded-lg hover:bg-blue-800">
            预约导师 1v1 规划 (免费)
          </a>
        </div>
      </div>
    </div>
  );
};