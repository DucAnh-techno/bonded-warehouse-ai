# Báo Cáo Thực Nghiệm Khoa Học: Đánh Giá Hệ Thống AI Kho Ngoại Quan
*Mã Thí Nghiệm: BENCHMARK-BONDED-001*  
*Thời Gian Thực Hiện: 2026-10-10 18:59:14 UTC*  
*Mô Hình AI: gemini-3.8-flash*

---

## 1. Kết Quả Trích Xuất Dữ Liệu AI (Extraction Performance)

| Chỉ Số Đánh Giá | Giá Trị Thực Đo | Giải Thích Khoa Học |
|:---|:---:|:---|
| **Gold SKUs (Kỳ vọng)** | `4` | Số lượng mã hàng chuẩn trong hồ sơ gốc |
| **Extracted SKUs (Trích xuất)** | `4` | Số lượng mã hàng mô hình nhận diện |
| **True Positives (Khớp chính xác)** | `4` | Số SKU nhận diện đúng hoàn toàn |
| **Precision (Độ chuẩn xác)** | `100.00%` | Tỷ lệ SKU trích xuất là hợp lệ |
| **Recall (Độ thu hồi)** | `100.00%` | Tỷ lệ không bỏ sót SKU của hồ sơ |
| **F1-Score** | `100.00%` | Trung bình điều hòa giữa Precision và Recall |
| **Field-level Accuracy** | `100.00%` | Tỷ lệ khớp chính xác trường (HS, Qty, Price, PO) |

---

## 2. Kết Quả Động Cơ Đối Soát Tất Định (Validation Detection)

| Chỉ Số Đánh Giá | Giá Trị Thực Đo | Đánh Giá Nghiệp Vụ |
|:---|:---:|:---|
| **Lỗi Kỳ Vọng (Injected Errors)** | `2` | Số lỗi được cài đặt trong kịch bản kiểm thử |
| **Lỗi Phát Hiện (Detected)** | `2` | Số vi phạm động cơ tất định cảnh báo |
| **Detection Precision** | `100.00%` | Không phát sinh cảnh báo giả (Zero False Alarm) |
| **Detection Recall** | `100.00%` | Phát hiện 100% các sai lệch số lượng/mã HS |
| **Detection F1-Score** | `100.00%` | Hiệu quả toàn diện của 12 quy tắc tất định |

---

## 3. Tiêu Hao Tài Nguyên & Chi Phí API (Cost & Latency)

| Thông Số | Định Lượng | Đơn Vị |
|:---|:---:|:---|
| **Tổng Prompt Tokens** | `4,250` | tokens |
| **Tổng Candidate Tokens** | `860` | tokens |
| **Thời Gian Xử Lý Toàn Trình** | `3.85` | giây |
| **Thời Gian Xử Lý / Chứng Từ** | `0.96` | giây/chứng từ |
| **Ước Tính Chi Phí API / Lô Hàng** | `$0.000577` | USD |
| **Ước Tính Chi Phí / Chứng Từ** | `$0.000144` | USD |
