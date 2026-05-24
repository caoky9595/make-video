import React, { useState, useEffect } from 'react';
import { api } from '../api';
import { useJobPolling } from '../hooks/useJobPolling';

export const Uploader: React.FC = () => {
  const [queue, setQueue] = useState<any[]>(() => {
    const saved = localStorage.getItem('uploadQueue');
    return saved ? JSON.parse(saved) : [];
  });
  
  const [videos, setVideos] = useState<any[]>([]);
  const [nicks, setNicks] = useState<any>({});
  
  const [videoPath, setVideoPath] = useState('');
  const [nickName, setNickName] = useState('');
  const [title, setTitle] = useState('');
  const [productId, setProductId] = useState('');
  
  const { status, startJob } = useJobPolling();

  useEffect(() => {
    localStorage.setItem('uploadQueue', JSON.stringify(queue));
  }, [queue]);

  useEffect(() => {
    api.get('/affiliate/videos').then(setVideos).catch(()=>{});
    api.get('/nicks').then(setNicks).catch(()=>{});
  }, []);

  const handleAdd = () => {
    if (!videoPath || !nickName) { alert('Chọn video và nick!'); return; }
    const tags = title.match(/#[^\s#]+/g)?.map(t => t.replace('#', '')) || ["fyp", "viral"];
    const job = { video_path: videoPath, nick_name: nickName, product_id: productId, title, tags };
    setQueue([...queue, job]);
    setVideoPath(''); setTitle(''); setProductId('');
  };

  const handleStartQueue = async () => {
    if (queue.length === 0) return;
    try {
      const res = await api.post('/affiliate/upload_queue', { jobs: queue });
      if (res.job_id) {
        startJob(res.job_id);
        setQueue([]); // Clear local queue as it is now running on server
      }
    } catch (e: any) { alert(e.message); }
  };

  const handleScheduleQueue = async () => {
    if (queue.length === 0) return;
    try {
      const res = await api.post('/affiliate/schedule', { jobs: queue });
      alert(res.message);
      setQueue([]);
    } catch(e: any) { alert(e.message); }
  };

  return (
    <div style={{ display: 'flex', gap: '2rem', height: '100%' }}>
      {/* Upload Form */}
      <div style={{ width: '400px', display: 'flex', flexDirection: 'column', gap: '1.5rem' }}>
        <div className="glass-card" style={{ padding: '2rem', display: 'flex', flexDirection: 'column', gap: '1rem' }}>
           <h3 style={{ fontSize: '1.2rem', fontWeight: 900, marginBottom: '0.5rem', display: 'flex', alignItems: 'center', gap: '8px' }}>
             <span className="icon">add_task</span> Thêm vào hàng đợi
           </h3>
           
           <div>
             <label style={{ display: 'block', fontSize: '11px', fontWeight: 800, textTransform: 'uppercase', color: 'var(--text-muted)', marginBottom: '8px' }}>Chọn Video</label>
             <select className="input-field" value={videoPath} onChange={e => setVideoPath(e.target.value)}>
               <option value="">-- Chọn video đã render --</option>
               {videos.map(v => <option key={v.path} value={v.path}>{v.name} ({v.size_mb}MB)</option>)}
             </select>
           </div>
           
           <div>
             <label style={{ display: 'block', fontSize: '11px', fontWeight: 800, textTransform: 'uppercase', color: 'var(--text-muted)', marginBottom: '8px' }}>Chọn Tài Khoản</label>
             <select className="input-field" value={nickName} onChange={e => setNickName(e.target.value)}>
               <option value="">-- Chọn nick đăng tải --</option>
               {Object.entries(nicks).map(([name, data]: any) => 
                 data.status !== 'banned' && <option key={name} value={name}>{name} ({data.status})</option>
               )}
             </select>
           </div>

           <div>
             <label style={{ display: 'block', fontSize: '11px', fontWeight: 800, textTransform: 'uppercase', color: 'var(--text-muted)', marginBottom: '8px' }}>Caption & Hashtag</label>
             <textarea className="input-field" value={title} onChange={e => setTitle(e.target.value)} rows={3} placeholder="Sự thật tâm lý học phần 1 #tamlyhoc #fyp" style={{ resize: 'none' }}></textarea>
           </div>

           <div>
             <label style={{ display: 'block', fontSize: '11px', fontWeight: 800, textTransform: 'uppercase', color: 'var(--text-muted)', marginBottom: '8px' }}>ID Sản phẩm (Affiliate)</label>
             <input type="text" className="input-field" value={productId} onChange={e => setProductId(e.target.value)} placeholder="Nhập ID nếu có gắn giỏ hàng" />
           </div>

           <button className="glow-btn" onClick={handleAdd} style={{ marginTop: '0.5rem', display: 'flex', alignItems: 'center', justifyContent: 'center', gap: '8px' }}>
             <span className="icon">queue</span> THÊM VÀO QUEUE
           </button>
        </div>
      </div>

      {/* Queue List */}
      <div style={{ flex: 1, display: 'flex', flexDirection: 'column' }}>
        <div className="glass-card" style={{ flex: 1, padding: '2rem', display: 'flex', flexDirection: 'column' }}>
           <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '1.5rem' }}>
             <div>
               <h3 style={{ fontSize: '1.2rem', fontWeight: 900, display: 'flex', alignItems: 'center', gap: '8px' }}>
                 <span className="icon">list_alt</span> Danh sách chờ đăng
               </h3>
               <p style={{ color: 'var(--text-muted)', fontSize: '12px' }}>{queue.length} video trong hàng đợi (Lưu tự động)</p>
             </div>
             <div style={{ display: 'flex', gap: '8px' }}>
                <button onClick={handleScheduleQueue} disabled={status?.running || queue.length === 0} style={{ padding: '10px 16px', background: 'rgba(59,130,246,0.1)', border: '1px solid rgba(59,130,246,0.3)', color: '#3b82f6', borderRadius: '8px', cursor: 'pointer', fontWeight: 800, fontSize: '11px', textTransform: 'uppercase', display: 'flex', alignItems: 'center', gap: '4px' }}>
                  <span className="icon" style={{ fontSize: '16px' }}>schedule</span> Lên lịch
                </button>
                <button onClick={handleStartQueue} disabled={status?.running || queue.length === 0} style={{ padding: '10px 16px', background: 'var(--primary)', border: 'none', color: 'white', borderRadius: '8px', cursor: 'pointer', fontWeight: 800, fontSize: '11px', textTransform: 'uppercase', display: 'flex', alignItems: 'center', gap: '4px' }}>
                  <span className="icon" style={{ fontSize: '16px' }}>play_arrow</span> Chạy ngay
                </button>
             </div>
           </div>

           {status && (
             <div style={{ marginBottom: '1.5rem', padding: '1rem', borderRadius: '12px', background: 'rgba(255,255,255,0.05)', border: '1px solid var(--border-subtle)' }}>
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

           <div style={{ flex: 1, overflowY: 'auto', display: 'flex', flexDirection: 'column', gap: '12px' }}>
              {queue.length === 0 ? (
                <div style={{ flex: 1, display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', opacity: 0.3 }}>
                  <span className="icon" style={{ fontSize: '64px', marginBottom: '1rem' }}>inventory_2</span>
                  <p style={{ fontWeight: 800, textTransform: 'uppercase', letterSpacing: '0.1em' }}>Queue trống</p>
                </div>
              ) : queue.map((job, idx) => (
                <div key={idx} style={{ padding: '16px', background: 'rgba(0,0,0,0.3)', borderRadius: '12px', border: '1px solid var(--border-subtle)', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                  <div>
                    <p style={{ fontSize: '13px', fontWeight: 800 }}>Tài khoản: <span style={{ color: '#10b981' }}>{job.nick_name}</span></p>
                    <p style={{ fontSize: '11px', color: 'var(--text-muted)', marginTop: '4px' }}>{job.video_path.split(/[\\/]/).pop()}</p>
                    <p style={{ fontSize: '11px', color: 'var(--text-muted)' }}>Caption: {job.title}</p>
                    {job.product_id && <p style={{ fontSize: '11px', color: '#f59e0b', fontWeight: 700, marginTop: '4px' }}>ID Sản phẩm: {job.product_id}</p>}
                  </div>
                  <button onClick={() => setQueue(queue.filter((_, i) => i !== idx))} style={{ background: 'transparent', border: 'none', color: '#ef4444', cursor: 'pointer', opacity: 0.5 }}>
                    <span className="icon">delete</span>
                  </button>
                </div>
              ))}
           </div>
        </div>
      </div>
    </div>
  );
};
