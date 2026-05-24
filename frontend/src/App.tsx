import { useState, useEffect } from 'react'
import { api } from './api'
import { Sidebar } from './components/Sidebar'
import { Editor } from './components/Editor'
import { Factory } from './components/Factory'
import { NicksManager } from './components/NicksManager'
import { Uploader } from './components/Uploader'

function App() {
  const [activePage, setActivePage] = useState(() => {
    return localStorage.getItem('activePage') || 'dashboard';
  })
  const [stats, setStats] = useState<any>(null)
  const [videos, setVideos] = useState<any[]>([])
  const [previewVideo, setPreviewVideo] = useState<string | null>(null)
  const [selectedVideos, setSelectedVideos] = useState<Set<string>>(new Set())

  const toggleSelect = (path: string, e: React.MouseEvent) => {
    e.stopPropagation();
    const newSet = new Set(selectedVideos);
    if (newSet.has(path)) newSet.delete(path);
    else newSet.add(path);
    setSelectedVideos(newSet);
  }

  const handleDelete = (path: string | 'all' | 'selected') => {
    let bodyPayload: any = {};
    let confirmMsg = '';

    if (path === 'all') {
      confirmMsg = 'Xoá toàn bộ video đã tạo? Không thể hoàn tác!';
      bodyPayload = { all: true };
    } else if (path === 'selected') {
      if (selectedVideos.size === 0) return;
      confirmMsg = `Xoá ${selectedVideos.size} video đã chọn?`;
      bodyPayload = { paths: Array.from(selectedVideos) };
    } else {
      confirmMsg = 'Xoá video này?';
      bodyPayload = { path };
    }

    if (!window.confirm(confirmMsg)) return;
    
    fetch('/api/affiliate/videos', {
      method: 'DELETE',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(bodyPayload)
    })
      .then(res => res.json())
      .then(data => {
        if (data.success) {
          if (path === 'all') {
            setVideos([]);
          } else if (path === 'selected') {
            setVideos(prev => prev.filter(v => !selectedVideos.has(v.path)));
            setSelectedVideos(new Set());
          } else {
            setVideos(prev => prev.filter(v => v.path !== path));
            if (selectedVideos.has(path as string)) toggleSelect(path as string, { stopPropagation: () => {} } as any);
          }
          setPreviewVideo(null);
        } else {
          alert('Lỗi: ' + data.error);
        }
      })
      .catch(err => alert('Lỗi: ' + err.message));
  };

  useEffect(() => {
    localStorage.setItem('activePage', activePage);
    if (activePage === 'dashboard') {
      Promise.all([
        api.get('/stats'),
        api.get('/nicks'),
        api.get('/affiliate/videos')
      ]).then(([statsData, nicksData, videosData]) => {
        setStats({
          videos_created: statsData.videos_created || 0,
          total_size_mb: statsData.total_size_mb || 0,
          ai_used_today: statsData.ai_used_today || 0,
          ai_limit: statsData.ai_limit || 10,
          total_nicks: Object.keys(nicksData || {}).length
        });
        setVideos(videosData || []);
      }).catch(console.error);
    }
  }, [activePage]);

  return (
    <div className="app-container">
      <Sidebar activePage={activePage} setActivePage={setActivePage} />
      
      <main className="main-content">
        <header style={{
          height: '64px',
          borderBottom: '1px solid var(--border-subtle)',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          padding: '0 2rem',
          background: 'rgba(10,10,15,0.5)',
          backdropFilter: 'blur(10px)',
          flexShrink: 0
        }}>
          <h2 style={{ fontSize: '14px', fontWeight: 700, color: 'var(--text-muted)', textTransform: 'uppercase', letterSpacing: '0.1em' }}>
            {activePage.replace('_', ' ')}
          </h2>
          
          <div style={{ display: 'flex', alignItems: 'center', gap: '24px' }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
              <span style={{
                position: 'relative', display: 'flex', width: '8px', height: '8px'
              }}>
                <span style={{ position: 'absolute', width: '100%', height: '100%', borderRadius: '50%', background: '#22c55e', opacity: 0.7 }} className="animate-pulse"></span>
                <span style={{ position: 'relative', width: '8px', height: '8px', borderRadius: '50%', background: '#22c55e' }}></span>
              </span>
              <span style={{ fontSize: '11px', fontWeight: 800, color: 'var(--text-muted)', textTransform: 'uppercase' }}>Hệ thống Online</span>
            </div>
            
            <div style={{ width: '1px', height: '32px', background: 'var(--border-subtle)' }}></div>
            
            <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
              <div style={{ textAlign: 'right' }}>
                <p style={{ fontSize: '12px', fontWeight: 800, lineHeight: 1 }}>Creator</p>
                <p style={{ fontSize: '10px', color: 'var(--primary)', fontWeight: 800, textTransform: 'uppercase' }}>Pro Plan</p>
              </div>
              <div style={{
                width: '40px', height: '40px', borderRadius: '16px',
                background: 'linear-gradient(135deg, var(--primary), var(--secondary))',
                display: 'flex', alignItems: 'center', justifyContent: 'center',
                fontWeight: 900, color: 'white'
              }}>K</div>
            </div>
          </div>
        </header>

        <div className="page-container">
          <div style={{ display: activePage === 'dashboard' ? 'flex' : 'none', flexDirection: 'column', gap: '2rem' }}>
            <div className="glass-card" style={{ padding: '3rem', position: 'relative', overflow: 'hidden' }}>
              <div style={{ position: 'absolute', top: '-100px', right: '-100px', width: '300px', height: '300px', background: 'var(--primary-glow)', borderRadius: '50%', filter: 'blur(100px)' }}></div>
              <div style={{ position: 'relative', zIndex: 1 }}>
                <div style={{ display: 'inline-flex', alignItems: 'center', gap: '8px', padding: '6px 16px', borderRadius: '100px', background: 'rgba(147,51,234,0.1)', border: '1px solid rgba(147,51,234,0.2)', marginBottom: '16px' }}>
                  <span style={{ width: '8px', height: '8px', borderRadius: '50%', background: 'var(--primary)' }}></span>
                  <span style={{ fontSize: '10px', fontWeight: 900, textTransform: 'uppercase', letterSpacing: '0.2em', color: '#d8b4fe' }}>AI Engine Ready</span>
                </div>
                <h1 style={{ fontSize: '3rem', fontWeight: 900, letterSpacing: '-1px', marginBottom: '16px', lineHeight: 1.1 }}>
                  Welcome back,<br />
                  <span className="glow-text" style={{ fontStyle: 'italic' }}>Creator! 🚀</span>
                </h1>
                <p style={{ color: 'var(--text-muted)', fontSize: '1.1rem', maxWidth: '600px', marginBottom: '2rem' }}>
                  Hệ thống AI Affiliate của bạn đã sẵn sàng. Giao diện mới sử dụng React + Vanilla CSS mang lại trải nghiệm mượt mà và tối ưu nhất.
                </p>
                <button className="glow-btn" style={{ display: 'inline-flex', alignItems: 'center', gap: '8px' }} onClick={() => setActivePage('editor')}>
                  <span className="icon">rocket_launch</span>
                  Bắt đầu sản xuất
                </button>
              </div>
            </div>
            
            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: '2rem' }}>
              {stats ? [
                {label: 'Tài khoản', value: `${stats.total_nicks}`, icon: 'group', color: '#9333ea'}, 
                {label: 'Sản lượng', value: `${stats.videos_created}`, icon: 'movie', color: '#3b82f6'},
                {label: 'Dung lượng', value: `${stats.total_size_mb} MB`, icon: 'sd_storage', color: '#10b981'},
                {label: 'Lượt AI', value: `${stats.ai_used_today}/${stats.ai_limit}`, icon: 'psychology', color: '#f59e0b'}
              ].map(stat => (
                <div key={stat.label} className="glass-card" style={{ padding: '2rem', display: 'flex', flexDirection: 'column', gap: '1rem' }}>
                   <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
                      <div style={{ width: '48px', height: '48px', borderRadius: '12px', background: `${stat.color}20`, color: stat.color, display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
                         <span className="icon">{stat.icon}</span>
                      </div>
                      <span style={{ fontSize: '11px', fontWeight: 800, color: 'var(--text-muted)', textTransform: 'uppercase', letterSpacing: '0.1em' }}>{stat.label}</span>
                   </div>
                   <h2 style={{ fontSize: '2.5rem', fontWeight: 900 }}>{stat.value}</h2>
                </div>
              )) : (
                <div style={{ gridColumn: 'span 4', textAlign: 'center', padding: '2rem', color: 'var(--text-muted)' }}>
                  <span className="icon animate-spin" style={{ fontSize: '2rem' }}>sync</span>
                  <p style={{ marginTop: '1rem' }}>Đang tải dữ liệu thực tế...</p>
                </div>
              )}
            </div>

            <div className="glass-card" style={{ padding: '2rem' }}>
               <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '1rem' }}>
                 <h3 style={{ fontSize: '1.2rem', fontWeight: 900, display: 'flex', alignItems: 'center', gap: '8px' }}>
                   <span className="icon">video_library</span> Video đã tạo ({videos.length})
                 </h3>
                 {videos.length > 0 && (
                   <div style={{ display: 'flex', gap: '8px' }}>
                     <button className="glow-btn" style={{ background: 'rgba(255,255,255,0.1)', color: 'white', padding: '6px 12px', fontSize: '12px' }} onClick={() => setSelectedVideos(selectedVideos.size === videos.length ? new Set() : new Set(videos.map(v => v.path)))}>
                       <span className="icon" style={{ fontSize: '14px' }}>{selectedVideos.size === videos.length ? 'deselect' : 'select_all'}</span> {selectedVideos.size === videos.length ? 'Bỏ chọn' : 'Chọn tất cả'}
                     </button>
                     {selectedVideos.size > 0 ? (
                       <button className="glow-btn" style={{ background: 'rgba(239,68,68,0.2)', color: '#ef4444', border: '1px solid rgba(239,68,68,0.5)', padding: '6px 12px', fontSize: '12px' }} onClick={() => handleDelete('selected')}>
                         <span className="icon" style={{ fontSize: '14px' }}>delete</span> Xoá {selectedVideos.size} video
                       </button>
                     ) : (
                       <button className="glow-btn" style={{ background: 'rgba(239,68,68,0.2)', color: '#ef4444', border: '1px solid rgba(239,68,68,0.5)', padding: '6px 12px', fontSize: '12px' }} onClick={() => handleDelete('all')}>
                         <span className="icon" style={{ fontSize: '14px' }}>delete_forever</span> Xoá tất cả
                       </button>
                     )}
                   </div>
                 )}
               </div>
               {videos.length === 0 ? (
                 <p style={{ color: 'var(--text-muted)' }}>Chưa có video nào. Hãy dùng Editor để tạo video!</p>
               ) : (
                 <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(200px, 1fr))', gap: '1rem' }}>
                   {videos.map(v => (
                     <div key={v.path} style={{ background: selectedVideos.has(v.path) ? 'rgba(var(--primary-rgb), 0.2)' : 'rgba(0,0,0,0.3)', border: selectedVideos.has(v.path) ? '1px solid var(--primary)' : '1px solid transparent', borderRadius: '12px', padding: '1rem', display: 'flex', flexDirection: 'column', gap: '8px', position: 'relative', transition: 'all 0.2s' }}>
                       <div style={{ position: 'absolute', top: '8px', left: '8px', zIndex: 2 }}>
                         <input type="checkbox" checked={selectedVideos.has(v.path)} onChange={(e) => toggleSelect(v.path, e as any)} style={{ width: '18px', height: '18px', cursor: 'pointer' }} />
                       </div>
                       <button style={{ position: 'absolute', top: '8px', right: '8px', background: 'rgba(0,0,0,0.6)', border: 'none', color: '#ef4444', borderRadius: '50%', width: '28px', height: '28px', display: 'flex', alignItems: 'center', justifyContent: 'center', cursor: 'pointer', zIndex: 2 }} onClick={(e) => { e.stopPropagation(); handleDelete(v.path); }}>
                         <span className="icon" style={{ fontSize: '16px' }}>delete</span>
                       </button>
                       <div style={{ width: '100%', aspectRatio: '9/16', background: v.cover ? `url(/media/${v.cover}) center/cover` : 'var(--bg-card)', borderRadius: '8px', display: 'flex', alignItems: 'center', justifyContent: 'center', cursor: 'pointer', position: 'relative', overflow: 'hidden' }} onClick={() => setPreviewVideo(v.path)}>
                         <span className="icon" style={{ fontSize: '32px', color: 'var(--primary)', zIndex: 1 }}>play_circle</span>
                         <div style={{ position: 'absolute', top: 0, left: 0, width: '100%', height: '100%', background: 'linear-gradient(to bottom, rgba(0,0,0,0.2), rgba(0,0,0,0.6))' }}></div>
                       </div>
                       <p style={{ fontSize: '12px', fontWeight: 800, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{v.name}</p>
                       <p style={{ fontSize: '11px', color: 'var(--text-muted)' }}>{v.size_mb} MB • {v.created}</p>
                     </div>
                   ))}
                 </div>
               )}
            </div>
          </div>

          {previewVideo && (
            <div style={{ position: 'fixed', top: 0, left: 0, width: '100vw', height: '100vh', background: 'rgba(0,0,0,0.9)', zIndex: 9999, display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
               <button style={{ position: 'absolute', top: '2rem', right: '2rem', background: 'transparent', border: 'none', color: 'white', cursor: 'pointer', display: 'flex', alignItems: 'center', gap: '8px', fontSize: '1.2rem', fontWeight: 800 }} onClick={() => setPreviewVideo(null)}>
                 <span className="icon" style={{ fontSize: '2rem' }}>close</span> Đóng
               </button>
               <video src={`/media/${previewVideo}`} controls autoPlay style={{ height: '85vh', maxWidth: '90vw', borderRadius: '16px', boxShadow: '0 20px 50px rgba(0,0,0,0.5)' }} />
            </div>
          )}

          <div style={{ display: activePage === 'editor' ? 'block' : 'none', height: '100%' }}>
            <Editor />
          </div>
          
          <div style={{ display: activePage === 'factory' ? 'block' : 'none', height: '100%' }}>
            <Factory />
          </div>

          <div style={{ display: activePage === 'nicks' ? 'block' : 'none', height: '100%' }}>
            <NicksManager />
          </div>

          <div style={{ display: activePage === 'uploader' ? 'block' : 'none', height: '100%' }}>
            <Uploader />
          </div>
        </div>
      </main>
    </div>
  )
}

export default App
