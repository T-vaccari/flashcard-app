import React from 'react';
import { BookOpen, Home, PlusCircle, Settings } from 'lucide-react';
import { Link, useLocation } from 'react-router-dom';

const Navbar = () => {
   const location = useLocation();

   const isActive = (path) => location.pathname === path ? 'text-primary' : 'text-muted';

   return (
      <nav className="glass sticky top-0 z-50 mb-8 border-b border-white/20">
         <div className="container flex items-center justify-between py-4">
            <Link to="/" className="flex items-center gap-2 text-2xl font-bold bg-clip-text text-transparent bg-gradient-to-r from-primary to-secondary">
               <BookOpen className="text-primary" />
               <span>FlashMaster</span>
            </Link>

            <div className="flex items-center gap-6">
               <Link to="/" className={`flex items-center gap-2 hover:text-primary transition-colors ${isActive('/')}`}>
                  <Home size={20} />
                  <span className="hidden md:block font-medium">Dashboard</span>
               </Link>
               <Link to="/manage" className={`flex items-center gap-2 hover:text-primary transition-colors ${isActive('/manage')}`}>
                  <PlusCircle size={20} />
                  <span className="hidden md:block font-medium">Manage Cards</span>
               </Link>
            </div>
         </div>
      </nav>
   );
};

export default Navbar;
