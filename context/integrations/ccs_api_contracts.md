# CCS API Contracts

## Meter Reads
- Endpoint: GET /ccs/meter-reads
- Query: nmi, fromDate, toDate
- Response:
  ```json
  {
    "reads": [
      {"read_type":"ACTUAL","date":"2025-10-01","value":1234},
      {"read_type":"ESTIMATE","date":"2025-11-01","value":1270}
    ]
  }
  ```
- Errors: 400 invalid NMI, 404 not found, 5xx upstream

## Special Read Orders
- Endpoint: POST /ccs/special-read-orders
- Body: { nmi, dueDate }
- Response: { order_id, status }
- Notes: Must log for audit; honor consent and purpose-of-use
