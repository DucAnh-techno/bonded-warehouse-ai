# Quy Trình Tác Nghiệp Chuẩn Kho Ngoại Quan (Standard Operating Procedures - SOP)

Căn cứ pháp lý:
- **Luật Hải quan số 54/2014/QH13** (Điều 61, 62, 63 quy định về Kho ngoại quan).
- **Nghị định 08/2015/NĐ-CP** (Điều 83 đến Điều 90 quy định về thủ tục hải quan đối với hàng hóa đưa vào, lưu giữ, đưa ra kho ngoại quan).
- **Nghị định 59/2018/NĐ-CP** (Sửa đổi, bổ sung một số điều của Nghị định 08/2015/NĐ-CP).
- **Thông tư 38/2015/TT-BTC** và **Thông tư 39/2018/TT-BTC** của Bộ Tài chính.

---

## 📌 Quy Trình 1: Tiếp Nhận & Thẩm Định Bộ Hồ Sơ Hải Quan (Inbound Document Screening)

1. **Bộ chứng từ yêu cầu**:
   - Tờ khai hải quan nhập kho ngoại quan (Mẫu HQ/2015/NK, mã loại hình C11).
   - Hóa đơn thương mại (Commercial Invoice).
   - Phiếu đóng gói hàng hóa (Packing List).
   - Vận đơn (Bill of Lading) có ghi rõ địa điểm dỡ hàng/giao hàng là kho ngoại quan.
   - Hợp đồng thuê kho ngoại quan còn hiệu lực.
   - Đơn đặt hàng (Purchase Orders) đối ứng.
2. **Nhiệm vụ của Hệ thống AI**:
   - Trích xuất toàn bộ các thực thể thông tin trên các chứng từ bằng Gemini Multimodal API.
   - Kiểm tra mã băm SHA-256 để đảm bảo tính nguyên bản của hồ sơ.
   - Không được sửa đổi hoặc đoán định các giá trị bị mờ/thiếu.

---

## 📌 Quy Trình 2: Đối Soát Chéo Dữ Liệu Tất Định (Deterministic Cross-Reconciliation)

1. **Kiểm tra tam giác số lượng**:
   $$\sum Qty(PL) == \sum Qty(CI) == Qty(\text{Tờ khai C11})$$
2. **Kiểm tra tính toán số học**:
   $$Qty \times UnitPrice == LineTotal \quad (\pm 0.01)$$
   $$\sum LineTotal == InvoiceTotal \quad (\pm 0.05)$$
3. **Kiểm tra quy cách trọng lượng**:
   $$GrossWeight \ge NetWeight > 0$$
   $$\left|GrossWeight_{B/L} - GrossWeight_{PL}\right| \le 0.5\% \times GrossWeight_{B/L}$$
4. **Kiểm tra mã HS Việt Nam**:
   - Đúng chuẩn 8 chữ số, đồng nhất giữa tờ khai và hóa đơn.
5. **Kiểm tra số Container & Số Chì**:
   - Khớp 100% giữa B/L, Packing List và Tờ khai.

---

## 📌 Quy Trình 3: Xử Lý Bất Đồng Bộ Dữ Liệu (Discrepancy Resolution & HITL)

1. Khi phát hiện sai lệch:
   - Hệ thống tự động tạo bản ghi `Discrepancy` với mức độ `ERROR` (Chặn truyền WMS) hoặc `WARNING` (Cảnh báo).
   - Cấm hệ thống tự động làm khớp số liệu.
2. Quy trình con người can thiệp (Human-in-the-Loop):
   - Nhân viên kho / Chuyên viên hải quan rà soát hai giá trị nguồn hiển thị song song.
   - Thực hiện thao tác `OVERRIDE` (nếu sai do lỗi OCR) hoặc `ACCEPT_WITH_REASON` (nếu sai lệch do hao hụt thực tế/giao bù).
   - Bắt buộc nhập lý do giải trình nghiệp vụ.
3. Kích hoạt tái đối soát tự động (Dynamic Revalidation):
   - Ngay khi lưu can thiệp, hệ thống tự động chạy lại toàn bộ quy tắc liên quan, ghi vết vào `AuditLog`.

---

## 📌 Quy Trình 4: Kiểm Soát Cổng Truyền WMS & Thực Nhập Kho (WMS Gatekeeping)

1. **Điều kiện mở khóa cổng WMS**:
   - 100% sai lệch mức độ `ERROR` đã được giải quyết (`status != 'OPEN'`).
   - Lô hàng đạt trạng thái `VALIDATED`.
   - Có chữ ký số / xác nhận phê duyệt `APPROVED` từ Giám sát kho ngoại quan.
2. **Đẩy dữ liệu vào WMS**:
   - Hệ thống tự động sinh cấu trúc dữ liệu phiếu nhập kho chuẩn (`WMSInboundReceiptPayload`).
   - Đẩy trực tiếp vào hệ thống quản lý kho hoặc xuất file Excel chuẩn `import-template.xlsx`.
3. **Dỡ hàng & Nhập kệ kho (Putaway)**:
   - Thủ kho quét barcode/RFID theo danh sách SKU đã duyệt.
   - Đưa hàng vào đúng vị trí kệ (Bin location).

---

## 📌 Quy Trình 5: Quản Lý Thời Hạn Gửi Kho Ngoại Quan (Storage & Retention)

- **Thời hạn lưu giữ**: Tối đa **12 tháng** kể từ ngày hàng hóa đưa vào kho ngoại quan.
- **Gia hạn**: Trường hợp có lý do chính đáng, Cục trưởng Cục Hải quan gia hạn một lần không quá **12 tháng**.
- Quá thời hạn trên, nếu chủ hàng không đưa hàng ra khỏi kho hoặc không tái xuất, cơ quan hải quan tổ chức thanh lý/xử lý theo quy định của pháp luật.

---

## 📌 Quy Trình 6: Đưa Hàng Ra Khỏi Kho Ngoại Quan (Outbound Procedures)

1. **Các hình thức xuất kho**:
   - Xuất khẩu ra nước ngoài (Mã loại hình B11 hoặc tái xuất).
   - Nhập khẩu vào nội địa Việt Nam (Mã loại hình A11, A12, E21... kèm nộp thuế NK và VAT).
   - Chuyển sang kho ngoại quan khác.
2. **Thủ tục hải quan**:
   - Đăng ký tờ khai xuất kho ngoại quan (Mã loại hình **C21**).
   - Hệ thống đối soát trừ lùi tồn kho (Inventory decrement) trên WMS, đảm bảo số lượng xuất không vượt quá số lượng tồn kho khả dụng.
