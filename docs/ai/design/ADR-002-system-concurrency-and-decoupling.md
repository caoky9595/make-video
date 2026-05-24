# ADR-002: Tái thiết kế Kiến trúc Đồng thì (Concurrency) và Giảm độ kết khối (Decoupling)

## Bối cảnh (Context)
Trong quá trình vận hành thực tế và phân tích hệ thống VideoMaker Pro, chúng tôi phát hiện ra các vấn đề nghiêm trọng về mặt kiến trúc:
1. **Trạng thái Đơn luồng & Xung đột Concurrency**: Hệ thống lưu trạng thái pipeline trong một biến toàn cục `pipeline_status` duy nhất ở `app.py`. Nếu 2 user chạy tạo video cùng lúc, tiến trình của họ sẽ ghi đè lẫn nhau, dẫn đến giao diện hiển thị thông tin sai lệch và tiến trình chạy nền bị crash.
2. **Kết khối chặt (Tight Coupling) trong Video Maker**: Hàm `make_video` trong `video_maker.py` nhận hơn 13 tham số độc lập. Mỗi lần thêm tính năng (ví dụ cấu hình font mới, thay đổi vị trí overlay, đổi cấu hình audio), chữ ký hàm lại phình to, vi phạm nguyên lý Single Responsibility.
3. **Không kiểm soát được vòng đời luồng (Ad-hoc Threading)**: Server khởi tạo `threading.Thread` trực tiếp trong endpoint mà không có sự quản lý của ThreadPool hay Worker Queue, dẫn đến khả năng bị cạn kiệt tài nguyên hệ thống (OOM) nếu có quá nhiều tiến trình render chạy song song.

---

## Quyết định Thiết kế (Decisions)

### 1. Kiến trúc Đa nhiệm dựa trên Job ID và SQLite State Manager
Chúng ta sẽ chuyển đổi hệ thống sang kiến trúc hướng tác vụ (Job-driven Architecture):
- Mỗi yêu cầu tạo video sẽ được cấp một `job_id` (UUIDv4) duy nhất.
- Trạng thái của từng Job sẽ được quản lý và lưu giữ trong SQLite Database (`jobs.db`) thay vì RAM cục bộ. Điều này đảm bảo tính bền vững (persistence) và an toàn luồng (thread-safety).
- Client sẽ gửi yêu cầu khởi tạo Job, nhận về `job_id`, và thực hiện polling trạng thái qua API endpoint `/api/pipeline/status/<job_id>`.

### 2. Sử dụng Pattern Config Data Classes để giảm tham số hàm
- Nhóm toàn bộ tham số cấu hình render vào các Class cấu hình chuyên biệt sử dụng Python `dataclasses`:
  - `AudioConfig`: Quản lý TTS, voice, rate, BGM path, BGM volume, BGM offset.
  - `SubtitleConfig`: Quản lý style font, màu sắc, vị trí hiển thị, hiệu ứng karaoke.
  - `RenderConfig`: Quản lý độ phân giải (w, h), fps, bitrate, preset FFmpeg.
- Hàm `make_video` sẽ chỉ nhận 2 đối số chính: `job_id: str` và một đối tượng `VideoJobPayload` chứa các config con trên.

### 3. Tích hợp Background Job Broker (Worker Thread Pool)
- Sử dụng `concurrent.futures.ThreadPoolExecutor` với giới hạn worker tối đa (mặc định là 2) để giới hạn số lượng tác vụ render nặng chạy đồng thời, tránh treo VPS/Server.

---

## API Contracts & Interfaces

### 1. Cấu hình Config Entities (`models.py`)
```python
from dataclasses import dataclass, field
from typing import Optional, List

@dataclass
class AudioConfig:
    voice: str = "vi-VN-HoaiMyNeural"
    rate: str = "+0%"
    bgm_path: Optional[str] = None
    bgm_volume: float = 0.22
    bgm_start_sec: float = 0.0

@dataclass
class SubtitleConfig:
    style: int = 1
    position: str = "bottom"
    font_path: Optional[str] = None
    overlay_opacity: float = 0.35

@dataclass
class RenderConfig:
    width: int = 1080
    height: int = 1920
    fps: int = 30
    preset: str = "ultrafast"
    threads: int = 4

@dataclass
class VideoJobPayload:
    script_text: str
    visual_mode: str  # "ai" | "uploaded" | "mix"
    video_mode: str   # "pexels" | "veo"
    audio: AudioConfig = field(default_factory=AudioConfig)
    subtitles: SubtitleConfig = field(default_factory=SubtitleConfig)
    render: RenderConfig = field(default_factory=RenderConfig)
```

### 2. Database Schema cho Job State (`jobs_db.py`)
```sql
CREATE TABLE IF NOT EXISTS video_jobs (
    job_id TEXT PRIMARY KEY,
    status TEXT NOT NULL,       -- "queued", "processing", "completed", "failed"
    progress INTEGER DEFAULT 0,
    message TEXT,
    output_file TEXT,
    error TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

### 3. API Endpoints mới (`app.py`)
- **Khởi chạy Pipeline**: `POST /api/pipeline/start`
  - Body: JSON tương thích với `VideoJobPayload`.
  - Trả về: `{"success": true, "job_id": "uuid-string"}`.
- **Truy vấn Trạng thái**: `GET /api/pipeline/status/<job_id>`
  - Trả về: `{"job_id": "uuid", "status": "processing", "progress": 50, "message": "...", "output_file": "..."}`.

---

## Data Flow (Luồng Dữ liệu)

```text
[React Client] 
     │
     ├── 1. POST /api/pipeline/start ────> [Flask Server] ──> Khởi tạo UUID & Lưu DB (status: queued)
     │                                                               │
     │                                                               ▼
     │                                                      [ThreadPoolExecutor] 
     │                                                      (Chạy ngầm run_pipeline)
     │                                                               │
     ├── 2. GET /api/status/<job_id> <─── Đọc trạng thái từ DB <──────┼── Cập nhật trạng thái từng bước
     │                                                               │
     ▼                                                               ▼
[Hiển thị Video] <────────────────── Đọc file đầu ra <─────────── Hoàn tất (status: completed)
```

---

## Alternatives Considered (Các Phương án Cân nhắc)

### Phương án A: Sử dụng Redis + Celery để quản lý Hàng đợi
- **Ưu điểm**: Khả năng chịu tải cực lớn, phù hợp scale ra nhiều server worker độc lập.
- **Khuyết điểm**: Tăng độ phức tạp khi deploy (yêu cầu cài đặt thêm Redis server và chạy daemon Celery), không phù hợp với môi trường Ubuntu cá nhân gọn nhẹ của dự án.
- **Lý do không chọn**: SQLite kết hợp với Python ThreadPool là giải pháp "Zero-dependency" cực kỳ thích hợp cho quy mô hiện tại của dự án.

---

## Consequences (Hệ quả)
- ✅ Đảm bảo hệ thống có khả năng xử lý đồng thời nhiều Job render cùng lúc mà không lo sợ xung đột trạng thái hiển thị.
- ✅ Cấu hình hệ thống trở nên tường minh, dễ viết test case và mở rộng thêm hiệu ứng/font chữ mới.
- ⚠️ Client cần chuyển đổi từ cơ chế lắng nghe trạng thái global sang polling theo `job_id`.
- ⚠️ Cần bảo trì cơ chế xóa các Job cũ trong SQLite để tránh db phình to sau thời gian dài.
