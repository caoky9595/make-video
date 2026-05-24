# ADR-001: Quản Lý Bộ Nhớ (Memory Management) & Chống Tràn RAM

### Context
Quá trình tạo video (đặc biệt khi dùng `moviepy` và nạp video 1080x1920) tiêu thụ một lượng lớn RAM để đệm (buffer) khung hình.
Hiện tại hệ thống sử dụng `ThreadPoolExecutor(max_workers=2)` trong `app.py` để xử lý song song. Khi người dùng gửi 2 yêu cầu tạo video cùng lúc, hệ thống sẽ chạy song song 2 tiến trình render, dẫn đến việc tiêu thụ gấp đôi lượng RAM (lên tới 4-8GB+). Điều này gây ra hiện tượng OOM (Out Of Memory) khiến hệ điều hành Linux buộc phải "giết" (kill) luôn tiến trình `app.py`, làm server bị sập hoàn toàn (Crash).

### Decision
Sử dụng mô hình **Sequential Queue (Hàng đợi tuần tự)** thay vì xử lý song song (Parallel Processing) cho toàn bộ Pipeline.

### API Contracts / Implementation Details
1. **app.py**: Giảm `ThreadPoolExecutor(max_workers=2)` xuống `max_workers=1`. Các yêu cầu tạo video tiếp theo sẽ được đẩy vào hàng đợi (queued) và chỉ chạy khi video trước đó đã hoàn tất.
2. **video_maker.py**: 
   - Giảm tham số `threads=4` xuống `threads=2` trong hàm `write_videofile` để giảm thiểu số lượng khung hình nạp trước (pre-fetched frames) trong bộ nhớ.
   - Thêm `import gc` và gọi `gc.collect()` ở cuối hàm `make_video` để giải phóng rác trong RAM ngay lập tức sau khi render xong.
   - Bọc các lệnh đóng clip (`close()`) trong khối `finally` để đảm bảo RAM luôn được giải phóng kể cả khi tiến trình render bị lỗi giữa chừng.

### Alternatives Considered
- **Sử dụng External Worker (Celery + Redis)**: Tách riêng Flask Server và Render Worker ra làm 2 tiến trình riêng biệt.
  - *Lý do từ chối*: Độ phức tạp cao (Over-engineering) so với quy mô hiện tại của project. Người dùng sẽ phải cài đặt và chạy thêm Redis server, không phù hợp với tiêu chí "cài đặt nhanh" của ứng dụng local.

### Consequences
- ✅ **Lợi ích**: Triệt tiêu 100% lỗi OOM do render song song. Hệ thống ổn định tuyệt đối dù người dùng bấm "TẠO VIDEO" bao nhiêu lần đi nữa.
- ⚠️ **Đánh đổi**: Các video sẽ được tạo lần lượt (cái sau phải đợi cái trước xong), do đó thời gian chờ đợi tổng thể nếu người dùng đặt hàng chục video cùng lúc sẽ lâu hơn.
