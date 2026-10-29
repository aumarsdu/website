import { create } from 'zustand';

export interface UserProfileState {
  gpa: number | null;
  sat: number | null;
  act: number | null;
  toefl: number | null;
  ielts: number | null;
}

interface UniversityStore {
  profile: UserProfileState;
  updateProfile: (updates: Partial<UserProfileState>) => void;
  resetProfile: () => void;
}

const initialProfile: UserProfileState = {
  gpa: null,
  sat: null,
  act: null,
  toefl: null,
  ielts: null,
};

export const useUniversityStore = create<UniversityStore>((set) => ({
  profile: initialProfile,
  updateProfile: (updates) =>
    set((state) => ({ profile: { ...state.profile, ...updates } })),
  resetProfile: () => set({ profile: initialProfile }),
}));