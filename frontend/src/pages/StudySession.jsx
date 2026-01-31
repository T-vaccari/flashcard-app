import React, { useState, useEffect, useCallback } from 'react';
import { ArrowLeft, RotateCw, Check, Edit3, Trash2, X, Save, Forward } from 'lucide-react';
import { useNavigate } from 'react-router-dom';
import api from '../api';

const StudySession = () => {
   const [card, setCard] = useState(null);
   const [isFlipped, setIsFlipped] = useState(false);
   const [loading, setLoading] = useState(true);
   const [stats, setStats] = useState({ reviewed: 0, total_due: 0 });
   const [finished, setFinished] = useState(false);
   const [rating, setRating] = useState(null);

   // Edit State
   const [isEditing, setIsEditing] = useState(false);
   const [editFront, setEditFront] = useState("");
   const [editBack, setEditBack] = useState("");

   const navigate = useNavigate();

   const fetchNextType = useCallback(() => {
      setLoading(true);
      setIsFlipped(false);
      setRating(null);
      setIsEditing(false);

      api.get('/study/next')
         .then(res => {
            if (res.data.finished) {
               setFinished(true);
               setStats(res.data.stats);
            } else {
               setCard(res.data.card);
               setStats(res.data.stats);
            }
            setLoading(false);
         })
         .catch(err => {
            console.error(err);
            setLoading(false);
         });
   }, []);

   useEffect(() => {
      fetchNextType();
   }, [fetchNextType]);

   const handleFlip = () => {
      if (!isEditing) setIsFlipped(!isFlipped);
   };

   const submitReview = (quality) => {
      if (!card) return;
      setLoading(true);
      api.post(`/study/review/${card.id}`, { quality })
         .then(res => {
            fetchNextType();
         })
         .catch(err => alert("Error submitting review"));
   };

   const handleEdit = (e) => {
      e.stopPropagation();
      if (card) {
         setEditFront(card.front);
         setEditBack(card.back);
         setIsEditing(true);
      }
   };

   const saveEdit = async (e) => {
      e.stopPropagation();
      if (!card) return;
      try {
         await api.put(`/cards/${card.id}`, { ...card, front: editFront, back: editBack });
         setCard({ ...card, front: editFront, back: editBack });
         setIsEditing(false);
      } catch (err) {
         alert("Failed to save");
      }
   };

   const cancelEdit = (e) => {
      e.stopPropagation();
      setIsEditing(false);
   }

   const handleDelete = async (e) => {
      e.stopPropagation();
      if (!card || !window.confirm("Delete this card permanently?")) return;
      try {
         await api.delete(`/cards/${card.id}`);
         fetchNextType();
      } catch (err) {
         alert("Failed to delete");
      }
   };

   const handleSkip = (e) => {
      e?.stopPropagation();
      fetchNextType();
   }

   // Keyboard shortcuts
   useEffect(() => {
      const handleKey = (e) => {
         if (loading || finished || isEditing) return;

         if (e.code === 'Space') {
            e.preventDefault();
            setIsFlipped(prev => !prev);
         }

         if (isFlipped) {
            if (e.key >= '1' && e.key <= '5') {
               submitReview(parseInt(e.key));
            }
            if (e.key === 'Enter' && rating) {
               submitReview(rating);
            }
         } else {
            if (e.key === 'ArrowRight') handleSkip();
         }
      };

      window.addEventListener('keydown', handleKey);
      return () => window.removeEventListener('keydown', handleKey);
   }, [loading, finished, isFlipped, card, rating, isEditing]);

   if (loading && !card && !finished) return <div className="flex justify-center p-20"><div className="animate-spin h-10 w-10 border-4 border-primary border-t-transparent rounded-full"></div></div>;

   if (finished) {
      return (
         <div className="flex flex-col items-center justify-center min-h-[60vh] text-center animate-fade-in">
            <div className="bg-green-100 p-6 rounded-full mb-6 text-green-600">
               <Check size={64} />
            </div>
            <h2 className="text-3xl font-bold mb-2">Session Complete!</h2>
            <p className="text-muted mb-8">You reviewed {stats.reviewed} cards today.</p>
            <button onClick={() => navigate('/')} className="btn btn-primary">Back to Dashboard</button>
         </div>
      );
   }

   const progress = stats.total_due > 0 ? (stats.reviewed / stats.total_due) * 100 : 0;

   // -- ROBUST FLIP LOGIC & LAYOUT --
   const transitionDuration = 500;
   const halfTransition = transitionDuration / 2;

   const cardContainerStyle = {
      position: 'relative',
      width: '100%',
      height: '500px', // Explicit height to prevent collapse
      perspective: '1000px',
      cursor: 'pointer',
   };

   const flipperStyle = {
      position: 'relative',
      width: '100%',
      height: '100%',
      transition: `transform ${transitionDuration}ms cubic-bezier(0.4, 0, 0.2, 1)`,
      transformStyle: 'preserve-3d',
      transform: isFlipped ? 'rotateY(180deg)' : 'rotateY(0deg)',
   };

   const faceCommon = {
      position: 'absolute',
      inset: 0,
      width: '100%',
      height: '100%',
      backfaceVisibility: 'hidden',
      WebkitBackfaceVisibility: 'hidden',
      // Toggle opacity to ensure absolutely NO mirrored text
      transition: `opacity 0s ${halfTransition}ms`,
   };

   const frontStyle = {
      ...faceCommon,
      zIndex: isFlipped ? 0 : 1,
      opacity: isFlipped ? 0 : 1,
      transform: 'rotateY(0deg)',
   };

   const backStyle = {
      ...faceCommon,
      zIndex: isFlipped ? 1 : 0,
      opacity: isFlipped ? 1 : 0,
      transform: 'rotateY(180deg)',
   };

   return (
      <div className="max-w-4xl mx-auto space-y-8 pb-20">
         {/* Header */}
         <div className="flex items-center justify-between">
            <button onClick={() => navigate('/')} className="flex items-center gap-2 text-muted hover:text-primary transition-colors bg-white px-4 py-2 rounded-lg border border-transparent hover:border-border shadow-sm">
               <ArrowLeft size={20} /> <span className="font-medium">Pause Session</span>
            </button>
            <div className="flex items-center gap-4">
               {!isFlipped && (
                  <button onClick={handleSkip} className="flex items-center gap-1 text-sm font-medium text-muted hover:text-primary transition-colors">
                     Skip <Forward size={16} />
                  </button>
               )}
               <div className="text-sm font-bold text-muted bg-white/50 border border-white/20 px-3 py-1 rounded-full">
                  CARD <span className="text-primary">{stats.reviewed + 1}</span> / {stats.total_due}
               </div>
            </div>
         </div>

         {/* Progress Bar */}
         <div className="h-2 w-full bg-gray-200 rounded-full overflow-hidden">
            <div className="h-full bg-primary transition-all duration-500 ease-out" style={{ width: `${progress}%` }}></div>
         </div>

         {/* Card Area */}
         <div style={cardContainerStyle} onClick={handleFlip} className="group">
            <div style={flipperStyle}>

               {/* Front */}
               <div
                  className="flex flex-col items-center justify-center p-12 text-center border bg-white shadow-xl rounded-2xl border-b-4 border-b-primary card-face-hover transition-transform active:scale-[0.99]"
                  style={frontStyle}
               >
                  <div className="absolute top-6 left-6 flex items-center gap-2">
                     <span className="text-xs font-bold uppercase tracking-wider text-primary bg-indigo-50 px-2 py-1 rounded">Question</span>
                     <span className="text-[10px] items-center text-muted uppercase tracking-wider hidden md:flex">
                        <RotateCw size={10} className="mr-1" /> Click or Space to flip
                     </span>
                  </div>

                  {isEditing ? (
                     <div className="w-full h-full flex items-center" onClick={(e) => e.stopPropagation()}>
                        <textarea
                           className="input h-64 text-center text-2xl shadow-inner bg-gray-50 resize-none p-6 leading-relaxed"
                           value={editFront}
                           onChange={(e) => setEditFront(e.target.value)}
                        />
                     </div>
                  ) : (
                     <div className="overflow-y-auto max-h-full w-full flex items-center justify-center custom-scrollbar">
                        <div className="text-3xl font-medium leading-normal text-main max-w-3xl px-8">
                           {card?.front}
                        </div>
                     </div>
                  )}
               </div>

               {/* Back */}
               <div
                  className="flex flex-col items-center justify-center p-12 text-center border bg-white shadow-xl rounded-2xl border-b-4 border-b-secondary card-face-hover transition-transform active:scale-[0.99]"
                  style={backStyle}
               >
                  <span className="absolute top-6 left-6 text-xs font-bold uppercase tracking-wider text-secondary bg-pink-50 px-2 py-1 rounded">Answer</span>

                  {isEditing ? (
                     <div className="w-full h-full flex flex-col items-center justify-center bg-white/90 z-10" onClick={(e) => e.stopPropagation()}>
                        <label className="text-xs text-muted mb-1 block w-full text-left">Answer</label>
                        <textarea
                           className="input h-64 text-center text-xl shadow-inner bg-gray-50 mb-4 resize-none p-4 leading-relaxed"
                           value={editBack}
                           onChange={(e) => setEditBack(e.target.value)}
                        />
                        <div className="flex gap-2">
                           <button className="btn btn-primary" onClick={saveEdit}><Save size={16} /> Save</button>
                           <button className="btn btn-secondary" onClick={cancelEdit}><X size={16} /> Cancel</button>
                        </div>
                     </div>
                  ) : (
                     <>
                        <div className="overflow-y-auto max-h-full w-full flex items-center justify-center custom-scrollbar">
                           <div className="text-xl leading-relaxed whitespace-pre-wrap text-main max-w-3xl px-8">
                              {card?.back}
                           </div>
                        </div>
                        {/* Actions */}
                        <div className="absolute top-6 right-6 flex gap-2" onClick={(e) => e.stopPropagation()}>
                           <button className="p-2 hover:bg-black/5 rounded-full text-muted transition-colors" title="Edit" onClick={handleEdit}>
                              <Edit3 size={20} />
                           </button>
                           <button className="p-2 hover:bg-black/5 rounded-full text-red-500 transition-colors" title="Delete" onClick={handleDelete}>
                              <Trash2 size={20} />
                           </button>
                        </div>
                     </>
                  )}
               </div>
            </div>
         </div>

         {/* Controls */}
         <div className={`transition-all duration-500 ${isFlipped ? 'opacity-100 translate-y-0' : 'opacity-0 translate-y-8 pointer-events-none'}`}>
            <div className="flex flex-col items-center gap-6">
               <p className="text-sm text-muted font-bold uppercase tracking-widest opacity-70">How well do you know this?</p>
               <div className="flex flex-wrap justify-center gap-4">
                  {[
                     { val: 1, label: 'Hard', color: 'bg-red-500 hover:bg-red-600 shadow-red-500/30' },
                     { val: 2, label: 'Diff', color: 'bg-orange-500 hover:bg-orange-600 shadow-orange-500/30' },
                     { val: 3, label: 'So-so', color: 'bg-yellow-500 hover:bg-yellow-600 shadow-yellow-500/30' },
                     { val: 4, label: 'Good', color: 'bg-lime-500 hover:bg-lime-600 shadow-lime-500/30' },
                     { val: 5, label: 'Easy', color: 'bg-green-500 hover:bg-green-600 shadow-green-500/30' }
                  ].map((btn) => (
                     <button
                        key={btn.val}
                        onClick={() => submitReview(btn.val)}
                        className={`${btn.color} text-white font-bold py-4 px-6 rounded-2xl shadow-lg transform hover:-translate-y-1 transition-all active:scale-95 flex flex-col items-center min-w-[90px] border border-white/20`}
                     >
                        <span className="text-2xl mb-1">{btn.val}</span>
                        <span className="text-[11px] uppercase tracking-wider font-bold opacity-90">{btn.label}</span>
                     </button>
                  ))}
               </div>
            </div>
         </div>

      </div>
   );
};

export default StudySession;
