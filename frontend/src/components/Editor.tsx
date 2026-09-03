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

  const [ideaInputValue, setIdeaInputValue] = useState('');
  const [selectedIdeaId, setSelectedIdeaId] = useState<number | null>(null);
  const [ideaFormat, setIdeaFormat] = useState('');
  const [scriptMode, setScriptMode] = useState(() => localStorage.getItem('editor_script_mode') || 'viral');
  const [textOnly, setTextOnly] = useState(() => localStorage.getItem('editor_text_only') === '1');
  const [wordCap, setWordCap] = useState(() => Number(localStorage.getItem('editor_word_cap')) || 65);
  const [ideaBank, setIdeaBank] = useState<any[]>([]);
  const [isSuggesting, setIsSuggesting] = useState(false);

  const [scenePrompts, setScenePrompts] = useState<any[]>([]);
  const [isGeneratingScenes, setIsGeneratingScenes] = useState(false);
  const [copiedSceneIndex, setCopiedSceneIndex] = useState<number | null>(null);
  const [recommendedDuration, setRecommendedDuration] = useState<number | null>(null);

  const [publishKit, setPublishKit] = useState<any>(null);
  const [isGeneratingKit, setIsGeneratingKit] = useState(false);

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

  const fetchIdeaBank = () =>
    fetch(`/api/ideas?status=new&mode=${scriptMode}`).then(r => r.json()).then(d => setIdeaBank(d.ideas || []))
      .catch(() => showToast('⚠️ Không tải được ngân hàng ý tưởng'));

  const handleSuggestIdeas = async () => {
    setIsSuggesting(true);
    try {
      const res = await fetch('/api/ideas/generate', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ format: ideaFormat, mode: scriptMode })
      });
      const data = await res.json();
      if (data.error) {
        alert(data.error);
      } else {
        fetchIdeaBank();
      }
    } catch (e: any) {
      alert('Lỗi gợi ý ý tưởng: ' + e.message);
    } finally {
      setIsSuggesting(false);
    }
  };

  const handleUseIdea = (idea: any) => {
    setIdeaInputValue(idea.text);
    setSelectedIdeaId(idea.id);
  };

  const handleSkipIdea = (id: number) =>
    fetch(`/api/ideas/${id}/status`, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ status: 'skipped' }) })
      .then(() => fetchIdeaBank())
      .catch(() => showToast('⚠️ Cập nhật ý tưởng thất bại'));

  const handleGenerateScenePrompts = async () => {
    if (!script.trim()) { alert('Vui lòng nhập/tạo kịch bản trước.'); return; }
    setIsGeneratingScenes(true);
    try {
      const res = await fetch('/api/scene-prompts/generate', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ script })
      });
      const data = await res.json();
      if (data.error) alert(data.error);
      else {
        setScenePrompts(data.scenes || []);
        setRecommendedDuration(data.recommended_duration_sec || null);
      }
    } catch (e: any) {
      alert('Lỗi sinh prompt cảnh: ' + e.message);
    } finally {
      setIsGeneratingScenes(false);
    }
  };

  const handleCopyScenePrompt = (index: number, prompt: string) => {
    navigator.clipboard.writeText(prompt).then(() => {
      setCopiedSceneIndex(index);
      setTimeout(() => setCopiedSceneIndex(null), 1500);
    });
  };

  const handleGeneratePublishKit = async (scriptText: string) => {
    if (!scriptText.trim()) return;
    setIsGeneratingKit(true);
    try {
      const res = await fetch('/api/publish-kit/generate', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ script: scriptText })
      });
      const data = await res.json();
      if (data.error) showToast('⚠️ ' + data.error);
      else setPublishKit(data);
    } catch (e: any) {
      showToast('⚠️ Không sinh được caption: ' + e.message);
    } finally {
      setIsGeneratingKit(false);
    }
  };

  const uploadBg = async (files: FileList) => {
    try {
      const fd = new FormData();
      // Gửi kèm lastModified (thời điểm file được tải về máy) — server dùng nó đặt lại mtime,
      // nếu không thì mtime thành giờ upload và thứ tự cảnh bị sai.
      Array.from(files).forEach(f => {
        fd.append('images', f);
        fd.append('last_modified', String(f.lastModified || 0));
      });
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

  /** Đổi chỗ 2 cảnh rồi chốt cứng thứ tự vào tên file (1_, 2_, 3_...). */
  const moveBg = async (index: number, direction: -1 | 1) => {
    const target = index + direction;
    if (target < 0 || target >= bgFiles.length) return;
    const next = [...bgFiles];
    [next[index], next[target]] = [next[target], next[index]];
    setBgFiles(next); // cập nhật ngay cho mượt, sau đó server trả về danh sách chuẩn
    try {
      const res = await fetch('/api/images/reorder', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ order: next })
      });
      const d = await res.json();
      if (d.error) showToast('⚠️ ' + d.error);
    } catch (e: any) {
      showToast('⚠️ Đổi thứ tự thất bại: ' + e.message);
    }
    fetchBgFiles();
  };

  const deleteMusic = (name: string) =>
    fetch('/api/music/delete', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ filenames: [name] }) })
      .then(() => fetchMusicFiles())
      .catch(() => showToast('⚠️ Xoá file thất bại'));

  useEffect(() => {
    fetchBgFiles();
    fetchMusicFiles();
  }, []);

  // Ngân hàng ý tưởng phải khớp với mode kịch bản đang chọn (viral/affiliate/digital_aff),
  // nên tải lại mỗi khi đổi mode để không hiện ý tưởng lệch tông với kịch bản sắp sinh.
  useEffect(() => {
    fetchIdeaBank();
  }, [scriptMode]);

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
        // Sinh sẵn caption + hashtag ngay khi render xong — người dùng chỉ việc copy, khỏi
        // phải bấm thêm bước nào trước khi sang TikTok đăng.
        handleGeneratePublishKit(script);
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
      const res = await fetch('/api/script/generate', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ idea: ideaInputValue, idea_id: selectedIdeaId, mode: scriptMode, word_cap: wordCap })
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
          setSelectedIdeaId(null);
          fetchIdeaBank();
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
      {/* Cột 1: Cấu hình (đặt 1 lần, ít khi đổi) */}
      <div style={{ width: '300px', display: 'flex', flexDirection: 'column', gap: '1.5rem', overflowY: 'auto', paddingRight: '10px' }}>
        <div className="glass-card" style={{ padding: '1.5rem', display: 'flex', flexDirection: 'column', gap: '1rem' }}>
          <h3 style={{ fontSize: '11px', fontWeight: 800, textTransform: 'uppercase', letterSpacing: '0.1em', color: 'var(--primary)' }}>
            Cấu hình · Giọng đọc AI
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
          <h3 style={{ fontSize: '11px', fontWeight: 800, textTransform: 'uppercase', letterSpacing: '0.1em', color: '#f59e0b' }}>
            Cấu hình · Nhạc Nền BGM
          </h3>
          <select id="music_mode_select" className="input-field" style={{ cursor: 'pointer' }}
                  defaultValue={localStorage.getItem('editor_music_mode') || "ai_local"}
                  onChange={(e) => localStorage.setItem('editor_music_mode', e.target.value)}>
            <option value="ai_local">AI Tự chọn nhạc hợp Mood</option>
            <option value="manual">Không dùng nhạc / Tuỳ chỉnh</option>
          </select>
          <p style={{ fontSize: '10px', color: 'var(--text-muted)', lineHeight: 1.4, margin: 0 }}>
            Khớp mood theo <b>tên file</b> — đặt tên có từ khoá tiếng Anh liên quan (vd <code>calm_piano.mp3</code>,
            <code>upbeat_motivation.mp3</code>) để chọn đúng hơn. Không file nào khớp thì chọn ngẫu nhiên trong thư viện.
          </p>

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

      {/* Cột 2: Quy trình làm video, Bước 1 -> 3 theo thứ tự từ trên xuống */}
      <div style={{ flex: 1, minWidth: 0, display: 'flex', flexDirection: 'column', gap: '1.5rem' }}>
        <div className="glass-card" style={{ padding: '1.5rem', display: 'flex', flexDirection: 'column', gap: '1rem', position: 'relative' }}>
           <h3 style={{ fontSize: '11px', fontWeight: 800, textTransform: 'uppercase', letterSpacing: '0.1em', color: 'var(--primary)', margin: 0 }}>
             Bước 1 · Ý tưởng &amp; Kịch bản
           </h3>
           <div style={{ display: 'flex', gap: '1rem', alignItems: 'center' }}>
             <input
               id="idea_input"
               type="text"
               className="input-field"
               placeholder="Nhập chủ đề video (VD: mẹo bảo quản hành lá...) hoặc để trống để AI tự nghĩ"
               style={{ flex: 1, border: 'none', background: 'transparent', fontSize: '1rem' }}
               value={ideaInputValue}
               onChange={(e) => { setIdeaInputValue(e.target.value); setSelectedIdeaId(null); }}
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

           <div style={{ display: 'flex', gap: '8px', alignItems: 'center' }}>
             <label style={{ fontSize: '11px', color: 'var(--text-muted)', flexShrink: 0 }}>Chế độ kịch bản:</label>
             <select className="input-field" style={{ fontSize: '12px', flex: '0 0 260px', cursor: 'pointer' }}
                     value={scriptMode}
                     onChange={(e) => { setScriptMode(e.target.value); localStorage.setItem('editor_script_mode', e.target.value); }}>
               <option value="viral">Sự thật/Tâm lý (GĐ1 — xây follower, khuyến nghị)</option>
               <option value="affiliate">Affiliate sản phẩm vật lý (GĐ2 — cần quay thật)</option>
               <option value="digital_aff">Affiliate sản phẩm số (app/dịch vụ — không cần quay)</option>
             </select>
           </div>

           {/* Trần độ dài kịch bản — đòn bẩy chính cho tỉ lệ xem hết (TikTok 2026 cần ~70%) */}
           <div style={{ display: 'flex', gap: '10px', alignItems: 'center', flexWrap: 'wrap' }}>
             <label style={{ fontSize: '11px', color: 'var(--text-muted)', flexShrink: 0 }}>
               Độ dài kịch bản:
             </label>
             <input
               type="range" min={25} max={120} step={5} value={wordCap}
               onChange={(e) => { const v = Number(e.target.value); setWordCap(v); localStorage.setItem('editor_word_cap', String(v)); }}
               style={{ flex: '0 0 180px', cursor: 'pointer', accentColor: 'var(--primary)' }}
             />
             <span style={{ fontSize: '12px', fontWeight: 800, color: 'var(--primary)', minWidth: '116px' }}>
               {/* Ước lượng phải khớp TARGET_LO/TARGET_HI ở app.py (0.80-0.95 lần trần), không
                   lấy thẳng trần — nếu không nhãn sẽ hứa dài hơn video thật khá nhiều. */}
               {wordCap} từ ≈ {Math.round(wordCap * 0.875 * 5 / 20)}s
             </span>
             <span style={{ fontSize: '10px', color: wordCap <= 70 ? '#10b981' : '#f59e0b', lineHeight: 1.4, flex: 1, minWidth: '200px' }}>
               {wordCap <= 70
                 ? '✅ Video ngắn → dễ đạt mốc ~70% xem hết, thuật toán dễ đẩy tiếp.'
                 : '⚠️ Video dài khó đạt mốc ~70% xem hết mà TikTok 2026 yêu cầu — chỉ dùng khi nội dung thật sự cần giải thích dài.'}
             </span>
           </div>

           <div style={{ display: 'flex', gap: '8px', alignItems: 'center' }}>
             {scriptMode === 'viral' && (
               <select className="input-field" style={{ fontSize: '12px', flex: '0 0 200px', cursor: 'pointer' }}
                       value={ideaFormat} onChange={(e) => setIdeaFormat(e.target.value)}>
                 <option value="">Định dạng bất kỳ</option>
                 <option value="listicle">Listicle đếm số</option>
                 <option value="before_after">Trước/Sau nhận thức</option>
                 <option value="myth_busting">Myth-busting / Sai lầm</option>
                 <option value="countdown_hook">Đếm ngược giữ chân</option>
                 <option value="relatable_moment">Khoảnh khắc đồng cảm</option>
                 <option value="reply_comment">Reply-to-comment</option>
               </select>
             )}
             <button className="glow-btn" style={{ fontSize: '12px', padding: '8px 16px', display: 'flex', alignItems: 'center', gap: '6px' }}
                     onClick={handleSuggestIdeas} disabled={isSuggesting}>
               {isSuggesting ? <span className="icon animate-spin">sync</span> : <span className="icon">lightbulb</span>}
               {isSuggesting ? 'Đang gợi ý...' : 'Gợi ý ý tưởng'}
             </button>
           </div>

           {ideaBank.length > 0 && (
             <div style={{ maxHeight: '220px', overflowY: 'auto', overflowX: 'hidden', display: 'flex', flexDirection: 'column', gap: '4px', minWidth: 0 }}>
               {ideaBank.map(idea => (
                 <div key={idea.id} style={{ display: 'flex', alignItems: 'flex-start', gap: '6px', padding: '6px 10px', background: 'rgba(255,255,255,0.05)', borderRadius: '8px', minWidth: 0 }}>
                   <span className="icon" style={{ fontSize: '14px', color: 'var(--primary)', flexShrink: 0, marginTop: '2px' }}>lightbulb</span>
                   <span
                     onClick={() => handleUseIdea(idea)}
                     title="Bấm để dùng ý tưởng này"
                     style={{
                       fontSize: '12px', flex: 1, minWidth: 0, cursor: 'pointer', lineHeight: 1.4,
                       display: '-webkit-box', WebkitLineClamp: 2, WebkitBoxOrient: 'vertical', overflow: 'hidden',
                     }}
                   >
                     {idea.format ? `[${idea.format}] ` : ''}{idea.text}
                   </span>
                   <button onClick={() => handleSkipIdea(idea.id)} title="Bỏ qua ý tưởng này" style={{ background: 'none', border: 'none', color: '#ef4444', cursor: 'pointer', padding: '2px', display: 'flex', flexShrink: 0 }}>
                     <span className="icon" style={{ fontSize: '14px' }}>close</span>
                   </button>
                 </div>
               ))}
             </div>
           )}

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
                <span style={{ fontSize: '11px', fontWeight: 800, textTransform: 'uppercase', letterSpacing: '0.1em', color: 'var(--text-muted)' }}>Kịch bản (sửa tay được)</span>
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

        <div className="glass-card" style={{ padding: '1.5rem', display: 'flex', flexDirection: 'column', gap: '1rem', minWidth: 0 }}>
          <h3 style={{ fontSize: '11px', fontWeight: 800, textTransform: 'uppercase', letterSpacing: '0.1em', color: '#3b82f6' }}>
            Bước 2 · Trợ lý Hoạt hình Veo (thủ công)
          </h3>
          <p style={{ fontSize: '11px', color: 'var(--text-muted)', lineHeight: 1.5, margin: 0 }}>
            Sinh sẵn prompt tiếng Anh cho từng cảnh, dán vào Google Flow để tạo video bằng Veo (dùng credit gói Gemini Pro của bạn) —
            audio bật hay tắt trong Flow đều được, không ảnh hưởng credit (đã kiểm chứng thực tế với cả Omni Flash lẫn Veo 3.1) — app chỉ lấy HÌNH từ clip bạn upload, không dùng tiếng gốc trong clip (âm thanh cuối luôn là giọng TTS + nhạc nền riêng của bạn), nên cứ để tuỳ ý,
            tải video về, đặt tên file bắt đầu bằng số thứ tự cảnh (vd <code>1_...</code>, <code>2_...</code>), rồi upload vào mục
            "Media Nền" ngay bên dưới — app tự sắp thứ tự cảnh theo thời gian tải file về máy, sai thì chỉnh bằng mũi tên ↑↓.
          </p>
          <div style={{ display: 'flex', gap: '8px' }}>
            <button
              className="glow-btn"
              style={{ background: 'rgba(59,130,246,0.15)', border: '1px solid rgba(59,130,246,0.4)', color: '#3b82f6', fontSize: '12px', padding: '8px 16px', display: 'flex', alignItems: 'center', gap: '6px' }}
              onClick={() => window.open('https://flow.google', '_blank')}
            >
              <span className="icon" style={{ fontSize: '16px' }}>open_in_new</span>
              Mở Google Flow
            </button>
            <button
              className="glow-btn"
              style={{ fontSize: '12px', padding: '8px 16px', display: 'flex', alignItems: 'center', gap: '6px' }}
              onClick={handleGenerateScenePrompts}
              disabled={isGeneratingScenes}
            >
              {isGeneratingScenes ? <span className="icon animate-spin">sync</span> : <span className="icon">movie_filter</span>}
              {isGeneratingScenes ? 'Đang sinh...' : 'Sinh prompt từng cảnh'}
            </button>
          </div>

          {scenePrompts.length > 0 && (
            <>
              {recommendedDuration && (
                <div style={{ padding: '8px 10px', background: 'rgba(251,191,36,0.1)', border: '1px solid rgba(251,191,36,0.3)', borderRadius: '8px', fontSize: '11px', lineHeight: 1.5 }}>
                  ⏱️ Mỗi cảnh nên dài <strong>{recommendedDuration} giây</strong> — đã ghép sẵn câu "Video duration: {recommendedDuration} seconds." vào cuối mỗi prompt bên dưới, cứ copy nguyên cả đoạn dán vào Flow là đủ, không cần nói thêm gì nữa.
                </div>
              )}
              <div style={{ maxHeight: '260px', overflowY: 'auto', overflowX: 'hidden', display: 'flex', flexDirection: 'column', gap: '8px', minWidth: 0 }}>
              {scenePrompts.map((scene) => (
                <div key={scene.index} style={{ padding: '8px 10px', background: 'rgba(59,130,246,0.08)', borderRadius: '8px', minWidth: 0 }}>
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '4px' }}>
                    <span style={{ fontSize: '10px', fontWeight: 800, color: '#3b82f6' }}>
                      CẢNH {scene.index} — tên file gợi ý: {scene.index}_canh.mp4
                    </span>
                    <button
                      onClick={() => handleCopyScenePrompt(scene.index, scene.prompt)}
                      style={{ background: 'none', border: '1px solid rgba(59,130,246,0.4)', color: '#3b82f6', cursor: 'pointer', padding: '2px 8px', borderRadius: '6px', fontSize: '10px', flexShrink: 0 }}
                    >
                      {copiedSceneIndex === scene.index ? '✅ Đã copy' : '📋 Copy'}
                    </button>
                  </div>
                  <p style={{
                    fontSize: '12px', margin: 0, lineHeight: 1.4, color: 'var(--text-primary, #eee)',
                    display: '-webkit-box', WebkitLineClamp: 3, WebkitBoxOrient: 'vertical', overflow: 'hidden',
                  }}>
                    {scene.prompt}
                  </p>
                </div>
              ))}
              </div>
            </>
          )}
        </div>

        <div className="glass-card" style={{ padding: '1.5rem', display: 'flex', flexDirection: 'column', gap: '1rem' }}>
          <h3 style={{ fontSize: '11px', fontWeight: 800, textTransform: 'uppercase', letterSpacing: '0.1em', color: '#10b981' }}>
            Bước 3 · Media Nền — thứ tự cảnh
          </h3>
          <label style={{ display: 'flex', alignItems: 'flex-start', gap: '8px', cursor: 'pointer',
                          padding: '10px 12px', borderRadius: '8px',
                          background: textOnly ? 'rgba(168,85,247,0.14)' : 'rgba(255,255,255,0.04)',
                          border: `1px solid ${textOnly ? 'rgba(168,85,247,0.5)' : 'var(--border-subtle)'}` }}>
            <input type="checkbox" checked={textOnly} style={{ marginTop: '2px', cursor: 'pointer' }}
              onChange={(e) => { setTextOnly(e.target.checked); localStorage.setItem('editor_text_only', e.target.checked ? '1' : '0'); }} />
            <span style={{ fontSize: '11px', lineHeight: 1.5 }}>
              <b>Chế độ chữ động</b> — nền gradient chuyển màu, chữ to giữa khung.
              <span style={{ color: 'var(--text-muted)' }}> Không cần tạo clip Veo, bỏ qua toàn bộ Bước 2 và phần upload bên dưới. Render ~20 giây.</span>
            </span>
          </label>
          <p style={{ fontSize: '11px', color: 'var(--text-muted)', lineHeight: 1.5, margin: 0 }}>
            Upload clip vừa tạo ở Bước 2.
            Danh sách dưới đây hiển thị <b>đúng thứ tự cảnh sẽ được render</b> — dùng mũi tên ↑↓ để sửa
            nếu sai.
          </p>

          {/* Upload background */}
          <input ref={bgInputRef} type="file" multiple accept=".mp4,.mov,.avi,.mkv,.webm,.jpg,.jpeg,.png,.webp" style={{ display: 'none' }}
            onChange={e => { if (e.target.files?.length) uploadBg(e.target.files); e.target.value = ''; }} />
          <button className="glow-btn" style={{ background: 'rgba(16,185,129,0.15)', border: '1px solid rgba(16,185,129,0.4)', color: '#10b981', padding: '8px', fontSize: '12px', display: 'flex', alignItems: 'center', gap: '6px', width: '100%', justifyContent: 'center' }}
            onClick={() => bgInputRef.current?.click()}>
            <span className="icon" style={{ fontSize: '16px' }}>upload_file</span>
            Upload video/ảnh nền
          </button>

          {bgFiles.length > 0 && (
            <div style={{ maxHeight: '160px', overflowY: 'auto', display: 'flex', flexDirection: 'column', gap: '4px' }}>
              {bgFiles.map((name, i) => (
                <div key={name} style={{ display: 'flex', alignItems: 'center', gap: '6px', padding: '4px 8px', background: 'rgba(255,255,255,0.05)', borderRadius: '6px' }}>
                  <span style={{
                    flexShrink: 0, width: '18px', height: '18px', borderRadius: '5px',
                    background: 'rgba(16,185,129,0.2)', color: '#10b981',
                    fontSize: '10px', fontWeight: 900,
                    display: 'flex', alignItems: 'center', justifyContent: 'center'
                  }}>{i + 1}</span>
                  <span style={{ fontSize: '11px', flex: 1, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{name}</span>
                  <button onClick={() => moveBg(i, -1)} disabled={i === 0} title="Lên trước 1 cảnh"
                    style={{ background: 'none', border: 'none', color: i === 0 ? 'var(--text-muted)' : '#10b981', cursor: i === 0 ? 'default' : 'pointer', opacity: i === 0 ? 0.3 : 1, padding: 0, display: 'flex' }}>
                    <span className="icon" style={{ fontSize: '15px' }}>arrow_upward</span>
                  </button>
                  <button onClick={() => moveBg(i, 1)} disabled={i === bgFiles.length - 1} title="Lùi sau 1 cảnh"
                    style={{ background: 'none', border: 'none', color: i === bgFiles.length - 1 ? 'var(--text-muted)' : '#10b981', cursor: i === bgFiles.length - 1 ? 'default' : 'pointer', opacity: i === bgFiles.length - 1 ? 0.3 : 1, padding: 0, display: 'flex' }}>
                    <span className="icon" style={{ fontSize: '15px' }}>arrow_downward</span>
                  </button>
                  <button onClick={() => deleteBg(name)} style={{ background: 'none', border: 'none', color: '#ef4444', cursor: 'pointer', padding: '2px', display: 'flex' }}>
                    <span className="icon" style={{ fontSize: '14px' }}>close</span>
                  </button>
                </div>
              ))}
            </div>
          )}
        </div>
      </div>

      {/* Cột 3: Bước 4 -> 5 — xuất video rồi đăng */}
      <div style={{ width: '350px', display: 'flex', flexDirection: 'column', gap: '1.5rem', height: '100%' }}>
         <div className="glass-card" style={{ flex: 1, padding: '1.5rem', display: 'flex', flexDirection: 'column', gap: '1rem', position: 'relative' }}>
            <h3 style={{ fontSize: '11px', fontWeight: 800, textTransform: 'uppercase', letterSpacing: '0.1em', color: 'var(--primary)' }}>
               Bước 4 · Preview & Xuất Video
            </h3>
            
            <div style={{ width: '100%', aspectRatio: '9/16', flexShrink: 0, background: 'var(--bg-card)', borderRadius: '12px', border: '1px solid var(--border-subtle)', overflow: 'hidden', display: 'flex', alignItems: 'center', justifyContent: 'center', marginTop: '1rem' }}>
               {pipelineStatus?.output_file ? (
                 <video src={`/media/${pipelineStatus.output_file}`} controls autoPlay style={{ width: '100%', height: '100%', objectFit: 'contain', background: '#000' }} />
               ) : (
                 <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', color: 'var(--text-muted)' }}>
                    <span className="icon" style={{ fontSize: '3rem', opacity: 0.5, marginBottom: '8px' }}>movie</span>
                    <span style={{ fontSize: '11px' }}>Chưa có video</span>
                 </div>
               )}
            </div>

            {pipelineStatus?.output_file && !pipelineStatus?.running && (
              <div style={{ padding: '1rem', borderRadius: '12px', background: 'rgba(16,185,129,0.08)', border: '1px solid rgba(16,185,129,0.25)', display: 'flex', flexDirection: 'column', gap: '0.75rem' }}>
                <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
                  <h3 style={{ fontSize: '11px', fontWeight: 800, textTransform: 'uppercase', letterSpacing: '0.1em', color: '#10b981', margin: 0 }}>
                    Bước 5 · Đăng lên TikTok
                  </h3>
                  <button
                    onClick={() => handleGeneratePublishKit(script)}
                    disabled={isGeneratingKit}
                    title="Sinh lại caption khác"
                    style={{ background: 'transparent', border: 'none', color: '#10b981', cursor: isGeneratingKit ? 'wait' : 'pointer', display: 'flex', alignItems: 'center', padding: 0 }}
                  >
                    <span className="icon" style={{ fontSize: '16px' }}>{isGeneratingKit ? 'sync' : 'refresh'}</span>
                  </button>
                </div>

                {/* B1: tải video + ảnh bìa. Nhạc trending chỉ gắn được bằng APP điện thoại
                    (web không có "Add sound"), nên hướng chính là chuyển file sang điện thoại. */}
                <div style={{ display: 'flex', gap: '6px' }}>
                  <a
                    href={`/media/${pipelineStatus.output_file}`}
                    download
                    style={{ flex: 1, display: 'flex', alignItems: 'center', justifyContent: 'center', gap: '6px', padding: '10px 8px', borderRadius: '8px', background: 'rgba(255,255,255,0.06)', border: '1px solid var(--border-subtle)', color: 'var(--text-main)', textDecoration: 'none', fontSize: '12px', fontWeight: 700 }}
                  >
                    <span className="icon" style={{ fontSize: '16px', color: '#10b981' }}>download</span>
                    1. Tải video
                  </a>
                  <a
                    href={`/media/${pipelineStatus.output_file.replace(/\.mp4$/, '_cover.jpg')}`}
                    download
                    title="Ảnh bìa sinh sẵn — đặt làm cover khi đăng"
                    style={{ flex: 1, display: 'flex', alignItems: 'center', justifyContent: 'center', gap: '6px', padding: '10px 8px', borderRadius: '8px', background: 'rgba(255,255,255,0.06)', border: '1px solid var(--border-subtle)', color: 'var(--text-main)', textDecoration: 'none', fontSize: '12px', fontWeight: 700 }}
                  >
                    <span className="icon" style={{ fontSize: '16px', color: '#10b981' }}>image</span>
                    Ảnh bìa
                  </a>
                </div>

                {/* B2: caption + hashtag sinh sẵn, copy 1 chạm */}
                <div>
                  <div style={{ fontSize: '10px', fontWeight: 800, color: 'var(--text-muted)', textTransform: 'uppercase', letterSpacing: '0.08em', marginBottom: '6px' }}>
                    2. Caption + hashtag
                  </div>
                  {isGeneratingKit && !publishKit ? (
                    <div style={{ fontSize: '11px', color: 'var(--text-muted)', padding: '10px 0' }}>Đang sinh caption...</div>
                  ) : publishKit ? (
                    <>
                      <div style={{ fontSize: '12px', lineHeight: 1.5, background: 'rgba(0,0,0,0.25)', borderRadius: '8px', padding: '10px', border: '1px solid var(--border-subtle)', whiteSpace: 'pre-wrap', maxHeight: '120px', overflowY: 'auto' }}>
                        {publishKit.full_caption}
                      </div>
                      <button
                        onClick={() => navigator.clipboard.writeText(publishKit.full_caption).then(() => showToast('✅ Đã copy caption + hashtag'))}
                        style={{ marginTop: '6px', width: '100%', padding: '8px', borderRadius: '8px', background: 'rgba(16,185,129,0.15)', border: '1px solid rgba(16,185,129,0.3)', color: '#10b981', cursor: 'pointer', fontSize: '11px', fontWeight: 800, display: 'flex', alignItems: 'center', justifyContent: 'center', gap: '6px' }}
                      >
                        <span className="icon" style={{ fontSize: '14px' }}>content_copy</span>
                        COPY CAPTION + HASHTAG
                      </button>
                    </>
                  ) : (
                    <button
                      onClick={() => handleGeneratePublishKit(script)}
                      style={{ width: '100%', padding: '8px', borderRadius: '8px', background: 'rgba(255,255,255,0.06)', border: '1px solid var(--border-subtle)', color: 'var(--text-main)', cursor: 'pointer', fontSize: '11px', fontWeight: 700 }}
                    >
                      Sinh caption + hashtag
                    </button>
                  )}
                </div>

                {/* B3: mở thẳng trang upload TikTok */}
                <a
                  href="https://www.tiktok.com/tiktokstudio/upload"
                  target="_blank"
                  rel="noopener noreferrer"
                  style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', gap: '8px', padding: '10px 12px', borderRadius: '8px', background: 'rgba(16,185,129,0.15)', border: '1px solid rgba(16,185,129,0.3)', color: '#10b981', textDecoration: 'none', fontSize: '12px', fontWeight: 800 }}
                >
                  <span className="icon" style={{ fontSize: '16px' }}>open_in_new</span>
                  3. MỞ TIKTOK ĐỂ ĐĂNG
                </a>

                {/* Checklist cài đặt bắt buộc — sai 1 trong số này là bóp reach hoặc vi phạm chính sách */}
                <div style={{ fontSize: '11px', lineHeight: 1.7, color: 'var(--text-muted)', borderTop: '1px solid rgba(16,185,129,0.15)', paddingTop: '8px' }}>
                  <div style={{ fontWeight: 800, color: '#f59e0b', marginBottom: '4px' }}>⚠️ Bật khi đăng:</div>
                  <div>• <strong style={{ color: 'var(--text-main)' }}>Quyền riêng tư = Everyone</strong> — để "Only me" thì không ai xem được, 0 view.</div>
                  <div>• <strong style={{ color: 'var(--text-main)' }}>Nhãn AI (AI-generated content)</strong> — bắt buộc vì dùng giọng AI. Tự bật thì gần như không mất reach; để TikTok tự phát hiện thì mất reach nặng + có thể bị phạt.</div>
                  <div>• <strong style={{ color: 'var(--text-main)' }}>Ảnh bìa</strong>: chọn "Tải lên" rồi chọn file <code>_cover.jpg</code> vừa tải ở trên. Sửa bìa sau khi đăng chỉ được trong <strong style={{ color: 'var(--text-main)' }}>7 ngày</strong>.</div>
                  <div>• <strong style={{ color: 'var(--text-main)' }}>Vị trí</strong>: Hà Nội hoặc TP.HCM. <strong style={{ color: 'var(--text-main)' }}>Giờ vàng</strong>: 11–13h hoặc 18–21h.</div>
                  <div>• Cho phép <strong style={{ color: 'var(--text-main)' }}>bình luận / duet / stitch</strong>. Đăng <strong style={{ color: 'var(--text-main)' }}>1–2 video/ngày</strong>.</div>
                  <div style={{ marginTop: '4px', color: '#f59e0b' }}>🎵 Muốn gắn <strong>nhạc trending</strong> thì phải đăng bằng <strong>APP điện thoại</strong> (web không có "Add sound"), và nên chọn "Không dùng nhạc" ở phần BGM để tránh chồng 2 lớp nhạc.</div>
                </div>
              </div>
            )}

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
                      music_mode,
                      music_volume,
                      text_only: textOnly
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
