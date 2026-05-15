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
    renderVoiceSelect();
  } catch(e) { console.log('API offline'); }
}

function renderVoiceSelect() {
  const container = document.getElementById('voiceSelect');
  if (!container) return;
  container.innerHTML = '';
  
  // Group voices by engine for better UX
  const engines = [...new Set(voicesData.map(v => v.engine))];
  
  engines.forEach(engine => {
    const group = document.createElement('optgroup');
    group.label = engine;
    
    const engineVoices = voicesData.filter(v => v.engine === engine);
    engineVoices.forEach(v => {
      const opt = document.createElement('option');
      opt.value = v.id;
      opt.textContent = `${v.name} (${v.gender} - ${v.region})`;
      if (v.id === selectedVoice) opt.selected = true;
      group.appendChild(opt);
    });
    container.appendChild(group);
  });

  container.onchange = (e) => {
    selectedVoice = e.target.value;
    const v = voicesData.find(x => x.id === selectedVoice);
    if (v) showToast(`Đã chọn: ${v.name}`);
  };
}

async function suggestViralIdeas() {
  const btn = event.currentTarget;
  const icon = btn.querySelector('.material-symbols-outlined');
  const originalIcon = icon.textContent;
  
  icon.textContent = 'sync';
  icon.classList.add('animate-spin');
  btn.disabled = true;

  try {
    const r = await fetch(`${API}/ideas/generate`);
    const data = await r.json();
    if (data.ideas && data.ideas.length > 0) {
      // Pick a random idea from the suggestions
      const randomIdea = data.ideas[Math.floor(Math.random() * data.ideas.length)];
      const input = document.getElementById('ideaInput');
      input.value = randomIdea;
      input.classList.add('text-purple-300');
      setTimeout(() => input.classList.remove('text-purple-300'), 1000);
      showToast('🪄 AI đã tìm thấy một chủ đề "ngon" cho bạn!');
    }
  } catch (e) {
    showToast('❌ Không thể kết nối với bộ não AI.');
  } finally {
    icon.textContent = originalIcon;
    icon.classList.remove('animate-spin');
    btn.disabled = false;
  }
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
  const originalHtml = btn ? btn.innerHTML : '';
  if (btn) btn.innerHTML = '<span class="material-symbols-outlined animate-spin text-[16px]">sync</span> ĐANG TẠO...';
  
  const scriptMode = document.getElementById('scriptMode')?.value || 'affiliate';
  
  try {
    const r = await fetch(`${API}/script/generate`, {
      method:'POST', headers:{'Content-Type':'application/json'},
      body: JSON.stringify({ idea, mode: scriptMode })
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
    if (btn) btn.innerHTML = originalHtml;
  }
}

function formatDuration(seconds) {
  if (seconds <= 0) return '0s';
  const h = Math.floor(seconds / 3600);
  const m = Math.floor((seconds % 3600) / 60);
  const s = seconds % 60;
  
  let res = '';
  if (h > 0) res += `${h}h `;
  if (m > 0) res += `${m}p `;
  if (s > 0 || res === '') res += `${s}s`;
  return res.trim();
}

function updateCharCount(count) {
  const el = document.getElementById('charCount');
  if (el) el.textContent = count;
  const timeEl = document.getElementById('estTime');
  if (timeEl) {
    const totalSeconds = Math.round(count / 17);
    timeEl.textContent = `~${formatDuration(totalSeconds)}`;
  }
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
  const modeEl = document.getElementById('videoMode');
  const video_mode = modeEl ? modeEl.value : 'realistic';

  const posEls = document.querySelectorAll('[data-pos]');
  let position = 'bottom';
  posEls.forEach(el => { if (el.classList.contains('bg-purple-500/20') || el.classList.contains('active-pos')) position = el.dataset.pos; });

  const visualModeEl = document.getElementById('visualMode');
  const visualMode = visualModeEl ? visualModeEl.value : 'pexels';
  if (visualMode === 'uploaded' && uploadedImages.length === 0) {
    showToast('❌ Bạn chọn chỉ dùng Media upload nhưng chưa thêm file nào.');
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
        video_mode: video_mode,
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
    
    // Core stats
    const elNicks = document.getElementById('stat-nicks');
    const elVideos = document.getElementById('stat-videos');
    const elViews = document.getElementById('stat-views');
    const elIncome = document.getElementById('stat-income');
    const elSize = document.getElementById('statSize');

    if (elNicks) elNicks.innerText = d.total_nicks || 0;
    if (elVideos) elVideos.innerText = d.total_videos || 0;
    if (elViews) elViews.innerText = (d.total_views || 0) + 'K';
    if (elIncome) elIncome.innerText = '$' + (d.total_income || 0);
    if (elSize) elSize.innerHTML = `${d.total_size_mb || '0.0'}<span class="text-lg text-muted/40 ml-1">MB</span>`;

    // AI Quota
    const aiPct = document.getElementById('aiPct');
    const aiBar = document.getElementById('aiBar');
    const aiText = document.getElementById('aiUsedText');
    const aiMarker = document.getElementById('aiPctMarker');
    
    if (aiPct && aiBar && aiText) {
      const pct = Math.round((d.ai_used / d.ai_limit) * 100) || 0;
      aiPct.innerText = pct + '%';
      aiBar.style.width = pct + '%';
      aiText.innerText = `${d.ai_used} / ${d.ai_limit} Requests`;
      if (aiMarker) aiMarker.style.left = pct + '%';
    }

    const fpt = document.getElementById('fptUsed');
    if (fpt) fpt.innerText = `FPT: ${d.fpt_used || 0} / ${d.fpt_limit || 0} CHARS`;

  } catch(e) { console.error("Stats Error:", e); }
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
    el.innerHTML = '<p class="text-[11px] text-[#958da1]">Chưa có file upload.</p>';
    return;
  }

  const IMAGE_EXTS = ['.jpg', '.jpeg', '.png', '.webp'];

  el.innerHTML = '';
  uploadedImages.forEach((img) => {
    const ext = img.name.slice((img.name.lastIndexOf(".") - 1 >>> 0) + 2).toLowerCase();
    const isImage = IMAGE_EXTS.includes('.' + ext);

    const item = document.createElement('div');
    item.className = 'flex items-center gap-2 bg-white/5 rounded-lg px-2 py-1.5';
    item.innerHTML = `
      <div class="w-8 h-8 rounded bg-black/20 flex items-center justify-center border border-white/10 shrink-0 overflow-hidden">
        ${isImage ? `<img src="/api/file/${img.path}" class="w-full h-full object-cover">` : `<span class="material-symbols-outlined text-sm opacity-50">movie</span>`}
      </div>
      <div class="flex-1 min-w-0">
        <p class="truncate text-[#e8dfee] text-[11px]">${img.name}</p>
        <p class="text-[9px] text-[#958da1] uppercase">${isImage ? 'Ảnh' : 'Video'} • ${img.size_mb} MB</p>
      </div>
      <button class="text-red-400 hover:text-red-300 text-[11px] px-1" data-name="${img.name}">Xóa</button>
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

  showToast('⏫ Đang upload Media...');
  try {
    const r = await fetch(`${API}/images/upload`, { method: 'POST', body: formData });
    const d = await r.json();
    if (!r.ok || d.error) {
      throw new Error(d.error || 'Upload thất bại');
    }
    showToast(`✅ Upload thành công ${d.uploaded.length} file`);
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
    if (!r.ok || d.error) throw new Error(d.error || 'Xóa Media thất bại');
    showToast('🗑️ Đã xóa Media');
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

function switchResourceTab(tabName, btn) {
  document.querySelectorAll('.resource-content').forEach(el => el.classList.add('hidden'));
  const target = document.getElementById(`tab-${tabName}`);
  if (target) target.classList.remove('hidden');
  document.querySelectorAll('.resource-tab').forEach(el => el.classList.remove('active'));
  if (btn) btn.classList.add('active');
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

  const aiLimitInput = document.getElementById('cfgAiLimit');
  if (aiLimitInput) {
    aiLimitInput.addEventListener('change', async () => {
      await fetch(`${API}/quota/update`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ limit: aiLimitInput.value })
      });
      loadStats();
    });
  }

  // Init first resource tab
  const firstTab = document.querySelector('.resource-tab');
  if (firstTab) firstTab.click();
});

// ============================================================
// ACCOUNT MANAGER & AUTO UPLOADER
// ============================================================

async function loadNicks() {
  try {
    const r = await fetch(`${API}/nicks`);
    const nicks = await r.json();
    const tbody = document.getElementById('nickTableBody');
    if(!tbody) return;
    
    if (Object.keys(nicks).length === 0) {
      tbody.innerHTML = '<tr><td colspan="5" class="py-12 text-center text-muted text-xs uppercase tracking-widest font-bold">Chưa có nick nào. Thêm nick để bắt đầu.</td></tr>';
      return;
    }
    
    tbody.innerHTML = '';
    for (const [name, data] of Object.entries(nicks)) {
      const statusIcon = {"new":"🆕","warmup":"🔥","active":"✅","paused":"⏸️","banned":"❌"}[data.status] || "❓";
      const statusColor = {"new":"blue","warmup":"orange","active":"green","paused":"gray","banned":"red"}[data.status] || "purple";
      
      tbody.innerHTML += `
        <tr class="hover:bg-white/[0.02] transition-colors group">
          <td class="px-8 py-5">
            <div class="flex items-center gap-4">
              <div class="w-10 h-10 rounded-2xl bg-gradient-to-br from-purple-500/20 to-blue-500/20 border border-white/5 flex items-center justify-center font-black text-white/80">
                ${name.charAt(0).toUpperCase()}
              </div>
              <div>
                <p class="text-xs font-black text-white tracking-tight">${name}</p>
                <p class="text-[10px] text-muted/60 font-medium">${data.username || '@username'}</p>
              </div>
            </div>
          </td>
          <td class="px-8 py-5">
            <div class="space-y-1">
              <p class="text-[10px] font-bold text-white/80 flex items-center gap-1.5">
                <span class="material-symbols-outlined text-[12px] text-blue-400">cloud</span>
                ${data.proxy || 'No Proxy (Direct)'}
              </p>
              <p class="text-[9px] text-muted uppercase tracking-tighter">Chromium Engine v145.x</p>
            </div>
          </td>
          <td class="px-8 py-5">
            <span class="inline-flex items-center gap-1.5 px-3 py-1 rounded-full bg-${statusColor}-500/10 text-${statusColor}-400 text-[10px] font-black uppercase tracking-widest border border-${statusColor}-500/20">
              <span class="w-1.5 h-1.5 rounded-full bg-${statusColor}-500 shadow-[0_0_8px_rgba(var(--${statusColor}-rgb),0.5)]"></span>
              ${data.status}
            </span>
          </td>
          <td class="px-8 py-5 text-center">
            <div class="flex flex-col items-center gap-1">
              <p class="text-xs font-black text-white">${data.videos_today} <span class="text-muted/40 font-medium">/ ${data.total_videos}</span></p>
              <div class="w-16 h-1 bg-white/5 rounded-full overflow-hidden">
                <div class="h-full bg-green-500" style="width: ${Math.min(100, (data.videos_today/5)*100)}%"></div>
              </div>
            </div>
          </td>
          <td class="px-8 py-5 text-right">
            <div class="flex gap-2 justify-end opacity-40 group-hover:opacity-100 transition-opacity">
              <button onclick="loginNick('${name}')" class="h-9 px-4 rounded-xl bg-purple-500 text-white text-[10px] font-black uppercase tracking-widest shadow-lg shadow-purple-500/20 hover:scale-105 active:scale-95 transition-all flex items-center gap-2">
                <span class="material-symbols-outlined text-sm">rocket_launch</span> MỞ BROWSER
              </button>
              <button onclick="deleteNick('${name}')" class="h-9 w-9 flex items-center justify-center rounded-xl bg-red-500/10 text-red-400 hover:bg-red-500 hover:text-white transition-all">
                <span class="material-symbols-outlined text-sm">delete</span>
              </button>
            </div>
          </td>
        </tr>
      `;
    }
  } catch(e) { console.error(e); }
}

async function loginNick(name) {
  showToast(`🚀 Đang mở trình duyệt cho ${name}...`);
  try {
    await fetch(`${API}/nicks/login`, {
      method: 'POST', headers:{'Content-Type':'application/json'},
      body: JSON.stringify({name})
    });
  } catch(e) { showToast('❌ Không thể mở trình duyệt'); }
}

async function submitAddNick() {
  const name = document.getElementById('addNickName').value.trim();
  const username = document.getElementById('addNickUser').value.trim();
  if(!name) { alert("Vui lòng nhập tên nick"); return; }
  
  try {
    const r = await fetch(`${API}/nicks/add`, {
      method: 'POST', headers:{'Content-Type':'application/json'},
      body: JSON.stringify({name, username})
    });
    if(r.ok) {
      document.getElementById('addNickModal').classList.add('hidden');
      document.getElementById('addNickName').value = '';
      document.getElementById('addNickUser').value = '';
      showToast('✅ Đã thêm nick');
      loadNicks();
    }
  } catch(e) { showToast('❌ Thêm nick thất bại'); }
}

async function deleteNick(name) {
  if(!confirm(`Xóa nick ${name}? (Không xóa profile Chrome)`)) return;
  try {
    const r = await fetch(`${API}/nicks/remove`, {
      method: 'POST', headers:{'Content-Type':'application/json'},
      body: JSON.stringify({name})
    });
    if(r.ok) {
      showToast('🗑️ Đã xóa nick');
      loadNicks();
    }
  } catch(e) {}
}

async function loadPlan() {
  try {
    const r = await fetch(`${API}/nicks`);
    const nicks = await r.json();
    const planList = document.getElementById('planList');
    if(!planList) return;
    
    planList.innerHTML = '';
    const today = new Date().toISOString().split('T')[0];
    let count = 0;
    for (const [name, data] of Object.entries(nicks)) {
      if(data.status === 'banned' || data.status === 'paused') continue;
      
      const created = new Date(data.created_at);
      const age_days = (new Date() - created) / (1000*60*60*24);
      let max_videos = age_days < 7 ? 2 : (age_days < 14 ? 3 : 5);
      
      let videos_today = data.videos_today_date === today ? data.videos_today : 0;
      let remaining = Math.max(0, max_videos - videos_today);
      if(remaining > 0) count++;
      
      planList.innerHTML += `
        <div class="bg-black/30 p-4 rounded-2xl border border-white/5 flex items-center justify-between">
          <div>
            <p class="font-bold text-xs text-white">${name}</p>
            <p class="text-[10px] text-muted">Status: ${data.status} | Đã đăng: ${videos_today}/${max_videos}</p>
          </div>
          <div class="w-8 h-8 rounded-full flex items-center justify-center font-black text-xs ${remaining > 0 ? 'bg-purple-500/20 text-purple-400' : 'bg-green-500/20 text-green-400'}">
            ${remaining}
          </div>
        </div>
      `;
    }
    if(count === 0) {
      planList.innerHTML = '<p class="text-xs text-muted/50 text-center py-4">Không còn tác vụ trống hôm nay.</p>';
    }
  } catch(e) {}
}

async function loadFacVideos() {
  try {
    const r = await fetch(`${API}/affiliate/videos`);
    const vids = await r.json();
    const el = document.getElementById('facList');
    if(!el) return;
    if(!vids.length) {
      el.innerHTML = '<div class="col-span-full py-16 flex flex-col items-center justify-center text-muted/30"><span class="material-symbols-outlined text-5xl mb-4">inventory_2</span><p class="font-bold uppercase tracking-widest text-xs">Chưa có video xử lý</p></div>';
      return;
    }
    el.innerHTML = '';
    vids.forEach(v => {
      el.innerHTML += `
        <div class="aspect-[9/16] bg-black/40 rounded-2xl border border-white/5 p-4 flex flex-col justify-end relative overflow-hidden group">
          <div class="absolute inset-0 bg-blue-500/10 opacity-0 group-hover:opacity-100 transition-opacity"></div>
          <div class="relative z-10">
            <p class="text-xs font-bold text-white truncate shadow-black drop-shadow-md">${v.name}</p>
            <p class="text-[10px] text-blue-300 font-medium">${v.size_mb} MB • ${v.created}</p>
          </div>
        </div>
      `;
    });
  } catch(e){}
}

async function loadFacVideosForUpload() {
  try {
    const r = await fetch(`${API}/affiliate/videos`);
    const vids = await r.json();
    const select = document.getElementById('upVideo');
    if(!select) return;
    select.innerHTML = '<option value="">-- Chọn video --</option>';
    vids.forEach(v => {
      select.innerHTML += `<option value="${v.path}">${v.name} (${v.size_mb}MB)</option>`;
    });
  } catch(e){}
}

async function loadNicksForUpload() {
  try {
    const r = await fetch(`${API}/nicks`);
    const nicks = await r.json();
    const select = document.getElementById('upNick');
    if(!select) return;
    select.innerHTML = '<option value="">-- Chọn nick --</option>';
    for (const [name, data] of Object.entries(nicks)) {
      if(data.status !== 'banned') {
         select.innerHTML += `<option value="${name}">${name} (${data.status})</option>`;
      }
    }
  } catch(e){}
}

async function startFactoryProcess() {
  const url = document.getElementById('facUrl').value.trim();
  const hook = document.getElementById('facHook').value.trim();
  const cta = document.getElementById('facCta').value.trim();
  
  if(!url) { alert("Nhập link video Douyin/TikTok!"); return; }
  
  const statusEl = document.getElementById('facStatus');
  statusEl.innerText = "Đang gửi yêu cầu...";
  try {
    const r = await fetch(`${API}/affiliate/process`, {
      method: 'POST', headers:{'Content-Type':'application/json'},
      body: JSON.stringify({url, hook, cta, bg_music: selectedMusicFile || undefined})
    });
    const d = await r.json();
    if(d.error) {
      statusEl.innerText = "Lỗi: " + d.error;
    } else {
      statusEl.innerText = "Đã vào hàng đợi...";
    }
  } catch(e) { statusEl.innerText = "Lỗi kết nối!"; }
}

let uploadQueue = [];

function addToQueue() {
  const video_path = document.getElementById('upVideo').value;
  const nick_name = document.getElementById('upNick').value;
  const product_id = document.getElementById('upProductId').value.trim();
  const title = document.getElementById('upTitle').value;
  
  if(!video_path || !nick_name) { alert("Vui lòng chọn Video và Nick đăng!"); return; }
  
  // Extract file name
  const videoName = video_path.split(/[\\/]/).pop();
  
  // Parse hashtags
  const tags = title.match(/#[^\s#]+/g) ? title.match(/#[^\s#]+/g).map(t => t.replace('#', '')) : ["fyp", "viral"];
  
  uploadQueue.push({
    video_path,
    nick_name,
    product_id,
    title,
    tags
  });
  
  renderQueue();
  
  // Reset fields loosely
  document.getElementById('upProductId').value = '';
}

function renderQueue() {
  const listEl = document.getElementById('queueList');
  const countEl = document.getElementById('queueCount');
  countEl.innerText = uploadQueue.length;
  
  if (uploadQueue.length === 0) {
    listEl.innerHTML = '<div class="py-8 text-center text-muted text-[10px] uppercase tracking-widest font-bold">Queue trống</div>';
    return;
  }
  
  listEl.innerHTML = '';
  uploadQueue.forEach((job, idx) => {
    const videoName = job.video_path.split(/[\\/]/).pop();
    listEl.innerHTML += `
      <div class="p-3 bg-white/5 rounded-xl border border-white/5 flex items-center justify-between group">
        <div>
          <div class="text-[11px] font-bold text-white mb-0.5">Nick: <span class="text-green-400">${job.nick_name}</span></div>
          <div class="text-[10px] text-muted truncate max-w-[200px]">${videoName}</div>
          ${job.product_id ? `<div class="text-[9px] text-yellow-400 font-bold mt-1">🛒 SP: ${job.product_id}</div>` : ''}
        </div>
        <button onclick="removeFromQueue(${idx})" class="text-red-400 hover:text-red-300 opacity-0 group-hover:opacity-100 transition-opacity">
          <span class="material-symbols-outlined text-[16px]">delete</span>
        </button>
      </div>
    `;
  });
}

function removeFromQueue(idx) {
  uploadQueue.splice(idx, 1);
  renderQueue();
}

async function startUploadQueue() {
  if(uploadQueue.length === 0) { alert("Hàng đợi trống!"); return; }
  
  const statusEl = document.getElementById('upStatus');
  statusEl.classList.remove('hidden');
  statusEl.innerText = "Đang gửi hàng đợi lên server...";
  
  try {
    const r = await fetch(`${API}/affiliate/upload_queue`, {
      method: 'POST', headers:{'Content-Type':'application/json'},
      body: JSON.stringify({ jobs: uploadQueue })
    });
    const d = await r.json();
    if(d.error) {
      statusEl.innerText = "Lỗi: " + d.error;
    } else {
      statusEl.innerText = "Hàng đợi đang chạy nền...";
      // Clear local queue since it's now on server
      uploadQueue = [];
      renderQueue();
    }
  } catch(e) { statusEl.innerText = "Lỗi kết nối!"; }
}

async function scheduleQueue() {
  if(uploadQueue.length === 0) { alert("Hàng đợi trống!"); return; }
  
  const statusEl = document.getElementById('upStatus');
  statusEl.classList.remove('hidden');
  statusEl.innerText = "Đang lên lịch...";
  
  try {
    const r = await fetch(`${API}/affiliate/schedule`, {
      method: 'POST', headers:{'Content-Type':'application/json'},
      body: JSON.stringify({ jobs: uploadQueue })
    });
    const d = await r.json();
    if(d.error) {
      statusEl.innerText = "Lỗi: " + d.error;
    } else {
      statusEl.innerText = d.message;
      // Clear local queue
      uploadQueue = [];
      renderQueue();
      setTimeout(()=> { statusEl.classList.add('hidden'); }, 5000);
    }
  } catch(e) { statusEl.innerText = "Lỗi kết nối!"; }
}

// Poll affiliate status
setInterval(async () => {
  try {
    const r = await fetch(`${API}/affiliate/status`);
    const s = await r.json();
    if(s.running) {
      if(s.task === 'process') {
         const el = document.getElementById('facStatus');
         if(el) el.innerText = s.message;
      } else if (s.task === 'upload' || s.task === 'upload_queue') {
         const el = document.getElementById('upStatus');
         if(el) { el.classList.remove('hidden'); el.innerText = s.message; }
      }
    } else {
       // Completed or error
       if(s.task === 'process') {
          const el = document.getElementById('facStatus');
          if(el && el.innerText !== s.message) {
             el.innerText = s.message;
             loadFacVideos();
          }
       } else if(s.task === 'upload' || s.task === 'upload_queue') {
          const el = document.getElementById('upStatus');
          if(el && el.innerText !== s.message && !el.classList.contains('hidden')) {
             el.innerText = s.message;
             if(s.message.includes('✅')) setTimeout(()=> { el.classList.add('hidden'); }, 10000);
          }
       }
    }
  } catch(e) {}
}, 2000);
