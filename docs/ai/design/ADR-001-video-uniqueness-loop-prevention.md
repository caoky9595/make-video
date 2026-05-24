# ADR-001: Tối ưu hóa tính độc nhất (Uniqueness) và chống lặp (Looping) video nền

## Context (Bối cảnh)
Hệ thống TikTok có thuật toán quét nội dung trùng lặp rất gắt gao. Sử dụng lại video nền cũ hoặc lặp lại một video nền nhiều lần trong một clip (looping) sẽ làm giảm mạnh tương tác và tăng nguy cơ tài khoản bị TikTok phạt hoặc bóp tương tác.
Hiện tại:
1. File `used_backgrounds.json` có tồn tại nhưng chưa từng được nạp để loại trừ các video đã dùng khi tìm kiếm trên Pexels.
2. Các video IDs đã sử dụng thành công không được ghi lại vào `used_backgrounds.json`.
3. Khi tổng thời lượng video ngắn hơn thời lượng âm thanh đọc phân cảnh, hệ thống sẽ thực hiện loop video cũ hoặc lặp lại clip bằng modulo, vi phạm nghiêm trọng quy tắc chống loop.

## Decision (Quyết định)
Chúng ta sẽ triển khai hai cải tiến kỹ thuật lớn:
1. **Lọc trùng lặp & Lưu vết IDs**: 
   - Hàm tìm kiếm Pexels sẽ lọc bỏ các kết quả có ID khớp với danh sách nạp từ `used_backgrounds.json`.
   - Sau khi render hoàn tất, hệ thống sẽ parse ID video nền đã dùng và lưu lại vào `used_backgrounds.json`.
2. **Thuật toán Ghép nối Clip không lặp (No-Loop Video Stitching)**:
   - Thay vì loop một video nền đơn lẻ để khớp thời lượng phân cảnh, hệ thống sẽ lấy lần lượt các video nền khác trong danh sách visual_sources tải về, thực hiện cắt ghép và nối chúng lại với nhau (concatenate) cho tới khi tổng thời lượng đạt yêu cầu.

## API Contracts & Interfaces

### 1. Hàm tìm kiếm trong `bg_finder.py`
```python
def search_pexels_videos(
    query: str, 
    api_key: str, 
    orientation: str = "portrait", 
    per_page: int = 5,
    exclude_ids: Optional[List[int]] = None
) -> List[dict]:
    """
    Tìm kiếm video trên Pexels và loại bỏ các video có ID trong danh sách exclude_ids.
    """
```

### 2. Hàm dọn dẹp và tải trong `bg_finder.py`
```python
def find_and_download_background(
    script_text: str, 
    output_dir: str = "backgrounds", 
    max_downloads: int = 5
) -> List[str]:
    """
    Nạp used_backgrounds.json để truyền vào làm danh sách exclude_ids khi gọi search.
    Trả về danh sách các đường dẫn file video vừa được tải về thành công.
    """
```

### 3. Hàm lưu vết trong `video_maker.py`
```python
def record_used_backgrounds(used_paths: List[str], database_path: str = "used_backgrounds.json"):
    """
    Trích xuất IDs từ tên file (ví dụ pexels_12345.mp4 -> ID 12345)
    và append các IDs này vào database_path dưới dạng mảng JSON.
    """
```

### 4. Thuật toán ghép nối clip trong `video_maker.py`
```python
def _prepare_non_loop_background(
    bg_paths: List[str], 
    target_duration: float, 
    start_idx: int
) -> Tuple[VideoClip, int]:
    """
    Stitch (ghép nối) các video khác nhau từ danh sách bg_paths bắt đầu từ start_idx
    cho tới khi tổng độ dài đạt target_duration.
    Trả về:
      - VideoClip đã được ghép và crop đúng tỉ lệ 9:16.
      - start_idx tiếp theo cho cảnh sau.
    """
```

---

## Data Flow (Luồng Dữ liệu)

```text
[Kịch bản] ──> Rút trích từ khóa 
                  │
                  ▼
         [used_backgrounds.json] ──> Nạp Exclude IDs ──> Tìm kiếm Pexels
                                                               │
                                                               ▼
                                                       Lọc bỏ trùng lặp
                                                               │
                                                               ▼
[Video Output] <── Ghi nhận IDs đã dùng <── Ghép nối Video <── Tải video mới
```

---

## Alternatives Considered (Các Phương án Cân nhắc)

### Phương án A: Tự sinh ảnh AI (Pollinations) thay thế hoàn toàn khi hết video nền
- **Ưu điểm**: Ảnh tĩnh sinh bằng AI luôn mới và độc nhất 100%.
- **Khuyết điểm**: Ảnh tĩnh không mang lại cảm giác động (Oddly Satisfying) cuốn hút như video, làm giảm retention rate của người xem trên TikTok.
- **Lý do không chọn**: Video nền động vẫn là ưu tiên số 1 để giữ chân người xem; ảnh AI chỉ nên dùng làm phương án dự phòng khi hết tài nguyên video.

---

## Consequences (Hệ quả)
- ✅ Giải quyết dứt điểm vấn đề video nền bị lặp lại nhiều lần.
- ✅ Đảm bảo 100% video xuất ra có sự độc nhất về mặt hình ảnh nền, tăng khả năng ăn đề xuất TikTok.
- ⚠️ Yêu cầu tải về nhiều video hơn mỗi lần chạy -> Tăng dung lượng lưu trữ tạm thời và thời gian tải ngầm. Tuy nhiên, việc dọn dẹp folder `backgrounds/` sau mỗi lần chạy đã giải quyết vấn đề lưu trữ.
