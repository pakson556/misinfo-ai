// frontend/components/InfoTooltip.jsx
import React, { useState } from 'react';
import { Info } from 'lucide-react';

export default function InfoTooltip({ content }) {
  const [show, setShow] = useState(false);

  return (
    <div className="relative inline-block">
      <button
        onMouseEnter={() => setShow(true)}
        onMouseLeave={() => setShow(false)}
        className="p-1 hover:bg-gray-100 rounded-full transition-colors"
      >
        <Info className="w-4 h-4 text-gray-400" />
      </button>
      
      {show && (
        <div className="absolute bottom-full left-1/2 transform -translate-x-1/2 mb-2 w-64 p-3 bg-gray-900 text-white text-xs rounded-lg shadow-lg z-50">
          <div className="absolute top-full left-1/2 transform -translate-x-1/2 -mt-1">
            <div className="border-4 border-transparent border-t-gray-900" />
          </div>
          {content}
        </div>
      )}
    </div>
  );
}