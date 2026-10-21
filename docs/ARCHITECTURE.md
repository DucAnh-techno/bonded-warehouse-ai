# Kiến Trúc Hệ Thống (System Architecture Document)

## Hệ Thống AI Xử Lý Chứng Từ Kho Ngoại Quan (Vietnamese Bonded Warehouse AI)

---

## 1. Kiến Trúc Tổng Thể (System Architecture Overview)

Hệ thống được thiết kế theo mô hình **Client - Server Decoupled Architecture** (Frontend và Backend phân tách hoàn toàn), hướng dịch vụ mô-đun hóa (Modular Service-Oriented).

```mermaid
flowchart TB
    subgraph UI["Tầng Giao Diện (Frontend - React + TypeScript + Vite + Tailwind)"]
        UI_Shipment["Quản Lý Lô Hàng (Shipment View)"]
        UI_Upload["Tải Lên Chứng Từ & Phân Loại"]
        UI_Recon["Bảng Đối Soát Chéo Đa PO/SKU"]
        UI_HITL["Panel Xử Lý Bất Đồng Bộ (HITL Discrepancy)"]
        UI_Audit["Nhật Ký Kiểm Toán & Revalidation"]
        UI_WMS["Cổng Kiểm Soát & Xuất Dữ Liệu WMS"]
    end

    subgraph API_GW["Tầng Tiếp Nhận & Điều Phối (FastAPI Gateway)"]
        APIRouter["API Router (/api/v1)"]
        CORSMiddleware["CORS Middleware"]
        AuthContext["Bảo Mật & Xác Thực Request"]
    end

    subgraph CoreServices["Tầng Dịch Vụ Nghiệp Vụ (Backend Services)"]
        DocParser["Dịch vụ Phân Tích & Lưu Trữ (document_parser)"]
        AIService["Dịch vụ AI Đa Phương Thức (ai / Gemini)"]
        ValEngine["Động Cơ Đối Soát Tất Định (validation)"]
        ExportService["Dịch vụ Phát Sinh Dữ Liệu & Payload (export)"]
        MockWMS["Dịch vụ Mô Phỏng WMS (mock_wms)"]
    end

    subgraph DataTier["Tầng Lưu Trữ & Quản Lý Dữ Liệu (Persistence)"]
        DB[(SQLite WAL Mode)]
        DocStorage[("Kho Tệp Bất Biến (data/uploads/)")]
    end

    subgraph External["Tích Hợp Bên Ngoài (External Services)"]
        GeminiAPI["Google Gemini Multimodal API (2.5-Flash)"]
        WMS_Target["Enterprise WMS / ERP Webhook"]
    end

    UI -->|HTTP REST JSON| API_GW
    API_GW --> CoreServices

    DocParser -->|Lưu tệp nguyên bản & Băm SHA-256| DocStorage
    DocParser -->|Tạo bản ghi Document| DB

    AIService -->|Gửi tệp đa phương thức| GeminiAPI
    GeminiAPI -->|JSON Cấu Trúc Chặt Chẽ| AIService
    AIService -->|Lưu kết quả độc lập| DB

    ValEngine -->|Truy vấn dữ liệu chi tiết| DB
    ValEngine -->|Tạo Discrepancy & AuditLog| DB

    ExportService -->|Kiểm tra điều kiện mở cổng| DB
    ExportService -->|Đẩy phiếu nhập/xuất kho| MockWMS
    MockWMS -->|Giao tiếp API| WMS_Target
```

---

## 2. Chi Tiết Các Mô-đun Dịch Vụ (Backend Services Breakdown)

### 2.1 `app/services/document_parser/`
- **Chức năng**:
  - Quản lý tệp tải lên an toàn, bảo toàn 100% dữ liệu gốc (Byte-for-byte immutability).
  - Tính toán mã băm SHA-256 xác thực tính toàn vẹn.
  - Phân loại phần mở rộng MIME, hỗ trợ PDF, PNG, JPG, JPEG, TIFF.
  - Quản lý đường dẫn lưu trữ bất biến tại `data/uploads/` bằng định danh UUIDv4.

### 2.2 `app/services/ai/`
- **Chức năng**:
  - Giao tiếp với Google Gemini API thông qua SDK chính thức.
  - Kỹ thuật tạo Prompt nghiệp vụ Hải quan kho ngoại quan Việt Nam.
  - Thực thi kỹ thuật **Pydantic Structured Outputs** (`response_schema`), đảm bảo dữ liệu trả về 100% chuẩn JSON có cấu trúc.
  - Trích xuất độc lập từng chứng từ: Tờ khai hải quan VNACCS, Commercial Invoice, Packing List, Bill of Lading, Purchase Order.

### 2.3 `app/services/validation/`
- **Chức năng**:
  - **100% logic Python tất định (Deterministic Logic)**. AI không bao giờ được dùng để tự đưa ra phán quyết hay tự điều chỉnh số liệu.
  - Kiểm tra toán học dòng hàng ($Qty \times Price == Total$), tổng hóa đơn, tỷ trọng Gross/Net.
  - Đối soát chéo số lượng giữa các chứng từ (Tam giác số lượng: PL vs CI vs Tờ khai).
  - Kiểm tra định dạng chuẩn Mã HS Việt Nam (8 chữ số).
  - Phát hiện xung đột và ghi nhận bản ghi `Discrepancy` ở trạng thái `OPEN`.
  - Hỗ trợ **Dynamic Revalidation**: Khi người dùng chỉnh sửa dữ liệu, dịch vụ chỉ định chạy lại các quy tắc bị ảnh hưởng và cập nhật trạng thái ngay lập tức.

### 2.4 `app/services/export/`
- **Chức năng**:
  - Chuẩn hóa dữ liệu dòng hàng sau khi đối soát thành công thành cấu trúc phiếu nhập kho (`WMSInboundReceiptPayload`) hoặc xuất kho ngoại quan.
  - Xuất dữ liệu đa định dạng: JSON chuẩn WMS, XML tờ khai, bảng tính Excel phục vụ đối soát nghiệp vụ.

### 2.5 `app/services/mock_wms/`
- **Chức năng**:
  - Cổng chặn (`Gatekeeper`): Kiểm tra trạng thái phê duyệt và tồn dư lỗi trước khi truyền dữ liệu.
  - Giả lập hệ thống WMS của doanh nghiệp kho ngoại quan tiếp nhận lệnh nhập/xuất kho và phản hồi mã trạng thái 200/400/422.

---

## 3. Quy Trình Vận Hành Dữ Liệu (Data Flow Lifecycle)

```mermaid
sequenceDiagram
    autonumber
    actor User as Nhân viên Kho
    actor Sup as Giám sát viên
    participant UI as Giao Diện React
    participant API as FastAPI Router
    participant Parser as document_parser
    participant AI as Gemini Extractor
    participant Val as Validation Engine
    participant DB as SQLite DB
    participant Gate as WMS Gatekeeper

    User->>UI: Tải lên hồ sơ (Tờ khai, Invoice, PL, B/L, PO)
    UI->>API: POST /documents/upload
    API->>Parser: Lưu tệp & Hash SHA-256 vào data/uploads/
    Parser->>DB: Ghi bản ghi Document
    API-->>UI: Upload thành công

    User->>UI: Bấm "Trích xuất AI"
    UI->>API: POST /extractions/extract/{doc_id}
    API->>AI: Gửi tệp & Prompt chuyên ngành tới Gemini
    AI->>DB: Lưu DocumentExtraction & ExtractedLineItem
    API->>Val: Tự động kích hoạt đối soát chéo (Reconcile)
    Val->>DB: Sinh Discrepancies (Lỗi số lượng, HS code,...)
    API-->>UI: Hiển thị kết quả & cảnh báo sai lệch

    User->>UI: Xem xét & Ghi đè (Override / Giải trình)
    UI->>API: POST /validations/discrepancies/{id}/resolve
    API->>DB: Ghi AuditLog & Cập nhật Discrepancy
    API->>Val: Tự động Tái kiểm tra (Dynamic Revalidation)
    Val->>DB: Cập nhật trạng thái Shipment -> VALIDATED
    API-->>UI: Trạng thái cập nhật thành công

    Sup->>UI: Ký duyệt lô hàng (Approval Sign-off)
    UI->>API: POST /wms/approve/{shipment_id}
    API->>DB: Cập nhật approval_status = APPROVED

    Sup->>UI: Bấm "Truyền WMS"
    UI->>API: POST /wms/transmit/{shipment_id}
    API->>Gate: Kiểm tra điều kiện mở cổng (Zero Error + Approved)
    Gate->>DB: Tạo WMSTransmission & Lưu Payload JSON
    API-->>UI: Truyền WMS thành công (HTTP 200)
```

---

## 4. Các Biện Pháp Đảm Bảo Tương Thích Windows 10 Localhost

1. **Đường dẫn tệp**: 100% sử dụng thư viện chuẩn `pathlib.Path`.
2. **Cơ sở dữ liệu SQLite**: Cấu hình chế độ WAL (`PRAGMA journal_mode=WAL`), bật `foreign_keys=ON`, và thiết lập `busy_timeout=5000` để tránh lỗi khóa tệp Windows `WinError 32`.
3. **CORS & Proxy**: Vite thiết lập proxy chuyển tiếp cổng 5173 về 8000 của FastAPI mà không bị xung đột chính sách cùng nguồn gốc (SOP).
