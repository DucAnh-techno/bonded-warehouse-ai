# Software Requirements Specification (SRS)
## Hệ Thống AI Xử Lý Chứng Từ Kho Ngoại Quan (Vietnamese Bonded Warehouse AI)

---

## 1. Giới Thiệu (Introduction)

### 1.1 Mục Đích (Purpose)
Tài liệu Đặc tả Yêu cầu Phần mềm (SRS) này xác định các yêu cầu chức năng, phi chức năng, dữ liệu và giao diện cho hệ thống **Xử lý & Đối soát Chứng từ Kho Ngoại Quan ứng dụng Trí tuệ Nhân tạo Đa phương thức (Multimodal AI)** phục vụ nghiên cứu khoa học và vận hành logistics kho ngoại quan tại Việt Nam.

### 1.2 Phạm Vi Ứng Dụng (Scope)
Hệ thống giải quyết bài toán xử lý hồ sơ chứng từ phức hợp trong kho ngoại quan:
- Tiếp nhận các bộ chứng từ: Tờ khai hải quan điện tử (VNACCS), Hóa đơn thương mại (Commercial Invoice - CI), Phiếu đóng gói (Packing List - PL), Vận đơn (Bill of Lading - B/L / AWB), Đơn đặt hàng (Purchase Order - PO đa nguồn).
- Trích xuất thông tin thực thể bằng mô hình thị giác ngôn ngữ Google Gemini multimodal API.
- Thực thi đối soát chéo (Cross-document Reconciliation) theo các nguyên tắc toán học và nghiệp vụ tất định (Deterministic Validation).
- Quản lý cảnh báo sai lệch (Human-in-the-Loop Discrepancy Resolution), cấm tự động đoán định hoặc tự sửa số liệu.
- Cơ chế cổng chặn an toàn (Gatekeeper) đối với hệ thống quản trị kho (WMS).

### 1.3 Căn Cứ Pháp Lý & Quy Chuẩn (Regulatory Standards)
- Luật Hải quan số 54/2014/QH13.
- Nghị định 08/2015/NĐ-CP và Nghị định 59/2018/NĐ-CP của Chính phủ.
- Thông tư 38/2015/TT-BTC và Thông tư 39/2018/TT-BTC của Bộ Tài chính.

---

## 2. Mô Tả Tổng Quan (Overall Description)

### 2.1 Đối Tượng Sử Dụng (User Personas)
1. **Nhân viên Khai thác Kho / Thủ kho (Warehouse Operator)**: Tải lên bộ chứng từ lô hàng, kiểm tra bảng đối soát, bổ sung giải trình khi có chênh lệch.
2. **Chuyên viên Thủ tục Hải quan (Customs Specialist)**: Đối chiếu mã HS, kiểm tra định dạng tờ khai, rà soát điều kiện giao hàng Incoterms và thuế suất.
3. **Giám sát Kho / Quản lý (Warehouse Supervisor)**: Xem xét báo cáo đối soát, ký duyệt số điện tử (Approval Sign-off) để mở khóa cổng truyền WMS.
4. **Nhà Nghiên cứu / Giảng viên (Researcher)**: Đánh giá độ chính xác của mô hình AI, tỷ lệ nhận diện lỗi và hiệu năng xử lý.

---

## 3. Yêu Cầu Chức Năng (Functional Requirements)

### FR-01: Quản Lý Lô Hàng & Tiếp Nhận Chứng Từ (Shipment & Ingestion)
- **FR-01.1**: Người dùng có thể tạo một lô hàng mới (`Shipment`) với mã lô hàng (`shipment_code`), chiều hàng (`INBOUND` / `OUTBOUND`), loại kho ngoại quan (`BONDED`).
- **FR-01.2**: Cho phép tải lên đồng thời nhiều tệp tài liệu dạng PDF, PNG, JPG, TIFF (dung lượng tối đa 25MB/tệp).
- **FR-01.3**: Hệ thống phải tính toán mã băm SHA-256 ngay khi nhận tệp và lưu trữ tệp gốc bất biến vào `data/uploads/`.
- **FR-01.4**: Cho phép xem lại hoặc tải về tệp gốc nguyên bản bất kỳ lúc nào.

### FR-02: Trích Xuất Dữ Liệu Bằng AI (Multimodal AI Extraction)
- **FR-02.1**: Tích hợp trực tiếp Google Gemini API sử dụng định dạng JSON Schema có cấu trúc chặt chẽ.
- **FR-02.2**: Trích xuất riêng rẽ cho từng chứng từ; tuyệt đối không ghi đè kết quả giữa các loại chứng từ khác nhau.
- **FR-02.3**: Dữ liệu trích xuất bao gồm: Thông tin chung (số chứng từ, ngày, bên gửi, bên nhận, container, seal, tổng trọng lượng) và Bảng danh mục dòng hàng (SKU, Part Number, Tên hàng tiếng Việt, Mã HS 8 số, Số lượng, ĐVT, Đơn giá, Thành tiền, Số PO).
- **FR-02.4**: Lưu trữ kết quả trích xuất dạng thô (Raw JSON) và dạng quan hệ (`ExtractedLineItem`) để phục vụ truy vấn.

### FR-03: Động Cơ Đối Soát Chéo & Kiểm Tra Tất Định (Deterministic Validation)
- **FR-03.1 (Tam Giác Số Lượng)**: $\sum Qty(PL) == \sum Qty(CI) == Qty(\text{Tờ khai})$.
- **FR-03.2 (Toán Học Dòng Hàng)**: $|(Qty \times UnitPrice) - LineTotal| \le 0.01$.
- **FR-03.3 (Tổng Trị Giá)**: $|\sum LineTotal - InvoiceTotal| \le 0.05$.
- **FR-03.4 (Quy Cách Trọng Lượng)**: $GrossWeight \ge NetWeight > 0$.
- **FR-03.5 (Mã HS Việt Nam)**: Mã HS phải đủ 8 chữ số và đồng nhất giữa Tờ khai và Hóa đơn.
- **FR-03.6 (Đồng Bộ Container / Seal)**: Danh sách container và seal phải khớp tuyệt đối giữa Vận đơn, Packing List và Tờ khai.
- **FR-03.7 (Hỗ Trợ Đa PO / Đa SKU)**: Hỗ trợ đối chiếu gom nhiều đơn đặt hàng (Multi-PO) trong cùng 1 lô hàng.

### FR-04: Xử Lý Xung Đột & Tái Đối Soát Động (Discrepancy & Revalidation)
- **FR-04.1**: Khi phát hiện dữ liệu không khớp, hệ thống tạo bản ghi `Discrepancy` và không bao giờ tự ý điều chỉnh.
- **FR-04.2**: Bảng đối soát hiển thị trực quan dữ liệu hai nguồn song song (`value_a` vs `value_b`).
- **FR-04.3**: Cho phép người dùng chọn phương án: `OVERRIDE` (Ghi đè giá trị đúng), `ACCEPT_WITH_REASON` (Chấp nhận sai lệch có giải trình), hoặc `REJECT`.
- **FR-04.4**: Bắt buộc nhập lý do nghiệp vụ cho mỗi thao tác can thiệp.
- **FR-04.5**: Mọi can thiệp kích hoạt tự động tái kiểm tra (Dynamic Revalidation) cho toàn bộ các quy tắc liên quan.
- **FR-04.6**: Ghi nhật ký kiểm toán bất biến (`AuditLog`).

### FR-05: Cổng Kiểm Soát & Truyền Dữ Liệu WMS (WMS Transmission Gatekeeper)
- **FR-05.1**: Nút chức năng và API truyền WMS phải bị KHÓA CỨNG (`BLOCKED`) nếu:
  1. Tồn tại bất kỳ sai lệch mức độ `ERROR` chưa được xử lý.
  2. Lô hàng chưa đạt trạng thái `VALIDATED`.
  3. Chưa có phê duyệt chính thức (`APPROVED`) từ Giám sát viên.
- **FR-05.2**: Khi đủ điều kiện và được phê duyệt, hệ thống tự động sinh cấu trúc dữ liệu phiếu nhập/xuất kho chuẩn (WMS Inbound/Outbound Receipt JSON) và truyền xuống Mock WMS / ERP.

---

## 4. Yêu Cầu Phi Chức Năng (Non-Functional Requirements)

### 4.1 Tính Bảo Mật (Security)
- Khóa `GEMINI_API_KEY` được bảo vệ độc quyền ở phía server (`backend/.env`), không xuất hiện ở client.
- Kiểm tra tính an toàn của tệp tải lên (chống tấn công Path Traversal, giới hạn dung lượng, chặn tệp thực thi độc hại).
- Giao thức CORS chỉ mở cho máy khách frontend được cấu hình.

### 4.2 Tính Tin Cậy & Tính Toán Vẹn (Reliability & Integrity)
- Tệp chứng từ gốc được lưu trữ nguyên bản (Byte-for-byte immutability).
- Cơ sở dữ liệu SQLite chạy chế độ WAL mode (`PRAGMA journal_mode=WAL; PRAGMA foreign_keys=ON;`) với busy timeout để chống xung đột khóa tệp trên Windows 10.

### 4.3 Khả Năng Vận Hành Trên Windows 10 Localhost (Portability)
- Không phụ thuộc vào Docker, Linux kernel hay các công cụ biên dịch C phức tạp.
- Sử dụng `pathlib.Path` cho tất cả thao tác đường dẫn tệp.
