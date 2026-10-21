# Bonded Warehouse AI — bản demo ba chứng từ

Bản demo cho giáo viên thử xử lý hồ sơ nhập kho. Chỉ dùng dữ liệu giả lập; WMS là bộ tiếp nhận giả lập.

## Phạm vi hiện tại (11/10/2026)

- Ba chứng từ bắt buộc: Commercial Invoice, Packing List, hợp đồng thuê kho.
- Gemini trích xuất PDF, ảnh và nội dung Excel; dữ liệu thiếu được đánh dấu để người dùng kiểm tra.
- Đối soát số lượng theo PO/SKU, cộng các dòng trùng trong cùng PO; kiểm tra đơn giá/thành tiền và tổng Invoice.
- Hợp đồng: số, bên thuê, bên cho thuê, kho, ngày hiệu lực; đối chiếu bên thuê với Consignee/Buyer trên Invoice/PL và ngày nhập kho.
- Sửa dòng hàng/thông tin chứng từ, lưu lịch sử, kiểm tra lại và thu hồi duyệt cũ. Sau khi đã truyền WMS, tạo hồ sơ mới để điều chỉnh.
- Duyệt, xuất bảng dữ liệu Excel demo 21 cột, WMS giả lập có chống gửi trùng và mô phỏng lỗi 503.
- Menu trái gồm Lô hàng, Chứng từ, Đối soát, Excel & WMS. Đã bỏ chatbot giải thích, benchmark và trang giới thiệu kỹ thuật.

## Chạy local

Backend: `cd backend`, cài `requirements.txt` trong môi trường Python, đặt khóa trong `.env`, chạy `.venv\Scripts\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8000`.

Frontend: `cd frontend`, `npm ci`, `npm run dev`. Mở http://127.0.0.1:5173.

Tải bộ chứng từ mẫu từ thanh đầu trang. Dùng ngày nhập kho 11/10/2026. Chọn một Invoice, PL và hợp đồng tương ứng. Có PL sai số lượng và hợp đồng hết hạn để thử chặn duyệt.

## Kiểm thử

Trong `backend`: `.venv\Scripts\python.exe -m pytest -q`. Kiểm thử tự động dùng cơ sở dữ liệu và thư mục upload tạm riêng; Gemini được giả lập chỉ trong tests. Kiểm thử gọi Gemini thật phải dùng bộ mẫu giả lập và khóa riêng phía máy chủ.

Trong `frontend`: `npm run build`.

## Triển khai sau

Xem `docs/DEPLOYMENT_DEMO.md`, `Dockerfile` và `backend/.env.production.example`. Chế độ công khai `DEMO_ONLY=true` chỉ nhận đúng nội dung bộ mẫu đóng gói; mọi người cùng dùng dữ liệu demo. Chưa triển khai lên Internet.

## Giới hạn cần biết

Bảng dữ liệu Excel 21 cột hiện tại khác bố cục phiếu BS-01 12 cột trong `project-reference`. Chưa xác nhận tương thích với một WMS thật. Bản demo chỉ kiểm tra dữ liệu theo phạm vi trên, không đưa ra kết luận pháp lý/thông quan. Tên bên thuê và chủ hàng được so sánh sau khi chuẩn hóa khoảng trắng và chữ hoa; tên viết tắt khác nhau cần người dùng kiểm tra và sửa.

Các tài liệu SRS/kiến trúc ban đầu có mô tả phạm vi hải quan rộng hơn; phạm vi ba chứng từ trên là yêu cầu mới nhất của người dùng.
