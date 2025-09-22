import React from 'react';

const RadioGroup = ({ 
  name, 
  options, 
  value, 
  onChange, 
  className = '' 
}) => {
  return (
    <div className={`radio-group ${className}`}>
      {options.map((option) => (
        <label key={option.value}>
          <input
            type="radio"
            name={name}
            value={option.value}
            checked={value === option.value}
            onChange={onChange}
          />
          {option.label}
        </label>
      ))}
    </div>
  );
};

export default RadioGroup;