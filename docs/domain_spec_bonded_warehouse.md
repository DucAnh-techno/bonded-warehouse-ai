# Quy Chuẩn Nghiệp Vụ Kho Ngoại Quan (Vietnamese Bonded Warehouse Domain Specification)

## 1. Cơ Sở Pháp Lý
- **Luật Hải quan số 54/2014/QH13**.
- **Nghị định 08/2015/NĐ-CP** (sửa đổi, bổ sung bởi Nghị định 59/2018/NĐ-CP): Quy định chi tiết thi hành Luật Hải quan về thủ tục hải quan, kiểm tra, giám sát, kiểm soát hải quan.
- **Thông tư 38/2015/TT-BTC** và **Thông tư 39/2018/TT-BTC** của Bộ Tài chính: Quy định về thủ tục hải quan đối với hàng hóa đưa vào, lưu giữ, đưa ra kho ngoại quan.

---

## 2. Các Loại Chứng Từ Cốt Lõi Trong Hồ Sơ Nhập / Xuất Kho Ngoại Quan

| Tên Chứng Từ | Tiếng Anh / Viết Tắt | Cơ Quan / Đơn Vị Phát Hành | Vai Trò & Các Trường Thông Tin Trọng Yếu |
|:---|:---|:---|:---|
| **Tờ khai hải quan** | Customs Declaration (VNACCS) | Tổng cục Hải quan / Chi cục Hải quan quản lý | - Số tờ khai, ngày đăng ký, mã loại hình (C11: Gửi kho ngoại quan; C21: Đưa hàng ra khỏi kho ngoại quan).<br>- Tên người nhập/xuất, đại lý hải quan.<br>- Bảng danh mục dòng hàng: Tên hàng, mã HS (8 số), lượng khai báo, đơn vị tính, đơn giá hóa đơn, trị giá khai báo. |
| **Hóa đơn thương mại** | Commercial Invoice (CI) | Người bán / Nhà cung cấp nước ngoài | - Số hóa đơn, ngày phát hành, đồng tiền thanh toán (USD, EUR,...).<br>- Điều kiện giao hàng (Incoterms: CIF, FOB, CFR, DDP...).<br>- Chi tiết đơn giá, chiết khấu, tổng trị giá thanh toán. |
| **Phiếu đóng gói hàng hóa** | Packing List (PL) | Nhà cung cấp / Đơn vị đóng gói | - Quy cách đóng gói (thùng carton, pallet, kiện).<br>- Số kiện (*Packages*), Trọng lượng tịnh (*Net Weight - NW*), Trọng lượng cả bì (*Gross Weight - GW*), Thể tích (*CBM*).<br>- Phân bổ SKU theo từng kiện/pallet. |
| **Vận tải đơn** | Bill of Lading (B/L) / Air Waybill (AWB) | Hãng tàu / Hãng hàng không / Forwarder | - Số vận đơn, tên tàu, số chuyến (*Vessel / Voyage*).<br>- Cảng xếp (*POL*), Cảng dỡ (*POD*).<br>- Số container, số niêm chì (*Seal number*).<br>- Tổng trọng lượng Gross, số kiện tổng. |
| **Đơn đặt hàng** | Purchase Order (PO) | Doanh nghiệp mua hàng | - Số hợp đồng/PO, danh sách SKU đặt mua, số lượng cam kết, đơn giá thỏa thuận.<br>- Hỗ trợ **nhiều PO** gộp chung trong 1 lô hàng giao vào kho. |
| **Phiếu nhập/xuất kho** | Goods Receipt / Issue Note (GRN/GIN) | Thủ kho / Hệ thống WMS Kho Ngoại Quan | - Ghi nhận thực tế số lượng hàng nhập vào kệ (*bin/rack*), tình trạng bao bì, đối soát với tờ khai được thông quan. |
| **Chứng nhận xuất xứ** | Certificate of Origin (C/O) | Cơ quan thẩm quyền nước xuất khẩu | - Mẫu C/O (Form E, Form D, Form AK, Form EUR.1,...), tiêu chí xuất xứ. |

---

## 3. Quy Trình Đối Soát & Kiểm Soát Rủi Ro (Reconciliation & Risk Rules)

### 3.1 Cấp Độ Dòng Hàng (Line Item / SKU Level)
1. **Kiểm tra Đối Ứng Số Lượng (Quantity Triangulation)**:
   $$\text{Số lượng trên PL (chi tiết kiện)} = \text{Số lượng trên CI (tính tiền)} = \text{Số lượng trên Tờ khai HQ (thông quan)}$$
2. **Kiểm tra Toán Học (Mathematical Integrity)**:
   $$\text{Thành tiền từng dòng} = \text{Số lượng} \times \text{Đơn giá} \quad (\pm 0.01)$$
   $$\text{Tổng trị giá hóa đơn} = \sum \text{Thành tiền từng dòng}$$
3. **Mã Số Hàng Hóa (HS Code Consistency)**:
   - Mã HS Việt Nam phải gồm 8 chữ số (hoặc nhóm 4 số `####.##.##`).
   - Mã HS khai báo hải quan phải khớp với mô tả kỹ thuật và mã HS trên Commercial Invoice / PO.

### 3.2 Cấp Độ Lô Hàng & Vận Chuyển (Consignment Level)
1. **Trọng lượng (Weight Invariance)**:
   $$\text{Gross Weight} \ge \text{Net Weight} > 0$$
   $$\left|\text{Gross Weight}_{B/L} - \text{Gross Weight}_{PL}\right| \le \text{Ngưỡng sai số cho phép (0.5\%) }$$
2. **Số Container & Số Seal**:
   - Khớp nối chính xác 100% giữa B/L, Packing List và ghi chú trên Tờ khai hải quan.
3. **Quan Hệ Đa Đơn Hàng (Multi-PO)**:
   - Cho phép 1 lô hàng chứa hàng hóa của nhiều PO khác nhau.
   - Mỗi dòng hàng được liên kết với `po_reference` tương ứng để theo dõi tiến độ hoàn thành đơn hàng.

---

## 4. Cơ Chế Chặn Cổng WMS (WMS Transmission Gatekeeper)
Hệ thống không cho phép truyền dữ liệu xuống WMS (*Kho ngoại quan*) khi:
- Tồn tại bất kỳ cảnh báo mức độ `ERROR` chưa được giải quyết.
- Trạng thái đối soát chưa đạt `VALIDATED`.
- Chưa có chữ ký phê duyệt (*Supervisor Approval*) của cán bộ phụ trách.
