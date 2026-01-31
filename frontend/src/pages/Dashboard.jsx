import React, { useEffect, useState } from 'react';
import { Play, Layers, BarChart3, AlertCircle } from 'lucide-react';
import { useNavigate } from 'react-router-dom';
import api from '../api';
import ChapterSelector from '../components/ChapterSelector';

const Dashboard = () => {
   const [stats, setStats] = useState(null);
   const [loading, setLoading] = useState(true);
   const [activeTab, setActiveTab] = useState('dashboard');
   const [selectedChapters, setSelectedChapters] = useState([]);
   const [studyMode, setStudyMode] = useState('cram');
   const navigate = useNavigate();

   useEffect(() => {
      fetchStats();
   }, []);

   const fetchStats = () => {
      api.get('/stats')
         .then(res => {
            setStats(res.data);
            setLoading(false);
         })
         .catch(err => {
            console.error(err);
            setLoading(false);
         });
   };

   const startSession = (mode, params = {}) => {
      api.post('/study/start', { mode, ...params })
         .then(res => {
            navigate('/study');
         })
         .catch(err => alert("Failed to start session"));
   };

   if (loading) return <div className="flex justify-center p-8"><div className="animate-spin h-8 w-8 border-4 border-primary border-t-transparent rounded-full"></div></div>;

   return (
      <div className="animate-fade-in space-y-8">
         {/* Stats Cards */}
         <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
            <div className="card text-center hover:border-primary cursor-default">
               <div className="text-4xl text-primary mb-2">{stats?.total_cards || 0}</div>
               <div className="text-muted font-medium uppercase tracking-wide text-xs">Total Cards</div>
            </div>
            <div className="card text-center hover:border-secondary cursor-default">
               <div className="text-4xl text-secondary mb-2">{stats?.due_cards || 0}</div>
               <div className="text-muted font-medium uppercase tracking-wide text-xs">Due for Review</div>
            </div>
         </div>

         {/* Main Tabbed Area */}
         <div className="bg-white rounded-2xl shadow-lg overflow-hidden border border-border">
            <div className="flex border-b border-gray-100">
               <button onClick={() => setActiveTab('dashboard')} className={`flex-1 py-4 text-center font-medium transition-colors ${activeTab === 'dashboard' ? 'text-primary border-b-2 border-primary bg-indigo-50/50' : 'text-muted hover:text-main'}`}>
                  <span className="flex items-center justify-center gap-2"><Play size={18} /> Quick Start</span>
               </button>
               <button onClick={() => setActiveTab('chapters')} className={`flex-1 py-4 text-center font-medium transition-colors ${activeTab === 'chapters' ? 'text-primary border-b-2 border-primary bg-indigo-50/50' : 'text-muted hover:text-main'}`}>
                  <span className="flex items-center justify-center gap-2"><Layers size={18} /> Chapters</span>
               </button>
               <button onClick={() => setActiveTab('difficulty')} className={`flex-1 py-4 text-center font-medium transition-colors ${activeTab === 'difficulty' ? 'text-primary border-b-2 border-primary bg-indigo-50/50' : 'text-muted hover:text-main'}`}>
                  <span className="flex items-center justify-center gap-2"><BarChart3 size={18} /> Difficulty</span>
               </button>
            </div>

            <div className="p-8 min-h-[300px]">
               {activeTab === 'dashboard' && (
                  <div className="flex flex-col items-center justify-center h-full gap-6 text-center">
                     <div>
                        <h2 className="text-2xl mb-2">Ready to learn?</h2>
                        <p className="text-muted max-w-md mx-auto">Review cards that are due today or start a random cram session if you're caught up.</p>
                     </div>
                     <div className="flex flex-col sm:flex-row gap-4">
                        <button onClick={() => startSession('due')} className="btn btn-primary" disabled={stats?.due_cards === 0}>
                           <AlertCircle size={18} /> Review Due ({stats?.due_cards})
                        </button>
                        <button onClick={() => startSession('cram')} className="btn btn-secondary">
                           <Layers size={18} /> Random Cram (All)
                        </button>
                     </div>
                  </div>
               )}

               {activeTab === 'chapters' && (
                  <div className="flex flex-col gap-6">
                     <div className="flex justify-between items-center">
                        <h3 className="text-xl">Select Chapters to Study</h3>
                        <div className="flex gap-2 bg-gray-100 p-1 rounded-lg">
                           <button onClick={() => setStudyMode('cram')} className={`px-3 py-1 text-sm rounded-md transition-all ${studyMode === 'cram' ? 'bg-white shadow text-primary font-medium' : 'text-muted'}`}>Cram</button>
                           <button onClick={() => setStudyMode('due')} className={`px-3 py-1 text-sm rounded-md transition-all ${studyMode === 'due' ? 'bg-white shadow text-primary font-medium' : 'text-muted'}`}>Due Only</button>
                        </div>
                     </div>
                     <ChapterSelector selectedChapters={selectedChapters} onChange={setSelectedChapters} />
                     <div className="flex justify-end pt-4 border-t border-gray-100">
                        <button
                           onClick={() => startSession(studyMode === 'cram' ? 'chapter' : 'due', { chapters: selectedChapters })}
                           className="btn btn-primary"
                           disabled={selectedChapters.length === 0}
                        >
                           Start Chapter Session
                        </button>
                     </div>
                  </div>
               )}

               {activeTab === 'difficulty' && (
                  <div className="flex flex-col items-center justify-center gap-6">
                     <h3 className="text-xl">Focus on Weak Spots</h3>
                     <div className="grid grid-cols-2 md:grid-cols-3 gap-4 w-full max-w-2xl">
                        {[1, 2, 3, 4, 5].map(level => (
                           <button key={level} onClick={() => startSession('confidence', { confidence_level: level })}
                              className="card hover:border-primary flex flex-col items-center gap-2 transition-all hover:-translate-y-1">
                              <span className={`text-2xl font-bold ${level < 3 ? 'text-red-500' : level < 4 ? 'text-yellow-500' : 'text-green-500'}`}>Level {level}</span>
                              <div className="text-xs font-bold uppercase text-muted">
                                 {level === 1 ? 'Hard' : level === 5 ? 'Easy' : 'Medium'}
                              </div>
                              <div className="text-sm bg-gray-100 px-2 py-1 rounded-full text-gray-600">
                                 {stats?.confidence?.[level] || 0} cards
                              </div>
                           </button>
                        ))}
                     </div>
                  </div>
               )}
            </div>
         </div>
      </div>
   );
};

export default Dashboard;
