import { create } from 'zustand';
import { TimelineFormData, TimelineStage, generateTimeline } from '../utils/timeline/data';

interface TimelineState {
  formData: TimelineFormData;
  timelineData: TimelineStage[] | null;
  isGenerated: boolean;
  setFormData: (data: Partial<TimelineFormData>) => void;
  generateTimeline: () => void;
  reset: () => void;
}

const initialFormData: TimelineFormData = {
  country: '',
  level: '',
  grade: '',
  major: '',
  tier: '',
  round: ''
};

export const useTimelineStore = create<TimelineState>((set, get) => ({
  formData: initialFormData,
  timelineData: null,
  isGenerated: false,
  
  setFormData: (data) => set((state) => ({
    formData: { ...state.formData, ...data }
  })),
  
  generateTimeline: () => {
    const { formData } = get();
    // 基础验证
    if (!formData.country || !formData.level || !formData.grade || !formData.major) {
      return;
    }
    
    const data = generateTimeline(formData);
    set({ timelineData: data, isGenerated: true });
  },
  
  reset: () => set({
    formData: initialFormData,
    timelineData: null,
    isGenerated: false
  })
}));
