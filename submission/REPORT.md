# Báo cáo cá nhân — K4-L3A Day 13 Monitoring & LLMOps

> Mỗi học viên hoàn thiện một file duy nhất này. Khi dẫn evidence, dùng đường dẫn tương đối, ví dụ `evidence/07-trace-waterfall.png`.

## 1. Thông tin học viên

- **Họ và tên:** Chu Minh Quân
- **MSSV:** 2A202602709
- **Lớp:** K4-L3A
- **Repository URL:** https://github.com/quanchu14104/K4-L3-DAY13-ChuMinhQuan-2A202602709-Monitoring-LLMOps
- **Commit SHA cuối:** `9743ec32f7cb0e27086bd93a3131428cc6183dc7`
- **Challenge ID:** day13-k4-l3a
- **Tên project Langfuse cá nhân:** `day13-k4-l3a-2A202602709`

## 2. Evidence index

| Evidence | Đường dẫn |
|---|---|
| Pytest cuối | [evidence/01-pytest.png](evidence/01-pytest.png) |
| Log validator | [evidence/02-log-validator.png](evidence/02-log-validator.png) |
| Dashboard validator | [evidence/03-dashboard-validator.png](evidence/03-dashboard-validator.png) |
| Structured log | [evidence/04-structured-log.png](evidence/04-structured-log.png) |
| PII redaction | [evidence/05-pii-redaction.png](evidence/05-pii-redaction.png) |
| Trace list | [evidence/06-trace-list.png](evidence/06-trace-list.png) |
| Trace waterfall | [evidence/07-trace-waterfall.png](evidence/07-trace-waterfall.png) |
| Trace metadata | [evidence/08-trace-metadata.png](evidence/08-trace-metadata.png) |
| Prompt versions | [evidence/09-prompt-versions.png](evidence/09-prompt-versions.png) |
| Prompt rollback | [evidence/10-prompt-rollback.png](evidence/10-prompt-rollback.png) |
| Dashboard runtime | [evidence/11-dashboard-overview.png](evidence/11-dashboard-overview.png) |
| Incident metric | [evidence/12-incident-metric.png](evidence/12-incident-metric.png) |
| Incident log | [evidence/13-incident-log.png](evidence/13-incident-log.png) |
| Incident trace | [evidence/14-incident-trace.png](evidence/14-incident-trace.png) |

## 3. Kết quả kỹ thuật

| Nội dung | Baseline | Kết quả cuối | Nhận xét |
|---|---|---|---|
| `validate_logs.py` | 12/100 | 100/100 | Đạt điểm tuyệt đối: 0 missing required, 0 missing enrichment, 100% correlation ID hợp lệ, 0 PII leak. |
| `validate_dashboard.py` | 0/6 | 6/6 | Đạt 100% contract spec của 6 panels theo `config/dashboard.yaml`. |
| `pytest` | 8 passed | 27 passed | 100% pass toàn bộ 27 test cases (gồm unit tests PII, middleware, tracing, dashboard). |
| Số traces hợp lệ | 0 | 15+ traces | Đầy đủ quan hệ phân cấp cha con (`lab-agent-run` -> `retrieval` + `generation`) trên Langfuse Cloud. |
| Số PII leak | >0 | 0 | Toàn bộ 4 loại PII (email, phone VN, CCCD, thẻ tín dụng) được scrub triệt để. |
| Latency P95 / TTFT P95 | 410 ms / 50 ms | 410 ms / 50 ms | Đáp ứng mục tiêu SLO <= 3000ms; TTFT ổn định ở 50ms. |
| Retrieval success rate | 1.0 (100%) | 1.0 (100%) | Tỷ lệ truy vấn retrieval thành công tuyệt đối. |

## 4. Logging và PII

- **Cách tạo/nhận và truyền correlation ID:**
  - Nhận qua header `x-request-id` từ client nếu có; nếu không có, middleware tự động sinh theo format `req-<8-hex>` (`secrets.token_hex(4)`).
  - Sử dụng Python `contextvars` (`request_context.correlation_id_var`) để lưu giữ ID trong suốt asynchronous execution context, đảm bảo cô lập tuyệt đối giữa các request đồng thời (được reset/clear ở đầu mỗi request).
  - Bind trực tiếp vào structlog context qua `structlog.contextvars.bind_contextvars(correlation_id=cid)`.
  - Trả về cho client qua response header `x-request-id` và `x-response-time-ms`.
  - Truyền vào `LabAgent.run(..., correlation_id=cid)` để gán vào trace metadata trên Langfuse.
- **Các metadata được ghi vào structured log:**
  - `correlation_id`: Định danh theo dõi request xuyên suốt logs và traces.
  - `user_id_hash`: Mã băm SHA-256 (12 ký tự hex đầu) của user ID để bảo đảm quyền riêng tư theo GDPR/CCPA.
  - `session_id`: Định danh phiên làm việc của người dùng.
  - `feature`: Tính năng nghiệp vụ (`qa`, `refund`, `summary`,...).
  - `model`: Tên mô hình LLM (`claude-sonnet-4-5`).
  - `env`: Môi trường triển khai (`dev`, `staging`, `prod`).
  - Các metrics hiệu năng & chi phí: `latency_ms`, `ttft_ms`, `tokens_in`, `tokens_out`, `cost_usd`, `quality_score`, `tool_name`, `tool_success`, `ts` (ISO8601 UTC), `level` ("info"), `service` ("api").
- **Cách bảo đảm PII được scrub trước khi ghi:**
  - Viết module `app/pii.py` với regex tối ưu cho 4 định dạng PII: Email, Số điện thoại Việt Nam (các đầu số 03, 05, 07, 08, 09 hoặc mã quốc gia +84), Số Căn cước công dân (12 chữ số), Thẻ tín dụng (13-19 chữ số).
  - Hàm `scrub_event` duyệt đệ quy (recursive traversal) qua dictionary của structlog event và payload.
  - Đăng ký `scrub_event` làm processor đầu tiên trong pipeline của `structlog` (`app/logging_config.py`), trước `JsonlFileProcessor` và `JSONRenderer`. Nhờ đó PII được thay thế thành `[REDACTED_...]` trước khi ghi ra file `data/logs.jsonl` hoặc stdout.
- **Cách kiểm chứng kết quả:**
  - Chạy `python scripts/validate_logs.py` đạt 100/100, xác nhận không có PII leak và đầy đủ trường schema.
  - Chạy unit tests `pytest tests/test_pii.py` và `tests/test_chat_observability.py` xác minh toàn bộ dữ liệu mẫu chứa PII đều được che chắn an toàn.

## 5. Tracing và prompt versioning

- **Cách xác nhận traces do chính tôi tạo trong project cá nhân:**
  - Sử dụng project Langfuse cá nhân riêng biệt: `day13-k4-l3a-2A202602709`.
  - Từng trace mang `user_id_hash` và `correlation_id` từ workload local của sinh viên.
  - Tên project `day13-k4-l3a-2A202602709` được thể hiện rõ ràng trên giao diện Langfuse Cloud và các bằng chứng ảnh (`06-trace-list.png`, `07-trace-waterfall.png`, `08-trace-metadata.png`).
- **Cấu trúc root/retrieval/generation observations:**
  - **Root observation**: `@observe(name="day13-agent-request")` bao bọc toàn bộ request xử lý của agent.
  - **Child span 1 (Retrieval)**: `@observe(name="retrieval", as_type="retriever")` đo lường thời gian truy xuất tài liệu từ RAG vector index, ghi nhận input preview đã scrub PII và document metadata.
  - **Child span 2 (Generation)**: `@observe(name="generation", as_type="generation")` đo lường LLM generation, ghi nhận thông tin `model="claude-sonnet-4-5"`, `usage_details` (`input`, `output`, `total`), và `cost_details` (`total`).
  - Cấu trúc cha–con rõ ràng tạo biểu đồ waterfall trực quan giúp cô lập ngay vị trí gây nghẽn (retrieval vs LLM).
- **Cách nối trace với log:**
  - Nối thông qua giá trị `correlation_id` (ví dụ `req-c7a05c06`):
    - Trong log: trường `"correlation_id": "req-c7a05c06"`.
    - Trong Langfuse trace: nằm trong `metadata.correlation_id` và tags của trace.
- **Prompt name:** `day13-chat`
- **Version/label baseline:** Version 1 (labels: `baseline`, `production`).
- **Version/label candidate:** Version 2 (label: `candidate`).
- **Trace ID của mỗi version:**
  - Trace ID chạy với Version 1 (`baseline`/`production` ban đầu): `d1a060f22a2c6bdb957883a4ad59c1f6`
  - Trace ID chạy với Version 2 (`candidate`): `9d6d625a4d79568c3b5245f96747e6fe`
  - Trace ID sau khi promote (`production` trỏ sang v2): `c7fa45daae98c09b1b49b7c78e5b09a8`
  - Trace ID sau khi rollback (`production` chuyển ngược lại v1): `0de20180c0a7b5f422002ab02874d31d`
- **Cách promote và rollback `production`:**
  - Trên Langfuse Cloud UI (Prompt Management):
    - *Promote*: Di chuyển nhãn `production` từ Version 1 sang Version 2 sau khi đánh giá chất lượng prompt candidate đạt yêu cầu.
    - *Rollback*: Khi phát hiện prompt mới có vấn đề (hallucination hoặc tăng đột biến token), di chuyển ngay lập tức nhãn `production` về Version 1.
    - Ứng dụng luôn fetch prompt theo nhãn `production` (`langfuse.get_prompt("day13-chat", label="production")`), cho phép rollback tức thì không cần redeploy mã nguồn.

## 6. Dashboard, SLO và alerts

- **Dashboard và sáu panel:**
  - Xây dựng giao diện web `/dashboard` và API `/api/dashboard-data` tuân thủ nghiêm ngặt hợp đồng `config/dashboard.yaml`:
    1. `latency_and_ttft`: Biểu đồ thời gian phản hồi (P50, P95, P99) và TTFT (ms), kèm đường ngưỡng SLO 3,000ms.
    2. `error_rate`: Biểu đồ tỷ lệ lỗi (%) kèm ngưỡng cảnh báo 2.0%.
    3. `request_volume`: Lưu lượng request theo thời gian và phân bố theo từng tính năng (`feature`).
    4. `token_usage`: Thống kê lượng token (input, output, total) theo từng model.
    5. `cost_usd`: Chi phí tích lũy theo USD.
    6. `quality_score`: Điểm số chất lượng câu trả lời trung bình và phân bố.
- **SLO và lý do chọn:**
  - **SLO**: 99.5% request hoàn thành với độ trễ <= 3,000ms trong chu kỳ 28 ngày lăn (rolling 28-day window).
  - **Lý do**: Trong điều kiện bình thường, hệ thống phản hồi P95 khoảng ~410ms và TTFT 50ms. Mức 3,000ms là ngưỡng tối đa đảm bảo người dùng tương tác realtime không cảm thấy ứng dụng bị treo mà vẫn chừa dung sai cho các truy vấn retrieval phức tạp.
- **Cách tính error budget:**
  - Với mục tiêu độ tin cậy 99.5%, tỷ lệ ngân sách lỗi cho phép là: `100% - 99.5% = 0.5%`.
  - Ví dụ trong chu kỳ 28 ngày hệ thống nhận 100,000 request:
    - Ngân sách lỗi tối đa = `100,000 * 0.005 = 500 requests` được phép chậm (> 3,000ms) hoặc gặp lỗi.
    - Tỷ lệ đốt ngân sách (burn rate) được giám sát liên tục để kịp thời đóng băng tính năng mới khi chạm ngưỡng rủi ro.
- **Ba alert và runbook tương ứng (`config/alert_rules.yaml` & `docs/alerts.md`):**
  1. `high_latency_p95`:
     - *Điều kiện*: Latency P95 > 3000ms trong 3 phút.
     - *Severity*: Warning. Kênh thông báo: `#alerts-llmops`.
     - *Runbook*: Kiểm tra dashboard xem P95/P99 tăng vọt ở đâu; đối chiếu TTFT. Mở trace waterfall để xem nghẽn ở bước `retrieval` hay `generation`.
  2. `high_error_rate`:
     - *Điều kiện*: Error rate > 2% trong 2 phút.
     - *Severity*: Critical. Kênh thông báo: `#alerts-critical`.
     - *Runbook*: Kiểm tra log lỗi HTTP 5xx, xác minh kết nối đến Langfuse và Vector DB; kích hoạt cơ chế fallback nếu upstream model bị lỗi.
  3. `retrieval_degradation`:
     - *Điều kiện*: Tỷ lệ retrieval thành công < 95% trong 5 phút.
     - *Severity*: Warning. Kênh thông báo: `#alerts-llmops`.
     - *Runbook*: Kiểm tra cluster Vector DB, tải CPU/RAM của retriever service, refresh index hoặc bật chế độ dự phòng keyword search.

## 7. Điều tra challenge

- **Challenge ID:** `day13-k4-l3a` (kịch bản mô phỏng sự cố: `rag_slow`)
- **Khoảng thời gian điều tra:** 2026-09-29 11:11:00 UTC – 11:12:00 UTC
- **Triệu chứng từ metrics:**
  - Panel `latency_and_ttft` trên dashboard ghi nhận Latency P95 tăng đột biến từ mức bình thường ~410ms lên `6,376 ms` (vượt xa ngưỡng SLO 3,000ms).
  - TTFT vẫn giữ ổn định ở 50ms, Error rate 0%. Dấu hiệu này cho thấy độ trễ không bắt nguồn từ thời gian chờ phản hồi đầu tiên của LLM mà nằm ở khâu nạp context retrieval.
- **Log line và correlation ID liên quan:**
  - **Correlation ID**: `req-c7a05c06`
  - **Log line trích xuất từ `data/logs.jsonl`**:
    ```json
    {"service": "api", "latency_ms": 3591, "ttft_ms": 50, "tokens_in": 36, "tokens_out": 125, "cost_usd": 0.001983, "quality_score": 0.9, "tool_name": "retrieval", "tool_success": true, "payload": {"answer_preview": "Starter answer. You should improve this output logic and add better quality chec..."}, "event": "response_sent", "correlation_id": "req-c7a05c06", "feature": "qa", "model": "claude-sonnet-4-5", "user_id_hash": "2055254ee30a", "env": "dev", "session_id": "s01", "level": "info", "ts": "2026-09-29T11:11:15.342112Z"}
    ```
- **Trace ID và span gây ảnh hưởng:**
  - **Trace ID**: `8773f758bcb547d5851882aa02ec6501`
  - **Span gây ảnh hưởng**: `retrieval` (as_type: retriever)
  - Biểu đồ waterfall cho thấy: Toàn bộ request mất `3,592 ms`, trong đó span `retrieval` chiếm `2,501 ms` (~70% thời gian thực thi), còn span `generation` chỉ mất `152 ms`.
- **Root cause:**
  - Vector database retrieval gặp tình trạng nghẽn hiệu năng (simulated `rag_slow`), dẫn đến việc tìm kiếm embedding bị trễ hơn 2.5s trước khi chuyển câu lệnh sang LLM.
- **Fix action:**
  - Gỡ bỏ giả lập độ trễ, cấu hình in-memory caching cho các câu truy vấn phổ biến, thiết lập timeout 1,500ms cho retriever client.
- **Preventive measure:**
  - Bổ sung circuit breaker cho retriever: nếu tìm kiếm vượt quá 1.5s, tự động fallback sang kết quả cache hoặc trả về prompt với kiến thức chung. Kích hoạt alert `retrieval_degradation` sớm để cảnh báo trước khi vi phạm SLO P95.

## 8. Giải thích và tự đánh giá

- **Một quyết định kỹ thuật quan trọng và lý do:**
  - *Quyết định*: Đặt logic PII scrubber đệ quy tại processor đầu chuỗi pipeline của `structlog` (`app/logging_config.py`) thay vì xử lý rời rạc tại từng API endpoint.
  - *Lý do*: Đảm bảo nguyên tắc "Secure by Design" và "Defense in Depth". Dù lập trình viên ở các route khác có sơ suất truyền payload thô hay dictionary lồng sâu, dữ liệu nhạy cảm vẫn luôn được thanh lọc trước khi ghi xuống đĩa hoặc gửi ra telemetry stream.
- **Một lỗi/blocker đã gặp:**
  - Khi mock Langfuse v4 observation API trong unit test (`tests/test_agent_prompt_trace.py`), mock object của `ManagedPrompt` thiếu thuộc tính `is_fallback`. Khi `mock_llm.py` gọi `update_current_generation(prompt=managed_prompt)`, SDK sinh lỗi `AttributeError`.
- **Cách tìm nguyên nhân và xử lý:**
  - Phân tích stacktrace và kiểm tra interface của Langfuse v4 `TextPromptClient`. Bổ sung điều kiện kiểm tra `if managed_prompt is not None and hasattr(managed_prompt, "is_fallback"): kwargs["prompt"] = managed_prompt`. Nhờ đó code tương thích hoàn hảo cả khi chạy test mock lẫn khi chạy thật trên Langfuse Cloud.
- **Cách hiểu luồng Metrics → Logs → Traces:**
  - **Metrics**: Cho biết *CÁI GÌ* đang xảy ra và *KHI NÀO* (tổng hợp vĩ mô: P95 latency tăng vọt, Error rate vượt ngưỡng).
  - **Logs**: Cho biết *ĐỐI TƯỢNG NÀO* bị ảnh hưởng (vi mô từng request: `correlation_id`, user ID, event, timestamp cụ thể).
  - **Traces**: Cho biết *TẠI SAO* và *Ở ĐÂU* (chi tiết từng mili-giây: waterfall span chỉ đích danh retriever bị nghẽn 2.5s hay LLM generation bị chậm).
- **Vai trò của prompt version, token/cost, SLO hoặc rollback trong vận hành LLM:**
  - Giúp quản lý hệ thống AI có kỷ luật như công nghệ phần mềm truyền thống: Prompt versioning coi prompt như mã nguồn cần kiểm thử (`baseline`, `candidate`); Token/Cost tracking ngăn ngừa rủi ro tài chính đột biến; SLO và Rollback tức thì là chốt chặn an toàn giúp khắc phục sự cố trong vài giây mà không cần redeploy.
- **Điều quan trọng nhất đã học:**
  - Tầm quan trọng của `correlation_id` như một sợi chỉ đỏ xuyên suốt: từ lúc request vào middleware, ghi log, gửi trace lên cloud, cho tới khi truy vết sự cố trên dashboard.
- **Hạn chế hoặc phần chưa hoàn thành, nếu có:**
  - Trong phạm vi lab, mô hình LLM và RAG là bản mock (`FakeLLM`, `MockRAG`). Ở môi trường thực tế, cần tích hợp thêm semantic cache (Redis) và reranker latency monitoring.

## 9. Checklist trước khi nộp

- [x] Kết quả và evidence thuộc commit SHA cuối.
- [x] Tất cả ảnh/output mở được bằng đường dẫn tương đối.
- [x] Incident evidence nối đúng metric → log → trace.
- [x] Trace/prompt evidence thuộc project Langfuse cá nhân và ảnh không lộ key/secret.
- [x] Repository chạy lại được theo README.
- [x] Không có secret, API key, PII thô hoặc evidence của người khác/lớp khác.
- [x] URL repo và commit SHA cuối đã được nộp trên LMS/Codelabs.
