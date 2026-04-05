import React from 'react';
import { BrowserRouter, Routes, Route } from 'react-router-dom';
import { Layout } from './components/Layout';
import { Home } from './pages/Home';
import { GpaCalculator } from './pages/GpaCalculator';
import { CostCalculator } from './pages/CostCalculator';
import { TimelineGenerator } from './pages/TimelineGenerator';
import { VisaChecklist } from './pages/VisaChecklist';
import { SchoolMatcher } from './pages/SchoolMatcher';

function App() {
  return (
    <BrowserRouter basename="/tools">
      <Layout>
        <Routes>
          <Route path="/" element={<Home />} />
          <Route path="/gpa" element={<GpaCalculator />} />
          <Route path="/cost" element={<CostCalculator />} />
          <Route path="/timeline" element={<TimelineGenerator />} />
          <Route path="/visa-checklist" element={<VisaChecklist />} />
          <Route path="/school-matcher" element={<SchoolMatcher />} />
        </Routes>
      </Layout>
    </BrowserRouter>
  );
}

export default App;
