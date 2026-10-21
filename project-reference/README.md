# Thư Mục Tài Liệu Tham Chiếu Dự Án (Project Reference Repository)

**Hệ Thống AI Xử Lý Chứng Từ Kho Ngoại Quan (Vietnamese Bonded Warehouse AI)**  
*Mục đích: Cung cấp kho dữ liệu mẫu, biểu mẫu chuẩn WMS, quy trình nghiệp vụ kho ngoại quan thực tế và dữ liệu Ground Truth phục vụ nghiên cứu khoa học.*

---

## 📂 Cấu Trúc Tổng Thể

```
project-reference/
├── sample-documents/              # Bộ tài liệu chứng từ mẫu đầy đủ của hồ sơ hải quan
│   ├── packing-list/              # Phiếu đóng gói hàng hóa (Packing List - PL)
│   ├── commercial-invoice/        # Hóa đơn thương mại (Commercial Invoice - CI)
│   ├── bill-of-lading/            # Vận đơn đường biển / hàng không (B/L / AWB)
│   ├── customs-declaration/       # Tờ khai hải quan điện tử (VNACCS/VCIS Form HQ/2015/NK)
│   └── contract/                  # Hợp đồng ngoại thương & Hợp đồng thuê kho ngoại quan
├── wms-template/                  # Biểu mẫu nhập liệu chuẩn tích hợp hệ thống WMS
│   └── import-template.xlsx       # Tệp Excel mẫu phiếu nhập kho ngoại quan chuẩn hóa
├── warehouse-procedures/          # Quy trình vận hành tiêu chuẩn (SOP) kho ngoại quan tại Việt Nam
└── ground-truth/                  # Bộ dữ liệu chân lý phục vụ đánh giá mô hình AI & OCR
```

---

## 🏛️ Ý Nghĩa Nghiệp Vụ & Nghiên Cứu

1. **Bộ chứng từ mẫu (`sample-documents/`)**:
   - Tái lập các tình huống thực tế của hồ sơ nhập kho ngoại quan theo mã loại hình **C11** (Hàng hóa gửi kho ngoại quan) và **C21** (Hàng hóa đưa ra khỏi kho ngoại quan).
   - Mô phỏng trường hợp **Đa PO (Multi-PO)**, **Đa SKU (Multi-SKU)**, và các trường hợp cố ý tạo sai lệch (Discrepancy test cases) để kiểm thử động cơ đối soát tất định.

2. **Biểu mẫu WMS (`wms-template/`)**:
   - `import-template.xlsx`: Tệp mẫu chứa 21 trường dữ liệu tiêu chuẩn theo quy cách của các hệ thống WMS/ERP doanh nghiệp kho vận tại Việt Nam.

3. **Quy trình kho ngoại quan (`warehouse-procedures/`)**:
   - Tài liệu hóa toàn diện các quy trình tác nghiệp chuẩn (SOP) theo Luật Hải quan 54/2014/QH13, Nghị định 08/2015/NĐ-CP, Thông tư 38/2015/TT-BTC và Thông tư 39/2018/TT-BTC.

4. **Dữ liệu chuẩn Ground Truth (`ground-truth/`)**:
   - Cung cấp nhãn dữ liệu thực tế chuẩn xác (Human Gold Standard) để đo lường độ chính xác (Precision, Recall, F1-Score) của mô hình Gemini Multimodal API và tỷ lệ phát hiện lỗi của Validation Engine.
