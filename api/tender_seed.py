"""
IT Helpdesk Portal — Tender Pack seed answer library (Batch I, HD-054–058 widened)
==================================================================================
The single source of the starter answer library. InMemoryTenderStore loads
it directly, and schema_and_seed_tender.sql is generated from it
(python tender_seed.py > schema_and_seed_tender.sql), so a fresh database and
the offline tests always hold the same rows.

*** EVERY SEED ANSWER IS A DRAFT ***
Only facts already verified in the Policy & Compliance hub are stated as
fact (the CLG_SEC_POL_001-006 policy set, the Board approval, the owner role,
Cyber Essentials / Cyber Essentials Plus, ICO registration ZA211766). Anything
not yet verified is written as a [confirm: ...] placeholder. The matcher
treats any answer containing "[confirm" as needing review, so a placeholder
can never reach a client without a person replacing it.

evidence = keys resolved against live Policy & Compliance records at match
time (exact title first, then "title starts with key", shortest wins), so
"Cyber Essentials" never resolves to "Cyber Essentials Plus".
"""

SEED_ANSWERS = [
    {
        "answerId": "cert-cyber-essentials-plus",
        "category": "Certifications",
        "question": "Do you hold Cyber Essentials Plus certification?",
        "keywords": ["cyber essentials plus", "ce+", "ce plus", "certification", "certified", "independently assessed"],
        "answerText": (
            "Yes. Cognition Learning Group holds Cyber Essentials Plus certification, which is independently "
            "assessed and verified against the UK Government's Cyber Essentials scheme. A copy of the current "
            "certificate is included in the evidence appendix."
        ),
        "evidence": ["Cyber Essentials Plus"],
    },
    {
        "answerId": "cert-cyber-essentials",
        "category": "Certifications",
        "question": "Do you hold Cyber Essentials certification?",
        "keywords": ["cyber essentials", "certification", "certified", "government scheme", "basic controls"],
        "answerText": (
            "Yes. Cognition Learning Group holds Cyber Essentials certification under the UK Government's Cyber "
            "Essentials scheme. A copy of the current certificate is included in the evidence appendix."
        ),
        "evidence": ["Cyber Essentials"],
    },
    {
        "answerId": "cert-iso-27001",
        "category": "Certifications",
        "question": "Are you certified to ISO/IEC 27001?",
        "keywords": ["iso 27001", "iso/iec 27001", "27001", "iso", "isms certification", "accredited"],
        "answerText": (
            "Our information security management system and policy set (CLG_SEC_POL_001 to CLG_SEC_POL_006) are "
            "aligned with ISO/IEC 27001:2022 and approved by the CLG Board of Directors. "
            "[confirm: state whether CLG holds ISO/IEC 27001 certification, and if not, any planned certification date.]"
        ),
        "evidence": ["CLG_SEC_POL_001"],
    },
    {
        "answerId": "gov-information-security-policy",
        "category": "Governance",
        "question": "Do you have a documented information security policy?",
        "keywords": ["information security policy", "security policy", "isms", "isms policy", "governance framework"],
        "answerText": (
            "Yes. Information security is governed by the CLG Information Security Management System (ISMS) "
            "Policy, CLG_SEC_POL_001, supported by policies CLG_SEC_POL_002 to CLG_SEC_POL_006. The policy set is "
            "aligned with ISO/IEC 27001:2022, approved by the CLG Board of Directors, and owned by the Group "
            "Director, IT and Digital Transformation. Each policy carries a scheduled review date."
        ),
        "evidence": ["CLG_SEC_POL_001"],
    },
    {
        "answerId": "gov-security-responsibility",
        "category": "Governance",
        "question": "Who is responsible for information security in your organisation?",
        "keywords": ["responsible", "responsibility", "accountable", "owner", "security lead", "ciso", "roles"],
        "answerText": (
            "Overall accountability for information security sits with the CLG Board of Directors, which approves "
            "the information security policy set. Day-to-day ownership sits with the Group Director, IT and "
            "Digital Transformation, who owns the ISMS Policy (CLG_SEC_POL_001)."
        ),
        "evidence": ["CLG_SEC_POL_001"],
    },
    {
        "answerId": "dp-ico-registration",
        "category": "Data protection",
        "question": "Are you registered with the Information Commissioner's Office (ICO)?",
        "keywords": ["ico", "information commissioner", "registered", "registration", "data protection fee"],
        "answerText": (
            "Yes. Cognition Education UK Limited is registered with the Information Commissioner's Office under "
            "registration reference ZA211766."
        ),
        "evidence": ["ICO"],
    },
    {
        "answerId": "dp-uk-gdpr",
        "category": "Data protection",
        "question": "How do you comply with UK GDPR and the Data Protection Act 2018?",
        "keywords": ["gdpr", "uk gdpr", "data protection act", "personal data", "privacy", "dpa", "lawful"],
        "answerText": (
            "Cognition Education UK Limited is registered with the ICO (ZA211766) and processes personal data "
            "under its Board-approved information security policies. Staff may only store or process personal or "
            "sensitive data in CLG's approved applications. [confirm: name the Data Protection Officer or data "
            "protection lead and how data subject requests are handled.]"
        ),
        "evidence": ["ICO", "CLG_SEC_POL_001"],
    },
    {
        "answerId": "access-mfa",
        "category": "Access control",
        "question": "Do you use multi-factor authentication?",
        "keywords": ["mfa", "multi-factor", "multifactor", "2fa", "two-factor", "authentication", "sign-in"],
        "answerText": (
            "Yes. Staff sign in with Microsoft Entra ID accounts. [confirm: multi-factor authentication is enforced "
            "for all staff accounts through Entra Conditional Access, including administrators and remote access.]"
        ),
        "evidence": ["CLG_SEC_POL_001", "Cyber Essentials"],
    },
    {
        "answerId": "access-control",
        "category": "Access control",
        "question": "How do you control access to systems and data?",
        "keywords": ["access control", "least privilege", "permissions", "role-based", "joiners", "leavers", "leave", "offboarding", "restrict", "privileged"],
        "answerText": (
            "Access to CLG systems is controlled through Microsoft Entra ID, with access granted by role and "
            "security group. [confirm: describe the joiner, mover and leaver process, how often access is "
            "reviewed, and how administrator accounts are separated from day-to-day accounts.]"
        ),
        "evidence": ["CLG_SEC_POL_001"],
    },
    {
        "answerId": "device-management",
        "category": "Devices",
        "question": "How are laptops and mobile devices secured?",
        "keywords": ["laptop", "device", "endpoint", "mobile", "intune", "encryption", "mdm", "asset"],
        "answerText": (
            "Corporate devices are managed through Microsoft Intune and recorded in the CLG IT Asset Register, "
            "which is reconciled against Intune. [confirm: full-disk encryption standard (for example BitLocker "
            "or FileVault), screen-lock policy, and remote wipe for lost or stolen devices.]"
        ),
        "evidence": ["Cyber Essentials"],
    },
    {
        "answerId": "malware-patching",
        "category": "Devices",
        "question": "How do you protect against malware and keep systems patched?",
        "keywords": ["malware", "antivirus", "anti-virus", "patch", "patching", "updates", "vulnerability"],
        "answerText": (
            "Malware protection and security updates are covered by the Cyber Essentials controls CLG is certified "
            "against. [confirm: the anti-malware product in use (for example Microsoft Defender) and the target "
            "time to apply critical security updates.]"
        ),
        "evidence": ["Cyber Essentials"],
    },
    {
        "answerId": "incident-response",
        "category": "Incident management",
        "question": "Do you have a process for responding to security incidents and data breaches?",
        "keywords": ["incident", "breach", "response", "report", "notify", "72 hours", "security event"],
        "answerText": (
            "Security incidents are reported to the IT team through the CLG IT helpdesk and handled under CLG's "
            "information security policies. Personal data breaches that meet the legal threshold are reported to "
            "the ICO within 72 hours. [confirm: name the incident response policy and the client notification "
            "commitment you are prepared to offer.]"
        ),
        "evidence": ["CLG_SEC_POL_001"],
    },
    {
        "answerId": "business-continuity",
        "category": "Resilience",
        "question": "Do you have a business continuity and disaster recovery plan?",
        "keywords": ["business continuity", "bcp", "disaster recovery", "dr", "resilience", "recovery"],
        "answerText": (
            "Yes. CLG maintains a Business Continuity Plan. [confirm: the approved version and date, how often it "
            "is tested, and the recovery time objectives you are prepared to state.]"
        ),
        "evidence": [],
    },
    {
        "answerId": "hosting-backup",
        "category": "Resilience",
        "question": "Where is your data hosted and how is it backed up?",
        "keywords": ["hosted", "hosting", "data centre", "data center", "cloud", "backup", "backed up", "stored", "storage", "residency"],
        "answerText": (
            "CLG's core systems run on Microsoft 365 and Microsoft Azure; CLG's own Azure services are hosted in "
            "the UK South region. [confirm: Microsoft 365 data residency, backup approach and retention period.]"
        ),
        "evidence": [],
    },
    {
        "answerId": "staff-training",
        "category": "People",
        "question": "Do your staff receive information security awareness training?",
        "keywords": ["training", "awareness", "staff", "phishing", "induction", "education"],
        "answerText": (
            "[confirm: describe security awareness training — at induction and how often after, the platform used, "
            "and whether phishing simulations are run.]"
        ),
        "evidence": ["CLG_SEC_POL_001"],
    },
    {
        "answerId": "supplier-security",
        "category": "Suppliers",
        "question": "How do you manage information security risks from suppliers and subcontractors?",
        "keywords": ["supplier", "suppliers", "third party", "subcontractor", "vendor", "supply chain"],
        "answerText": (
            "[confirm: describe how suppliers that handle CLG or client data are assessed before use and reviewed, "
            "and whether contracts include security and data protection terms.]"
        ),
        "evidence": ["CLG_SEC_POL_001"],
    },
]


def _sql_str(value):
    if value is None:
        return "NULL"
    return "N'" + str(value).replace("'", "''") + "'"


def render_sql() -> str:
    """Schema + idempotent seed for Azure SQL. Seed rows are inserted per
    row only when that answerId is absent (never a blanket IF NOT EXISTS),
    so re-running never overwrites answers IT Security has since edited."""
    import json
    out = [
        "-- Tender Pack schema and seed (generated by: python tender_seed.py)",
        "-- Safe to re-run: creates tables only if missing; inserts each seed answer only if its answerId is absent.",
        "",
        "IF OBJECT_ID('dbo.tender_answer', 'U') IS NULL",
        "CREATE TABLE dbo.tender_answer (",
        "    answerId     NVARCHAR(100)  NOT NULL PRIMARY KEY,",
        "    category     NVARCHAR(200)  NOT NULL,",
        "    question     NVARCHAR(2000) NOT NULL,",
        "    keywords     NVARCHAR(MAX)  NOT NULL,  -- JSON array",
        "    answerText   NVARCHAR(MAX)  NOT NULL,",
        "    evidence     NVARCHAR(MAX)  NOT NULL,  -- JSON array of Policy & Compliance title keys",
        "    owner        NVARCHAR(400)  NOT NULL,",
        "    status       NVARCHAR(50)   NOT NULL,  -- Draft | Approved | Retired",
        "    reviewDate   DATE           NULL,",
        "    approvedBy   NVARCHAR(400)  NULL,",
        "    approvedAt   DATETIME2      NULL,",
        "    updatedBy    NVARCHAR(400)  NULL,",
        "    updatedAt    DATETIME2      NOT NULL DEFAULT SYSUTCDATETIME()",
        ");",
        "",
        "IF OBJECT_ID('dbo.tender_pack', 'U') IS NULL",
        "CREATE TABLE dbo.tender_pack (",
        "    packId       NVARCHAR(64)   NOT NULL PRIMARY KEY,",
        "    packRef      NVARCHAR(64)   NOT NULL,",
        "    clientName   NVARCHAR(400)  NOT NULL,",
        "    bidReference NVARCHAR(400)  NULL,",
        "    deadline     DATE           NOT NULL,",
        "    preparedBy   NVARCHAR(400)  NOT NULL,",
        "    createdAt    DATETIME2      NOT NULL DEFAULT SYSUTCDATETIME(),",
        "    summary      NVARCHAR(MAX)  NOT NULL,  -- JSON: counts by status",
        "    snapshot     NVARCHAR(MAX)  NOT NULL   -- JSON: the full pack exactly as issued (audit record)",
        ");",
        "",
    ]
    for a in SEED_ANSWERS:
        out.append(f"IF NOT EXISTS (SELECT 1 FROM dbo.tender_answer WHERE answerId = {_sql_str(a['answerId'])})")
        out.append(
            "INSERT INTO dbo.tender_answer (answerId, category, question, keywords, answerText, evidence, owner, status, reviewDate) VALUES ("
            + ", ".join([
                _sql_str(a["answerId"]), _sql_str(a["category"]), _sql_str(a["question"]),
                _sql_str(json.dumps(a["keywords"])), _sql_str(a["answerText"]), _sql_str(json.dumps(a["evidence"])),
                _sql_str("IT Security"), _sql_str("Draft"), "NULL",
            ])
            + ");"
        )
    return "\n".join(out) + "\n"


if __name__ == "__main__":
    print(render_sql(), end="")
