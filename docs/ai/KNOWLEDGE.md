# Sổ Tay Phục Hồi (KNOWLEDGE.md)

> Những bài học kinh nghiệm từ quá trình debug và phát triển. AI agents NÊN đọc file này
> trước khi bắt đầu công việc để tránh lặp lại những lỗi đã từng mắc phải.

## Cách Dùng
- **Trước khi debug**: Kiểm tra xem một lỗi tương tự đã được giải quyết trước đây chưa
- **Sau khi fix một bug khó**: Thêm một mục (entry) xuống bên dưới
- **Định dạng**: Lỗi (Error) → Nguyên Nhân Gốc Rễ (Root Cause) → Chiến Lược Sửa Lỗi (Fix Strategy)

---

## Các Bài Học

<!-- Thêm các bài học mới dưới dòng này -->

### Lỗi không preview được video hoặc lỗi gọi API trên thiết bị khác (Hardcoded Localhost)
- **[Error]**: Khi mở UI trên trình duyệt ở máy khác (hoặc điện thoại) qua LAN IP, không thể xem preview video (màn hình đen/lỗi 404) và các nút bấm tạo kịch bản/render không hoạt động.
- **[Root Cause]**: Frontend (React) đã hardcode đường dẫn cứng `http://localhost:5000/` cho file media (`<video src="http://localhost:5000/media/...">`) và các API call (trong `Editor.tsx`). Khi truy cập từ thiết bị khác, `localhost` trỏ về chính thiết bị đó chứ không phải máy chủ, dẫn đến không thể tải file.
- **[Fix Strategy]**: Luôn sử dụng Relative URLs (đường dẫn tương đối) như `/media/${previewVideo}` và `/api/...` trong frontend thay vì hardcode absolute URL. Trình duyệt sẽ tự động nội suy đúng IP/Domain của máy chủ.

### Lỗi OOM (Out Of Memory) / Tràn RAM gây đơ máy khi tạo video
- **[Error]**: Máy tính bị đơ (freeze) một lúc, tiến trình tạo video bị crash hoặc bị hệ điều hành kill (OOM Killer).
- **[Root Cause]**: Dùng `CompositeVideoClip` của `moviepy` để ghép nối liên tiếp nhiều đoạn video ngắn. `moviepy` sẽ khởi tạo và giữ tất cả các đối tượng `VideoFileClip` (và tiến trình `ffmpeg` đi kèm) trong bộ nhớ cùng một lúc. Ví dụ 30 scene = 30 tiến trình ffmpeg mở song song, làm cạn kiệt toàn bộ RAM.
- **[Fix Strategy]**: Sử dụng cơ chế Lazy Load (tự định nghĩa một lớp như `LazyBackgroundClip`). Lớp này giữ track thời gian (t) và chỉ khởi tạo (mở file) video của scene đang chạy hiện tại. Khi qua scene mới, `.close()` video cũ đi trước khi mở video mới. Điều này giới hạn RAM sử dụng bằng với chỉ 1 video reader duy nhất.

### Lỗi TikTok TTS Mã Lỗi 1 (Text-to-speech isn’t supported)
- **[Error]**: `Text-to-speech isn’t supported for this language (Mã lỗi: 1)` khi gọi TikTok TTS API.
- **[Root Cause]**: Thuật toán chia nhỏ câu (`re.split`) vô tình tách các dấu câu (như `.`, `,`, `-`) thành một chunk độc lập có độ dài 1 ký tự. Khi TikTok API nhận một chuỗi chỉ có dấu câu hoặc khoảng trắng mà không có chữ/số (alphanumeric), thuật toán nhận diện ngôn ngữ của nó thất bại và ném ra lỗi mã 1.
- **[Fix Strategy]**: Dùng regex `re.search(r'\w', chunk)` để kiểm tra. Nếu chunk không chứa bất kỳ ký tự chữ/số nào, bỏ qua không gửi lên TikTok API.

### Lỗi Không tìm thấy lệnh FFmpeg khi dùng subprocess
- **[Error]**: `FileNotFoundError: [Errno 2] No such file or directory: 'ffmpeg'` khi gọi `subprocess.Popen(["ffmpeg", ...])`.
- **[Root Cause]**: Lệnh `ffmpeg` không được cài đặt sẵn ở biến môi trường toàn cục (global PATH) trên máy của người dùng (đặc biệt là Windows hoặc Ubuntu chưa cài ffmpeg native). Trước đó hệ thống chạy được vì `moviepy` tự động tải binary ffmpeg riêng của nó thông qua thư viện `imageio_ffmpeg`.
- **[Fix Strategy]**: Không gọi string `"ffmpeg"`. Import `imageio_ffmpeg` và gọi `imageio_ffmpeg.get_ffmpeg_exe()` để lấy đường dẫn tuyệt đối của file thực thi FFmpeg đi kèm, đảm bảo luôn chạy được trên mọi máy có cài `moviepy`.

### Lỗi TikTok TTS API quá tải (HTTP 502/504)
- **[Error]**: `Exception: TikTok TTS API trả về HTTP code 504 ở đoạn 1: upstream failed to respond`
- **[Root Cause]**: Máy chủ API của TikTok (api16-normal-v6.tiktokv.com) thỉnh thoảng bị quá tải hoặc mạng chập chờn, trả về lỗi Gateway Timeout (504) hoặc Bad Gateway (502). Code hiện tại không có cơ chế thử lại (retry) nên toàn bộ pipeline tạo video bị chết oan uổng.
- **[Fix Strategy]**: Bọc request `requests.post()` bằng một vòng lặp `for attempt in range(max_retries)`. Nếu nhận được `response.status_code >= 500` hoặc bắt được Exception, tạm dừng bằng `time.sleep()` với cơ chế Exponential Backoff rồi thử lại tối đa 3 lần trước khi bỏ cuộc.
