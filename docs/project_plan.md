# Kế Hoạch Triển Khai Dự Án (Project Implementation Plan)

**Hệ Thống AI Xử Lý Chứng Từ Kho Ngoại Quan (Vietnamese Bonded Warehouse AI)**  
*Môi trường phát triển: Windows 10 Localhost | Tech Stack: React, TypeScript, Vite, Tailwind CSS, FastAPI, SQLite, SQLAlchemy, Gemini API*

---

## 📅 Lộ Trình Phân Kỳ Thực Hiện (Phased Roadmap)

```mermaid
gantt
    title Lộ Trình Phát Triển Hệ Thống AI Kho Ngoại Quan
    dateFormat  YYYY-MM-DD
    section Giai Đoạn 1: Nền Tảng & Khung Cấu Trúc
    Quy chuẩn AGENTS.md & Cấu trúc Thư mục      :done,    p1_1, 2026-10-09, 1d
    Schema ORM & Pydantic Model                :active,  p1_2, 2026-10-10, 2d
    Skeleton Backend & Frontend Config          :active,  p1_3, 2026-10-10, 2d
    section Giai Đoạn 2: Lưu Trữ & Trích Xuất Gemini
    Dịch vụ Lưu trữ Chứng từ Bất biến (SHA-256) :         p2_1, 2026-10-12, 2d
    Tích hợp Gemini Multimodal API (JSON Schema):         p2_2, 2026-10-14, 3d
    Trích xuất độc lập từng loại chứng từ      :         p2_3, 2026-10-17, 2d
    section Giai Đoạn 3: Động Cơ Đối Soát & Kiểm Tra
    Bộ quy tắc đối soát tất định (Deterministic):         p3_1, 2026-10-19, 3d
    Xử lý Đa PO (Multi-PO) & Đa SKU (Multi-SKU) :         p3_2, 2026-10-22, 2d
    Phát hiện xung đột không tự giải quyết      :         p3_3, 2026-10-24, 2d
    Cơ chế Tái kiểm tra (Dynamic Revalidation)  :         p3_4, 2026-10-26, 2d
    Bộ kiểm thử Pytest cho logic nghiệp vụ       :         p3_5, 2026-10-28, 2d
    section Giai Đoạn 4: Cổng Kiểm Soát WMS & Audit
    Audit Trail bất biến cho mọi chỉnh sửa      :         p4_1, 2026-10-30, 2d
    Cổng chặn truyền WMS (Hard Gatekeeper)      :         p4_2, 2026-11-01, 2d
    Chuẩn hóa Payload WMS Inbound/Outbound      :         p4_3, 2026-11-03, 2d
    section Giai Đoạn 5: Giao Diện Người Dùng (React)
    Layout Dashboard & Upload Đa chứng từ       :         p5_1, 2026-11-05, 3d
    Bảng đối soát Đa PO/SKU Matrix trực quan    :         p5_2, 2026-11-08, 3d
    Panel Xử lý Bất đồng bộ (Discrepancy Hub)   :         p5_3, 2026-11-11, 3d
    Panel Phê duyệt & Đẩy dữ liệu WMS           :         p5_4, 2026-11-14, 2d
    section Giai Đoạn 6: Đánh Giá Nghiên Cứu
    Thử nghiệm bộ mẫu chứng từ Hải quan thực tế :         p6_1, 2026-11-16, 4d
    Báo cáo đánh giá độ chính xác & độ tin cậy  :         p6_2, 2026-11-20, 3d
```

---

## 🎯 Chi Tiết Từng Giai Đoạn

### Giai Đoạn 1: Thiết Lập Kiến Trúc & Cấu Trúc Khung (Current Phase)
- **Mục tiêu**: Chuẩn hóa toàn bộ quy tắc kỹ thuật (`AGENTS.md`), xây dựng cây thư mục sạch, phân tách frontend/backend, cấu hình môi trường Windows 10.
- **Đầu ra**:
  - `AGENTS.md` hoàn chỉnh.
  - Cây thư mục backend/frontend với đầy đủ `.gitkeep` và file cấu hình (`requirements.txt`, `package.json`, `vite.config.ts`, `tsconfig.json`).
  - Định nghĩa cấu trúc Model (SQLAlchemy) và Schemas (Pydantic).
  - Bản kế hoạch dự án chi tiết.

### Giai Đoạn 2: Lưu Trữ Bất Biến & Trích Xuất Gemini Đích Thực
- **Mục tiêu**: Đảm bảo chứng từ gốc được lưu trữ nguyên bản và sử dụng API Gemini thật với đầu ra JSON định dạng nghiêm ngặt.
- **Tiêu chí hoàn thành**:
  - `StorageService` tính toán băm SHA-256, lưu tệp vào `backend/storage/uploads/` mà không làm biến dạng dữ liệu.
  - `GeminiExtractor` gọi `gemini-2.5-flash` / `gemini-1.5-flash` sử dụng Pydantic Structured Outputs.
  - Kết quả trích xuất của từng chứng từ (Tờ khai, Invoice, Packing List, B/L, PO) được lưu riêng biệt vào bảng `document_extractions`.

### Giai Đoạn 3: Động Cơ Đối Soát Tất Định & Quản Lý Xung Đột
- **Mục tiêu**: Xây dựng thuật toán kiểm tra logic toán học và nghiệp vụ hải quan bằng Python 100% tất định (không dùng AI để phán xét đúng/sai).
- **Tiêu chí hoàn thành**:
  - Triển khai toàn bộ quy tắc `VAL-QTY-001`, `VAL-PRC-001`, `VAL-WGT-001`, `VAL-HS-001`, `VAL-PO-001`, `VAL-CNT-001`.
  - Nhận diện xung đột và tạo bản ghi `Discrepancy` với cờ `severity=ERROR/WARNING`.
  - Nghiêm cấm giải quyết xung đột tự động; bắt buộc người dùng can thiệp.
  - Khi người dùng sửa dữ liệu, hệ thống tự động chạy lại các quy tắc bị ảnh hưởng (Dynamic Revalidation).
  - Viết bộ kiểm thử `pytest` đạt độ bao phủ cao cho module tính toán.

### Giai Đoạn 4: Nhật Ký Kiểm Toán (Audit) & Cổng Chặn WMS
- **Mục tiêu**: Đảm bảo tính toàn vẹn dữ liệu và ngăn chặn việc đẩy dữ liệu chưa chuẩn hóa vào hệ thống quản lý kho (WMS).
- **Tiêu chí hoàn thành**:
  - Bảng `AuditLog` lưu lại mọi thao tác ghi đè (ai sửa, sửa lúc nào, giá trị cũ/mới, lý do).
  - Cổng chặn WMS từ chối (HTTP 422/403) mọi yêu cầu phát sinh payload nếu còn lỗi hoặc chưa có phê duyệt `APPROVED`.

### Giai Đoạn 5: Giao Diện Người Dùng (React + Tailwind CSS)
- **Mục tiêu**: Xây dựng giao diện nghiệp vụ trực quan, mượt mà, thuần tiếng Việt.
- **Tiêu chí hoàn thành**:
  - Giao diện kéo thả chứng từ với thanh tiến trình trích xuất thời gian thực.
  - Bảng đối soát Đa PO / Đa SKU hiển thị chênh lệch số lượng, đơn giá, mã HS nổi bật với màu cảnh báo rõ ràng.
  - Hộp thoại giải quyết sai lệch (Human Override Modal) kèm bắt buộc nhập lý do nghiệp vụ.
  - Nút phê duyệt và xuất dữ liệu WMS (mở khóa khi toàn bộ lỗi được khắc phục).

### Giai Đoạn 6: Đánh Giá Nghiên Cứu Khoa Học & Báo Cáo
- **Mục tiêu**: Thu thập số liệu thực nghiệm phục vụ báo cáo nghiên cứu.
- **Tiêu chí hoàn thành**:
  - Kiểm thử trên bộ hồ sơ hải quan thực tế.
  - Đo lường độ chính xác (Precision, Recall), thời gian xử lý và tỷ lệ phát hiện sai lệch.
