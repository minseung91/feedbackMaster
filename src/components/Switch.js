import React from 'react';

const Switch = ({ 
  checked, 
  onChange, 
  label, 
  className = '' 
}) => {
  return (
    <div className={`switch-container ${className}`}>
      <label className="switch">
        <input
          type="checkbox"
          checked={checked}
          onChange={onChange}
        />
        <span className="slider"></span>
      </label>
      {label && <span className="switch-label">{label}</span>}
    </div>
  );
};

export default Switch;