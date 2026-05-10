import { create } from 'zustand';
import { COST_DATA, ACCOMMODATION_TYPES } from '../utils/cost/data';

interface CostState {
  country: string;
  city: string;
  degree: string;
  schoolType: string;
  duration: number;
  accommodation: string;
  
  setField: (field: keyof CostState, value: string | number) => void;
  getCalculatedCosts: () => CostResult;
}

export interface CostResult {
  tuition: { budget: number, medium: number, comfort: number };
  living: { budget: number, medium: number, comfort: number };
  application: number;
  hidden: number;
  total: { budget: number, medium: number, comfort: number };
}

export const useCostStore = create<CostState>((set, get) => ({
  country: 'us',
  city: 'us-nyc',
  degree: 'master_taught',
  schoolType: 'unsure',
  duration: 1.5,
  accommodation: 'dorm',

  setField: (field, value) => set((state) => {
    const updates: Partial<CostState> = { [field]: value };
    
    // 如果修改了国家，重置城市和学制
    if (field === 'country') {
      const countryData = COST_DATA[value as string];
      if (countryData) {
        updates.city = countryData.cities[0].id;
        updates.duration = countryData.degrees[state.degree]?.defaultDuration || 1;
      }
    }
    
    // 如果修改了学位，重置学制
    if (field === 'degree') {
      const countryData = COST_DATA[state.country];
      if (countryData) {
        updates.duration = countryData.degrees[value as string]?.defaultDuration || 1;
      }
    }
    
    return updates;
  }),

  getCalculatedCosts: () => {
    const { country, city, degree, schoolType, duration, accommodation } = get();
    const data = COST_DATA[country];
    
    if (!data) return {
      tuition: { budget: 0, medium: 0, comfort: 0 },
      living: { budget: 0, medium: 0, comfort: 0 },
      application: 0,
      hidden: 0,
      total: { budget: 0, medium: 0, comfort: 0 }
    };

    const cityData = data.cities.find(c => c.id === city) || data.cities[0];
    const degreeData = data.degrees[degree] || data.degrees['bachelor'];
    const rate = data.exchangeRate;

    // 1. 学费计算
    let tuitionBase = 0;
    if (schoolType === 'public') tuitionBase = degreeData.publicTuition;
    else if (schoolType === 'private') tuitionBase = degreeData.privateTuition;
    else tuitionBase = (degreeData.publicTuition + degreeData.privateTuition) / 2; // 不确定取平均
    
    // 假设预算型学费略低（例如公立/非核心区），宽裕型略高（私立/名校）
    const tBaseRmb = tuitionBase * duration * rate;
    const tuition = {
      budget: Math.round(tBaseRmb * 0.85),
      medium: Math.round(tBaseRmb),
      comfort: Math.round(tBaseRmb * 1.2)
    };

    // 2. 生活费计算
    const accomData = ACCOMMODATION_TYPES.find(a => a.id === accommodation) || ACCOMMODATION_TYPES[0];
    const accomMonthly = cityData.accommodationBase * accomData.multiplier;
    
    // 其他生活费（餐饮、交通、日常）基数 (按月)
    // 根据国家的经济水平大致设一个常数，或者直接给个系数。这里简单化处理：
    const otherMonthlyBase = 600 * cityData.livingMultiplier; // 当地货币
    
    // 每年按12个月计算
    const livingMonthlyMedium = accomMonthly + otherMonthlyBase;
    
    const livingBaseRmb = livingMonthlyMedium * 12 * duration * rate;
    const living = {
      budget: Math.round(livingBaseRmb * 0.7), // 自己做饭、少娱乐
      medium: Math.round(livingBaseRmb),
      comfort: Math.round(livingBaseRmb * 1.5) // 经常外食、旅游多
    };

    // 3. 申请与隐性费用
    const application = data.applicationFee;
    const hidden = data.hiddenFee;

    // 4. 总计
    const total = {
      budget: tuition.budget + living.budget + application + hidden,
      medium: tuition.medium + living.medium + application + hidden,
      comfort: tuition.comfort + living.comfort + application + hidden
    };

    return { tuition, living, application, hidden, total };
  }
}));
