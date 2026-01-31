import React, { useEffect, useState } from 'react';
import api from '../api';

const ChapterSelector = ({ selectedChapters, onChange }) => {
   const [chapters, setChapters] = useState({});
   const [loading, setLoading] = useState(true);

   useEffect(() => {
      api.get('/chapters')
         .then(res => {
            setChapters(res.data);
            setLoading(false);
         })
         .catch(err => console.error(err));
   }, []);

   const toggleChapter = (id) => {
      const idInt = parseInt(id);
      const newSelection = selectedChapters.includes(idInt)
         ? selectedChapters.filter(c => c !== idInt)
         : [...selectedChapters, idInt];
      onChange(newSelection);
   };

   if (loading) return <div className="text-muted text-sm">Loading chapters...</div>;

   return (
      <div className="grid grid-cols-1 gap-2 max-h-60 overflow-y-auto pr-2 custom-scrollbar">
         {Object.entries(chapters).map(([id, name]) => (
            <label key={id} className={`flex items-start gap-3 p-3 rounded-lg border cursor-pointer transition-all ${selectedChapters.includes(parseInt(id)) ? 'border-primary bg-blue-50/50' : 'border-border hover:bg-gray-50'}`}>
               <input
                  type="checkbox"
                  checked={selectedChapters.includes(parseInt(id))}
                  onChange={() => toggleChapter(id)}
                  className="mt-1 accent-primary w-4 h-4"
               />
               <div className="text-sm">
                  <span className="font-bold text-primary mr-2">Ch.{id}</span>
                  <span className="text-gray-700">{name}</span>
               </div>
            </label>
         ))}
      </div>
   );
};

export default ChapterSelector;
