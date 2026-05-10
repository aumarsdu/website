export interface CityData {
  id: string;
  name: string;
  livingMultiplier: number;
  accommodationBase: number;
}

export interface DegreeCost {
  publicTuition: number;
  privateTuition: number;
  defaultDuration: number;
}

export interface CountryData {
  id: string;
  name: string;
  flag: string;
  currency: string;
  exchangeRate: number; // 相对人民币汇率
  cities: CityData[];
  degrees: Record<string, DegreeCost>;
  applicationFee: number;
  hiddenFee: number;
}

export const COST_DATA: Record<string, CountryData> = {
  us: {
    id: 'us',
    name: '美国',
    flag: '🇺🇸',
    currency: 'USD',
    exchangeRate: 7.2,
    cities: [
      { id: 'us-nyc', name: '纽约/加州 (一线)', livingMultiplier: 1.3, accommodationBase: 1800 },
      { id: 'us-chicago', name: '芝加哥/波士顿 (二线)', livingMultiplier: 1.1, accommodationBase: 1200 },
      { id: 'us-other', name: '其他地区 (三线)', livingMultiplier: 0.9, accommodationBase: 800 }
    ],
    degrees: {
      bachelor: { publicTuition: 35000, privateTuition: 55000, defaultDuration: 4 },
      master_taught: { publicTuition: 40000, privateTuition: 60000, defaultDuration: 1.5 },
      master_research: { publicTuition: 30000, privateTuition: 50000, defaultDuration: 2 },
      phd: { publicTuition: 30000, privateTuition: 50000, defaultDuration: 5 }
    },
    applicationFee: 2000, // RMB
    hiddenFee: 15000 // RMB (机票、签证、体检等)
  },
  uk: {
    id: 'uk',
    name: '英国',
    flag: '🇬🇧',
    currency: 'GBP',
    exchangeRate: 9.1,
    cities: [
      { id: 'uk-london', name: '伦敦', livingMultiplier: 1.4, accommodationBase: 1200 },
      { id: 'uk-other', name: '非伦敦地区', livingMultiplier: 1.0, accommodationBase: 700 }
    ],
    degrees: {
      bachelor: { publicTuition: 20000, privateTuition: 20000, defaultDuration: 3 },
      master_taught: { publicTuition: 25000, privateTuition: 25000, defaultDuration: 1 },
      master_research: { publicTuition: 22000, privateTuition: 22000, defaultDuration: 2 },
      phd: { publicTuition: 20000, privateTuition: 20000, defaultDuration: 3.5 }
    },
    applicationFee: 1500,
    hiddenFee: 12000
  },
  hk: {
    id: 'hk',
    name: '中国香港',
    flag: '🇭🇰',
    currency: 'HKD',
    exchangeRate: 0.92,
    cities: [
      { id: 'hk-all', name: '全区', livingMultiplier: 1.2, accommodationBase: 8000 }
    ],
    degrees: {
      bachelor: { publicTuition: 145000, privateTuition: 160000, defaultDuration: 4 },
      master_taught: { publicTuition: 200000, privateTuition: 250000, defaultDuration: 1 },
      master_research: { publicTuition: 42100, privateTuition: 42100, defaultDuration: 2 },
      phd: { publicTuition: 42100, privateTuition: 42100, defaultDuration: 3 }
    },
    applicationFee: 800,
    hiddenFee: 5000
  },
  sg: {
    id: 'sg',
    name: '新加坡',
    flag: '🇸🇬',
    currency: 'SGD',
    exchangeRate: 5.3,
    cities: [
      { id: 'sg-all', name: '全区', livingMultiplier: 1.2, accommodationBase: 1500 }
    ],
    degrees: {
      bachelor: { publicTuition: 30000, privateTuition: 35000, defaultDuration: 3.5 },
      master_taught: { publicTuition: 40000, privateTuition: 45000, defaultDuration: 1 },
      master_research: { publicTuition: 35000, privateTuition: 35000, defaultDuration: 2 },
      phd: { publicTuition: 35000, privateTuition: 35000, defaultDuration: 4 }
    },
    applicationFee: 1000,
    hiddenFee: 6000
  }
};

export const DEGREE_TYPES = [
  { id: 'bachelor', name: '本科' },
  { id: 'master_taught', name: '硕士 (授课型)' },
  { id: 'master_research', name: '硕士 (研究型)' },
  { id: 'phd', name: '博士' }
];

export const SCHOOL_TYPES = [
  { id: 'public', name: '公立' },
  { id: 'private', name: '私立' },
  { id: 'unsure', name: '不确定' }
];

export const ACCOMMODATION_TYPES = [
  { id: 'dorm', name: '学校宿舍', multiplier: 1.0 },
  { id: 'share', name: '校外合租', multiplier: 0.8 },
  { id: 'solo', name: '校外独住', multiplier: 1.5 }
];
