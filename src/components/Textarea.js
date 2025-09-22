import React from 'react';

const Textarea = ({ 
  label, 
  value, 
  onChange, 
  placeholder, 
  rows = 4, 
  helpText,
  className = '',
  ...props 
}) => {
  return (
    <div className={`form-group ${className}`}>
      {label && <label>{label}</label>}
      <textarea
        value={value}
        onChange={onChange}
        placeholder={placeholder}
        rows={rows}
        {...props}
      />
      {helpText && <div className="template-help">{helpText}</div>}
    </div>
  );
};

export default Textarea;