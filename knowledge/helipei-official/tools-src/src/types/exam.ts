export interface Question {
  id: string;
  examType: string;
  year: number;
  questionNumber: number;
  content: string; // Markdown + LaTeX
  options: {
    key: 'A' | 'B' | 'C' | 'D' | 'E';
    text: string;
  }[];
  correctAnswer: 'A' | 'B' | 'C' | 'D' | 'E';
  weight: number;
}

export interface ExamSession {
  examType: string;
  startTime: number;
  answers: Record<string, string>; // questionId -> option key
  isSubmitted: boolean;
  isLeadCaptured: boolean;
}
