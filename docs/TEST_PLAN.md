# Kế Hoạch Kiểm Thử (Test Plan)

## Hệ Thống AI Xử Lý Chứng Từ Kho Ngoại Quan (Vietnamese Bonded Warehouse AI)

---

## 1. Mục Tiêu & Phạm Vi Kiểm Thử (Objectives & Scope)

Mục tiêu của kế hoạch kiểm thử nhằm bảo đảm tính chính xác tuyệt đối, sự ổn định và tuân thủ các quy tắc bất biến trong kiến trúc:
1. **Kiểm thử Động cơ Đối Soát Tất Định (Deterministic Validation Engine)**: Đảm bảo 100% logic số học, mã HS và quy tắc hải quan hoạt động chính xác, không sai số.
2. **Kiểm thử Quản lý Xung Đột & Tái Đối Soát (HITL & Dynamic Revalidation)**: Đảm bảo hệ thống không bao giờ tự ý sửa sai lệch, và luôn tự động chạy lại kiểm tra khi có can thiệp.
3. **Kiểm thử Cổng Chặn WMS (Gatekeeper)**: Xác minh việc khóa cứng đường truyền khi có lỗi hoặc chưa ký duyệt.
4. **Kiểm thử Bảo Toàn Chứng Từ & Bảo Mật**: Kiểm tra mã băm SHA-256, cấm rò rỉ API key ra client.
5. **Kiểm thử Môi Trường Windows 10 Localhost**: Xác minh việc không bị khóa tệp SQLite (`WinError 32`) khi thao tác song song.

---

## 2. Chiến Lược Kiểm Thử (Testing Strategy)

| Tầng Kiểm Thử | Công Cụ & Thư Viện | Đối Tượng Kiểm Thử | Tiêu Chí Đạt (Pass Criteria) |
|:---|:---|:---|:---|
| **Unit Test** | `pytest` | Các hàm kiểm tra độc lập trong `validation_engine` | 100% test case toán học, mã HS, trọng lượng pass. |
| **Integration Test** | `pytest`, `httpx` | Luồng đối soát chéo Đa PO/SKU, Revalidation, WMS Gatekeeper | Chạy mượt mà trên database SQLite in-memory / file WAL. |
| **Security Test** | `pytest`, grep scripts | Quét rò rỉ key trong mã nguồn frontend và file log | Không tìm thấy bất kỳ chuỗi API key nào ở frontend. |
| **End-to-End Test** | Playwright / React Test Lib | Giao diện tải tệp, hiển thị bảng đối soát, hộp thoại Override | Luồng tương tác người dùng mượt mà, phản hồi tiếng Việt chuẩn. |

---

## 3. Danh Mục Các Ca Kiểm Thử Trọng Yếu (Test Matrix)

### TC-VAL-01: Kiểm tra tính toán số học dòng hàng (`VAL-PRC-001`)
- **Điều kiện**: Hàng có $Qty = 100$, $Price = 25.50$.
- **Kịch bản A (Đúng)**: $Total = 2550.00$ $\rightarrow$ Kết quả: `PASS` (Không sinh Discrepancy).
- **Kịch bản B (Sai)**: $Total = 2500.00$ $\rightarrow$ Kết quả: `FAIL` (Sinh Discrepancy mức `ERROR`, chặn WMS).

### TC-VAL-02: Kiểm tra tổng trị giá hóa đơn (`VAL-PRC-002`)
- **Điều kiện**: Hóa đơn khai báo tổng 10,000 USD.
- **Kịch bản A (Khớp)**: Tổng cộng các dòng hàng bằng 10,000 USD $\rightarrow$ `PASS`.
- **Kịch bản B (Lệch)**: Tổng cộng các dòng hàng bằng 9,850 USD $\rightarrow$ `FAIL` (Mức `ERROR`).

### TC-VAL-03: Kiểm tra quy cách trọng lượng Gross / Net (`VAL-WGT-001`)
- **Kịch bản A**: $Gross = 1500$ kg, $Net = 1200$ kg $\rightarrow$ `PASS`.
- **Kịch bản B**: $Gross = 800$ kg, $Net = 1200$ kg $\rightarrow$ `FAIL` (Gross < Net là phi lý, sinh `ERROR`).

### TC-VAL-04: Định dạng Mã HS 8 số Việt Nam (`VAL-HS-001`)
- **Kịch bản A**: `8471.30.20` hoặc `84713020` $\rightarrow$ `PASS`.
- **Kịch bản B**: `8471` (4 số) hoặc `ABCD.12` $\rightarrow$ `FAIL` (Báo lỗi định dạng mã HS).

### TC-VAL-05: Đối soát tam giác số lượng SKU (`VAL-QTY-001`)
- **Kịch bản A**: $Qty_{PL} = 500$, $Qty_{CI} = 500$, $Qty_{Declaration} = 500$ $\rightarrow$ `PASS`.
- **Kịch bản B**: $Qty_{PL} = 500$, $Qty_{CI} = 480$, $Qty_{Declaration} = 500$ $\rightarrow$ `FAIL` (Sinh `ERROR`, lưu rõ 480 vs 500 kèm tên chứng từ nguồn).

### TC-GATE-01: Khóa Cổng WMS khi còn lỗi bất đồng bộ
- **Điều kiện**: Lô hàng có 1 lỗi `ERROR` ở trạng thái `OPEN`.
- **Hành động**: Gọi endpoint `/api/v1/wms/transmit/{id}`.
- **Kỳ vọng**: Trả về `HTTP 403 Forbidden` kèm thông báo lý do bằng tiếng Việt, cờ `is_blocked = True`.

### TC-GATE-02: Khóa Cổng WMS khi chưa có chữ ký duyệt
- **Điều kiện**: Lô hàng không còn lỗi (`VALIDATED`), nhưng `approval_status == 'PENDING'`.
- **Hành động**: Gọi endpoint `/api/v1/wms/transmit/{id}`.
- **Kỳ vọng**: Trả về `HTTP 403 Forbidden`, yêu cầu Giám sát viên ký duyệt trước.

### TC-GATE-03: Mở Cổng WMS khi đã hợp lệ và được ký duyệt
- **Điều kiện**: Lô hàng `VALIDATED` và `approval_status == 'APPROVED'`.
- **Hành động**: Gọi endpoint `/api/v1/wms/transmit/{id}`.
- **Kỳ vọng**: Trả về `HTTP 200 OK`, sinh payload WMS chuẩn hóa, chuyển trạng thái lô hàng thành `TRANSMITTED`.

### TC-REVAL-01: Tái kiểm tra động (Dynamic Revalidation)
- **Điều kiện**: Lô hàng đang ở trạng thái `DISCREPANT` do lỗi lệch số lượng.
- **Hành động**: Người dùng thực hiện `OVERRIDE` số lượng và nhập lý do giải trình.
- **Kỳ vọng**:
  - Bản ghi `AuditLog` được tạo mới với giá trị cũ, mới và lý do.
  - Động cơ tự động chạy lại kiểm tra.
  - Trạng thái lô hàng tự động chuyển từ `DISCREPANT` sang `VALIDATED`.

---

## 4. Hướng Dẫn Thực Thi Bộ Kiểm Thử (Execution Guide)

### Chạy kiểm thử tự động trên Windows 10 PowerShell:
```powershell
cd backend
py -m pytest -v
```

### Chạy kiểm thử kèm đo lường độ bao phủ (Coverage):
```powershell
cd backend
py -m pytest --cov=app tests/
```
