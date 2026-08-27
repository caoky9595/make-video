"""
video_maker.py - Shared Video Rendering Utilities
====================================================
Các hàm dùng chung cho engine render GSAP (core/engines/html_video_maker.py):
chuẩn bị video/ảnh nền, chọn encoder, trộn audio, parse SRT.
Hỗ trợ Mac, Windows, Linux (cross-platform).

NOTE: Dùng OpenCV (cv2) để đọc/xử lý frame video, không phụ thuộc MoviePy.
"""

import os
import re
import random
import platform
import json
import subprocess
import numpy as np
import cv2
from PIL import Image, ImageFont
from core.utils.logger_config import logger


# ============================================================
# CẤU HÌNH VIDEO (Chỉnh sửa tại đây nếu muốn)
# ============================================================
VIDEO_WIDTH = 1080
VIDEO_HEIGHT = 1920
FPS = 30

# Cấu hình Subtitle
FONT_SIZE = 60
FONT_COLOR = (255, 255, 255)  # Trắng
HIGHLIGHT_COLOR = (247, 194, 4)  # Vàng Hormozi mượt hơn (#F7C204)
STROKE_COLOR = (0, 0, 0)  # Đen viền
STROKE_WIDTH = 5

# Overlay tối nền để chữ nổi bật hơn
OVERLAY_OPACITY = 0.35
BGM_VOLUME = 0.22


# ============================================================
# CHỌN ENCODER (ưu tiên tăng tốc bằng iGPU Intel QuickSync nếu có)
# ============================================================
_ENCODER_CACHE = None


def _select_video_encoder():
    """Chọn (ffmpeg_exe, pre_input_args, post_input_args) tốt nhất theo từng máy.

    Encode bằng GPU/iGPU để nhanh và nhẹ CPU. Vì nhiều encoder được ffmpeg liệt kê
    nhưng init runtime lại lỗi (vd h264_qsv trên một số máy), ta PROBE THẬT bằng cách
    encode thử 1 frame chứ không tin danh sách -encoders. Chọn ứng viên theo hệ điều hành:

      - macOS:   VideoToolbox (GPU Apple)
      - Linux:   VAAPI (iGPU Intel/AMD) > QuickSync (Intel) > NVENC (NVIDIA)
      - Windows: NVENC (NVIDIA) > QuickSync (Intel) > AMF (AMD)

    Không có cái nào chạy được thì fallback libx264 (CPU) trên ffmpeg bundled của imageio.
    Kết quả cache để khỏi probe lại mỗi lần render.

    pre_input_args đặt TRƯỚC -i (vd khởi tạo vaapi_device), post_input_args đặt SAU input
    (filter hwupload + codec).
    """
    global _ENCODER_CACHE
    if _ENCODER_CACHE is not None:
        return _ENCODER_CACHE

    import os as _os
    import glob
    import shutil
    import tempfile
    import subprocess

    sys_ffmpeg = shutil.which("ffmpeg")
    system = platform.system()
    probe_out = _os.path.join(tempfile.gettempdir(), "_enc_probe.mp4")

    def _probe(exe, pre, post):
        """Encode thử 1 frame testsrc; True nếu ra file hợp lệ."""
        if not exe:
            return False
        try:
            if _os.path.exists(probe_out):
                _os.remove(probe_out)
        except OSError:
            pass
        cmd = [exe, "-hide_banner", "-y", *pre,
               "-f", "lavfi", "-i", f"testsrc=size={VIDEO_WIDTH}x{VIDEO_HEIGHT}:rate={FPS}:duration=1",
               *post, probe_out]
        try:
            subprocess.run(cmd, capture_output=True, timeout=20)
            return _os.path.exists(probe_out) and _os.path.getsize(probe_out) > 0
        except Exception:
            return False

    # Danh sách ứng viên (label, pre_input, post_input) theo hệ điều hành
    candidates = []
    if system == "Darwin":
        candidates.append((
            "VideoToolbox (GPU Apple)", [],
            ["-c:v", "h264_videotoolbox", "-b:v", "8M", "-pix_fmt", "yuv420p"],
        ))
    elif system == "Windows":
        candidates += [
            ("NVENC (NVIDIA)", [], ["-c:v", "h264_nvenc", "-preset", "fast", "-pix_fmt", "yuv420p"]),
            ("QuickSync (Intel)", [], ["-c:v", "h264_qsv", "-global_quality", "24"]),
            ("AMF (AMD)", [], ["-c:v", "h264_amf", "-quality", "balanced", "-pix_fmt", "yuv420p"]),
        ]
    else:  # Linux và các hệ Unix khác
        render_nodes = sorted(glob.glob("/dev/dri/renderD*"))
        render_dev = render_nodes[0] if render_nodes else "/dev/dri/renderD128"
        candidates += [
            ("VAAPI (iGPU Intel/AMD)", ["-vaapi_device", render_dev],
             ["-vf", "format=nv12,hwupload", "-c:v", "h264_vaapi", "-qp", "24"]),
            ("QuickSync (Intel)", [], ["-c:v", "h264_qsv", "-global_quality", "24"]),
            ("NVENC (NVIDIA)", [], ["-c:v", "h264_nvenc", "-preset", "fast", "-pix_fmt", "yuv420p"]),
        ]

    for label, pre, post in candidates:
        if sys_ffmpeg and _probe(sys_ffmpeg, pre, post):
            logger.info(f"  [Encoder] Dùng {label} - encode bằng GPU.")
            _ENCODER_CACHE = (sys_ffmpeg, pre, post)
            return _ENCODER_CACHE

    # Fallback: libx264 (CPU) trên ffmpeg bundled của imageio
    import imageio_ffmpeg
    bundled = imageio_ffmpeg.get_ffmpeg_exe()
    logger.info("  [Encoder] Không có HW encoder khả dụng, dùng libx264 (CPU).")
    _ENCODER_CACHE = (bundled, [], ["-c:v", "libx264", "-preset", "ultrafast", "-pix_fmt", "yuv420p"])
    return _ENCODER_CACHE


def _mix_audio_with_ducking(voice_path, bgm_path, out_path, duration, bgm_start_sec, bgm_volume):
    """Trộn giọng + nhạc nền với DUCKING (nhạc tự hạ xuống khi có giọng) bằng ffmpeg sidechaincompress.

    Trả True nếu tạo được file out_path hợp lệ, False nếu lỗi (để caller fallback sang mix thường).
    """
    import shutil
    import subprocess

    ff = shutil.which("ffmpeg")
    if not ff:
        try:
            import imageio_ffmpeg
            ff = imageio_ffmpeg.get_ffmpeg_exe()
        except Exception:
            return False

    start = max(0.0, float(bgm_start_sec or 0.0))
    vol = max(0.0, min(1.0, float(bgm_volume)))
    bg_filter = f"volume={vol}"
    if start > 0:
        bg_filter = f"atrim=start={start},asetpts=PTS-STARTPTS,{bg_filter}"

    # [1]=nhạc (loop để phủ đủ duration) hạ volume → sidechaincompress dùng [0]=giọng làm tín hiệu
    # ép nhạc hạ xuống mỗi khi có giọng, rồi amix giọng (full) với nhạc đã ducking.
    filter_complex = (
        f"[1:a]{bg_filter}[bg];"
        f"[bg][0:a]sidechaincompress=threshold=0.02:ratio=8:attack=5:release=300[duck];"
        f"[0:a][duck]amix=inputs=2:duration=first:normalize=0[mix]"
    )
    out_dir = os.path.dirname(out_path)
    if out_dir:
        os.makedirs(out_dir, exist_ok=True)
    cmd = [
        ff, "-hide_banner", "-y",
        "-i", voice_path,
        "-stream_loop", "-1", "-i", bgm_path,
        "-filter_complex", filter_complex,
        "-map", "[mix]", "-t", str(duration), "-ar", "44100",
        out_path,
    ]
    try:
        subprocess.run(cmd, capture_output=True, timeout=180)
        return os.path.exists(out_path) and os.path.getsize(out_path) > 0
    except Exception:
        return False


def _mix_audio_simple(voice_path, bgm_path, out_path, duration, bgm_start_sec, bgm_volume):
    """Trộn giọng + nhạc nền bằng ffmpeg amix thường (không ducking) — dùng khi
    _mix_audio_with_ducking thất bại (sidechaincompress không khả dụng trên máy)."""
    import shutil

    ff = shutil.which("ffmpeg")
    if not ff:
        try:
            import imageio_ffmpeg
            ff = imageio_ffmpeg.get_ffmpeg_exe()
        except Exception:
            return False

    start = max(0.0, float(bgm_start_sec or 0.0))
    vol = max(0.0, min(1.0, float(bgm_volume)))
    bg_filter = f"volume={vol}"
    if start > 0:
        bg_filter = f"atrim=start={start},asetpts=PTS-STARTPTS,{bg_filter}"

    filter_complex = (
        f"[1:a]{bg_filter}[bg];"
        f"[0:a][bg]amix=inputs=2:duration=first:normalize=0[mix]"
    )
    out_dir = os.path.dirname(out_path)
    if out_dir:
        os.makedirs(out_dir, exist_ok=True)
    cmd = [
        ff, "-hide_banner", "-y",
        "-i", voice_path,
        "-stream_loop", "-1", "-i", bgm_path,
        "-filter_complex", filter_complex,
        "-map", "[mix]", "-t", str(duration), "-ar", "44100",
        out_path,
    ]
    try:
        subprocess.run(cmd, capture_output=True, timeout=180)
        return os.path.exists(out_path) and os.path.getsize(out_path) > 0
    except Exception:
        return False


def open_ffmpeg_with_log(ffmpeg_cmd, output_path):
    """Mở tiến trình FFmpeg, stderr ghi ra file log (pipe trực tiếp dễ deadlock vì
    FFmpeg in progress liên tục). Trả về (process, log_path)."""
    log_path = output_path + ".ffmpeg.log"
    log_file = open(log_path, "wb")
    process = subprocess.Popen(ffmpeg_cmd, stdin=subprocess.PIPE, stdout=subprocess.DEVNULL, stderr=log_file)
    # Gắn file handle vào process để check_ffmpeg_result đóng được
    process._log_file = log_file
    return process, log_path


def check_ffmpeg_result(process, output_path, log_path):
    """Raise RuntimeError nếu FFmpeg fail hoặc file output rỗng. Xoá log nếu OK."""
    log_file = getattr(process, "_log_file", None)
    if log_file:
        try: log_file.close()
        except OSError: pass

    failed = process.returncode != 0 or not os.path.exists(output_path) or os.path.getsize(output_path) == 0
    if failed:
        tail = ""
        try:
            with open(log_path, "r", encoding="utf-8", errors="replace") as f:
                tail = f.read()[-2000:]
        except OSError:
            pass
        raise RuntimeError(
            f"FFmpeg thất bại (code {process.returncode}), file output "
            f"{'rỗng/thiếu' if process.returncode == 0 else 'lỗi'}: {output_path}\n--- FFmpeg log ---\n{tail}"
        )
    try:
        os.remove(log_path)
    except OSError:
        pass


def _get_font(size: int = FONT_SIZE):
    """Tìm font phù hợp tùy theo hệ điều hành (Cross-platform) và trả về ImageFont."""
    system = platform.system()

    if system == "Darwin":  # macOS
        candidates = [
            "/System/Library/Fonts/Supplemental/Arial Bold.ttf",
            "/System/Library/Fonts/Supplemental/Arial.ttf",
            "/Library/Fonts/Arial Bold.ttf",
            "/System/Library/Fonts/Helvetica.ttc",
        ]
    elif system == "Windows":
        candidates = [
            "C:\\Windows\\Fonts\\arialbd.ttf",
            "C:\\Windows\\Fonts\\arial.ttf",
            "C:\\Windows\\Fonts\\segoeui.ttf",
        ]
    else:  # Linux
        candidates = [
            "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
            "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
            "/usr/share/fonts/truetype/freefont/FreeSansBold.ttf",
            "/usr/share/fonts/TTF/DejaVuSans-Bold.ttf",
        ]

    for font_path in candidates:
        if os.path.exists(font_path):
            logger.info(f"  [Font] Using: {font_path}")
            return ImageFont.truetype(font_path, size)

    logger.info("  [Font] No preferred font found, using Pillow default.")
    return ImageFont.load_default()


def _parse_srt(srt_path: str):
    """
    Đọc file SRT và trả về danh sách subtitle chunks.
    Mỗi chunk chứa: start (giây), end (giây), text.
    """
    with open(srt_path, "r", encoding="utf-8") as f:
        content = f.read()

    # SRT format:
    # 1
    # 00:00:00,100 --> 00:00:01,537
    # Xin chào bạn
    pattern = re.compile(
        r"\d+\s*\n"
        r"(\d{2}):(\d{2}):(\d{2}),(\d{3})\s*-->\s*(\d{2}):(\d{2}):(\d{2}),(\d{3})\s*\n"
        r"(.*?)(?:\n\n|\Z)",
        re.DOTALL,
    )

    subs = []
    for match in pattern.finditer(content):
        h1, m1, s1, ms1 = int(match[1]), int(match[2]), int(match[3]), int(match[4])
        h2, m2, s2, ms2 = int(match[5]), int(match[6]), int(match[7]), int(match[8])
        start = h1 * 3600 + m1 * 60 + s1 + ms1 / 1000.0
        end = h2 * 3600 + m2 * 60 + s2 + ms2 / 1000.0
        text = match[9].strip().replace("\n", " ")
        if text:
            subs.append({"start": start, "end": end, "text": text})

    if not subs:
        logger.info("  [WARNING] No subtitles found in SRT file!")
    else:
        logger.info(f"  [Subtitles] Parsed {len(subs)} subtitle blocks from SRT.")

    return subs


def _parse_words(srt_path: str):
    words_path = srt_path.replace(".srt", "_words.json")
    if os.path.exists(words_path):
        with open(words_path, "r", encoding="utf-8") as f:
            return json.load(f)
    return []


def _collect_visual_sources(image_dir: str, uploaded_images=None):
    """Trả về danh sách ảnh/video người dùng đã upload (vd clip tải về từ Google Flow), sắp xếp
    theo đúng thứ tự cảnh.

    Ưu tiên tên file theo quy ước `1_, 2_, 3_...` (trợ lý "Hoạt hình Veo thủ công" dặn dùng) —
    sắp theo SỐ thật chứ không phải thứ tự chữ cái (tránh lỗi "10_..." đứng trước "2_..." nếu
    sort chuỗi thường). Nếu có file KHÔNG theo đúng quy ước này (thiếu số thứ tự ở đầu tên), tên
    file không còn đáng tin cậy để suy ra thứ tự cảnh nữa — chuyển sang sắp theo THỜI GIAN TẢI VỀ
    MÁY (mtime), vì người dùng thường tải các clip Flow về đúng theo thứ tự vừa tạo ra.
    """
    video_ext = (".mp4", ".mov", ".avi", ".mkv", ".webm")
    image_ext = (".jpg", ".jpeg", ".png", ".webp")

    uploaded_media = []
    if os.path.isdir(image_dir):
        uploaded_media = [
            os.path.join(image_dir, f)
            for f in os.listdir(image_dir)
            if f.lower().endswith(image_ext + video_ext)
        ]

    if uploaded_images:
        allowed = {os.path.basename(x) for x in uploaded_images}
        uploaded_media = [p for p in uploaded_media if os.path.basename(p) in allowed]

    if not uploaded_media:
        return uploaded_media

    numbered_re = re.compile(r"^(\d+)_")

    def _scene_number(path):
        m = numbered_re.match(os.path.basename(path))
        return int(m.group(1)) if m else None

    if all(_scene_number(p) is not None for p in uploaded_media):
        uploaded_media.sort(key=_scene_number)
    else:
        uploaded_media.sort(key=os.path.getmtime)

    return uploaded_media


class _FrameSource:
    """Bọc 1 hàm sinh frame theo thời gian t — dùng cho ảnh tĩnh (Ken Burns)."""

    def __init__(self, make_frame, duration):
        self._make_frame = make_frame
        self.duration = duration

    def get_frame(self, t):
        return self._make_frame(t)

    def close(self):
        pass


class _ColorSource:
    """Khung hình màu đơn sắc tĩnh — dùng khi không có tài nguyên nền hoặc lỗi tải asset."""

    def __init__(self, color=(30, 30, 30), duration=1.0, size=None):
        w, h = size or (VIDEO_WIDTH, VIDEO_HEIGHT)
        self._frame = np.full((h, w, 3), color, dtype=np.uint8)
        self.duration = duration

    def get_frame(self, t):
        return self._frame

    def close(self):
        pass


class _Cv2VideoSource:
    """Đọc frame thô từ 1 file video bằng OpenCV, thay cho moviepy.VideoFileClip.

    Đọc tuần tự khi có thể (nhanh), chỉ seek khi t nhảy cóc.
    """

    def __init__(self, path):
        self.path = path
        self.cap = cv2.VideoCapture(path)
        if not self.cap.isOpened():
            raise IOError(f"Không mở được video: {path}")
        fps = self.cap.get(cv2.CAP_PROP_FPS) or 0
        frame_count = self.cap.get(cv2.CAP_PROP_FRAME_COUNT) or 0
        self.native_fps = fps if fps > 0 else FPS
        self.duration = (frame_count / self.native_fps) if frame_count > 0 else 0.0
        self._last_frame_no = -1
        self._last_frame = None

    def get_frame(self, t):
        max_frame_no = max(0, int(self.duration * self.native_fps) - 1)
        frame_no = min(int(t * self.native_fps), max_frame_no)
        if frame_no == self._last_frame_no and self._last_frame is not None:
            return self._last_frame

        if frame_no != self._last_frame_no + 1:
            self.cap.set(cv2.CAP_PROP_POS_FRAMES, frame_no)
        ret, frame = self.cap.read()
        if not ret:
            if self._last_frame is not None:
                return self._last_frame
            raise RuntimeError(f"Không đọc được frame nào từ video: {self.path}")

        frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        self._last_frame_no = frame_no
        self._last_frame = frame_rgb
        return frame_rgb

    def close(self):
        try:
            self.cap.release()
        except Exception:
            pass


def _fit_frame_9_16(frame):
    """Crop trung tâm 1 frame về đúng tỉ lệ 9:16 rồi resize khớp VIDEO_WIDTH x VIDEO_HEIGHT."""
    h, w = frame.shape[:2]
    target_ratio = VIDEO_WIDTH / VIDEO_HEIGHT
    ratio = w / h
    if ratio > target_ratio:
        new_w = max(1, int(h * target_ratio))
        x0 = (w - new_w) // 2
        frame = frame[:, x0:x0 + new_w]
    else:
        new_h = max(1, int(w / target_ratio))
        y0 = (h - new_h) // 2
        frame = frame[y0:y0 + new_h, :]
    return cv2.resize(frame, (VIDEO_WIDTH, VIDEO_HEIGHT), interpolation=cv2.INTER_AREA)


# Biên độ zoom cho chuyển động camera thêm vào clip video. Cần vì clip sinh bằng Veo thường
# gần như TĨNH: đo trên video thật thấy 99% pixel giống hệt nhau giữa 2 frame liên tiếp
# (tblend difference -> pblack:99), mà mỗi cảnh lại dài 6-8 giây. Hình không đổi suốt 6-8s trên
# TikTok bị đọc là "không có gì xảy ra" và người xem lướt luôn — khớp đúng số đo: phần lớn rời
# ở mốc 0:02, chỉ 4,8% xem hết. Trước đây Ken Burns chỉ áp cho ẢNH TĨNH, clip video phát nguyên.
VIDEO_KEN_BURNS_ZOOM = 0.14


def _apply_ken_burns(frame, progress: float, pan_mode: str, zoom_range: float = VIDEO_KEN_BURNS_ZOOM):
    """Crop dần theo thời gian để tạo cảm giác camera đang zoom/trôi, rồi resize về khung chuẩn.

    progress: 0.0 -> 1.0 theo tiến độ của cảnh. pan_mode chọn kiểu chuyển động.
    """
    h, w = frame.shape[:2]
    # zoom_out bắt đầu ở mức phóng to nhất rồi lùi ra; các kiểu còn lại phóng dần vào.
    z = 1.0 + zoom_range * ((1.0 - progress) if pan_mode == "zoom_out" else progress)
    crop_w = max(1, int(w / z))
    crop_h = max(1, int(h / z))

    # Dư ngang/dọc để trôi khung. left/right trôi dần sang 1 bên, còn lại giữ giữa.
    max_x = w - crop_w
    max_y = h - crop_h
    if pan_mode == "left":
        fx = 0.5 * (1.0 - progress)
    elif pan_mode == "right":
        fx = 0.5 + 0.5 * progress
    else:
        fx = 0.5
    x0 = int(max_x * min(1.0, max(0.0, fx)))
    y0 = int(max_y * 0.5)

    cropped = frame[y0:y0 + crop_h, x0:x0 + crop_w]
    return cv2.resize(cropped, (VIDEO_WIDTH, VIDEO_HEIGHT), interpolation=cv2.INTER_LINEAR)


class _FormattedVideoSource:
    """Bọc _Cv2VideoSource: crop/resize mỗi frame về khung 1080x1920, THÊM chuyển động camera
    (zoom/pan chậm), và cho phép chọn 1 đoạn con (start_offset, duration) của video gốc."""

    def __init__(self, path, start_offset=0.0, duration=None):
        self._src = _Cv2VideoSource(path)
        self.start_offset = max(0.0, start_offset)
        self.duration = duration if duration is not None else max(0.0, self._src.duration - self.start_offset)
        # Mỗi cảnh 1 kiểu chuyển động khác nhau để các cảnh liên tiếp không giống hệt nhau.
        self.pan_mode = random.choice(["center", "left", "right", "zoom_out"])

    def get_frame(self, t):
        frame = self._src.get_frame(self.start_offset + t)
        frame = _fit_frame_9_16(frame)
        progress = 0.0 if self.duration <= 0 else min(1.0, max(0.0, t / self.duration))
        return _apply_ken_burns(frame, progress, self.pan_mode)

    def close(self):
        self._src.close()


class _ConcatVideoSource:
    """Nối nhiều đoạn (path hoặc None=màu đen, start_offset, seg_duration) thành 1 nguồn frame
    liên tục — thay cho moviepy.concatenate_videoclips. Chỉ giữ 1 đoạn con mở tại 1 thời điểm."""

    def __init__(self, segments):
        self.segments = segments
        self.duration = sum(seg[2] for seg in segments)
        self._cum_start = []
        acc = 0.0
        for _, _, dur in segments:
            self._cum_start.append(acc)
            acc += dur
        self._current_idx = -1
        self._current_src = None

    def _segment_index_at(self, t):
        idx = 0
        for i in range(len(self.segments) - 1, -1, -1):
            if t >= self._cum_start[i]:
                idx = i
                break
        return idx

    def get_frame(self, t):
        idx = self._segment_index_at(t)
        if idx != self._current_idx:
            if self._current_src is not None:
                self._current_src.close()
            path, start_offset, seg_dur = self.segments[idx]
            if path is None:
                self._current_src = _ColorSource(color=(0, 0, 0), duration=seg_dur)
            else:
                self._current_src = _FormattedVideoSource(path, start_offset=start_offset, duration=seg_dur)
            self._current_idx = idx

        local_t = t - self._cum_start[idx]
        local_t = max(0.0, min(local_t, self._current_src.duration - 0.001))
        return self._current_src.get_frame(local_t)

    def close(self):
        if self._current_src is not None:
            self._current_src.close()


def _prepare_image_background(image_path: str, duration: float):
    """Chuẩn bị nền từ ảnh tĩnh với hiệu ứng Cinematic Zoom (Ken Burns).

    Chọn ngẫu nhiên 1 trong 4 kiểu chuyển động mỗi cảnh (zoom-in tâm / lệch trái / lệch phải /
    zoom-out nhẹ) để các cảnh liên tiếp trong cùng video không lặp lại y hệt nhau.
    """
    # Load image with PIL to get size
    img = Image.open(image_path)
    img_w, img_h = img.size

    # Resize sao cho phủ kín 1080x1920 (crop trung tâm)
    target_ratio = VIDEO_WIDTH / VIDEO_HEIGHT
    img_ratio = img_w / img_h

    if img_ratio > target_ratio:
        new_h = VIDEO_HEIGHT
        new_w = int(new_h * img_ratio)
    else:
        new_w = VIDEO_WIDTH
        new_h = int(new_w / img_ratio)

    img = img.resize((new_w, new_h), Image.LANCZOS)

    pan_mode = random.choice(["center", "left", "right", "zoom_out"])
    ZOOM_RANGE = 0.12  # biên độ zoom nhẹ hơn cố định 15% cũ, vì có thêm chuyển động pan

    # Hàm tạo frame với hiệu ứng zoom + pan
    def make_frame(t):
        """Make frame."""
        progress = t / duration
        zoom = 1.0 + ZOOM_RANGE * ((1 - progress) if pan_mode == "zoom_out" else progress)
        curr_w = int(new_w * zoom)
        curr_h = int(new_h * zoom)

        # Resize frame
        frame_img = img.resize((curr_w, curr_h), Image.LANCZOS)

        # Vị trí crop: center/zoom_out giữ giữa khung, left/right trôi dần sang 1 bên
        horizontal_range = max(0, curr_w - VIDEO_WIDTH)
        if pan_mode == "left":
            left_frac = 0.5 * (1 - progress)
        elif pan_mode == "right":
            left_frac = 0.5 + 0.5 * progress
        else:
            left_frac = 0.5
        left = int(horizontal_range * left_frac)
        top = (curr_h - VIDEO_HEIGHT) // 2
        frame_img = frame_img.crop((left, top, left + VIDEO_WIDTH, top + VIDEO_HEIGHT))

        return np.array(frame_img.convert("RGB"))

    return _FrameSource(make_frame, duration)


def _prepare_visual_background(asset_path: str, duration: float, other_bg_paths=None):
    """Tự động xử lý background là video hoặc ảnh."""
    image_ext = (".jpg", ".jpeg", ".png", ".webp")
    if asset_path.lower().endswith(image_ext):
        return _prepare_image_background(asset_path, duration)
    return _prepare_non_loop_background(asset_path, duration, other_bg_paths)


def _prepare_non_loop_background(bg_path: str, duration: float, other_bg_paths=None):
    """
    Chuẩn bị video nền bằng cách ghép nối nhiều video khác nhau từ other_bg_paths nếu video hiện tại quá ngắn.
    Tránh lặp lại một video đơn lẻ.
    """
    probe = _Cv2VideoSource(bg_path)
    src_duration = probe.duration
    probe.close()

    if src_duration >= duration:
        # Nếu đủ dài, lấy một đoạn ngẫu nhiên
        max_start = src_duration - duration
        start_time = random.uniform(0, max_start)
        return _FormattedVideoSource(bg_path, start_offset=start_time, duration=duration)

    # Nếu quá ngắn, thực hiện ghép nối (concatenate) với các clip khác
    logger.info(f"  [Video] Clip '{os.path.basename(bg_path)}' ({src_duration:.1f}s) ngắn hơn scene ({duration:.1f}s). Đang ghép nối thêm video...")
    segments = [(bg_path, 0.0, src_duration)]
    remaining = duration - src_duration

    # Lọc các video khác từ list
    pool = []
    if other_bg_paths:
        image_ext = (".jpg", ".jpeg", ".png", ".webp")
        pool = [p for p in other_bg_paths if p != bg_path and not p.lower().endswith(image_ext)]
        random.shuffle(pool)

    # Nếu không có video khác trong pool, ta đành phải dùng lại chính video đó (fallback cuối cùng)
    if not pool:
        pool = [bg_path]

    pool_idx = 0
    while remaining > 0.01:
        next_path = pool[pool_idx % len(pool)]
        pool_idx += 1

        try:
            probe = _Cv2VideoSource(next_path)
            next_duration = probe.duration
            probe.close()

            if next_duration >= remaining:
                # Đủ bù thời lượng còn lại
                max_start = next_duration - remaining
                start_t = random.uniform(0, max_start)
                segments.append((next_path, start_t, remaining))
                remaining = 0
            else:
                segments.append((next_path, 0.0, next_duration))
                remaining -= next_duration
        except Exception as e:
            logger.info(f"  [Video] ⚠️ Lỗi load clip phụ '{next_path}': {e}")
            # Fallback nếu lỗi: đoạn màu đen tạm thời
            segments.append((None, 0.0, remaining))
            remaining = 0

    return _ConcatVideoSource(segments)


class LazyBackgroundClip:
    """Trình quản lý Lazy Load cho background video. Chỉ mở 1 video tại một thời điểm để tiết kiệm RAM."""

    CROSSFADE_SEC = 0.3  # thời lượng chuyển cảnh mượt ở đầu mỗi scene (trừ scene đầu tiên)

    def __init__(self, subs, duration, visual_sources):
        self.subs = subs
        self.duration = duration
        self.visual_sources = visual_sources

        self.scenes = []
        self.actually_used = []

        for i, sub in enumerate(subs):
            start_t = sub["start"]
            end_t = subs[i+1]["start"] if i+1 < len(subs) else duration
            scene_duration = end_t - start_t

            asset_p = visual_sources[i % len(visual_sources)] if visual_sources else None

            if asset_p:
                self.scenes.append({
                    "start": start_t,
                    "end": end_t,
                    "duration": scene_duration,
                    "asset": asset_p
                })
                self.actually_used.append(asset_p)
            
        self.current_idx = -1
        self.current_clip = None
        self.current_start_t = 0.0
        self.prev_last_frame = None  # frame cuối của cảnh trước, dùng để crossfade sang cảnh mới

    def get_frame(self, t):
        """Get frame."""
        if not self.scenes:
            return np.zeros((VIDEO_HEIGHT, VIDEO_WIDTH, 3), dtype=np.uint8)

        idx = 0
        for i, scene in enumerate(self.scenes):
            if scene["start"] <= t < scene["end"]:
                idx = i
                break
        else:
            if t >= self.scenes[-1]["end"]:
                idx = len(self.scenes) - 1

        if self.current_idx != idx:
            if self.current_clip is not None:
                # Lưu lại frame cuối để crossfade, rồi đóng ngay — không giữ clip cũ mở
                # lâu hơn (tránh lặp lại sự cố OOM đã ghi trong docs/ai/KNOWLEDGE.md).
                try:
                    self.prev_last_frame = self.current_clip.get_frame(max(0.0, self.current_clip.duration - 0.001))
                except Exception:
                    self.prev_last_frame = None
                try:
                    self.current_clip.close()
                except Exception:
                    pass
                self.current_clip = None
            else:
                self.prev_last_frame = None

            scene = self.scenes[idx]
            try:
                self.current_clip = _prepare_visual_background(scene["asset"], scene["duration"], self.visual_sources)
            except Exception as e:
                logger.info(f"  [Video] ⚠️ Lỗi nạp asset {scene['asset']}: {e}")
                self.current_clip = _ColorSource(color=(30, 30, 30), duration=scene["duration"])

            self.current_idx = idx
            self.current_start_t = scene["start"]

        clip_t = t - self.current_start_t
        clip_t = max(0.0, min(clip_t, self.current_clip.duration - 0.001))
        frame = self.current_clip.get_frame(clip_t)

        # Crossfade ngắn ở đầu mỗi cảnh (trừ cảnh đầu tiên, không có prev_last_frame) để
        # tránh cắt cứng khi đổi background.
        if self.prev_last_frame is not None and clip_t < self.CROSSFADE_SEC:
            alpha = clip_t / self.CROSSFADE_SEC
            frame = (self.prev_last_frame.astype(np.float32) * (1 - alpha) + frame.astype(np.float32) * alpha).astype(np.uint8)

        return frame
        
    def close(self):
        """Close."""
        if self.current_clip is not None:
            try:
                self.current_clip.close()
            except Exception:
                pass


