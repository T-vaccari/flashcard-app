import React from 'react';
import { BrowserRouter as Router, Routes, Route } from 'react-router-dom';
import Navbar from './components/Navbar';
import Dashboard from './pages/Dashboard';
import StudySession from './pages/StudySession';
import CardManager from './pages/CardManager';

function App() {
  return (
    <Router>
      <div className="min-h-screen pb-10">
        <Navbar />
        <main className="container">
          <Routes>
            <Route path="/" element={<Dashboard />} />
            <Route path="/study" element={<StudySession />} />
            <Route path="/manage" element={<CardManager />} />
          </Routes>
        </main>
      </div>
    </Router>
  );
}

export default App;
