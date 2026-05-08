/**
 * VideoMaker Pro - Frontend Logic
 * Kết nối giao diện web với Flask API backend
 */
// Use same-origin API to avoid hardcoded-port conflicts (e.g. AirPlay on :5000).
const API = '/api';

// ============================================================
// VOICES
// ============================================================
let selectedVoice = 'hoaimy';
let voicesData = [];
let selectedVideos = [];
let allVideos = [];
let uploadedImages = [];
let musicLibrary = [];
let selectedMusicFile = '';
let currentMusicPreview = null;

function parseTimeToSeconds(raw) {
  const value = String(raw || '').trim();
  if (!value) return 0;

  // Support plain seconds: "75" -> 75s
  if (/^\d+(\.\d+)?$/.test(value)) {
    return Math.max(0, Number(value));
  }

  // Support mm:ss and hh:mm:ss
  const parts = value.split(':').map((x) => x.trim());
  if (parts.some((x) => x === '' || !/^\d+$/.test(x))) {
    return NaN;
  }

  if (parts.length === 2) {
    const mm = Number(parts[0]);
    const ss = Number(parts[1]);
    if (ss >= 60) return NaN;
    return mm * 60 + ss;
  }

  if (parts.length === 3) {
    const hh = Number(parts[0]);
    const mm = Number(parts[1]);
    const ss = Number(parts[2]);
    if (mm >= 60 || ss >= 60) return NaN;
    return hh * 3600 + mm * 60 + ss;
  }

  return NaN;
}

async function loadVoices() {
  try {
    const r = await fetch(`${API}/voices`);
    voicesData = await r.json();
    renderVoiceCards();
  } catch(e) { console.log('API offline'); }
}

function renderVoiceCards() {
  const container = document.getElementById('voiceGrid');
  if (!container) return;
  container.innerHTML = '';
  voicesData.forEach(v => {
    const active = v.id === selectedVoice;
    const card = document.createElement('div');
    card.className = `glass-card rounded-xl p-3 flex flex-col items-center gap-2 cursor-pointer transition-all ${active ? 'border-2 border-purple-500 shadow-[0_0_20px_rgba(124,58,237,0.3)]' : 'hover:border-white/20'}`;
    card.innerHTML = `
      <div class="w-10 h-10 rounded-full ${v.gender==='Nữ'?'bg-purple-500/20':'bg-blue-500/20'} flex items-center justify-center">
        <span class="material-symbols-outlined ${v.gender==='Nữ'?'text-purple-400':'text-blue-400'}">${v.gender==='Nữ'?'face_3':'face'}</span>
      </div>
      <span class="text-xs font-bold">${v.name}</span>
      <div class="flex gap-1 flex-wrap justify-center">
        <span class="text-[9px] px-1.5 py-0.5 bg-white/5 rounded-md">${v.gender} ${v.region}</span>
        <span class="text-[9px] px-1.5 py-0.5 ${v.engine==='FPT.AI'?'bg-purple-500/20 text-purple-300':'bg-green-500/20 text-green-300'} rounded-md">${v.engine}</span>
      </div>`;
    card.onclick = () => { selectedVoice = v.id; renderVoiceCards(); showToast(`Đã chọn: ${v.name}`); };
    container.appendChild(card);
  });
}

async function previewVoice(voiceId) {
  showToast('Đang tạo audio preview...');
  try {
    const r = await fetch(`${API}/tts/preview`, {
      method:'POST', headers:{'Content-Type':'application/json'},
      body: JSON.stringify({ voice: voiceId || selectedVoice, text: 'Xin chào, đây là giọng đọc mẫu của tôi.' })
    });
    if (!r.ok) throw new Error('TTS failed');
    const blob = await r.blob();
    const url = URL.createObjectURL(blob);
    const audio = new Audio(url);
    audio.play();
    showToast('▶️ Đang phát...');
  } catch(e) { showToast('❌ Lỗi preview: ' + e.message); }
}

// ============================================================
// SCRIPT EDITOR
// ============================================================
async function loadScript() {
  const ta = document.getElementById('scriptArea');
  if (!ta) return;
  try {
    const r = await fetch(`${API}/script/load`);
    const d = await r.json();
    ta.value = d.text;
    updateCharCount(d.chars);
  } catch(e) {}
}

async function saveScript() {
  const ta = document.getElementById('scriptArea');
  if (!ta) return;
  try {
    const r = await fetch(`${API}/script/save`, {
      method:'POST', headers:{'Content-Type':'application/json'},
      body: JSON.stringify({ text: ta.value })
    });
    const d = await r.json();
    updateCharCount(d.chars);
    showToast('✅ Đã lưu kịch bản!');
  } catch(e) { showToast('❌ Lỗi lưu: ' + e.message); }
}

async function generateScript() {
  const ideaInput = document.getElementById('ideaInput');
  const ta = document.getElementById('scriptArea');
  if (!ideaInput || !ta) return;
  
  const idea = ideaInput.value.trim();
  if (!idea) { showToast('❌ Vui lòng nhập ý tưởng!'); return; }
  
  const btn = document.getElementById('btnGenerate');
  if (btn) btn.innerHTML = '<span class="material-symbols-outlined animate-spin text-sm">sync</span> Đang tạo...';
  
  try {
    const r = await fetch(`${API}/script/generate`, {
      method:'POST', headers:{'Content-Type':'application/json'},
      body: JSON.stringify({ idea })
    });
    const d = await r.json();
    if (d.error) throw new Error(d.error);
    
    ta.value = d.text;
    updateCharCount(d.text.length);
    saveScript();
    showToast('✨ Đã tạo kịch bản thành công!');
  } catch(e) { 
    showToast('❌ Lỗi: ' + e.message); 
  } finally {
    if (btn) btn.innerHTML = '<span class="material-symbols-outlined text-sm">auto_awesome</span> Tạo bằng AI';
  }
}

function updateCharCount(count) {
  const el = document.getElementById('charCount');
  if (el) el.textContent = `${count} ký tự`;
  const timeEl = document.getElementById('estTime');
  if (timeEl) timeEl.textContent = `~${Math.round(count/17)}s`;
}

// ============================================================
// PIPELINE
// ============================================================
let pollInterval = null;

async function startPipeline() {
  const ta = document.getElementById('scriptArea');
  if (ta && ta.value.trim().length < 10) { showToast('❌ Kịch bản quá ngắn!'); return; }
  
  // Save script first
  if (ta) await saveScript();

  const speedEl = document.getElementById('speedSlider');
  const rate = speedEl ? `${speedEl.value >= 0 ? '+' : ''}${Math.round(speedEl.value * 20)}%` : '+20%';
  
  const styleEl = document.getElementById('subtitleStyle');
  const style = styleEl ? parseInt(styleEl.value) : 1;

  const posEls = document.querySelectorAll('[data-pos]');
  let position = 'bottom';
  posEls.forEach(el => { if (el.classList.contains('bg-purple-500/20') || el.classList.contains('active-pos')) position = el.dataset.pos; });

  const visualModeEl = document.getElementById('visualMode');
  const visualMode = visualModeEl ? visualModeEl.value : 'pexels';
  if (visualMode === 'uploaded' && uploadedImages.length === 0) {
    showToast('❌ Bạn chọn chỉ dùng ảnh upload nhưng chưa thêm ảnh nào.');
    return;
  }

  const startSecEl = document.getElementById('musicStartSec');
  const musicOffsetSec = startSecEl ? parseTimeToSeconds(startSecEl.value) : 0;
  const musicModeEl = document.getElementById('musicMode');
  const musicMode = musicModeEl ? musicModeEl.value : 'manual';
  const musicVolumeEl = document.getElementById('musicVolumeSlider');
  const musicVolume = musicVolumeEl ? Math.min(1, Math.max(0, Number(musicVolumeEl.value || 22) / 100)) : 0.22;

  if (!Number.isFinite(musicOffsetSec)) {
    showToast('❌ Thời gian nhạc không hợp lệ. Dùng định dạng mm:ss (VD: 01:30).');
    return;
  }

  if (musicMode === 'manual' && !selectedMusicFile && !musicLibrary.length) {
    showToast('ℹ️ Chưa có nhạc thư viện, video sẽ render không có BGM.');
  }

  showToast('🚀 Bắt đầu pipeline...');
  const pContainer = document.getElementById('progressContainer');
  const vContainer = document.getElementById('videoPreviewContainer');
  const bDownload = document.getElementById('btnDownload');
  const eState = document.getElementById('emptyResultState');
  if (pContainer) pContainer.classList.remove('hidden');
  if (vContainer) vContainer.classList.add('hidden');
  if (bDownload) bDownload.classList.add('hidden');
  if (eState) eState.classList.add('hidden');
  
  updateProgress(5, 'Khởi tạo...');

  try {
    const r = await fetch(`${API}/pipeline/start`, {
      method:'POST', headers:{'Content-Type':'application/json'},
      body: JSON.stringify({
        voice: selectedVoice,
        rate,
        style,
        position,
        visual_mode: visualMode,
        uploaded_images: uploadedImages.map(x => x.name),
        music_file: selectedMusicFile || null,
        music_offset_sec: Number.isFinite(musicOffsetSec) ? musicOffsetSec : 0,
        music_volume: Number.isFinite(musicVolume) ? musicVolume : 0.22,
        music_mode: musicMode,
      })
    });
    const d = await r.json();
    if (d.error) { showToast('❌ ' + d.error); return; }
    
    // Start polling
    if (pollInterval) clearInterval(pollInterval);
    pollInterval = setInterval(pollStatus, 1500);
  } catch(e) { showToast('❌ Server offline!'); }
}

let lastOutputFile = '';

async function pollStatus() {
  try {
    const r = await fetch(`${API}/pipeline/status`);
    const d = await r.json();
    updateProgress(d.progress, d.message);
    
    if (!d.running && d.step !== '') {
      clearInterval(pollInterval);
      pollInterval = null;
      if (d.step === 'done') {
        showToast('🎉 Video đã hoàn tất!');
        loadOutputs();
        loadStats();
        
        // Show Video Preview
        const pContainer = document.getElementById('progressContainer');
        const vContainer = document.getElementById('videoPreviewContainer');
        const vPlayer = document.getElementById('resultPlayer');
        const bDownload = document.getElementById('btnDownload');
        const eState = document.getElementById('emptyResultState');
        
        if (pContainer) pContainer.classList.add('hidden');
        if (eState) eState.classList.add('hidden');
        if (vContainer) {
          vContainer.classList.remove('hidden');
          vContainer.classList.add('flex');
        }
        if (bDownload) bDownload.classList.remove('hidden');
        
        if (vPlayer && d.output_file) {
          // output_file is "output/video_xxx.mp4", we need "video_xxx.mp4"
          lastOutputFile = d.output_file.split('/').pop();
          vPlayer.src = `/api/file/${d.output_file}`;
          vPlayer.play();
        }
      } else if (d.error) {
        showToast('❌ ' + d.error);
        const pContainer = document.getElementById('progressContainer');
        const eState = document.getElementById('emptyResultState');
        if (pContainer) pContainer.classList.add('hidden');
        if (eState) eState.classList.remove('hidden');
      }
    }
  } catch(e) {}
}

function downloadVideo() {
  if (!lastOutputFile) return;
  const link = document.createElement('a');
  link.href = `/api/file/output/${lastOutputFile}`;
  link.download = lastOutputFile;
  document.body.appendChild(link);
  link.click();
  document.body.removeChild(link);
}

function keepResult() {
  showToast('✅ Đã lưu video vào thư viện!');
  // Optionally reset to empty state if user wants to create more
  // resetPreviewState();
}

async function discardResult() {
  if (!lastOutputFile) return;
  if (!confirm('Bạn có chắc muốn bỏ video này? File sẽ bị xóa khỏi bộ nhớ.')) return;
  
  try {
    const r = await fetch(`${API}/outputs/delete`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ filenames: [lastOutputFile] })
    });
    const d = await r.json();
    if (d.success) {
      showToast('🗑️ Đã bỏ video thành công!');
      resetPreviewState();
      loadOutputs();
      loadStats();
    }
  } catch(e) { showToast('❌ Lỗi: ' + e.message); }
}

function resetPreviewState() {
  const pContainer = document.getElementById('progressContainer');
  const vContainer = document.getElementById('videoPreviewContainer');
  const vPlayer = document.getElementById('resultPlayer');
  const bDownload = document.getElementById('btnDownload');
  const eState = document.getElementById('emptyResultState');
  
  if (pContainer) pContainer.classList.add('hidden');
  if (vContainer) vContainer.classList.add('hidden');
  if (bDownload) bDownload.classList.add('hidden');
  if (eState) eState.classList.remove('hidden');
  if (vPlayer) {
    vPlayer.pause();
    vPlayer.src = '';
  }
  lastOutputFile = '';
}

function updateProgress(pct, msg) {
  const bar = document.getElementById('progressBar');
  const label = document.getElementById('progressLabel');
  const pctEl = document.getElementById('progressPct');
  if (bar) bar.style.width = pct + '%';
  if (label) label.textContent = msg || '';
  if (pctEl) pctEl.textContent = pct + '%';
}

// ============================================================
// STATS & OUTPUTS
// ============================================================
async function loadStats() {
  try {
    const r = await fetch(`${API}/stats`);
    const d = await r.json();
    const el = (id) => document.getElementById(id);
    if (el('statVideos')) el('statVideos').textContent = d.videos_created;
    if (el('statSize')) el('statSize').textContent = d.total_size_mb + ' MB';
    if (el('fptUsed')) el('fptUsed').textContent = `${d.fpt_chars_used} / ${d.fpt_chars_limit.toLocaleString()} ký tự`;
    if (el('fptBar')) el('fptBar').style.width = (d.fpt_chars_used/d.fpt_chars_limit*100) + '%';
    if (el('fptPct')) el('fptPct').textContent = (d.fpt_chars_used/d.fpt_chars_limit*100).toFixed(1) + '%';
  } catch(e) {}
}

async function loadOutputs() {
  try {
    const r = await fetch(`${API}/outputs`);
    allVideos = await r.json();
    const el = document.getElementById('outputList');
    const actions = document.getElementById('outputActions');
    if (!el) return;
    
    if (allVideos.length === 0) {
      el.innerHTML = `<div class="col-span-full py-20 flex flex-col items-center justify-center text-[#958da1] opacity-50">
        <span class="material-symbols-outlined text-5xl mb-2">video_library</span>
        <p>Chưa có video nào được tạo.</p>
      </div>`;
      if (actions) actions.style.display = 'none';
      return;
    }

    if (actions) actions.style.display = 'flex';
    el.innerHTML = '';
    
    allVideos.forEach(v => {
      const isSelected = selectedVideos.includes(v.name);
      const card = document.createElement('div');
      card.className = `group relative aspect-[9/16] bg-[#1d1a24] rounded-2xl overflow-hidden border-2 transition-all ${isSelected ? 'border-purple-500 ring-4 ring-purple-500/20' : 'border-white/5 hover:border-white/20'}`;
      
      const coverUrl = v.cover ? `/api/file/${v.cover}` : '';
      
      card.innerHTML = `
        <!-- Thumbnail -->
        <div class="absolute inset-0 cursor-pointer" onclick="playVideo('${v.name}')">
          ${v.cover ? `<img src="${coverUrl}" class="w-full h-full object-cover transition-transform group-hover:scale-105">` : `<div class="w-full h-full flex flex-col items-center justify-center gap-2"><span class="material-symbols-outlined text-3xl opacity-20">movie</span><span class="text-[10px] opacity-30">No Cover</span></div>`}
          <div class="absolute inset-0 bg-gradient-to-t from-black/80 via-transparent to-transparent opacity-60 group-hover:opacity-40 transition-opacity"></div>
        </div>
        
        <!-- Selection Checkbox -->
        <div class="absolute top-3 left-3 z-10">
          <div onclick="toggleVideoSelection('${v.name}')" class="w-6 h-6 rounded-md border-2 flex items-center justify-center cursor-pointer transition-all ${isSelected ? 'bg-purple-600 border-purple-600' : 'bg-black/20 border-white/30 hover:border-white/50 backdrop-blur'}">
            ${isSelected ? '<span class="material-symbols-outlined text-white text-lg">check</span>' : ''}
          </div>
        </div>

        <!-- Info Overlay -->
        <div class="absolute bottom-0 left-0 right-0 p-3 pointer-events-none">
          <p class="text-[11px] font-bold truncate">${v.name}</p>
          <p class="text-[9px] text-[#958da1]">${v.size_mb}MB · ${v.created}</p>
        </div>

        <!-- Single Delete Button (Desktop only hover) -->
        <button onclick="deleteSingleVideo('${v.name}')" class="absolute top-3 right-3 w-8 h-8 rounded-lg bg-black/40 backdrop-blur-md text-red-400 opacity-0 group-hover:opacity-100 transition-all flex items-center justify-center hover:bg-red-500 hover:text-white border border-white/10">
          <span class="material-symbols-outlined text-sm">delete</span>
        </button>
      `;
      el.appendChild(card);
    });
    
    updateSelectionUI();
  } catch(e) { console.error('Load outputs failed', e); }
}

function toggleVideoSelection(name) {
  const index = selectedVideos.indexOf(name);
  if (index === -1) {
    selectedVideos.push(name);
  } else {
    selectedVideos.splice(index, 1);
  }
  loadOutputs();
}

function selectAllVideos(select) {
  if (select) {
    selectedVideos = allVideos.map(v => v.name);
  } else {
    selectedVideos = [];
  }
  loadOutputs();
}

function updateSelectionUI() {
  const countEl = document.getElementById('selectedCount');
  if (countEl) countEl.textContent = selectedVideos.length;
}

async function deleteSingleVideo(name) {
  if (!confirm(`Bạn có chắc muốn xóa video "${name}"?`)) return;
  await deleteVideos([name]);
}

async function deleteSelectedVideos() {
  if (selectedVideos.length === 0) return;
  if (!confirm(`Bạn có chắc muốn xóa ${selectedVideos.length} video đã chọn?`)) return;
  await deleteVideos(selectedVideos);
  selectedVideos = [];
}

async function deleteAllVideos() {
  if (!confirm('CẢNH BÁO: Xóa TOÀN BỘ video trong thư viện? Hành động này không thể hoàn tác.')) return;
  try {
    const r = await fetch(`${API}/outputs/delete_all`, { method: 'POST' });
    const d = await r.json();
    if (d.success) {
      showToast('🗑️ Đã xóa toàn bộ thư viện!');
      loadOutputs();
      loadStats();
    }
  } catch(e) { showToast('❌ Lỗi: ' + e.message); }
}

async function deleteVideos(filenames) {
  try {
    const r = await fetch(`${API}/outputs/delete`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ filenames })
    });
    const d = await r.json();
    if (d.success) {
      showToast(`🗑️ Đã xóa ${filenames.length} video!`);
      loadOutputs();
      loadStats();
    }
  } catch(e) { showToast('❌ Lỗi: ' + e.message); }
}

function playVideo(name) {
  const video = allVideos.find(v => v.name === name);
  if (!video) return;
  
  const modal = document.getElementById('videoModal');
  const player = document.getElementById('modalPlayer');
  const title = document.getElementById('modalTitle');
  const info = document.getElementById('modalInfo');
  const dl = document.getElementById('modalDownload');
  
  if (modal && player) {
    modal.classList.remove('hidden');
    modal.classList.add('flex');
    player.src = `/api/file/output/${name}`;
    player.play();
    title.textContent = name;
    info.textContent = `Dung lượng: ${video.size_mb} MB | Ngày tạo: ${video.created}`;
    dl.href = `/api/file/output/${name}`;
  }
}

function closeVideoModal() {
  const modal = document.getElementById('videoModal');
  const player = document.getElementById('modalPlayer');
  if (modal && player) {
    modal.classList.add('hidden');
    modal.classList.remove('flex');
    player.pause();
    player.src = '';
  }
}

async function loadBackgrounds() {
  try {
    const r = await fetch(`${API}/backgrounds`);
    const files = await r.json();
    const el = document.getElementById('bgList');
    if (!el || files.length === 0) return;
    el.innerHTML = '';
    files.forEach((f, i) => {
      const item = document.createElement('div');
      item.className = `aspect-video bg-gray-800 rounded-lg flex items-center justify-center text-xs cursor-pointer border ${i===0?'border-purple-500':'border-white/10 hover:border-purple-500/50'} transition-all`;
      item.innerHTML = `<span>🎥 ${f.name}<br>${f.size_mb}MB</span>`;
      el.appendChild(item);
    });
  } catch(e) {}
}

async function loadUploadedImages() {
  try {
    const r = await fetch(`${API}/images`);
    uploadedImages = await r.json();
    renderUploadedImages();
  } catch (e) {
    uploadedImages = [];
    renderUploadedImages();
  }
}

function renderUploadedImages() {
  const el = document.getElementById('uploadedImageList');
  if (!el) return;

  if (!uploadedImages.length) {
    el.innerHTML = '<p class="text-[11px] text-[#958da1]">Chưa có ảnh upload.</p>';
    return;
  }

  el.innerHTML = '';
  uploadedImages.forEach((img) => {
    const item = document.createElement('div');
    item.className = 'flex items-center gap-2 bg-white/5 rounded-lg px-2 py-1.5';
    item.innerHTML = `
      <img src="/api/file/${img.path}" class="w-8 h-8 rounded object-cover border border-white/10" alt="${img.name}">
      <div class="flex-1 min-w-0">
        <p class="truncate text-[#e8dfee]">${img.name}</p>
        <p class="text-[10px] text-[#958da1]">${img.size_mb} MB</p>
      </div>
      <button class="text-red-400 hover:text-red-300 text-[11px]" data-name="${img.name}">Xóa</button>
    `;

    const deleteBtn = item.querySelector('button[data-name]');
    if (deleteBtn) {
      deleteBtn.onclick = () => deleteUploadedImage(img.name);
    }
    el.appendChild(item);
  });
}

function openImagePicker() {
  const input = document.getElementById('imageUploadInput');
  if (input) input.click();
}

async function handleImageUpload(event) {
  const files = Array.from(event.target.files || []);
  if (!files.length) return;

  const formData = new FormData();
  files.forEach((f) => formData.append('images', f));

  showToast('⏫ Đang upload ảnh...');
  try {
    const r = await fetch(`${API}/images/upload`, { method: 'POST', body: formData });
    const d = await r.json();
    if (!r.ok || d.error) {
      throw new Error(d.error || 'Upload thất bại');
    }
    showToast(`✅ Upload thành công ${d.uploaded.length} ảnh`);
    await loadUploadedImages();
  } catch (e) {
    showToast('❌ ' + e.message);
  } finally {
    event.target.value = '';
  }
}

async function deleteUploadedImage(name) {
  try {
    const r = await fetch(`${API}/images/delete`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ filenames: [name] }),
    });
    const d = await r.json();
    if (!r.ok || d.error) throw new Error(d.error || 'Xóa ảnh thất bại');
    showToast('🗑️ Đã xóa ảnh');
    await loadUploadedImages();
  } catch (e) {
    showToast('❌ ' + e.message);
  }
}

async function loadMusicLibrary() {
  try {
    const r = await fetch(`${API}/music`);
    musicLibrary = await r.json();
    if (selectedMusicFile && !musicLibrary.some(x => x.name === selectedMusicFile)) {
      selectedMusicFile = '';
    }
    renderMusicLibrary();
  } catch (e) {
    musicLibrary = [];
    selectedMusicFile = '';
    renderMusicLibrary();
  }
}

function renderMusicLibrary() {
  const el = document.getElementById('musicLibraryList');
  if (!el) return;

  if (!musicLibrary.length) {
    el.innerHTML = '<p class="text-[11px] text-[#958da1]">Chưa có file nhạc. Bạn có thể upload MP3/WAV/OGG/M4A...</p>';
    return;
  }

  el.innerHTML = '';
  musicLibrary.forEach((track) => {
    const selected = selectedMusicFile === track.name;
    const item = document.createElement('div');
    item.className = `flex items-center gap-2 rounded-lg px-2 py-1.5 border ${selected ? 'bg-purple-500/10 border-purple-400/40' : 'bg-white/5 border-white/10'}`;
    item.innerHTML = `
      <button class="w-5 h-5 rounded-full border text-[10px] flex items-center justify-center ${selected ? 'border-purple-300 text-purple-200' : 'border-white/30 text-transparent'}" data-select="${track.name}">●</button>
      <div class="flex-1 min-w-0">
        <p class="truncate text-[#e8dfee]">${track.name}</p>
        <p class="text-[10px] text-[#958da1]">${track.size_mb} MB</p>
      </div>
      <button class="text-red-400 hover:text-red-300 text-[11px]" data-delete="${track.name}">Xóa</button>
    `;

    const selectBtn = item.querySelector('button[data-select]');
    const deleteBtn = item.querySelector('button[data-delete]');
    if (selectBtn) selectBtn.onclick = () => toggleSelectMusic(track.name);
    if (deleteBtn) deleteBtn.onclick = () => deleteMusicFile(track.name);
    el.appendChild(item);
  });
}

function toggleSelectMusic(name) {
  stopMusicPreview();
  selectedMusicFile = selectedMusicFile === name ? '' : name;
  renderMusicLibrary();
}

function openMusicPicker() {
  const input = document.getElementById('musicUploadInput');
  if (input) input.click();
}

async function handleMusicUpload(event) {
  const files = Array.from(event.target.files || []);
  if (!files.length) return;

  const formData = new FormData();
  files.forEach((f) => formData.append('tracks', f));

  showToast('⏫ Đang upload nhạc...');
  try {
    const r = await fetch(`${API}/music/upload`, { method: 'POST', body: formData });
    const d = await r.json();
    if (!r.ok || d.error) {
      throw new Error(d.error || 'Upload nhạc thất bại');
    }
    if (d.uploaded && d.uploaded.length) {
      selectedMusicFile = d.uploaded[0];
    }
    showToast(`✅ Upload thành công ${d.uploaded.length} file nhạc`);
    await loadMusicLibrary();
  } catch (e) {
    showToast('❌ ' + e.message);
  } finally {
    event.target.value = '';
  }
}

async function deleteMusicFile(name) {
  try {
    if (selectedMusicFile === name) {
      stopMusicPreview();
    }
    const r = await fetch(`${API}/music/delete`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ filenames: [name] }),
    });
    const d = await r.json();
    if (!r.ok || d.error) throw new Error(d.error || 'Xóa nhạc thất bại');
    if (selectedMusicFile === name) {
      selectedMusicFile = '';
    }
    showToast('🗑️ Đã xóa nhạc');
    await loadMusicLibrary();
  } catch (e) {
    showToast('❌ ' + e.message);
  }
}

async function previewSelectedMusic() {
  if (!musicLibrary.length) {
    showToast('❌ Chưa có nhạc trong thư viện để nghe thử.');
    return;
  }

  const targetTrack = selectedMusicFile || musicLibrary[0].name;
  if (!selectedMusicFile) {
    selectedMusicFile = targetTrack;
    renderMusicLibrary();
  }

  const startSecEl = document.getElementById('musicStartSec');
  const offsetSec = startSecEl ? parseTimeToSeconds(startSecEl.value) : 0;
  if (!Number.isFinite(offsetSec)) {
    showToast('❌ Mốc thời gian không hợp lệ. Dùng mm:ss (VD: 01:30).');
    return;
  }

  stopMusicPreview();
  const audioUrl = `/api/file/audio_bg/${encodeURIComponent(targetTrack)}`;
  const player = new Audio(audioUrl);
  currentMusicPreview = player;

  player.addEventListener('loadedmetadata', async () => {
    const safeOffset = Math.max(0, Math.min(offsetSec, Math.max(0, (player.duration || 0) - 0.1)));
    player.currentTime = safeOffset;
    try {
      await player.play();
      showToast(`🎵 Đang nghe thử: ${targetTrack} từ ${startSecEl ? startSecEl.value : '00:00'}`);
    } catch (err) {
      showToast('❌ Không thể phát nhạc preview.');
    }
  }, { once: true });

  player.addEventListener('ended', () => {
    currentMusicPreview = null;
  }, { once: true });
}

function stopMusicPreview() {
  if (!currentMusicPreview) return;
  currentMusicPreview.pause();
  currentMusicPreview.currentTime = 0;
  currentMusicPreview = null;
}

// ============================================================
// TOAST NOTIFICATION
// ============================================================
function showToast(msg) {
  let t = document.getElementById('toast');
  if (!t) {
    t = document.createElement('div');
    t.id = 'toast';
    t.style.cssText = 'position:fixed;bottom:60px;right:24px;background:rgba(30,20,50,0.95);backdrop-filter:blur(20px);border:1px solid rgba(124,58,237,0.3);color:#e8dfee;padding:12px 20px;border-radius:12px;font-size:13px;z-index:9999;transition:all 0.3s;box-shadow:0 4px 20px rgba(0,0,0,0.4);';
    document.body.appendChild(t);
  }
  t.textContent = msg;
  t.style.opacity = '1';
  t.style.transform = 'translateY(0)';
  clearTimeout(t._timer);
  t._timer = setTimeout(() => { t.style.opacity = '0'; t.style.transform = 'translateY(10px)'; }, 3000);
}

// ============================================================
// INIT
// ============================================================
document.addEventListener('DOMContentLoaded', () => {
  // Restore active page
  const savedPage = localStorage.getItem('activePage') || 'dashboard';
  const navItems = document.querySelectorAll('.nav-item');
  let targetNav = navItems[0];
  if (savedPage === 'editor') targetNav = navItems[1];
  if (savedPage === 'settings') targetNav = navItems[2];
  showPage(savedPage, targetNav);
  window.addEventListener('beforeunload', stopMusicPreview);

  loadVoices();
  loadScript();
  loadStats();
  loadOutputs();
  loadBackgrounds();
  loadUploadedImages();
  loadMusicLibrary();

  const imageInput = document.getElementById('imageUploadInput');
  if (imageInput) {
    imageInput.addEventListener('change', handleImageUpload);
  }

  const musicInput = document.getElementById('musicUploadInput');
  if (musicInput) {
    musicInput.addEventListener('change', handleMusicUpload);
  }

  // Auto-save script on typing
  const ta = document.getElementById('scriptArea');
  if (ta) {
    let saveTimer;
    ta.addEventListener('input', () => {
      updateCharCount(ta.value.length);
      clearTimeout(saveTimer);
      saveTimer = setTimeout(saveScript, 2000);
    });
  }

  // Speed slider
  const slider = document.getElementById('speedSlider');
  const speedLabel = document.getElementById('speedLabel');
  if (slider && speedLabel) {
    slider.addEventListener('input', () => {
      const v = parseFloat(slider.value);
      speedLabel.textContent = v === 0 ? '1.0x' : v > 0 ? `${(1+v*0.2).toFixed(1)}x` : `${(1+v*0.2).toFixed(1)}x`;
    });
  }

  const musicVolumeSlider = document.getElementById('musicVolumeSlider');
  const musicVolumeValue = document.getElementById('musicVolumeValue');
  if (musicVolumeSlider && musicVolumeValue) {
    musicVolumeSlider.addEventListener('input', () => {
      musicVolumeValue.textContent = `${musicVolumeSlider.value}%`;
    });
  }
});
