import React, { createContext, useContext, useState } from 'react';
import './style.css';
const FeedbackContext = createContext();

/**
 * 
 * FeedbackProvider Component
 * --------------------------
 * This Hook provides a context for managing and displaying feedback messages across the application.
 * It uses React's Context API to share feedback state (message, type) with showMessage function that 
 * gets (message, type) and display component with them
 * 
 * Features:
 * - Displays a modal with the feedback message in the center of the screen.
 * - Automatically clears the message after 5 seconds.
 * - Includes a "confirm" button to manually dismiss the message.
 * - Supports dynamic styling based on the feedback type (e.g., 'success', 'error').
 */
export const FeedbackProvider = ({ children }) => {
  const [message, setMessage] = useState('');
  const [type, setType] = useState(''); 
  const [fade, setFade] = useState('');

  const showMessage = (msg, msgType) => {
    setFade(false)
    setMessage(msg);
    setType(msgType);
    setTimeout(() => setFade(true), 3000); // Clear message after 5 seconds
  };

  
  return (
    <FeedbackContext.Provider value={{ message, type, showMessage }}>
      {children}
      { message && (
          <div className={`flex items-center pl-8 pr-8 p-4 mb-4 text-sm rounded-lg border ${type == 'success' ? 'text-green-500 border-green-500 bg-green-50': 'text-red-500 border-red-500 bg-red-50'} absolute left-1/2 -translate-x-1/2 z-20 top-[105px] duration-700
                  ${fade ? "opacity-100 -translate-y-[200px]" : "opacity-100 translate-y-0"}`} role="alert">
            <svg className="shrink-0 inline w-4 h-4 me-3" aria-hidden="true" xmlns="http://www.w3.org/2000/svg" fill="currentColor" viewBox="0 0 20 20">
              <path d="M10 .5a9.5 9.5 0 1 0 9.5 9.5A9.51 9.51 0 0 0 10 .5ZM9.5 4a1.5 1.5 0 1 1 0 3 1.5 1.5 0 0 1 0-3ZM12 15H8a1 1 0 0 1 0-2h1v-3H8a1 1 0 0 1 0-2h2a1 1 0 0 1 1 1v4h1a1 1 0 0 1 0 2Z"/>
            </svg>
            <span className="sr-only">Info</span>
            <div>
              <span className="font-medium">{message}</span> 
            </div>
          </div>
      )}
    </FeedbackContext.Provider>
  );
};

export const useFeedback = () => useContext(FeedbackContext);
