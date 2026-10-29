import { Question } from '../../types/exam';

export const amc8Questions: Question[] = [
  {
    id: 'AMC8-2023-01',
    examType: 'AMC 8',
    year: 2023,
    questionNumber: 1,
    content: 'What is the value of $(8 \\times 4 + 2) - (8 + 4 \\times 2)$?',
    options: [
      { key: 'A', text: '0' },
      { key: 'B', text: '6' },
      { key: 'C', text: '10' },
      { key: 'D', text: '18' },
      { key: 'E', text: '24' }
    ],
    correctAnswer: 'D',
    weight: 1
  },
  {
    id: 'AMC8-2023-03',
    examType: 'AMC 8',
    year: 2023,
    questionNumber: 3,
    content: 'Wind chill is a measure of how cold people feel when exposed to wind outside. A good estimate for wind chill can be found using this calculation:\n\n$$W = T - 0.7 \\cdot S$$\n\nWhere $W$ represents the wind chill, $T$ represents air temperature measured in degrees Fahrenheit ($^{\\circ}F$), and $S$ represents wind speed measured in miles per hour (mph).\n\nSuppose the air temperature is $36^{\\circ}F$ and the wind speed is $18$ mph. Which of the following is closest to the approximate wind chill?',
    options: [
      { key: 'A', text: '18' },
      { key: 'B', text: '23' },
      { key: 'C', text: '28' },
      { key: 'D', text: '32' },
      { key: 'E', text: '35' }
    ],
    correctAnswer: 'B',
    weight: 1
  },
  {
    id: 'AMC8-2023-05',
    examType: 'AMC 8',
    year: 2023,
    questionNumber: 5,
    content: 'A lake contains $250$ trout, along with a variety of other fish. When a marine biologist catches and releases a sample of $180$ fish from the lake, $30$ are identified as trout. Assume that the ratio of trout to the total number of fish is the same in both the sample and the lake. How many fish are there in the lake?',
    options: [
      { key: 'A', text: '1250' },
      { key: 'B', text: '1500' },
      { key: 'C', text: '1750' },
      { key: 'D', text: '1800' },
      { key: 'E', text: '2000' }
    ],
    correctAnswer: 'B',
    weight: 1
  },
  {
    id: 'AMC8-2023-06',
    examType: 'AMC 8',
    year: 2023,
    questionNumber: 6,
    content: 'The digits $2, 0, 2,$ and $3$ are placed in an expression $a^b \\times c^d$, where each digit is used exactly once. What is the maximum possible value of the expression?',
    options: [
      { key: 'A', text: '0' },
      { key: 'B', text: '8' },
      { key: 'C', text: '9' },
      { key: 'D', text: '16' },
      { key: 'E', text: '18' }
    ],
    correctAnswer: 'C',
    weight: 1
  },
  {
    id: 'AMC8-2023-11',
    examType: 'AMC 8',
    year: 2023,
    questionNumber: 11,
    content: 'NASA\'s Perseverance Rover was launched on July 30, 2020. After traveling 292,526,838 miles, it landed on Mars in Jezero Crater about 6.5 months later. Which of the following is closest to the Rover\'s average interplanetary speed in miles per hour?',
    options: [
      { key: 'A', text: '6,000' },
      { key: 'B', text: '12,000' },
      { key: 'C', text: '60,000' },
      { key: 'D', text: '120,000' },
      { key: 'E', text: '600,000' }
    ],
    correctAnswer: 'C',
    weight: 1
  }
];
