import React, { useState, useEffect } from 'react';
import { api } from '../api';
import { useJobPolling } from '../hooks/useJobPolling';

export const Factory: React.FC = () => {
  const [url, setUrl] = useState('');
  const [hookText, setHookText] = useState('');
  const { status, startJob } = useJobPolling();
  const [videos, setVideos] = useState<any[]>([]);

  const fetchVideos = async () => {
    try {
      const data = await api.get('/affiliate/videos');
      setVideos(data);
    } catch(e) {}
  };

  useEffect(() => {
    fetchVideos();
  }, []);

  useEffect(() => {
    if (status && !status.running) fetchVideos();
  }, [status?.running]);

  const handleSubmit = async () => {
    if (!url) { alert('Nhập URL!'); return; }
    try {
      const res = await api.post('/affiliate/process', { url, hook: hookText });
      if (res.job_id) startJob(res.job_id);
    } catch (e: any) {
      alert(e.message);
    }
  };

  return (
    <div style={{ display: 'flex', gap: '2rem', height: '100%' }}>
      <div style={{ flex: 1, display: 'flex', flexDirection: 'column', gap: '1.5rem' }}>
         <div className="glass-card" style={{ padding: '2rem', flex: 1 }}>
            <h3 style={{ fontSize: '1.2rem', fontWeight: 900, marginBottom: '1.5rem', display: 'flex', alignItems: 'center', gap: '8px' }}>
              <span className="icon">link</span> Nhập Nguồn Video
            </h3>
            
            <div style={{ display: 'flex', flexDirection: 'column', gap: '1rem' }}>
               <div>
                 <label style={{ display: 'block', fontSize: '11px', fontWeight: 800, textTransform: 'uppercase', color: 'var(--text-muted)', marginBottom: '8px' }}>URL Video (Douyin/TikTok)</label>
                 <input type="text" className="input-field" value={url} onChange={e => setUrl(e.target.value)} placeholder="https://v.douyin.com/..." />
               </div>
               
               <div>
                 <label style={{ display: 'block', fontSize: '11px', fontWeight: 800, textTransform: 'uppercase', color: 'var(--text-muted)', marginBottom: '8px' }}>Text Hook (Tuỳ chọn)</label>
                 <input type="text" className="input-field" value={hookText} onChange={e => setHookText(e.target.value)} placeholder="Nhập câu hook để dán lên đầu video..." />
               </div>

               <button className="glow-btn" onClick={handleSubmit} disabled={status?.running} style={{ marginTop: '1rem', display: 'flex', alignItems: 'center', justifyContent: 'center', gap: '8px', padding: '16px', fontSize: '1.1rem' }}>
                  {status?.running ? <span className="icon animate-spin">sync</span> : <span className="icon">precision_manufacturing</span>}
                  {status?.running ? 'ĐANG XỬ LÝ...' : 'XỬ LÝ VIDEO'}
               </button>

               {status && (
                 <div style={{ marginTop: '1rem', padding: '1rem', borderRadius: '12px', background: 'rgba(255,255,255,0.05)', border: '1px solid var(--border-subtle)' }}>
                    <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '8px' }}>
                       <span style={{ fontSize: '11px', fontWeight: 800, color: status.error ? '#f87171' : 'var(--primary)', textTransform: 'uppercase' }}>
                         {status.error ? 'Lỗi!' : status.message}
                       </span>
                       <span style={{ fontSize: '11px', fontWeight: 800 }}>{status.progress}%</span>
                    </div>
                    <div style={{ width: '100%', height: '4px', background: 'rgba(0,0,0,0.5)', borderRadius: '4px', overflow: 'hidden' }}>
                       <div style={{ width: `${status.progress}%`, height: '100%', background: status.error ? '#ef4444' : 'var(--grad-primary)', transition: 'width 0.3s' }}></div>
                    </div>
                 </div>
               )}
            </div>
         </div>
      </div>

      <div style={{ width: '350px', display: 'flex', flexDirection: 'column' }}>
         <div className="glass-card" style={{ flex: 1, padding: '1.5rem', overflowY: 'auto' }}>
            <h3 style={{ fontSize: '11px', fontWeight: 800, textTransform: 'uppercase', letterSpacing: '0.1em', color: 'var(--text-muted)', marginBottom: '1rem' }}>
               Thư viện Video đã xử lý
            </h3>
            
            <div style={{ display: 'flex', flexDirection: 'column', gap: '12px' }}>
              {videos.length === 0 ? (
                <div style={{ textAlign: 'center', padding: '2rem 0', opacity: 0.5 }}>
                  <span className="icon" style={{ fontSize: '32px', marginBottom: '8px' }}>inbox</span>
                  <p style={{ fontSize: '12px' }}>Chưa có video nào</p>
                </div>
              ) : videos.map((v: any) => (
                <div key={v.name} style={{ padding: '12px', background: 'rgba(0,0,0,0.3)', borderRadius: '12px', border: '1px solid var(--border-subtle)' }}>
                  <p style={{ fontSize: '12px', fontWeight: 700, wordBreak: 'break-all' }}>{v.name}</p>
                  <p style={{ fontSize: '10px', color: 'var(--text-muted)', marginTop: '4px' }}>{v.size_mb} MB • {v.created}</p>
                </div>
              ))}
            </div>
         </div>
      </div>
    </div>
  );
};
