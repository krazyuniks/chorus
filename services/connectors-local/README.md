# Local Connectors

Local connectors are contract-faithful sandbox adapters behind the Tool
Gateway. They are real local software, not mocks.

Current adapters:

- UC1 quoting queue routing;
- UC1 referral inbox routing;
- UC1 decline ledger routing;
- UC1 outbound communications through Mailpit;
- UC1 customer profile lookup;
- UC1 product catalogue lookup;
- Radicale-backed CalDAV calendar availability and hold tools.

Rules:

- workflows, agents, and the BFF never invoke connectors directly;
- connector writes require explicit Tool Gateway mode and approval policy where
  relevant;
- production third-party systems are out of scope for the local POC;
- missing credentials fail closed.
