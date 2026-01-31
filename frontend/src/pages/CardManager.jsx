import React, { useState } from 'react';
import { Plus } from 'lucide-react';
import api from '../api';

const CardManager = () => {
   // Basic placeholder for now
   const [q, setQ] = useState("");
   const [a, setA] = useState("");

   const addCard = () => {
      if (!q || !a) return;
      api.post('/cards', { front: q, back: a, chapter: 1, id: 'temp' })
         .then(() => { alert("Added!"); setQ(""); setA(""); })
         .catch(() => alert("Error"));
   };

   return (
      <div className="animate-fade-in space-y-6">
         <h2 className="text-2xl font-bold">Manage Cards</h2>
         <div className="card space-y-4 max-w-xl mx-auto">
            <h3 className="text-lg font-medium">Add New Flashcard</h3>
            <input className="input" placeholder="Question / Front" value={q} onChange={e => setQ(e.target.value)} />
            <textarea className="input min-h-[100px]" placeholder="Answer / Back" value={a} onChange={e => setA(e.target.value)} />
            <button className="btn btn-primary w-full" onClick={addCard}>
               <Plus size={20} /> Add Card
            </button>
         </div>
         <div className="text-center text-muted">A full management interface is coming soon.</div>
      </div>
   );
};

export default CardManager;
