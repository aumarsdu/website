export type AlgorithmType = 
  | 'standard40'
  | 'pku40'
  | 'improved40v1'
  | 'improved40v2'
  | 'canada43'
  | 'ustc43'
  | 'wes40';

export interface Course {
  id: string;
  name: string;
  credits: number;
  score: number;
}

export interface AlgorithmConfig {
  id: AlgorithmType;
  name: string;
  maxGPA: number;
  calculate: (score: number) => number;
}

export const ALGORITHMS: Record<AlgorithmType, AlgorithmConfig> = {
  standard40: {
    id: 'standard40',
    name: '标准 4.0',
    maxGPA: 4.0,
    calculate: (score) => {
      if (score >= 90) return 4.0;
      if (score >= 80) return 3.0;
      if (score >= 70) return 2.0;
      if (score >= 60) return 1.0;
      return 0.0;
    }
  },
  pku40: {
    id: 'pku40',
    name: '北大 4.0',
    maxGPA: 4.0,
    calculate: (score) => {
      if (score >= 90) return 4.0;
      if (score >= 85) return 3.7;
      if (score >= 82) return 3.3;
      if (score >= 78) return 3.0;
      if (score >= 75) return 2.7;
      if (score >= 72) return 2.3;
      if (score >= 68) return 2.0;
      if (score >= 64) return 1.5;
      if (score >= 60) return 1.0;
      return 0.0;
    }
  },
  improved40v1: {
    id: 'improved40v1',
    name: '改进 4.0 (版1)',
    maxGPA: 4.0,
    calculate: (score) => {
      if (score >= 85) return 4.0;
      if (score >= 70) return 3.0;
      if (score >= 60) return 2.0;
      return 0.0;
    }
  },
  improved40v2: {
    id: 'improved40v2',
    name: '改进 4.0 (版2)',
    maxGPA: 4.0,
    calculate: (score) => {
      if (score >= 85) return 4.0;
      if (score >= 75) return 3.0;
      if (score >= 60) return 2.0;
      return 0.0;
    }
  },
  canada43: {
    id: 'canada43',
    name: '加拿大 4.3',
    maxGPA: 4.3,
    calculate: (score) => {
      if (score >= 90) return 4.3;
      if (score >= 85) return 4.0;
      if (score >= 80) return 3.7;
      if (score >= 77) return 3.3;
      if (score >= 73) return 3.0;
      if (score >= 70) return 2.7;
      if (score >= 67) return 2.3;
      if (score >= 63) return 2.0;
      if (score >= 60) return 1.7;
      return 0.0;
    }
  },
  ustc43: {
    id: 'ustc43',
    name: '中科大 4.3',
    maxGPA: 4.3,
    calculate: (score) => {
      if (score >= 95) return 4.3;
      if (score >= 90) return 4.0;
      if (score >= 85) return 3.7;
      if (score >= 82) return 3.3;
      if (score >= 78) return 3.0;
      if (score >= 75) return 2.7;
      if (score >= 72) return 2.3;
      if (score >= 68) return 2.0;
      if (score >= 65) return 1.7;
      if (score >= 64) return 1.5;
      if (score >= 61) return 1.3;
      if (score >= 60) return 1.0;
      return 0.0;
    }
  },
  wes40: {
    id: 'wes40',
    name: 'WES 4.0',
    maxGPA: 4.0,
    calculate: (score) => {
      if (score >= 85) return 4.0;
      if (score >= 75) return 3.0;
      if (score >= 60) return 2.0;
      return 0.0;
    }
  }
};

export function calculateGPA(courses: Course[], algorithm: AlgorithmType): { gpa: number, totalCredits: number } {
  let totalCredits = 0;
  let totalPoints = 0;
  const algo = ALGORITHMS[algorithm];

  courses.forEach(course => {
    if (course.credits > 0 && course.score > 0) {
      totalCredits += course.credits;
      const gpaPoint = algo.calculate(course.score);
      totalPoints += gpaPoint * course.credits;
    }
  });

  return {
    gpa: totalCredits > 0 ? Number((totalPoints / totalCredits).toFixed(2)) : 0,
    totalCredits
  };
}
