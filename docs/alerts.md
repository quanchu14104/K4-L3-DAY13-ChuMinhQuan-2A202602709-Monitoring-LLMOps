# Template Alert và Runbook

Mỗi alert phải dựa trên triệu chứng người dùng hoặc SLO, không dựa trực tiếp vào tên implementation nội bộ.

## Alert 1

- Tên: High Latency P95 (Phản hồi người dùng chậm)
- Severity: warning
- Duration: 5m
- Kênh thông báo: Slack (#alerts-llmops)
- SLI/SLO liên quan: `primary_slo.fast_successful_requests` (latency_ms <= 3000ms >= 99.5%)
- Điều kiện và thời gian duy trì: Latency P95 > 3000ms kéo dài liên tục từ 5 phút trở lên
- Ảnh hưởng tới người dùng: Người dùng cảm nhận hệ thống phản hồi rất chậm, nguy cơ timeout ở client interface
- Ba bước kiểm tra đầu tiên:
  1. Kiểm tra panel Latency và TTFT trên Dashboard để xem độ trễ phân bổ ở đâu.
  2. Lọc log `response_sent` có `latency_ms > 3000` trong `data/logs.jsonl`, lấy `correlation_id` của các request chậm.
  3. Mở trace tương ứng trên Langfuse để phân tích waterfall: xác định do bước `retrieval` (RAG bị nghẽn/chậm) hay bước `generation` (LLM suy luận lâu).
- Mitigation tạm thời: Bật cache cho kết quả retrieval, tăng worker concurrency hoặc kích hoạt fallback retrieval trả về document nhanh.
- Owner: platform-oncall

## Alert 2

- Tên: High Error Rate (Tỷ lệ lỗi API tăng cao)
- Severity: critical
- Duration: 3m
- Kênh thông báo: Slack (#alerts-llmops)
- SLI/SLO liên quan: `guardrails.error_rate_pct_max` (<= 2%)
- Điều kiện và thời gian duy trì: Tỷ lệ request lỗi (`request_failed / request_received * 100`) > 2% kéo dài trong 3 phút
- Ảnh hưởng tới người dùng: Người dùng gặp lỗi HTTP 500, không nhận được câu trả lời từ trợ lý AI
- Ba bước kiểm tra đầu tiên:
  1. Kiểm tra panel Errors trên Dashboard để phân tích phân phối lỗi theo `error_type` (ví dụ `RuntimeError`, `TimeoutError`).
  2. Lọc log `request_failed` trong `data/logs.jsonl` để đọc `payload.detail` và stack trace.
  3. Mở trace trên Langfuse theo `correlation_id` để xác định observation nào bị gãy (retrieval vector store hay model endpoint).
- Mitigation tạm thời: Khởi động lại service vector store hoặc API upstream, kích hoạt circuit breaker chuyển sang trả câu trả lời fallback an toàn.
- Owner: backend-oncall

## Alert 3

- Tên: Retrieval Degradation (Tỷ lệ tìm kiếm tri thức suy giảm)
- Severity: warning
- Duration: 5m
- Kênh thông báo: Slack (#alerts-llmops)
- SLI/SLO liên quan: `guardrails.retrieval_success_rate_pct_min` (>= 90%)
- Điều kiện và thời gian duy trì: Tỷ lệ `tool_success` của tool `retrieval` giảm dưới 90% trong 5 phút
- Ảnh hưởng tới người dùng: Trợ lý không lấy được tài liệu phù hợp, dẫn tới câu trả lời fallback kém chất lượng hoặc suy giảm quality score
- Ba bước kiểm tra đầu tiên:
  1. Kiểm tra panel Error rate and retrieval success cùng Quality proxy trên Dashboard.
  2. Lọc các bản ghi log có `tool_name == "retrieval"` và `tool_success == false` để xác định mã lỗi và câu hỏi bị ảnh hưởng.
  3. Kiểm tra trạng thái kết nối tới vector database cluster và embedding service.
- Mitigation tạm thời: Chuyển sang cơ chế keyword fallback retrieval, sử dụng tài liệu tĩnh mặc định cho các chủ đề phổ biến.
- Owner: rag-team
