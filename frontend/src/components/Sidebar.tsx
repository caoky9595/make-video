import React from 'react';

interface SidebarProps {
  activePage: string;
  setActivePage: (page: string) => void;
}

const NAV_ITEMS = [
  { id: 'dashboard', icon: 'space_dashboard', label: 'Bảng điều khiển', color: '#9333ea' },
  { id: 'editor', icon: 'movie_edit', label: 'Meme Studio', color: '#3b82f6' },
  { id: 'factory', icon: 'factory', label: 'Content Factory', color: '#4f46e5' },
  { id: 'nicks', icon: 'group', label: 'Quản lý Tài khoản', color: '#10b981' },
  { id: 'uploader', icon: 'rocket', label: 'Auto Uploader', color: '#f59e0b' },
  { id: 'settings', icon: 'settings', label: 'Cấu hình', color: '#64748b' }
];

export const Sidebar: React.FC<SidebarProps> = ({ activePage, setActivePage }) => {
  return (
    <aside style={{
      width: '260px',
      backgroundColor: '#0a0a0f',
      borderRight: '1px solid rgba(255,255,255,0.05)',
      display: 'flex',
      flexDirection: 'column',
      padding: '2rem 1rem',
      flexShrink: 0
    }}>
      <div style={{ marginBottom: '2.5rem', padding: '0 0.75rem' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '12px', marginBottom: '4px' }}>
          <div style={{
            width: '32px', height: '32px', borderRadius: '8px', 
            background: 'linear-gradient(135deg, #9333ea, #4f46e5)',
            display: 'flex', alignItems: 'center', justifyContent: 'center',
            boxShadow: '0 4px 15px rgba(147,51,234,0.3)'
          }}>
            <span className="icon" style={{ color: 'white', fontSize: '18px' }}>bolt</span>
          </div>
          <h1 style={{ fontSize: '1.1rem', fontWeight: 900, letterSpacing: '-0.5px' }}>
            AFFILIATE<span style={{ color: '#a855f7' }}>AI</span>
          </h1>
        </div>
        <p style={{ fontSize: '10px', color: '#94a3b8', textTransform: 'uppercase', letterSpacing: '0.2em', fontWeight: 700 }}>
          Production Suite
        </p>
      </div>

      <nav style={{ display: 'flex', flexDirection: 'column', gap: '6px', flex: 1 }}>
        {NAV_ITEMS.map(item => {
          const isActive = activePage === item.id;
          return (
            <button
              key={item.id}
              onClick={() => setActivePage(item.id)}
              style={{
                display: 'flex',
                alignItems: 'center',
                gap: '12px',
                padding: '12px 16px',
                borderRadius: '12px',
                border: 'none',
                background: isActive ? 'linear-gradient(135deg, rgba(147,51,234,0.2), rgba(79,70,229,0.1))' : 'transparent',
                color: isActive ? '#fff' : '#94a3b8',
                cursor: 'pointer',
                transition: 'all 0.2s',
                textAlign: 'left',
                borderLeft: isActive ? `3px solid ${item.color}` : '3px solid transparent'
              }}
              onMouseEnter={(e) => {
                if (!isActive) {
                  e.currentTarget.style.background = 'rgba(255,255,255,0.05)';
                  e.currentTarget.style.color = '#fff';
                }
              }}
              onMouseLeave={(e) => {
                if (!isActive) {
                  e.currentTarget.style.background = 'transparent';
                  e.currentTarget.style.color = '#94a3b8';
                }
              }}
            >
              <div style={{
                width: '32px', height: '32px', borderRadius: '8px',
                background: isActive ? 'transparent' : 'rgba(255,255,255,0.05)',
                display: 'flex', alignItems: 'center', justifyContent: 'center'
              }}>
                <span className="icon" style={{ fontSize: '18px', color: isActive ? item.color : 'inherit' }}>
                  {item.icon}
                </span>
              </div>
              <span style={{ fontSize: '11px', fontWeight: 800, textTransform: 'uppercase', letterSpacing: '0.1em' }}>
                {item.label}
              </span>
            </button>
          );
        })}
      </nav>

      <div style={{ marginTop: 'auto', paddingTop: '1.5rem', borderTop: '1px solid rgba(255,255,255,0.05)' }}>
        <button
          onClick={() => alert('Chức năng dọn dẹp hệ thống chưa tích hợp ở React')}
          style={{
            display: 'flex', alignItems: 'center', gap: '8px', padding: '12px 16px',
            background: 'transparent', border: 'none', color: '#f87171',
            cursor: 'pointer', fontSize: '11px', fontWeight: 800, textTransform: 'uppercase',
            width: '100%', borderRadius: '12px'
          }}
          onMouseEnter={(e) => e.currentTarget.style.background = 'rgba(248,113,113,0.1)'}
          onMouseLeave={(e) => e.currentTarget.style.background = 'transparent'}
        >
          <span className="icon" style={{ fontSize: '18px' }}>delete_sweep</span>
          Dọn dẹp hệ thống
        </button>
      </div>
    </aside>
  );
};
