#!/usr/bin/env python3
"""Populate the AI Search index with sample documents.

Usage:
    export AZURE_AI_SEARCH_ENDPOINT=https://<your-search>.search.windows.net
    export AZURE_AI_SEARCH_INDEX=knowledge-base-docs
    python populate_index.py

Replace these sample documents with your own to customize the RAG agent
for your domain.
"""

import json
import os

import httpx
from azure.identity import DefaultAzureCredential

SEARCH_ENDPOINT = os.environ.get("AZURE_AI_SEARCH_ENDPOINT", "")
INDEX_NAME = os.environ.get("AZURE_AI_SEARCH_INDEX", "knowledge-base-docs")
API_VERSION = "2024-07-01"

# Sample documents — replace with your own domain-specific content
DOCUMENTS = [
    {
        "id": "doc-001",
        "title": "Sample Project — Product Technical Specification",
        "category": "Technical Specification",
        "source": "SPEC-001 Rev 3",
        "content": """Sample Project — Product Technical Specification SPEC-001 Rev 3

1. SCOPE
This specification covers the minimum requirements for the design, manufacturing, inspection, testing, and delivery of core platform components for Sample Project.

2. APPLICABLE STANDARDS
- ISO 9001: Quality Management Systems
- ISO 27001: Information Security Management
- ISO 14001: Environmental Management
- IEEE 830: Software Requirements Specification
- NIST SP 800-53: Security and Privacy Controls

3. DESIGN REQUIREMENTS
3.1 System Availability: 99.95% uptime (excluding planned maintenance)
3.2 Response Time: P95 latency < 500ms for API requests
3.3 Throughput: Support 10,000 concurrent users minimum
3.4 Data Retention: 7 years for audit records, 2 years for operational logs

4. SECURITY REQUIREMENTS
4.1 All data encrypted at rest (AES-256) and in transit (TLS 1.3)
4.2 Authentication via OAuth 2.0 / OIDC federation
4.3 Role-based access control with least-privilege principle
4.4 Penetration testing required annually per SOC 2 Type II

5. TESTING REQUIREMENTS
5.1 Unit test coverage minimum 80%
5.2 Integration tests for all API endpoints
5.3 Load testing to 2x expected peak capacity
5.4 Security scanning (SAST/DAST) on every release
""",
    },
    {
        "id": "doc-002",
        "title": "Quarterly Compliance Audit Report — Q4 2025",
        "category": "Compliance Report",
        "source": "AUDIT-Q4-2025-001",
        "content": """Quarterly Compliance Audit Report — Q4 2025

1. EXECUTIVE SUMMARY
The platform maintained full compliance with SOC 2 Type II, ISO 27001, and GDPR requirements during Q4 2025. Zero critical findings. Two minor findings addressed and closed within SLA.

2. REGULATORY COMPLIANCE STATUS
2.1 SOC 2 Type II: COMPLIANT
    - All 73 controls verified operational
    - Annual audit completed by external assessor
2.2 ISO 27001: COMPLIANT
    - Surveillance audit passed with zero non-conformities
2.3 GDPR: COMPLIANT
    - Data subject access requests: 14 received, 14 completed within 30-day SLA
    - Data Protection Impact Assessments current for all AI model deployments

3. SECURITY METRICS
3.1 Vulnerability Management
    - Critical vulnerabilities patched within 24 hours: 100%
    - High vulnerabilities patched within 7 days: 98%
    - Zero unpatched critical/high vulnerabilities as of end Q4
3.2 Access Reviews
    - Quarterly access review completed for all privileged accounts
    - 3 stale accounts deprovisioned

4. AUDIT FINDINGS
4.1 Finding AUDIT-2025-041: Documentation gap in disaster recovery runbook
    - Severity: Minor
    - Corrective action: Runbook updated, tabletop exercise scheduled
    - Status: CLOSED
4.2 Finding AUDIT-2025-042: Missing MFA enforcement on service account
    - Severity: Minor
    - Corrective action: Conditional access policy updated
    - Status: CLOSED

5. KEY METRICS
| Metric | Q4 Target | Q4 Actual | Status |
|--------|-----------|-----------|--------|
| Uptime | 99.95% | 99.98% | ✓ |
| Incident Response | <4hr | 2.1hr avg | ✓ |
| Patch Compliance | >95% | 98% | ✓ |
| Training Completion | >95% | 97% | ✓ |
""",
    },
    {
        "id": "doc-003",
        "title": "Organization Standard — Material Standards Reference Guide",
        "category": "Standards Reference",
        "source": "STD-002 Rev 7",
        "content": """Organization Standard — Material Standards Reference Guide STD-002 Rev 7

1. PURPOSE
This guide defines the approved technology standards for all platform deployments, ensuring consistent selection of frameworks, services, and configurations aligned with organizational requirements.

2. COMPUTE STANDARDS
2.1 Container Runtime: Kubernetes 1.28+ or Azure Container Apps
2.2 Serverless: Azure Functions (Python 3.12, Node.js 20 LTS)
2.3 Virtual Machines: Only for legacy workloads with approved exception
2.4 Minimum resource allocation documented per workload tier

3. DATA STANDARDS
3.1 Relational: Azure SQL or PostgreSQL Flexible Server
3.2 Document: Azure Cosmos DB (NoSQL API preferred)
3.3 Search: Azure AI Search (Standard tier minimum for production)
3.4 Cache: Azure Redis Cache (Enterprise tier for HA)
3.5 All databases require geo-redundant backup

4. NETWORKING STANDARDS
4.1 All production workloads in VNet with private endpoints
4.2 Public endpoints only via API Management or Application Gateway
4.3 Network segmentation via NSG and Azure Firewall
4.4 DNS: Azure Private DNS zones for all internal resolution

5. SECURITY STANDARDS
5.1 Identity: Microsoft Entra ID (Managed Identity for service-to-service)
5.2 Secrets: Azure Key Vault (no hardcoded credentials)
5.3 Certificates: Auto-rotation via Key Vault
5.4 Logging: All security events to Microsoft Sentinel
""",
    },
    {
        "id": "doc-004",
        "title": "Sample Project — Service Level Agreement",
        "category": "Contract",
        "source": "SLA-001 Rev 2",
        "content": """Sample Project — Service Level Agreement SLA-001 Rev 2

1. PARTIES
This SLA is between the Platform Team (Provider) and Business Units (Consumers).

2. SERVICE LEVELS

2.1 Availability
- Target: 99.95% monthly uptime
- Measurement: Synthetic monitoring from 3 Azure regions
- Exclusions: Planned maintenance windows (Sundays 02:00-06:00 UTC)
- Credits: 10% for <99.9%, 25% for <99.5%, 50% for <99.0%

2.2 Performance
- API Response Time: P95 < 500ms, P99 < 2000ms
- Search Latency: P95 < 300ms
- Agent Orchestration: P95 < 15s for multi-agent workflows
- Measurement: Application Insights percentile metrics

2.3 Support Response Times
- P1 (Critical): 15 minutes initial response, 4 hours resolution
- P2 (High): 1 hour initial response, 8 hours resolution
- P3 (Medium): 4 hours initial response, 3 business days resolution
- P4 (Low): 1 business day response, 10 business days resolution

3. INCIDENT MANAGEMENT
3.1 All incidents tracked in the Governance Hub
3.2 Post-incident reviews within 5 business days for P1/P2
3.3 Monthly service review meetings with top consumers

4. CHANGE MANAGEMENT
4.1 Standard changes: 3 business days notice
4.2 Emergency changes: Immediate with post-change review
4.3 Major changes: 10 business days notice with impact assessment
""",
    },
    {
        "id": "doc-005",
        "title": "Equipment Maintenance Data Sheet — API Gateway",
        "category": "Data Sheet",
        "source": "DS-003 Rev 2",
        "content": """Equipment Maintenance Data Sheet — API Gateway DS-003 Rev 2

SERVICE: Azure API Management (Production AI Gateway)
ENVIRONMENT: Production
TIER: Premium (multi-region)

1. CONFIGURATION
- SKU: Premium, 2 units (active-active across 2 regions)
- Virtual Network: Integrated (internal mode)
- Custom domain: api.platform.example.com
- TLS: 1.3 minimum, managed certificates via Key Vault

2. HEALTH MONITORING
- Synthetic probes: Every 60 seconds from 3 regions
- Alert threshold: 2 consecutive failures triggers P2 incident
- Dashboard: Grafana — API Gateway Health panel
- Metrics: Request count, latency P50/P95/P99, error rate, backend health

3. MAINTENANCE SCHEDULE
- Certificate rotation: Automatic via Key Vault (30-day renewal)
- Policy updates: Via Terraform apply, reviewed in PR
- Scaling review: Monthly capacity assessment
- Backup: Named value export weekly to storage account

4. CAPACITY
- Rate limiting: 1000 req/min per subscription key
- Burst: 50 concurrent connections per backend
- Total throughput: 10,000 req/min sustained
- Backend timeout: 120 seconds (configurable per API)

5. DISASTER RECOVERY
- RTO: 15 minutes (automatic failover to secondary region)
- RPO: 0 (active-active, no data loss)
- Failover trigger: Automatic via Traffic Manager health probes
- Manual override: Portal or CLI
""",
    },
    {
        "id": "doc-006",
        "title": "AI Governance & Ethics Policy",
        "category": "Governance Policy",
        "source": "POL-GOV-001 Rev 1",
        "content": """AI Governance & Ethics Policy — POL-GOV-001 Rev 1

1. PURPOSE
This policy establishes the governance framework for all AI models consumed through the Unified AI Platform, covering Azure OpenAI, AWS Bedrock, and other model providers.

2. MODEL APPROVAL PROCESS
2.1 All AI models must be registered in the Model Registry before use
2.2 New model requests require approval from:
    - Business unit AI Champion
    - Enterprise Architecture team
    - Information Security (for data classification review)
2.3 Approval SLA: 5 business days for standard models, 15 days for custom/fine-tuned

3. USAGE MONITORING
3.1 All model interactions are logged via the APIM AI Gateway
3.2 Token consumption tracked per business unit, project, and user
3.3 Monthly cost reports generated by the Governance Hub
3.4 Alerts triggered when spend exceeds 80% of allocated budget

4. CONTENT SAFETY
4.1 Azure Content Safety enabled for all Azure-hosted model interactions
4.2 Prompt injection detection via APIM policies
4.3 Output filtering for PII, safety-critical misinformation, and IP leakage
4.4 Human review required for any AI-generated content in critical documents

5. DATA GOVERNANCE
5.1 No customer data processed through third-party models without classification review
5.2 All data in transit encrypted (TLS 1.3)
5.3 Data residency: Regional compliance per deployment configuration
5.4 Retention: Model interaction logs retained for 2 years per regulatory requirements

6. CROSS-CLOUD FEDERATION
6.1 All cross-cloud calls authenticated via OIDC federation (Entra ID ↔ AWS IAM)
6.2 No static credentials — managed identity or federated tokens only
6.3 Trace propagation: W3C traceparent headers mandatory on all cross-cloud calls

7. ETHICAL AI PRINCIPLES
7.1 Transparency: Users must be informed when interacting with AI
7.2 Fairness: Regular bias audits on model outputs
7.3 Accountability: Clear ownership for each deployed model
7.4 Privacy: Minimize data collection, anonymize where possible
""",
    },
]


def create_index(endpoint: str, index_name: str, token: str) -> None:
    """Create the search index with semantic configuration."""
    url = f"{endpoint}/indexes/{index_name}?api-version={API_VERSION}"

    index_def = {
        "name": index_name,
        "fields": [
            {"name": "id", "type": "Edm.String", "key": True, "filterable": True},
            {"name": "title", "type": "Edm.String", "searchable": True, "filterable": True, "retrievable": True},
            {"name": "content", "type": "Edm.String", "searchable": True, "retrievable": True},
            {"name": "category", "type": "Edm.String", "searchable": True, "filterable": True, "facetable": True, "retrievable": True},
            {"name": "source", "type": "Edm.String", "searchable": True, "filterable": True, "retrievable": True},
        ],
        "semantic": {
            "configurations": [
                {
                    "name": "default",
                    "prioritizedFields": {
                        "titleField": {"fieldName": "title"},
                        "contentFields": [{"fieldName": "content"}],
                        "keywordsFields": [{"fieldName": "category"}, {"fieldName": "source"}],
                    },
                }
            ]
        },
    }

    with httpx.Client(timeout=30.0) as client:
        resp = client.put(url, json=index_def, headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"})
        if resp.status_code in (200, 201):
            print(f"✓ Index '{index_name}' created/updated")
        else:
            print(f"✗ Index creation failed ({resp.status_code}): {resp.text[:200]}")
            resp.raise_for_status()


def upload_documents(endpoint: str, index_name: str, token: str, docs: list) -> None:
    """Upload documents to the search index."""
    url = f"{endpoint}/indexes/{index_name}/docs/index?api-version={API_VERSION}"

    batch = {"value": [{"@search.action": "mergeOrUpload", **doc} for doc in docs]}

    with httpx.Client(timeout=30.0) as client:
        resp = client.post(url, json=batch, headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"})
        if resp.status_code in (200, 207):
            results = resp.json().get("value", [])
            success = sum(1 for r in results if r.get("status"))
            print(f"✓ Uploaded {success}/{len(docs)} documents")
        else:
            print(f"✗ Upload failed ({resp.status_code}): {resp.text[:200]}")
            resp.raise_for_status()


def main():
    credential = DefaultAzureCredential()
    token = credential.get_token("https://search.azure.com/.default").token

    print(f"Using search endpoint: {SEARCH_ENDPOINT}")
    print(f"Index name: {INDEX_NAME}")
    print(f"Documents to upload: {len(DOCUMENTS)}")
    print()

    create_index(SEARCH_ENDPOINT, INDEX_NAME, token)
    upload_documents(SEARCH_ENDPOINT, INDEX_NAME, token, DOCUMENTS)

    print()
    print("Done! The index is ready for the RAG agent.")


if __name__ == "__main__":
    main()
