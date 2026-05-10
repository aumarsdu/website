import { create } from 'zustand';
import { Course, AlgorithmType, calculateGPA } from '../utils/gpa';
import { v4 as uuidv4 } from 'uuid';

interface AppState {
  courses: Course[];
  algorithm: AlgorithmType;
  addCourse: () => void;
  removeCourse: (id: string) => void;
  updateCourse: (id: string, field: keyof Course, value: string | number) => void;
  setAlgorithm: (algo: AlgorithmType) => void;
  clearCourses: () => void;
  fillExample: () => void;
  getResults: () => { gpa: number, totalCredits: number };
}

const initialCourses: Course[] = [
  { id: uuidv4(), name: '高等数学', credits: 4, score: 85 },
  { id: uuidv4(), name: '大学物理', credits: 3, score: 78 },
  { id: uuidv4(), name: '计算机网络', credits: 3, score: 92 },
];

export const useStore = create<AppState>((set, get) => ({
  courses: [{ id: uuidv4(), name: '', credits: 0, score: 0 }],
  algorithm: 'standard40',

  addCourse: () => set((state) => ({
    courses: [...state.courses, { id: uuidv4(), name: '', credits: 0, score: 0 }]
  })),

  removeCourse: (id) => set((state) => ({
    courses: state.courses.filter(c => c.id !== id)
  })),

  updateCourse: (id, field, value) => set((state) => ({
    courses: state.courses.map(c => 
      c.id === id ? { ...c, [field]: value } : c
    )
  })),

  setAlgorithm: (algo) => set({ algorithm: algo }),

  clearCourses: () => set({ courses: [{ id: uuidv4(), name: '', credits: 0, score: 0 }] }),

  fillExample: () => set({ courses: initialCourses.map(c => ({...c, id: uuidv4()})) }),

  getResults: () => {
    const { courses, algorithm } = get();
    return calculateGPA(courses, algorithm);
  }
}));
