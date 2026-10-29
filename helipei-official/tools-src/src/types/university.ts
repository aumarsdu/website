export interface University {
  id: string;
  nameEn: string;
  nameZh: string;
  tier: string;
  tags: string[];
  logoUrl?: string;
  location: string;
  admissionProfile: {
    gpa: { min: number; max: number };
    sat?: { min: number; max: number };
    act?: { min: number; max: number };
    toefl?: number;
    ielts?: number;
  };
}

export type MatchLevel = 'Reach' | 'Match' | 'Safe' | 'Unknown';