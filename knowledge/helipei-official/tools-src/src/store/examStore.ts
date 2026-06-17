import { create } from 'zustand';
import { ExamSession, Question } from '../types/exam';

interface ExamState {
  session: ExamSession | null;
  questions: Question[];
  startExam: (examType: string, questions: Question[]) => void;
  answerQuestion: (questionId: string, answer: string) => void;
  submitExam: () => void;
  unlockReport: () => void;
  resetExam: () => void;
}

export const useExamStore = create<ExamState>((set) => ({
  session: null,
  questions: [],
  startExam: (examType, questions) => set({
    questions,
    session: {
      examType,
      startTime: Date.now(),
      answers: {},
      isSubmitted: false,
      isLeadCaptured: false,
    }
  }),
  answerQuestion: (questionId, answer) => set((state) => {
    if (!state.session) return state;
    return {
      session: {
        ...state.session,
        answers: { ...state.session.answers, [questionId]: answer }
      }
    };
  }),
  submitExam: () => set((state) => {
    if (!state.session) return state;
    return {
      session: { ...state.session, isSubmitted: true }
    };
  }),
  unlockReport: () => set((state) => {
    if (!state.session) return state;
    return {
      session: { ...state.session, isLeadCaptured: true }
    };
  }),
  resetExam: () => set({ session: null, questions: [] })
}));
