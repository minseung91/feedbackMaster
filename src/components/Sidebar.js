import React from 'react';

const Sidebar = ({ 
  title = '메뉴', 
  logoSrc,
  menuItems, 
  activeMenu, 
  onMenuClick 
}) => {
  return (
    <div className="sidebar">
      {logoSrc ? (
        <img 
          src={logoSrc} 
          alt="Logo" 
          className="sidebar-logo"
          onClick={() => window.location.reload()}
        />
      ) : (
        <h2>{title}</h2>
      )}
      <div className="sidebar-divider"></div>
      <ul className="menu-list">
        {menuItems.map((item) => (
          <li 
            key={item.key}
            className={activeMenu === item.key ? 'active' : ''}
            onClick={() => onMenuClick(item.key)}
          >
            {item.label}
          </li>
        ))}
      </ul>
      <div className="sidebar-footer">
        The Project of AWS Hackathon 2025, by [Team LMJ]
      </div>
    </div>
  );
};

export default Sidebar;