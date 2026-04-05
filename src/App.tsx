import React from 'react';
import { BrowserRouter, Routes, Route } from 'react-router-dom';
import { Layout } from './components/Layout';
import { Home } from './pages/Home';
import { GpaCalculator } from './pages/GpaCalculator';
import { CostCalculator } from './pages/CostCalculator';

function App() {
  return (
    <BrowserRouter>
      <Layout>
        <Routes>
          <Route path="/" element={<Home />} />
          <Route path="/gpa" element={<GpaCalculator />} />
          <Route path="/cost" element={<CostCalculator />} />
        </Routes>
      </Layout>
    </BrowserRouter>
  );
}

export default App;
