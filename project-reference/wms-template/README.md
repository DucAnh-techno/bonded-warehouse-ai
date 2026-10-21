# Biểu Mẫu Nhập Kho WMS Mẫu (WMS Inbound Template)

## 1. Tệp Dữ Liệu
- **Tên tệp**: [`import-template.xlsx`](./import-template.xlsx)
- **Định dạng**: Microsoft Excel OpenXML Spreadsheet (`.xlsx`)
- **Tên Sheet**: `Inbound_Bonded_Receipt`

---

## 2. Cấu Trúc Các Trường Dữ Liệu Trong Template

Biểu mẫu gồm 21 cột chuẩn hóa phục vụ truyền dữ liệu từ cổng kiểm soát AI xuống phần mềm quản lý kho ngoại quan (WMS):

| Cột | Tên Cột Trong Excel | Kiểu Dữ Liệu | Bắt Buộc | Mô Tả & Ý Nghĩa Nghiệp Vụ |
|:---:|:---|:---:|:---:|:---|
| A | `STT` | Số nguyên | Có | Thứ tự dòng hàng trong phiếu nhập kho |
| B | `Mã SKU` | Chuỗi | Có | Mã sản phẩm quản lý tồn kho tại kho ngoại quan |
| C | `Mã Phụ Tùng` | Chuỗi | Không | Ký hiệu nhà sản xuất (Manufacturer Part Number) |
| D | `Tên Hàng Hóa` | Chuỗi | Có | Tên mô tả hàng hóa theo tờ khai hải quan |
| E | `Mã HS` | Chuỗi | Có | Mã số HS 8 chữ số đã được đối soát thống nhất |
| F | `Đơn Vị Tính` | Chuỗi | Có | ĐVT chuẩn hải quan (PCS, KG, BOX, SET, ROLL...) |
| G | `Số Lượng Thực Nhập` | Số thực | Có | Số lượng thực tế kiểm đếm sau khi dỡ hàng |
| H | `Số Lượng Tờ Khai` | Số thực | Có | Số lượng đăng ký trên tờ khai hải quan VNACCS |
| I | `Đơn Giá (USD)` | Số thực | Có | Đơn giá khai báo trên Commercial Invoice |
| J | `Thành Tiền (USD)` | Số thực | Có | Thành tiền = Số lượng thực nhập x Đơn giá |
| K | `Loại Tiền` | Chuỗi | Có | Đồng tiền thanh toán (USD, EUR, JPY, VND...) |
| L | `Số PO` | Chuỗi | Có | Số đơn đặt hàng tương ứng (hỗ trợ nhiều PO) |
| M | `Số Hợp Đồng` | Chuỗi | Không | Số hợp đồng ngoại thương hoặc hợp đồng thuê kho |
| N | `Số Tờ Khai HQ` | Chuỗi | Có | Số tờ khai hải quan C11 đã được thông quan |
| O | `Số Vận Đơn (B/L)` | Chuỗi | Có | Số vận tải đơn đường biển hoặc hàng không |
| P | `Số Container` | Chuỗi | Có | Số hiệu container vận chuyển |
| Q | `Số Niêm Chì` | Chuỗi | Có | Số chì hải quan / chì hãng tàu niêm phong |
| R | `Net Weight (kg)` | Số thực | Có | Trọng lượng tịnh của dòng hàng |
| S | `Gross Weight (kg)` | Số thực | Có | Trọng lượng cả bì (Gross $\ge$ Net) |
| T | `Vị Trí Kệ Kho (Bin)` | Chuỗi | Không | Vị trí định vị kệ kho (Ví dụ: `RACK-A-01-02`) |
| U | `Ghi Chú Nghiệp Vụ` | Chuỗi | Không | Tình trạng bao bì, lưu ý kiểm đếm, niêm phong |
