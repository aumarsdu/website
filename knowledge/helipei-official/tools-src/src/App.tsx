import React from 'react';
import { BrowserRouter, Routes, Route } from 'react-router-dom';
import { Layout } from './components/Layout';
import { Home } from './pages/Home';
import { GpaCalculator } from './pages/GpaCalculator';
import { CostCalculator } from './pages/CostCalculator';
import { TimelineGenerator } from './pages/TimelineGenerator';
import { VisaChecklist } from './pages/VisaChecklist';
import { SchoolMatcher } from './pages/SchoolMatcher';
import { MockExamEntry } from './pages/MockExamEntry';
import { MockExamPlayground } from './pages/MockExamPlayground';
import { MockExamResult } from './pages/MockExamResult';
import { TendencyTest } from './pages/TendencyTest';
import { UniversityTieringPage } from './pages/UniversityTieringPage';
import { ExtracurricularActivityPlannerPage } from './pages/ExtracurricularActivityPlannerPage';
import { CaseMatcherPage } from './pages/CaseMatcherPage';

function App() {
  return (
    <BrowserRouter basename="/tools">
      <Routes>
        <Route path="/" element={<Layout />}>
          <Route index element={<Home />} />
          <Route path="gpa" element={<GpaCalculator />} />
          <Route path="cost" element={<CostCalculator />} />
          <Route path="timeline" element={<TimelineGenerator />} />
          <Route path="visa-checklist" element={<VisaChecklist />} />
          <Route path="school-matcher" element={<SchoolMatcher />} />
          <Route path="mock-exam" element={<MockExamEntry />} />
          <Route path="mock-exam/play" element={<MockExamPlayground />} />
          <Route path="mock-exam/result" element={<MockExamResult />} />
          <Route path="tendency" element={<TendencyTest />} />
          <Route path="university-tiering" element={<UniversityTieringPage />} />
          <Route path="extracurricular-activity-planner" element={<ExtracurricularActivityPlannerPage />} />
          <Route path="case-matcher" element={<CaseMatcherPage />} />
        </Route>
      </Routes>
    </BrowserRouter>
  );
}

export default App;
