import React from 'react';

const Button = ({ 
  children, 
  onClick, 
  priority = 'primary', 
  size = 'middle', 
  className = '',
  ...props 
}) => {
  const getButtonClass = () => {
    const baseClass = 'btn';
    const priorityClass = `btn-${priority}`;
    const sizeClass = `btn-${size}`;
    return `${baseClass} ${priorityClass} ${sizeClass} ${className}`.trim();
  };

  return (
    <button 
      className={getButtonClass()} 
      onClick={onClick}
      {...props}
    >
      {children}
    </button>
  );
};

export default Button;