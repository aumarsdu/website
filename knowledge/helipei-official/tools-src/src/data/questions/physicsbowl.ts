import { Question } from '../../types/exam';

export const physicsbowlQuestions: Question[] = [
  {
    id: 'PB-2023-01',
    examType: 'PhysicsBowl',
    year: 2023,
    questionNumber: 1,
    content: 'Which of the following is NOT a fundamental SI unit?',
    options: [
      { key: 'A', text: 'ampere' },
      { key: 'B', text: 'candela' },
      { key: 'C', text: 'kelvin' },
      { key: 'D', text: 'newton' },
      { key: 'E', text: 'mole' }
    ],
    correctAnswer: 'D',
    weight: 1
  },
  {
    id: 'PB-2023-02',
    examType: 'PhysicsBowl',
    year: 2023,
    questionNumber: 2,
    content: 'A car traveling at $20.0\\text{ m/s}$ applies its brakes and comes to a stop in $4.0\\text{ s}$. Assuming constant deceleration, what is the distance traveled during this time?',
    options: [
      { key: 'A', text: '$20\\text{ m}$' },
      { key: 'B', text: '$40\\text{ m}$' },
      { key: 'C', text: '$60\\text{ m}$' },
      { key: 'D', text: '$80\\text{ m}$' },
      { key: 'E', text: '$100\\text{ m}$' }
    ],
    correctAnswer: 'B',
    weight: 1
  },
  {
    id: 'PB-2023-03',
    examType: 'PhysicsBowl',
    year: 2023,
    questionNumber: 3,
    content: 'Two point charges, $+Q$ and $-Q$, are separated by a distance $d$. The electric potential at the midpoint between them is (assuming potential is zero at infinity):',
    options: [
      { key: 'A', text: '$\\frac{4kQ}{d}$' },
      { key: 'B', text: '$\\frac{2kQ}{d}$' },
      { key: 'C', text: 'Zero' },
      { key: 'D', text: '$-\\frac{2kQ}{d}$' },
      { key: 'E', text: '$-\\frac{4kQ}{d}$' }
    ],
    correctAnswer: 'C',
    weight: 1
  },
  {
    id: 'PB-2023-04',
    examType: 'PhysicsBowl',
    year: 2023,
    questionNumber: 4,
    content: 'A block of mass $m$ is pushed against a horizontal spring of constant $k$, compressing it by a distance $x$. When released, the block slides across a frictionless horizontal surface. What is the maximum speed of the block?',
    options: [
      { key: 'A', text: '$x\\sqrt{\\frac{k}{m}}$' },
      { key: 'B', text: '$x\\frac{k}{m}$' },
      { key: 'C', text: '$\\sqrt{\\frac{kx}{m}}$' },
      { key: 'D', text: '$\\frac{kx^2}{2m}$' },
      { key: 'E', text: '$\\frac{1}{2}x\\sqrt{\\frac{k}{m}}$' }
    ],
    correctAnswer: 'A',
    weight: 1
  },
  {
    id: 'PB-2023-05',
    examType: 'PhysicsBowl',
    year: 2023,
    questionNumber: 5,
    content: 'An ideal gas undergoes an isothermal expansion. Which of the following statements is true?',
    options: [
      { key: 'A', text: 'The internal energy of the gas increases.' },
      { key: 'B', text: 'The pressure of the gas increases.' },
      { key: 'C', text: 'Heat is added to the gas.' },
      { key: 'D', text: 'Work is done on the gas.' },
      { key: 'E', text: 'The temperature of the gas decreases.' }
    ],
    correctAnswer: 'C',
    weight: 1
  }
];
