import React from 'react';

const SettingsSection = ({ 
  title, 
  children, 
  className = '',
  required = false
}) => {
  return (
    <div className={`settings-section ${className}`}>
      <div className="settings-section-title">
        {title}
        {required && <span className="required-asterisk">*</span>}
      </div>
      <div className="settings-section-content">
        {children}
      </div>
    </div>
  );
};

export default SettingsSection;