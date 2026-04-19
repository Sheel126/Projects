// components/MultiSelectDropdown.jsx
import React, { useState } from 'react';

const MultiSelectDropdown = ({ title, options, selected, setSelected}) => {
  const [isOpen, setIsOpen] = useState(false);

  const toggleOption = (value) => {
    if (selected.includes(value)) {
      setSelected(selected.filter((v) => v !== value));
    } else {
      setSelected([...selected, value]);
    }
  };

  return (
    <div className="relative mb-8 mr-5">
      <button
        onMouseEnter={() => setIsOpen(true)}
        onMouseLeave={() => setIsOpen(false)}
        className="text-white bg-green-700 text-nowrap hover:bg-green-800 focus:ring-4 focus:outline-none focus:ring-blue-300 font-medium rounded-lg text-sm px-5 py-2.5 inline-flex items-center"
        type="button"
      >
        {title}
        <svg className="w-2.5 h-2.5 ms-3" aria-hidden="true" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 10 6">
          <path stroke="currentColor" strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="m1 1 4 4 4-4" />
        </svg>
      </button>

      <div
        onMouseEnter={() => setIsOpen(true)}
        onMouseLeave={() => setIsOpen(false)}
        className={`z-10 ${isOpen ? 'block' : 'hidden'} absolute bg-white divide-y divide-gray-100 rounded-lg shadow-sm w-44`}
      >
        <ul className="py-2 text-sm text-gray-700 ml-2 mt-2">
          {options.map(([val, name], index) => (
            <li key={index}>
              <div className="flex items-center mb-4 text-left">
                <input
                  id={`${title}_${val}`}
                  type="checkbox"
                  checked={selected.includes(val)}
                  onChange={() => toggleOption(val)}
                  className="w-4 h-4 bg-gray-100 border-gray-300 rounded-sm focus:ring-blue-500 focus:ring-2"
                />
                <label htmlFor={`${title}_${name}`} className="ms-2 text-sm font-medium text-black">
                  {name}
                </label>
              </div>
            </li>
          ))}
        </ul>
      </div>
    </div>
  );
};

export default MultiSelectDropdown;
