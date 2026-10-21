# Bộ Dữ Liệu Chuẩn Thực Nghiệm (Ground Truth Benchmark Datasets)

## 1. Mục Đích Nghiên Cứu Khoa Học
Thư mục này lưu trữ các bộ dữ liệu **Ground Truth (Human Gold Standard)** được kiểm định thủ công 100% bởi các chuyên gia thủ tục hải quan và logistics kho ngoại quan.

Dữ liệu này đóng vai trò là "chân lý" để đánh giá định lượng:
1. **Độ chính xác của mô hình Trích xuất Thực thể AI (Multimodal Entity Extraction Evaluation)**:
   - Đánh giá mô hình Google Gemini trên các trường thông tin: Số tờ khai, ngày phát hành, Container, Seal, SKU, Mã HS, Số lượng, Đơn giá, Thành tiền.
   - Các chỉ số: **Precision**, **Recall**, **F1-Score**, **Field-Level Exact Match (EM)**.
2. **Độ nhạy và độ chính xác của Động cơ Đối Soát Tất Định (Deterministic Validation Engine Evaluation)**:
   - Tỷ lệ phát hiện sai lệch thực tế (**True Positive Rate - Sensitivity**).
   - Tỷ lệ cảnh báo sai lệch giả (**False Positive Rate - Type I Error**).

---

## 2. Tiêu Chuẩn Định Dạng Ground Truth JSON

Mỗi bộ hồ sơ mẫu được biểu diễn dưới dạng JSON chuẩn hóa gồm:
- `shipment_metadata`: Thông tin lô hàng thực nghiệm.
- `documents_gold_truth`: Dữ liệu chính xác 100% của từng chứng từ.
- `expected_discrepancies`: Danh sách các lỗi và bất đồng bộ đã được thiết kế sẵn để kiểm tra động cơ đối soát.
- `expected_wms_payload`: Dữ liệu đầu ra mong đợi sau khi vượt qua cổng kiểm soát.

---

## 3. Các Tệp Dữ Liệu Tham Chiếu
- [`sample-ground-truth-benchmark.json`](./sample-ground-truth-benchmark.json): Bộ dữ liệu chuẩn cho lô hàng điện tử 4 SKU giao theo 2 PO.
