# Chuẩn bị bản demo cho giáo viên

Phạm vi đã chốt: truy cập bằng đường dẫn, không đăng nhập; chỉ dùng chứng từ mẫu. Chưa triển khai lên Internet.

## Chạy ở máy cá nhân

Backend: trong thư mục `backend`, chạy `.venv\Scripts\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8000`.
Frontend: trong thư mục `frontend`, chạy `npm run dev`. Mở http://127.0.0.1:5173.
Khóa Gemini chỉ nằm trong `backend/.env`. Đặt `DEMO_ONLY=true` để thử đúng chế độ online chỉ nhận tệp mẫu.

## Đóng gói để triển khai sau

Dockerfile dựng React và phục vụ cùng FastAPI trên cổng 8000. Nhà cung cấp cần hỗ trợ container, HTTPS và ổ lưu trữ bền vững.

1. Dựng image: `docker build -t bonded-warehouse-demo .`
2. Tạo volume: `docker volume create bonded-demo-data`
3. Đặt biến `GEMINI_API_KEY` qua trang quản lý bí mật của dịch vụ; dùng `backend/.env.production.example` làm danh sách cấu hình.
4. Gắn volume vào `/app/persistent`, cấp quyền ghi cho UID 10001. Chỉ chạy **một worker / một instance** với SQLite và giới hạn AI dùng chung trong bộ nhớ.
5. Chạy image ở cổng 8000; cấu hình domain và HTTPS của nhà cung cấp. Kiểm tra `/health`.
6. Tải bộ mẫu trên giao diện, tạo lô với ngày nhập kho 2026-10-11, tải ba file, trích xuất, đối soát, duyệt, xuất Excel và gửi WMS giả lập.
7. Thử PL sai số lượng hoặc hợp đồng hết hạn: cả duyệt, Excel và gửi WMS phải bị chặn.

Chế độ `DEMO_ONLY=true` chỉ nhận nội dung file có trong bộ mẫu đóng gói, kiểm tra bằng SHA-256. Khách vẫn có thể sửa dữ liệu trích xuất để thử xử lý lỗi. Mọi khách cùng dùng một bộ dữ liệu demo; không có cách ly người dùng.

Giới hạn mặc định 20 yêu cầu trích xuất mỗi giờ cho toàn bộ instance; mỗi yêu cầu có thể có các lần thử lại của Gemini. Đây là giới hạn sử dụng demo, không phải giới hạn chi phí tuyệt đối. Đặt quota của khóa riêng cho demo tại dịch vụ Gemini trước khi công khai. Không dùng khóa hoặc cơ sở dữ liệu vận hành thật.

Sao lưu cả SQLite và thư mục uploads trong volume; khởi động lại với volume phải còn dữ liệu. Không đưa `backend/.env`, cơ sở dữ liệu local, chứng từ đã tải lên hoặc `project-reference` vào image. `.dockerignore` đã loại các thư mục đó.

Container chưa được dựng/triển khai trong phiên kiểm thử local. Mẫu Excel 21 cột là định dạng demo hiện có; cần xác nhận riêng nếu kết nối WMS thật.
