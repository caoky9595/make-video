import React, { useState, useEffect } from 'react';
import { api } from '../api';

export const NicksManager: React.FC = () => {
  const [nicks, setNicks] = useState<any>({});
  const [showAddForm, setShowAddForm] = useState(false);
  const [newNick, setNewNick] = useState({ name: '', username: '' });

  const fetchNicks = async () => {
    try {
      const data = await api.get('/nicks');
      setNicks(data);
    } catch(e) {}
  };

  useEffect(() => {
    fetchNicks();
  }, []);

  const handleAddNick = async () => {
    if (!newNick.name) return;
    try {
      await api.post('/nicks/add', newNick);
      setNewNick({ name: '', username: '' });
      setShowAddForm(false);
      fetchNicks();
    } catch(e: any) { alert(e.message); }
  };

  const handleLogin = async (name: string) => {
    try {
      await api.post('/nicks/login', { name });
    } catch(e: any) { alert(e.message); }
  };

  const handleDelete = async (name: string) => {
    if (!window.confirm(`Xoá nick ${name}?`)) return;
    try {
      await api.post('/nicks/remove', { name });
      fetchNicks();
    } catch(e: any) { alert(e.message); }
  };

  const getStatusColor = (status: string) => {
    switch(status) {
      case 'new': return '#3b82f6';
      case 'warmup': return '#f59e0b';
      case 'active': return '#10b981';
      case 'paused': return '#6b7280';
      case 'banned': return '#ef4444';
      default: return '#8b5cf6';
    }
  };

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '2rem', height: '100%' }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
        <div>
          <h2 style={{ fontSize: '1.5rem', fontWeight: 900, display: 'flex', alignItems: 'center', gap: '8px' }}>
             <span className="icon">group</span> Quản lý Tài khoản (Stealth Nicks)
          </h2>
          <p style={{ color: 'var(--text-muted)', fontSize: '13px' }}>Quản lý các profile Chrome ảo dành cho TikTok.</p>
        </div>
        <button className="glow-btn" onClick={() => setShowAddForm(true)}>+ THÊM TÀI KHOẢN</button>
      </div>

      {showAddForm && (
        <div className="glass-card" style={{ padding: '2rem', display: 'flex', gap: '1rem', alignItems: 'flex-end' }}>
          <div style={{ flex: 1 }}>
            <label style={{ display: 'block', fontSize: '11px', fontWeight: 800, textTransform: 'uppercase', color: 'var(--text-muted)', marginBottom: '8px' }}>Tên Nick (ID)</label>
            <input type="text" className="input-field" value={newNick.name} onChange={e => setNewNick({...newNick, name: e.target.value})} placeholder="Vd: nick_01" />
          </div>
          <div style={{ flex: 1 }}>
            <label style={{ display: 'block', fontSize: '11px', fontWeight: 800, textTransform: 'uppercase', color: 'var(--text-muted)', marginBottom: '8px' }}>Username (Tuỳ chọn)</label>
            <input type="text" className="input-field" value={newNick.username} onChange={e => setNewNick({...newNick, username: e.target.value})} placeholder="@..." />
          </div>
          <div style={{ display: 'flex', gap: '8px' }}>
            <button className="glow-btn" onClick={handleAddNick}>LƯU LẠI</button>
            <button style={{ background: 'transparent', border: '1px solid var(--border-subtle)', color: 'var(--text-main)', padding: '12px 24px', borderRadius: '12px', cursor: 'pointer' }} onClick={() => setShowAddForm(false)}>Huỷ</button>
          </div>
        </div>
      )}

      <div className="glass-card" style={{ flex: 1, padding: '1rem', overflowY: 'auto' }}>
        <table style={{ width: '100%', borderCollapse: 'collapse', textAlign: 'left' }}>
          <thead>
            <tr style={{ borderBottom: '1px solid var(--border-subtle)', color: 'var(--text-muted)' }}>
              <th style={{ padding: '1rem', fontSize: '11px', fontWeight: 800, textTransform: 'uppercase', letterSpacing: '0.1em' }}>Tài khoản</th>
              <th style={{ padding: '1rem', fontSize: '11px', fontWeight: 800, textTransform: 'uppercase', letterSpacing: '0.1em' }}>Hệ thống</th>
              <th style={{ padding: '1rem', fontSize: '11px', fontWeight: 800, textTransform: 'uppercase', letterSpacing: '0.1em' }}>Trạng thái</th>
              <th style={{ padding: '1rem', fontSize: '11px', fontWeight: 800, textTransform: 'uppercase', letterSpacing: '0.1em' }}>Tiến độ hôm nay</th>
              <th style={{ padding: '1rem', textAlign: 'right' }}>Hành động</th>
            </tr>
          </thead>
          <tbody>
            {Object.keys(nicks).length === 0 ? (
              <tr>
                <td colSpan={5} style={{ padding: '3rem', textAlign: 'center', color: 'var(--text-muted)' }}>Chưa có nick nào.</td>
              </tr>
            ) : Object.entries(nicks).map(([name, data]: any) => {
              const color = getStatusColor(data.status);
              return (
                <tr key={name} style={{ borderBottom: '1px solid var(--border-subtle)' }}>
                  <td style={{ padding: '1rem' }}>
                    <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
                      <div style={{ width: '40px', height: '40px', borderRadius: '12px', background: `${color}20`, color: color, display: 'flex', alignItems: 'center', justifyContent: 'center', fontWeight: 900 }}>
                         {name.charAt(0).toUpperCase()}
                      </div>
                      <div>
                        <p style={{ fontWeight: 800, fontSize: '13px' }}>{name}</p>
                        <p style={{ fontSize: '11px', color: 'var(--text-muted)' }}>{data.username || '@username'}</p>
                      </div>
                    </div>
                  </td>
                  <td style={{ padding: '1rem' }}>
                    <p style={{ fontSize: '11px', fontWeight: 700, color: '#3b82f6', display: 'flex', alignItems: 'center', gap: '4px' }}><span className="icon" style={{ fontSize: '16px' }}>cloud</span> Direct Proxy</p>
                    <p style={{ fontSize: '10px', color: 'var(--text-muted)' }}>Chromium v145</p>
                  </td>
                  <td style={{ padding: '1rem' }}>
                    <span style={{ display: 'inline-flex', alignItems: 'center', gap: '6px', padding: '6px 12px', borderRadius: '100px', background: `${color}15`, color: color, fontSize: '10px', fontWeight: 900, textTransform: 'uppercase', border: `1px solid ${color}30` }}>
                      <span style={{ width: '6px', height: '6px', borderRadius: '50%', background: color, boxShadow: `0 0 10px ${color}` }}></span>
                      {data.status}
                    </span>
                  </td>
                  <td style={{ padding: '1rem' }}>
                    <p style={{ fontSize: '12px', fontWeight: 800, marginBottom: '4px' }}>{data.videos_today} <span style={{ color: 'var(--text-muted)' }}>/ 5</span></p>
                    <div style={{ width: '100%', height: '4px', background: 'rgba(255,255,255,0.1)', borderRadius: '4px', overflow: 'hidden' }}>
                       <div style={{ width: `${Math.min(100, (data.videos_today/5)*100)}%`, height: '100%', background: '#10b981' }}></div>
                    </div>
                  </td>
                  <td style={{ padding: '1rem', textAlign: 'right' }}>
                    <div style={{ display: 'flex', justifyContent: 'flex-end', gap: '8px' }}>
                      <button onClick={() => handleLogin(name)} style={{ padding: '8px 16px', background: 'var(--primary)', border: 'none', color: 'white', borderRadius: '8px', fontSize: '11px', fontWeight: 800, textTransform: 'uppercase', cursor: 'pointer', display: 'flex', alignItems: 'center', gap: '6px' }}>
                        <span className="icon" style={{ fontSize: '16px' }}>rocket_launch</span> MỞ TRÌNH DUYỆT
                      </button>
                      <button onClick={() => handleDelete(name)} style={{ padding: '8px', background: 'rgba(239, 68, 68, 0.1)', border: 'none', color: '#ef4444', borderRadius: '8px', cursor: 'pointer' }}>
                        <span className="icon">delete</span>
                      </button>
                    </div>
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </div>
  );
};
