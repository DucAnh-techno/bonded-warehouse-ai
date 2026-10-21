# Từ Điển Dữ Liệu (Data Dictionary)

## Hệ Thống AI Xử Lý Chứng Từ Kho Ngoại Quan (Vietnamese Bonded Warehouse AI)

---

## 1. Bảng `shipments` (Hồ Sơ Lô Hàng Kho Ngoại Quan)

| Tên Cột | Kiểu Dữ Liệu | Ràng Buộc | Ý Nghĩa Nghiệp Vụ | Ví Dụ |
|:---|:---|:---|:---|:---|
| `id` | `VARCHAR(36)` | PRIMARY KEY | Định danh duy nhất lô hàng (UUIDv4) | `a8b29c11-9452-4f33-b912-3c88421b8f01` |
| `shipment_code` | `VARCHAR(64)` | UNIQUE, NOT NULL, INDEX | Mã quản lý lô hàng nội bộ | `SHP-2026-001` |
| `customs_declaration_no` | `VARCHAR(64)` | NULLABLE, INDEX | Số tờ khai hải quan (VNACCS) | `100234567890` |
| `warehouse_type` | `VARCHAR(32)` | DEFAULT 'BONDED' | Loại hình kho hải quan | `BONDED` (Kho ngoại quan) |
| `direction` | `VARCHAR(16)` | DEFAULT 'INBOUND' | Hướng vận chuyển | `INBOUND` (Nhập kho), `OUTBOUND` (Xuất kho) |
| `status` | `VARCHAR(32)` | DEFAULT 'DRAFT', INDEX | Trạng thái vòng đời lô hàng | `DRAFT`, `EXTRACTING`, `RECONCILING`, `DISCREPANT`, `VALIDATED`, `APPROVED`, `TRANSMITTED` |
| `approval_status` | `VARCHAR(32)` | DEFAULT 'PENDING' | Trạng thái ký duyệt giám sát | `PENDING`, `APPROVED`, `REJECTED` |
| `approved_by` | `VARCHAR(64)` | NULLABLE | Người ký duyệt | `supervisor_le` |
| `approved_at` | `DATETIME` | NULLABLE | Thời điểm ký duyệt | `2026-10-09 20:30:00` |
| `notes` | `TEXT` | NULLABLE | Ghi chú nghiệp vụ | `Lô hàng linh kiện điện tử giao theo 2 PO` |
| `created_at` | `DATETIME` | NOT NULL | Thời gian tạo | `2026-10-09 19:00:00` |
| `updated_at` | `DATETIME` | NOT NULL | Thời gian cập nhật gần nhất | `2026-10-09 20:30:00` |

---

## 2. Bảng `documents` (Chứng Từ Gốc Được Bảo Tồn)

| Tên Cột | Kiểu Dữ Liệu | Ràng Buộc | Ý Nghĩa Nghiệp Vụ | Ví Dụ |
|:---|:---|:---|:---|:---|
| `id` | `VARCHAR(36)` | PRIMARY KEY | Định danh chứng từ (UUIDv4) | `c5f89110-82a1-432d-94bb-124b89f0a202` |
| `shipment_id` | `VARCHAR(36)` | FOREIGN KEY (`shipments.id`), INDEX | Khóa ngoại liên kết tới lô hàng | `a8b29c11-9452-4f33-b912-3c88421b8f01` |
| `document_type` | `VARCHAR(48)` | NOT NULL, INDEX | Phân loại chứng từ | `CUSTOMS_DECLARATION`, `COMMERCIAL_INVOICE`, `PACKING_LIST`, `BILL_OF_LADING`, `PURCHASE_ORDER` |
| `original_filename` | `VARCHAR(255)` | NOT NULL | Tên tệp gốc người dùng tải lên | `To_Khai_HQ_100234567890.pdf` |
| `storage_path` | `VARCHAR(500)` | NOT NULL | Đường dẫn lưu trữ bất biến | `data/uploads/9b10a24f0c7a.pdf` |
| `mime_type` | `VARCHAR(100)` | NOT NULL | Định dạng tệp | `application/pdf`, `image/png` |
| `file_size_bytes` | `INTEGER` | NOT NULL | Dung lượng tệp tính bằng byte | `2458900` |
| `sha256_hash` | `VARCHAR(64)` | NOT NULL, INDEX | Mã băm toàn vẹn SHA-256 | `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855` |
| `page_count` | `INTEGER` | DEFAULT 1 | Số trang tài liệu | `4` |
| `uploaded_at` | `DATETIME` | NOT NULL | Thời điểm tải lên | `2026-10-09 19:05:00` |

---

## 3. Bảng `document_extractions` (Kết Quả Trích Xuất AI Độc Lập)

| Tên Cột | Kiểu Dữ Liệu | Ràng Buộc | Ý Nghĩa Nghiệp Vụ | Ví Dụ |
|:---|:---|:---|:---|:---|
| `id` | `VARCHAR(36)` | PRIMARY KEY | Định danh bản trích xuất (UUIDv4) | `f1a89c31-9231-41fa-89df-128a9b23c401` |
| `document_id` | `VARCHAR(36)` | FOREIGN KEY (`documents.id`), UNIQUE, INDEX | Chứng từ được trích xuất | `c5f89110-82a1-432d-94bb-124b89f0a202` |
| `status` | `VARCHAR(32)` | DEFAULT 'PENDING' | Trạng thái trích xuất | `PENDING`, `SUCCESS`, `FAILED` |
| `model_name` | `VARCHAR(64)` | NOT NULL | Mô hình AI thực thi | `gemini-2.5-flash` |
| `raw_response_json` | `TEXT` | NOT NULL | Dữ liệu JSON gốc từ Gemini API | `{"document_type_detected": "...", "items": [...]}` |
| `confidence_score` | `FLOAT` | NULLABLE | Độ tin cậy trung bình của AI | `0.98` |
| `error_message` | `TEXT` | NULLABLE | Chi tiết lỗi nếu trích xuất thất bại | `Quota exceeded / Parse error` |
| `extracted_header_json`| `TEXT` | NULLABLE | JSON chuẩn hóa thông tin tiêu đề | `{"doc_no": "...", "containers": [...]}` |
| `extracted_at` | `DATETIME` | NOT NULL | Thời điểm trích xuất | `2026-10-09 19:06:30` |
| `version` | `INTEGER` | DEFAULT 1 | Phiên bản trích xuất | `1` |

---

## 4. Bảng `extracted_line_items` (Chi Tiết Dòng Hàng SKU)

| Tên Cột | Kiểu Dữ Liệu | Ràng Buộc | Ý Nghĩa Nghiệp Vụ | Ví Dụ |
|:---|:---|:---|:---|:---|
| `id` | `VARCHAR(36)` | PRIMARY KEY | Định danh dòng hàng (UUIDv4) | `882a1c02-7711-40be-b439-01289cba4110` |
| `extraction_id` | `VARCHAR(36)` | FOREIGN KEY (`document_extractions.id`), INDEX | Khóa ngoại tới kết quả trích xuất | `f1a89c31-9231-41fa-89df-128a9b23c401` |
| `item_index` | `INTEGER` | DEFAULT 1 | Số thứ tự dòng hàng | `1` |
| `sku` | `VARCHAR(100)` | NULLABLE, INDEX | Mã sản phẩm / Part Number | `SKU-IC-STM32` |
| `part_number` | `VARCHAR(100)` | NULLABLE | Mã phụ tùng nhà sản xuất | `STM32F407VGT6` |
| `description_vi` | `VARCHAR(500)` | NOT NULL | Tên hàng hóa tiếng Việt / Anh | `Vi điều khiển 32-bit ARM Cortex-M4` |
| `hs_code` | `VARCHAR(32)` | NULLABLE, INDEX | Mã số HS 8 chữ số | `8542.31.00` |
| `quantity` | `FLOAT` | NOT NULL | Số lượng hàng | `5000.0` |
| `uom` | `VARCHAR(32)` | NULLABLE | Đơn vị tính | `PCS` |
| `unit_price` | `FLOAT` | NULLABLE | Đơn giá khai báo/hóa đơn | `4.25` |
| `total_amount` | `FLOAT` | NULLABLE | Thành tiền ($Qty \times Price$) | `21250.00` |
| `currency` | `VARCHAR(10)` | DEFAULT 'USD' | Loại tiền tệ | `USD` |
| `gross_weight_kg` | `FLOAT` | NULLABLE | Trọng lượng cả bì (kg) | `120.5` |
| `net_weight_kg` | `FLOAT` | NULLABLE | Trọng lượng tịnh (kg) | `115.0` |
| `po_reference` | `VARCHAR(100)` | NULLABLE, INDEX | Số đơn đặt hàng PO đối ứng | `PO-2026-HANOI-01` |
| `page_number` | `INTEGER` | DEFAULT 1 | Số trang xuất hiện trong tệp | `2` |

---

## 5. Bảng `discrepancies` (Sai Lệch & Bất Đồng Bộ Dữ Liệu)

| Tên Cột | Kiểu Dữ Liệu | Ràng Buộc | Ý Nghĩa Nghiệp Vụ | Ví Dụ |
|:---|:---|:---|:---|:---|
| `id` | `VARCHAR(36)` | PRIMARY KEY | Định danh sai lệch (UUIDv4) | `d720bca1-1901-49fa-aa81-889921bcfa01` |
| `shipment_id` | `VARCHAR(36)` | FOREIGN KEY (`shipments.id`), INDEX | Lô hàng liên quan | `a8b29c11-9452-4f33-b912-3c88421b8f01` |
| `rule_code` | `VARCHAR(32)` | NOT NULL, INDEX | Mã quy tắc đối soát vi phạm | `VAL-QTY-001`, `VAL-HS-001`, `VAL-PRC-001` |
| `severity` | `VARCHAR(16)` | NOT NULL | Mức độ nghiêm trọng | `ERROR` (Chặn WMS), `WARNING` (Cảnh báo) |
| `field_name` | `VARCHAR(100)` | NOT NULL | Trường thông tin xảy ra sai lệch | `sku[SKU-IC-STM32].quantity` |
| `description_vi` | `TEXT` | NOT NULL | Mô tả chi tiết sai lệch bằng tiếng Việt | `Sai lệch số lượng: Invoice ghi 5000, Packing List ghi 4800` |
| `source_doc_a_name` | `VARCHAR(255)` | NULLABLE | Tên chứng từ nguồn A | `Commercial_Invoice.pdf` |
| `value_a` | `TEXT` | NULLABLE | Giá trị trích xuất nguồn A | `5000` |
| `source_doc_b_name` | `VARCHAR(255)` | NULLABLE | Tên chứng từ nguồn B | `Packing_List.pdf` |
| `value_b` | `TEXT` | NULLABLE | Giá trị trích xuất nguồn B | `4800` |
| `status` | `VARCHAR(32)` | DEFAULT 'OPEN', INDEX | Trạng thái giải quyết (Cấm tự động đoán) | `OPEN`, `OVERRIDDEN`, `ACCEPTED`, `REJECTED` |
| `resolution_action` | `VARCHAR(32)` | NULLABLE | Hành động can thiệp của con người | `OVERRIDE` |
| `resolution_reason` | `TEXT` | NULLABLE | Bắt buộc nhập lý do nghiệp vụ | `Nhà cung cấp gửi bù 200 con ở đợt giao sau` |
| `resolved_by` | `VARCHAR(100)` | NULLABLE | Cán bộ thực hiện can thiệp | `operator_minh` |
| `resolved_at` | `DATETIME` | NULLABLE | Thời điểm can thiệp | `2026-10-09 20:15:00` |

---

## 6. Bảng `audit_logs` (Nhật Ký Kiểm Toán Bất Biến)

| Tên Cột | Kiểu Dữ Liệu | Ràng Buộc | Ý Nghĩa Nghiệp Vụ | Ví Dụ |
|:---|:---|:---|:---|:---|
| `id` | `VARCHAR(36)` | PRIMARY KEY | Định danh dòng nhật ký (UUIDv4) | `991a2b00-3312-4cca-b991-889921bcfa22` |
| `shipment_id` | `VARCHAR(36)` | FOREIGN KEY (`shipments.id`), INDEX | Lô hàng liên quan | `a8b29c11-9452-4f33-b912-3c88421b8f01` |
| `action` | `VARCHAR(64)` | NOT NULL, INDEX | Hành động nghiệp vụ | `FIELD_OVERRIDE`, `REVALIDATION_TRIGGERED`, `DISCREPANCY_RESOLVED`, `WMS_APPROVAL` |
| `target_entity` | `VARCHAR(64)` | NOT NULL | Đối tượng bị tác động | `Discrepancy`, `ExtractedLineItem`, `Shipment` |
| `field_name` | `VARCHAR(100)` | NULLABLE | Tên trường bị sửa đổi | `quantity` |
| `old_value` | `TEXT` | NULLABLE | Giá trị cũ | `5000` |
| `new_value` | `TEXT` | NULLABLE | Giá trị mới | `4800` |
| `user_id` | `VARCHAR(100)` | NOT NULL | Tài khoản thực hiện | `operator_minh` |
| `reason` | `TEXT` | NULLABLE | Lý do giải trình | `Điều chỉnh theo số lượng thực tế kiểm đếm` |
| `timestamp` | `DATETIME` | NOT NULL, INDEX | Thời điểm ghi nhận | `2026-10-09 20:15:00` |

---

## 7. Bảng `wms_transmissions` (Giao Dịch Đẩy Dữ Liệu WMS)

| Tên Cột | Kiểu Dữ Liệu | Ràng Buộc | Ý Nghĩa Nghiệp Vụ | Ví Dụ |
|:---|:---|:---|:---|:---|
| `id` | `VARCHAR(36)` | PRIMARY KEY | Định danh phiên truyền (UUIDv4) | `771a2b00-9901-4cca-b991-889921bcfa99` |
| `shipment_id` | `VARCHAR(36)` | FOREIGN KEY (`shipments.id`), INDEX | Lô hàng liên quan | `a8b29c11-9452-4f33-b912-3c88421b8f01` |
| `status` | `VARCHAR(32)` | DEFAULT 'BLOCKED', INDEX | Trạng thái cổng truyền | `BLOCKED`, `READY`, `TRANSMITTED`, `FAILED` |
| `is_blocked` | `BOOLEAN` | DEFAULT TRUE | Cờ chặn cứng | `TRUE` (Khóa), `FALSE` (Đã mở khóa) |
| `blocking_reason` | `TEXT` | NULLABLE | Lý do đang bị chặn | `Còn 2 lỗi ERROR chưa giải quyết` |
| `approved_by` | `VARCHAR(100)` | NULLABLE | Cán bộ ký duyệt | `supervisor_le` |
| `payload_json` | `TEXT` | NULLABLE | Dữ liệu JSON đẩy xuống WMS | `{"receipt_id": "...", "line_items": [...]}` |
| `wms_response_code` | `INTEGER` | NULLABLE | Mã phản hồi từ WMS | `200` |
| `wms_response_body` | `TEXT` | NULLABLE | Chi tiết phản hồi từ WMS | `{"status": "SUCCESS", "receipt_no": "REC-01"}` |
| `transmitted_at` | `DATETIME` | NULLABLE | Thời điểm truyền thành công | `2026-10-09 20:35:00` |
