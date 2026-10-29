import { Question } from '../../types/exam';

export const amc12Questions: Question[] = [
  {
    id: 'AMC12-2023-01',
    examType: 'AMC 12',
    year: 2023,
    questionNumber: 1,
    content: 'Which of the following is the value of $\\sqrt{49} - \\sqrt{25}$?',
    options: [
      { key: 'A', text: '$\\sqrt{24}$' },
      { key: 'B', text: '2' },
      { key: 'C', text: '$\\sqrt{12}$' },
      { key: 'D', text: '4' },
      { key: 'E', text: '12' }
    ],
    correctAnswer: 'B',
    weight: 1
  },
  {
    id: 'AMC12-2023-02',
    examType: 'AMC 12',
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
  },
  {
    id: 'AMC12-2023-03',
    examType: 'AMC 12',
    year: 2023,
    questionNumber: 3,
    content: 'A right square pyramid has a base with area $36$ and a height of $4$. What is the total surface area of the pyramid?',
    options: [
      { key: 'A', text: '48' },
      { key: 'B', text: '60' },
      { key: 'C', text: '84' },
      { key: 'D', text: '96' },
      { key: 'E', text: '120' }
    ],
    correctAnswer: 'D',
    weight: 1
  }
];
