import { Question } from '../types/exam';
import { amc8Questions } from './questions/amc8';
import { amc12Questions } from './questions/amc12';
import { physicsbowlQuestions } from './questions/physicsbowl';

export const mockAmc10Questions: Question[] = [
  {
    id: 'AMC10-2023-A-01',
    examType: 'AMC 10',
    year: 2023,
    questionNumber: 1,
    content: 'What is the value of $$\\frac{2023}{2+0+2+3}$$?',
    options: [
      { key: 'A', text: '285' },
      { key: 'B', text: '289' },
      { key: 'C', text: '291' },
      { key: 'D', text: '293' },
      { key: 'E', text: '295' }
    ],
    correctAnswer: 'B',
    weight: 1
  },
  {
    id: 'AMC10-2023-A-02',
    examType: 'AMC 10',
    year: 2023,
    questionNumber: 2,
    content: 'If $3^x = 9^{y+1}$ and $4^y = 16^{x-1}$, what is the value of $x+y$?',
    options: [
      { key: 'A', text: '3' },
      { key: 'B', text: '4' },
      { key: 'C', text: '5' },
      { key: 'D', text: '6' },
      { key: 'E', text: '7' }
    ],
    correctAnswer: 'C',
    weight: 1
  }
];

export const getMockQuestions = (examId: string): Question[] => {
  if (examId === 'amc8') return amc8Questions;
  if (examId === 'amc10') return mockAmc10Questions;
  if (examId === 'amc12') return amc12Questions;
  if (examId === 'physicsbowl') return physicsbowlQuestions;

  return mockAmc10Questions.map(q => ({
    ...q,
    examType: examId.toUpperCase()
  }));
};
