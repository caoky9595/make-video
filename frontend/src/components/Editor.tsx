import React, { useState, useEffect, useRef } from 'react';

export const Editor: React.FC = () => {
  const [script, setScript] = useState(() => localStorage.getItem('editor_script') || '');
  const [isGenerating, setIsGenerating] = useState(false);
  const [genProgress, setGenProgress] = useState(0);
  const [pipelineStatus, setPipelineStatus] = useState<any>(null);
  const [selectedVoice, setSelectedVoice] = useState(() => localStorage.getItem('editor_voice') || 'tiktok_nu_1');
  const [bgFiles, setBgFiles] = useState<string[]>([]);
  const [musicFiles, setMusicFiles] = useState<string[]>([]);
  const bgInputRef = useRef<HTMLInputElement>(null);
  const musicInputRef = useRef<HTMLInputElement>(null);

  const [toast, setToast] = useState<string | null>(null);
  const prevRunningRef = useRef(false);

  const showToast = (msg: string) => {
    setToast(msg);
    setTimeout(() => setToast(null), 5000);
  };

  const fetchBgFiles = () =>
    fetch('/api/images').then(r => r.json()).then(d => setBgFiles((d || []).map((f: any) => f.name || f)))
      .catch(() => showToast('⚠️ Không tải được danh sách background'));

  const fetchMusicFiles = () =>
    fetch('/api/music').then(r => r.json()).then(d => setMusicFiles((d || []).map((f: any) => f.name || f)))
      .catch(() => showToast('⚠️ Không tải được danh sách nhạc'));

  const uploadBg = async (files: FileList) => {
    try {
      const fd = new FormData();
      Array.from(files).forEach(f => fd.append('images', f));
      const res = await fetch('/api/images/upload', { method: 'POST', body: fd });
      const d = await res.json();
      if (d.error) alert(d.error);
      else { showToast(`✅ Đã upload ${d.uploaded?.length || 0} file nền`); fetchBgFiles(); }
    } catch (e: any) {
      alert('Upload thất bại: ' + e.message);
    }
  };

  const uploadMusic = async (files: FileList) => {
    try {
      const fd = new FormData();
      Array.from(files).forEach(f => fd.append('tracks', f));
      const res = await fetch('/api/music/upload', { method: 'POST', body: fd });
      const d = await res.json();
      if (d.error) alert(d.error);
      else { showToast(`✅ Đã upload ${d.uploaded?.length || 0} file nhạc`); fetchMusicFiles(); }
    } catch (e: any) {
      alert('Upload thất bại: ' + e.message);
    }
  };

  const deleteBg = (name: string) =>
    fetch('/api/images/delete', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ filenames: [name] }) })
      .then(() => fetchBgFiles())
      .catch(() => showToast('⚠️ Xoá file thất bại'));

  const deleteMusic = (name: string) =>
    fetch('/api/music/delete', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ filenames: [name] }) })
      .then(() => fetchMusicFiles())
      .catch(() => showToast('⚠️ Xoá file thất bại'));

  useEffect(() => {
    fetchBgFiles();
    fetchMusicFiles();
  }, []);

  // Poll trạng thái: 1s khi đang render, 5s khi rảnh (đỡ spam server)
  useEffect(() => {
    const running = !!pipelineStatus?.running;
    const interval = setInterval(() => {
      fetch('/api/pipeline/status')
        .then(res => res.json())
        .then(data => { if (data) setPipelineStatus(data); })
        .catch(() => {});
    }, running ? 1000 : 5000);
    return () => clearInterval(interval);
  }, [pipelineStatus?.running]);

  // Phát hiện render xong: running true → false
  useEffect(() => {
    const running = !!pipelineStatus?.running;
    if (prevRunningRef.current && !running) {
      if (pipelineStatus?.error) {
        showToast('❌ Tạo video thất bại: ' + pipelineStatus.error);
      } else {
        showToast('🎉 Video đã xuất xong!');
        // Báo App.tsx refresh danh sách video + stats trên dashboard
        window.dispatchEvent(new CustomEvent('video-completed'));
      }
    }
    prevRunningRef.current = running;
  }, [pipelineStatus?.running]);

  const handleGenerate = async () => {
    setIsGenerating(true);
    setGenProgress(10);
    
    // Giả lập thanh tiến trình tăng dần đến 90% trong lúc chờ AI
    const simInterval = setInterval(() => {
      setGenProgress(prev => prev < 90 ? prev + (90 - prev) * 0.1 : prev);
    }, 500);

    try {
      const idea = (document.getElementById('idea_input') as HTMLInputElement).value;
      const res = await fetch('/api/script/generate', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ idea, mode: 'viral' })
      });
      const data = await res.json();
      if (data.error) {
        alert(data.error);
        setGenProgress(0);
      } else if (data.text) {
        setGenProgress(100);
        setTimeout(() => {
          setScript(data.text);
          localStorage.setItem('editor_script', data.text);
        }, 300);
      }
    } catch (e: any) {
      alert('Lỗi: ' + e.message);
      setGenProgress(0);
    } finally {
      clearInterval(simInterval);
      setTimeout(() => {
        setIsGenerating(false);
        setGenProgress(0);
      }, 500);
    }
  };

  return (
    <div style={{ display: 'flex', gap: '2rem', height: '100%' }}>
      {toast && (
        <div style={{
          position: 'fixed', bottom: '2rem', left: '50%', transform: 'translateX(-50%)',
          background: 'rgba(20,20,30,0.95)', border: '1px solid var(--border-subtle)',
          borderRadius: '12px', padding: '12px 24px', zIndex: 10000,
          fontSize: '14px', fontWeight: 700, boxShadow: '0 10px 30px rgba(0,0,0,0.5)',
          backdropFilter: 'blur(10px)'
        }}>
          {toast}
        </div>
      )}
      {/* Cột 1: Tool Panel */}
      <div style={{ width: '300px', display: 'flex', flexDirection: 'column', gap: '1.5rem', overflowY: 'auto', paddingRight: '10px' }}>
        <div className="glass-card" style={{ padding: '1.5rem', display: 'flex', flexDirection: 'column', gap: '1rem' }}>
          <h3 style={{ fontSize: '11px', fontWeight: 800, textTransform: 'uppercase', letterSpacing: '0.1em', color: 'var(--primary)' }}>
            Giọng đọc AI
          </h3>
          <select 
            id="voice_select" 
            className="input-field" 
            style={{ cursor: 'pointer' }}
            value={selectedVoice}
            onChange={(e) => {
              setSelectedVoice(e.target.value);
              localStorage.setItem('editor_voice', e.target.value);
            }}
          >
            <option value="tiktok_nu_1">⭐ TikTok - Giọng Nữ Review (hợp viral)</option>
            <option value="tiktok_nu_2">⭐ TikTok - Giọng Nữ Trẻ</option>
            <option value="tiktok_nam_1">⭐ TikTok - Giọng Nam Bí Ẩn</option>
            <option value="tiktok_nam_2">⭐ TikTok - Giọng Nam Đọc Nhanh</option>
            <option value="banmai">Ban Mai (FPT) - Nữ Bắc trẻ trung</option>
            <option value="thuminh">Thu Minh (FPT) - Nữ Bắc dịu dàng</option>
            <option value="leminh">Lê Minh (FPT) - Nam Bắc trầm ấm</option>
            <option value="myan">Mỹ An (FPT) - Nữ Trung Bộ</option>
            <option value="giahuy">Gia Huy (FPT) - Nam Trung Bộ</option>
            <option value="lannhi">Lan Nhi (FPT) - Nữ Nam Bộ</option>
            <option value="linhsan">Linh San (FPT) - Nữ Nam mềm mại</option>
          </select>
          {selectedVoice.startsWith('tiktok') && (
            <p style={{ fontSize: '10px', color: 'var(--text-muted)', marginTop: '4px', lineHeight: 1.4 }}>
              Giọng TikTok cần <b>TIKTOK_SESSION_ID</b> trong file <code>.env</code>.
              Đăng nhập tiktok.com trên trình duyệt → mở DevTools → Application → Cookies → copy giá trị <code>sessionid</code>.
            </p>
          )}

          <h3 style={{ fontSize: '11px', fontWeight: 800, textTransform: 'uppercase', letterSpacing: '0.1em', color: 'var(--primary)', marginTop: '0.5rem' }}>
            Tốc độ đọc
          </h3>
          <select id="rate_select" className="input-field" style={{ cursor: 'pointer' }}
                  defaultValue={localStorage.getItem('editor_rate') || "+50%"}
                  onChange={(e) => localStorage.setItem('editor_rate', e.target.value)}>
            <option value="+0%">Bình thường (0%)</option>
            <option value="+10%">Nhanh nhẹ (+10%)</option>
            <option value="+20%">Nhanh (+20%)</option>
            <option value="+50%">Nhanh (50% - Mặc định)</option>
          </select>

          <h3 style={{ fontSize: '11px', fontWeight: 800, textTransform: 'uppercase', letterSpacing: '0.1em', color: 'var(--primary)', marginTop: '0.5rem' }}>
            Trình Render Video (Engine)
          </h3>
          <select id="engine_select" className="input-field" style={{ cursor: 'pointer' }}
                  defaultValue={localStorage.getItem('editor_engine') || "moviepy"}
                  onChange={(e) => localStorage.setItem('editor_engine', e.target.value)}>
            <option value="moviepy">MoviePy (Truyền thống)</option>
            <option value="gsap">GSAP + Playwright (Chữ động mượt mà)</option>
          </select>
          
          <h3 style={{ fontSize: '11px', fontWeight: 800, textTransform: 'uppercase', letterSpacing: '0.1em', color: 'var(--primary)', marginTop: '0.5rem' }}>
            Phong cách Phụ đề
          </h3>
          <select id="style_select" className="input-field" style={{ cursor: 'pointer' }}
                  defaultValue={localStorage.getItem('editor_style') || "1"}
                  onChange={(e) => localStorage.setItem('editor_style', e.target.value)}>
            <option value="1">Viral (MrBeast Style - Nảy chữ)</option>
            <option value="2">Minimal (Ali Abdaal Style - Tối giản)</option>
            <option value="3">Marker Box (Highlight nền hộp)</option>
            <option value="4">Typewriter (Đánh máy cổ điển - Chỉ GSAP)</option>
            <option value="5">Aesthetic Elegant (Lora Serif - Chỉ GSAP)</option>
          </select>

          <h3 style={{ fontSize: '11px', fontWeight: 800, textTransform: 'uppercase', letterSpacing: '0.1em', color: 'var(--primary)', marginTop: '0.5rem' }}>
            Vị trí Phụ đề
          </h3>
          <select id="position_select" className="input-field" style={{ cursor: 'pointer' }}
                  defaultValue={localStorage.getItem('editor_position') || "bottom"}
                  onChange={(e) => localStorage.setItem('editor_position', e.target.value)}>
            <option value="center">Giữa màn hình</option>
            <option value="bottom">Dưới cùng</option>
            <option value="top">Trần nhà (Top)</option>
          </select>
        </div>

        <div className="glass-card" style={{ padding: '1.5rem', display: 'flex', flexDirection: 'column', gap: '1rem' }}>
          <h3 style={{ fontSize: '11px', fontWeight: 800, textTransform: 'uppercase', letterSpacing: '0.1em', color: '#10b981' }}>
            Media Nền (Background)
          </h3>
          <select id="visual_select" className="input-field" style={{ cursor: 'pointer' }}
                  defaultValue={localStorage.getItem('editor_visual') || "pexels"}
                  onChange={(e) => localStorage.setItem('editor_visual', e.target.value)}>
            <option value="pexels">Video Lofi/Chill (Youtube/Pexels)</option>
            <option value="mix">Trộn lẫn Video ngẫu nhiên</option>
            <option value="uploaded">Video tự upload (Folder)</option>
            <option value="ai">AI Tự vẽ hình tĩnh (Pollinations)</option>
          </select>
          
          {/* Upload background */}
          <input ref={bgInputRef} type="file" multiple accept=".mp4,.mov,.avi,.mkv,.webm,.jpg,.jpeg,.png,.webp" style={{ display: 'none' }}
            onChange={e => { if (e.target.files?.length) uploadBg(e.target.files); e.target.value = ''; }} />
          <button className="glow-btn" style={{ background: 'rgba(16,185,129,0.15)', border: '1px solid rgba(16,185,129,0.4)', color: '#10b981', padding: '8px', fontSize: '12px', display: 'flex', alignItems: 'center', gap: '6px', width: '100%', justifyContent: 'center' }}
            onClick={() => bgInputRef.current?.click()}>
            <span className="icon" style={{ fontSize: '16px' }}>upload_file</span>
            Upload video/ảnh nền
          </button>

          {bgFiles.length > 0 && (
            <div style={{ maxHeight: '120px', overflowY: 'auto', display: 'flex', flexDirection: 'column', gap: '4px' }}>
              {bgFiles.map(name => (
                <div key={name} style={{ display: 'flex', alignItems: 'center', gap: '6px', padding: '4px 8px', background: 'rgba(255,255,255,0.05)', borderRadius: '6px' }}>
                  <span className="icon" style={{ fontSize: '14px', color: '#10b981', flexShrink: 0 }}>movie</span>
                  <span style={{ fontSize: '11px', flex: 1, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{name}</span>
                  <button onClick={() => deleteBg(name)} style={{ background: 'none', border: 'none', color: '#ef4444', cursor: 'pointer', padding: '2px', display: 'flex' }}>
                    <span className="icon" style={{ fontSize: '14px' }}>close</span>
                  </button>
                </div>
              ))}
            </div>
          )}

          <div>
            <label style={{ fontSize: '11px', color: 'var(--text-muted)' }}>Hoặc tải từ Youtube</label>
            <div style={{ display: 'flex', gap: '8px', marginTop: '4px' }}>
              <input type="text" className="input-field" id="yt_url" placeholder="https://youtube.com/..." style={{ flex: 1, fontSize: '12px' }} />
              <button className="glow-btn" style={{ padding: '8px 12px' }} onClick={() => {
                const url = (document.getElementById('yt_url') as HTMLInputElement).value;
                if (!url) return;
                fetch('/api/background/fetch', { method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify({url}) })
                  .then(() => alert('Đang tải ngầm! Kiểm tra terminal.'));
              }}>
                <span className="icon">download</span>
              </button>
            </div>
          </div>
        </div>

        <div className="glass-card" style={{ padding: '1.5rem', display: 'flex', flexDirection: 'column', gap: '1rem' }}>
          <h3 style={{ fontSize: '11px', fontWeight: 800, textTransform: 'uppercase', letterSpacing: '0.1em', color: '#f59e0b' }}>
            Nhạc Nền BGM
          </h3>
          <select id="music_mode_select" className="input-field" style={{ cursor: 'pointer' }}
                  defaultValue={localStorage.getItem('editor_music_mode') || "ai_local"}
                  onChange={(e) => localStorage.setItem('editor_music_mode', e.target.value)}>
            <option value="ai_local">AI Tự chọn nhạc hợp Mood</option>
            <option value="manual">Không dùng nhạc / Tuỳ chỉnh</option>
          </select>

          <h3 style={{ fontSize: '11px', fontWeight: 800, textTransform: 'uppercase', letterSpacing: '0.1em', color: '#f59e0b', marginTop: '0.5rem' }}>
            Âm lượng Nhạc
          </h3>
          <select id="music_volume_select" className="input-field" style={{ cursor: 'pointer' }}
                  defaultValue={localStorage.getItem('editor_music_volume') || "0.22"}
                  onChange={(e) => localStorage.setItem('editor_music_volume', e.target.value)}>
            <option value="0.1">Rất nhỏ (10%)</option>
            <option value="0.22">Vừa phải (22%)</option>
            <option value="0.5">Lớn (50%)</option>
          </select>

          {/* Upload nhạc */}
          <input ref={musicInputRef} type="file" multiple accept=".mp3,.wav,.ogg,.m4a,.aac,.flac,.webm" style={{ display: 'none' }}
            onChange={e => { if (e.target.files?.length) uploadMusic(e.target.files); e.target.value = ''; }} />
          <button className="glow-btn" style={{ background: 'rgba(245,158,11,0.15)', border: '1px solid rgba(245,158,11,0.4)', color: '#f59e0b', padding: '8px', fontSize: '12px', display: 'flex', alignItems: 'center', gap: '6px', width: '100%', justifyContent: 'center' }}
            onClick={() => musicInputRef.current?.click()}>
            <span className="icon" style={{ fontSize: '16px' }}>audio_file</span>
            Upload nhạc nền (.mp3, .wav...)
          </button>

          {musicFiles.length > 0 && (
            <div style={{ maxHeight: '100px', overflowY: 'auto', display: 'flex', flexDirection: 'column', gap: '4px' }}>
              {musicFiles.map(name => (
                <div key={name} style={{ display: 'flex', alignItems: 'center', gap: '6px', padding: '4px 8px', background: 'rgba(255,255,255,0.05)', borderRadius: '6px' }}>
                  <span className="icon" style={{ fontSize: '14px', color: '#f59e0b', flexShrink: 0 }}>music_note</span>
                  <span style={{ fontSize: '11px', flex: 1, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{name}</span>
                  <button onClick={() => deleteMusic(name)} style={{ background: 'none', border: 'none', color: '#ef4444', cursor: 'pointer', padding: '2px', display: 'flex' }}>
                    <span className="icon" style={{ fontSize: '14px' }}>close</span>
                  </button>
                </div>
              ))}
            </div>
          )}
        </div>
      </div>

      {/* Cột 2: Script Workspace */}
      <div style={{ flex: 1, display: 'flex', flexDirection: 'column', gap: '1.5rem' }}>
        <div className="glass-card" style={{ padding: '1.5rem', display: 'flex', flexDirection: 'column', gap: '1rem', position: 'relative' }}>
           <div style={{ display: 'flex', gap: '1rem', alignItems: 'center' }}>
             <input 
               id="idea_input"
               type="text" 
               className="input-field" 
               placeholder="Nhập chủ đề video (VD: Sự thật tâm lý học về tình yêu...) hoặc để trống để AI tự nghĩ" 
               style={{ flex: 1, border: 'none', background: 'transparent', fontSize: '1rem' }}
             />
             <button 
               className="glow-btn" 
               onClick={handleGenerate}
               style={{ display: 'flex', alignItems: 'center', gap: '8px', padding: '12px 24px' }}
               disabled={isGenerating}
             >
               {isGenerating ? <span className="icon animate-spin">sync</span> : <span className="icon">magic_button</span>}
               {isGenerating ? 'ĐANG TẠO...' : 'AI VIẾT KỊCH BẢN'}
             </button>
           </div>
           {isGenerating && (
             <div style={{ position: 'absolute', bottom: 0, left: 0, width: '100%', height: '3px', background: 'rgba(0,0,0,0.2)', overflow: 'hidden', borderBottomLeftRadius: '12px', borderBottomRightRadius: '12px' }}>
                <div style={{ width: `${Math.round(genProgress)}%`, height: '100%', background: 'var(--grad-primary)', transition: 'width 0.3s ease-out' }}></div>
             </div>
           )}
        </div>

        <div className="glass-card" style={{ flex: 1, padding: '2rem', display: 'flex', flexDirection: 'column', position: 'relative' }}>
           <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '1rem' }}>
             <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                <span style={{ width: '8px', height: '8px', borderRadius: '50%', background: 'var(--primary)' }} className="animate-pulse"></span>
                <span style={{ fontSize: '11px', fontWeight: 800, textTransform: 'uppercase', letterSpacing: '0.1em', color: 'var(--text-muted)' }}>Editor Console</span>
             </div>
             <span style={{ fontSize: '11px', fontWeight: 800, color: 'var(--primary)', background: 'rgba(147,51,234,0.1)', padding: '4px 12px', borderRadius: '12px' }}>
               {script.length} CHARS
             </span>
           </div>
           
           <textarea
             className="input-field"
             value={script}
             onChange={(e) => { setScript(e.target.value); localStorage.setItem('editor_script', e.target.value); }}
             placeholder="Kịch bản sẽ hiển thị ở đây..."
             style={{ 
               flex: 1, resize: 'none', background: 'transparent', border: 'none', 
               fontSize: '1.1rem', lineHeight: 1.6, outline: 'none' 
             }}
           />

        </div>
      </div>

      {/* Cột 3: Preview Panel */}
      <div style={{ width: '350px', display: 'flex', flexDirection: 'column', gap: '1.5rem', height: '100%' }}>
         <div className="glass-card" style={{ flex: 1, padding: '1.5rem', display: 'flex', flexDirection: 'column', gap: '1rem', position: 'relative' }}>
            <h3 style={{ fontSize: '11px', fontWeight: 800, textTransform: 'uppercase', letterSpacing: '0.1em', color: 'var(--primary)' }}>
               Preview & Xuất Video
            </h3>
            
            <div style={{ width: '100%', aspectRatio: '9/16', background: 'var(--bg-card)', borderRadius: '12px', border: '1px solid var(--border-subtle)', overflow: 'hidden', display: 'flex', alignItems: 'center', justifyContent: 'center', marginTop: '1rem' }}>
               {pipelineStatus?.output_file ? (
                 <video src={`/media/${pipelineStatus.output_file}`} controls autoPlay style={{ width: '100%', height: '100%', objectFit: 'contain', background: '#000' }} />
               ) : (
                 <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', color: 'var(--text-muted)' }}>
                    <span className="icon" style={{ fontSize: '3rem', opacity: 0.5, marginBottom: '8px' }}>movie</span>
                    <span style={{ fontSize: '11px' }}>Chưa có video</span>
                 </div>
               )}
            </div>

            <div style={{ flex: 1 }}></div>

            {pipelineStatus && (
               <div style={{ width: '100%', padding: '1rem', borderRadius: '12px', background: 'rgba(255,255,255,0.05)', border: '1px solid var(--border-subtle)', backdropFilter: 'blur(10px)', marginBottom: '1rem' }}>
                  <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '8px' }}>
                     <span style={{ fontSize: '11px', fontWeight: 800, color: pipelineStatus.error ? '#f87171' : 'var(--primary)', textTransform: 'none' }}>
                       {pipelineStatus.error ? pipelineStatus.error : (pipelineStatus.message || 'Đang xử lý...')}
                     </span>
                     <span style={{ fontSize: '11px', fontWeight: 800 }}>{pipelineStatus.progress}%</span>
                  </div>
                  <div style={{ width: '100%', height: '4px', background: 'rgba(0,0,0,0.5)', borderRadius: '4px', overflow: 'hidden' }}>
                     <div style={{ width: `${pipelineStatus.progress}%`, height: '100%', background: pipelineStatus.error ? '#ef4444' : 'var(--grad-primary)', transition: 'width 0.3s' }}></div>
                  </div>
               </div>
            )}

            {pipelineStatus?.running ? (
              <div style={{ display: 'flex', flexDirection: 'column', gap: '0.75rem', width: '100%' }}>
                <button className="glow-btn" disabled style={{ padding: '16px', fontSize: '1.1rem', borderRadius: '12px', display: 'flex', alignItems: 'center', justifyContent: 'center', gap: '8px', opacity: 0.5, width: '100%' }}>
                  <span className="icon">sync</span>
                  ĐANG TẠO VIDEO...
                </button>
                <button className="stop-btn" onClick={() => {
                  if (window.confirm('Bạn có chắc muốn dừng quá trình tạo video hiện tại không?')) {
                    fetch('/api/pipeline/stop', { method: 'POST' })
                      .then(res => res.json())
                      .then(data => {
                        if (data.success) {
                          setPipelineStatus((prev: any) => prev ? { ...prev, running: false, message: '❌ Đã dừng tạo video theo yêu cầu.' } : null);
                        }
                      });
                  }
                }}>
                  <span className="icon">stop_circle</span>
                  HỦY TẠO VIDEO
                </button>
              </div>
            ) : (
              <button className="glow-btn" style={{ padding: '16px', fontSize: '1.1rem', borderRadius: '12px', display: 'flex', alignItems: 'center', justifyContent: 'center', gap: '8px', width: '100%' }} onClick={() => {
                  if(!script.trim()) { alert('Vui lòng nhập kịch bản trước khi xuất video.'); return; }
                  if(pipelineStatus?.running) { alert('Đang có video đang render, vui lòng đợi hoặc huỷ trước.'); return; }
                  const voice = (document.getElementById('voice_select') as HTMLSelectElement).value;
                  const rate = (document.getElementById('rate_select') as HTMLSelectElement).value;
                  const style = parseInt((document.getElementById('style_select') as HTMLSelectElement).value);
                  const position = (document.getElementById('position_select') as HTMLSelectElement).value;
                  const engine = (document.getElementById('engine_select') as HTMLSelectElement).value;
                  const visual = (document.getElementById('visual_select') as HTMLSelectElement).value;
                  const music_mode = (document.getElementById('music_mode_select') as HTMLSelectElement).value;
                  const music_volume = parseFloat((document.getElementById('music_volume_select') as HTMLSelectElement).value);
                  
                  fetch('/api/pipeline/start', {
                    method: 'POST', headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({ 
                      script, 
                      voice, 
                      rate,
                      style, 
                      position,
                      engine,
                      visual_mode: visual, 
                      music_mode,
                      music_volume 
                    })
                  }).then(() => {
                    setPipelineStatus({ running: true, progress: 0, message: "Bắt đầu tiến trình..." });
                  });
               }}>
                  <span className="icon">auto_videocam</span>
                  XUẤT VIDEO NGAY
               </button>
            )}
         </div>
      </div>
    </div>
  );
};
