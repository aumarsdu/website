import { Suspense, lazy } from 'react';
import { BrowserRouter, Routes, Route } from 'react-router-dom';
import { Layout } from './components/Layout';

// 使用 React.lazy 实现路由级别的代码分割
const Home = lazy(() => import('./pages/Home').then(module => ({ default: module.Home })));
const GpaCalculator = lazy(() => import('./pages/GpaCalculator').then(module => ({ default: module.GpaCalculator })));
const CostCalculator = lazy(() => import('./pages/CostCalculator').then(module => ({ default: module.CostCalculator })));
const TimelineGenerator = lazy(() => import('./pages/TimelineGenerator').then(module => ({ default: module.TimelineGenerator })));
const VisaChecklist = lazy(() => import('./pages/VisaChecklist').then(module => ({ default: module.VisaChecklist })));
const SchoolMatcher = lazy(() => import('./pages/SchoolMatcher').then(module => ({ default: module.SchoolMatcher })));
const MockExamEntry = lazy(() => import('./pages/MockExamEntry').then(module => ({ default: module.MockExamEntry })));
const MockExamPlayground = lazy(() => import('./pages/MockExamPlayground').then(module => ({ default: module.MockExamPlayground })));
const MockExamResult = lazy(() => import('./pages/MockExamResult').then(module => ({ default: module.MockExamResult })));
const UniversityTieringPage = lazy(() => import('./pages/UniversityTieringPage').then(module => ({ default: module.UniversityTieringPage })));
const TendencyTest = lazy(() => import('./pages/TendencyTest').then(module => ({ default: module.TendencyTest })));

function App() {
  return (
    <BrowserRouter basename="/tools">
      <Layout>
        <Suspense fallback={
          <div className="min-h-[50vh] flex items-center justify-center">
            <div className="w-10 h-10 border-4 border-brand-blue-light border-t-brand-blue rounded-full animate-spin"></div>
          </div>
        }>
          <Routes>
            <Route path="/" element={<Home />} />
            <Route path="/gpa" element={<GpaCalculator />} />
            <Route path="/cost" element={<CostCalculator />} />
            <Route path="/timeline" element={<TimelineGenerator />} />
            <Route path="/visa-checklist" element={<VisaChecklist />} />
            <Route path="/school-matcher" element={<SchoolMatcher />} />
            <Route path="/mock-exam" element={<MockExamEntry />} />
            <Route path="/mock-exam/play" element={<MockExamPlayground />} />
            <Route path="/mock-exam/result" element={<MockExamResult />} />
            <Route path="/university-tiering" element={<UniversityTieringPage />} />
            <Route path="/tendency" element={<TendencyTest />} />
          </Routes>
        </Suspense>
      </Layout>
    </BrowserRouter>
  );
}

export default App;
