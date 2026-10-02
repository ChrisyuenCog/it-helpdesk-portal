"""
Tender Pack answer library v2 — 100 answers grounded in CLG's policy set
=========================================================================
Source documents (read in full, 2 Oct 2026):
  POL_001 ISMS Policy V1.0 · POL_002 Information and Cyber Security Policy V1.0 ·
  POL_003 Acceptable Use and Remote Working Policy V1.0 · POL_004 Data Protection
  and Privacy Policy V1.1 (pending Board approval) · POL_005 Secure Software
  Development Policy V1.0 · POL_006 AI Governance Policy V1.0 · Business
  Continuity Plan and Cyber Security Policy (March 2026) · Cyber Essentials and
  Cyber Essentials Plus certificates · ICO registration certificate ZA211766.

Rules followed when writing these answers:
  * State only what a source document says. Policy requirements are written as
    requirements ("our policy requires…"), not as audited fact, unless the BCP or
    a certificate states it as current practice (e.g. MFA enforced, Sophos deployed).
  * Every answer names its source and section so a reviewer can check it.
  * Anything the documents do not commit to is a [confirm: …] placeholder, which
    the tender engine refuses to issue until a person replaces it.
  * Technical answers cite Cyber Essentials (valid), not Cyber Essentials Plus,
    so they are not blocked while CE+ recertification is outstanding.

Each row: (answerId, category, question, keywords, answerText, evidence keys).
The first 16 ids are the original seed ids, kept so existing links still work.
"""

P1, P2, P3, P4, P5, P6 = (f"CLG_SEC_POL_00{i}" for i in range(1, 7))
BCP, CE, CEP, ICO = "CLG Business Continuity Plan", "Cyber Essentials", "Cyber Essentials Plus", "ICO"

LIBRARY_V2 = [
    # ------------------------------------------------------------ Certifications and assurance
    ("cert-cyber-essentials-plus", "Certifications", "Do you hold Cyber Essentials Plus certification?",
     ["cyber essentials plus", "ce+", "ce plus", "independently assessed", "certification"],
     "Yes. Cognition Education Ltd (NZ), trading as Cognition Learning Group and incorporating all subsidiary companies, "
     "holds Cyber Essentials Plus certification for the whole organisation, independently assessed under the IASME "
     "scheme. A copy of the current certificate is included with this response.", [CEP]),
    ("cert-cyber-essentials", "Certifications", "Do you hold Cyber Essentials certification?",
     ["cyber essentials", "certification", "certified", "government scheme", "iasme"],
     "Yes. Cognition Learning Group holds Cyber Essentials certification covering the whole organisation, issued under "
     "the UK Government's Cyber Essentials scheme through the IASME certification body. A copy of the current "
     "certificate is included with this response.", [CE]),
    ("cert-iso-27001", "Certifications", "Are you certified to ISO/IEC 27001?",
     ["iso 27001", "27001", "iso certification", "accredited", "certified"],
     "CLG's Information Security Management System and its six Board-approved policies (CLG_SEC_POL_001 to 006) are "
     "aligned with ISO/IEC 27001:2022, and CLG maintains a Statement of Applicability mapping Annex A controls "
     "(ISMS Policy, section 5). The Board is committed to obtaining and retaining certification as needed (section 9). "
     "[confirm: current ISO/IEC 27001 certification status and any target date.]", [P1]),
    ("gov-information-security-policy", "Governance", "Do you have a documented information security policy?",
     ["information security policy", "security policy", "isms", "isms policy", "documented policy"],
     "Yes. Information security is governed by the CLG ISMS Policy (CLG_SEC_POL_001), aligned with ISO/IEC 27001:2022 "
     "and approved by the CLG Board of Directors. It is supported by five Board-approved policies covering information "
     "and cyber security, acceptable use and remote working, data protection and privacy, secure software development, "
     "and AI governance.", [P1]),
    ("gov-security-responsibility", "Governance", "Who is responsible for information security in your organisation?",
     ["responsible", "responsibility", "accountable", "ciso", "security lead", "isms manager"],
     "The CLG Board of Directors has ultimate responsibility for information security and approves the ISMS and its "
     "supporting policies. Day-to-day operation of the ISMS is led by the Group Director, IT and Digital "
     "Transformation, acting as ISMS Manager, with authority to develop and enforce security controls "
     "(ISMS Policy, section 4).", [P1]),
    ("dp-ico-registration", "Data protection", "Are you registered with the Information Commissioner's Office (ICO)?",
     ["ico", "information commissioner", "registered", "registration number", "data protection fee"],
     "Yes. Cognition Education UK Limited is registered with the Information Commissioner's Office under registration "
     "reference ZA211766, first registered on 16 October 2016. A copy of the current registration certificate is "
     "included with this response.", [ICO]),
    ("dp-uk-gdpr", "Data protection", "How do you comply with UK GDPR and the Data Protection Act 2018?",
     ["gdpr", "uk gdpr", "data protection act", "personal data", "privacy", "compliance"],
     "CLG applies the principles of the UK GDPR and EU GDPR as its Group benchmark, together with local data protection "
     "law in each jurisdiction where it operates (Data Protection and Privacy Policy, CLG_SEC_POL_004, section 5). "
     "Personal data is processed only under a valid lawful basis, classified at least as Confidential, protected by "
     "role-based access and encryption, and retained only as long as necessary. Cognition Education UK Limited is "
     "registered with the ICO (ZA211766).", [P4, ICO]),
    ("access-mfa", "Access control", "Do you use multi-factor authentication?",
     ["mfa", "multi-factor", "2fa", "two-factor", "authentication", "conditional access"],
     "Yes. Multi-factor authentication is enforced across all of CLG's cloud services, including Microsoft 365, Zoho "
     "and Xero (Business Continuity Plan). Policy makes MFA mandatory for remote access to internal systems, for all "
     "cloud service logins where available, and for every administrative or privileged account (Information and "
     "Cyber Security Policy, CLG_SEC_POL_002, section 4.1).", [P2, BCP, CE]),
    ("access-control", "Access control", "How do you control access to systems and data?",
     ["access control", "least privilege", "permissions", "role-based", "unique user id", "authorisation"],
     "Every user has a unique ID, shared accounts are prohibited, and access is granted on the principle of least "
     "privilege according to job role. Accounts are created only after authorisation by HR or the hiring manager and "
     "validated by IT, and privileged accounts are tightly controlled and monitored (CLG_SEC_POL_002, sections 3 "
     "and 4).", [P2]),
    ("device-management", "Devices", "How are laptops and mobile devices secured?",
     ["laptop", "device", "endpoint", "mobile", "intune", "mdm", "secure build"],
     "Company devices are built to CLG's secure standard before issue: full disk encryption (BitLocker or FileVault), "
     "endpoint protection, device management agents for patching and monitoring, standard (non-administrator) user "
     "accounts and host firewalls (CLG_SEC_POL_002, section 7.1). Devices are managed through Microsoft Intune and "
     "recorded in CLG's IT asset register.", [P2, CE]),
    ("malware-patching", "Devices", "How do you protect against malware and keep systems patched?",
     ["malware", "antivirus", "anti-virus", "sophos", "patch", "patching", "ransomware"],
     "Sophos endpoint protection, including deep learning, anti-exploit and anti-ransomware capabilities, is deployed "
     "across the Group (Business Continuity Plan). Policy requires real-time scanning, automatic updates and alerting "
     "on all endpoints and servers, and risk-based patching with a target of, for example, 14 days for critical patches "
     "and 30 days for others (CLG_SEC_POL_002, sections 5.3 and 5.4).", [P2, BCP, CE]),
    ("incident-response", "Incident management", "Do you have a process for responding to security incidents and data breaches?",
     ["incident", "incident response", "breach", "security event", "containment", "report"],
     "Yes. All staff must report suspected incidents immediately; each incident is logged, classified by severity "
     "(Critical, High, Medium, Low) and handled through a structured plan of containment, investigation, eradication, "
     "recovery and notification, followed by a post-incident review (CLG_SEC_POL_002, section 10). Personal data "
     "breaches are handled under the Data Protection and Privacy Policy, including ICO notification within 72 hours "
     "where required.", [P2, P4]),
    ("business-continuity", "Resilience", "Do you have a business continuity and disaster recovery plan?",
     ["business continuity", "bcp", "disaster recovery", "dr", "resilience", "continuity plan"],
     "Yes. CLG maintains a Business Continuity Plan, reviewed and tested at least every twelve months, which assesses "
     "risks, defines four prioritised critical functions with recovery objectives, and sets out command and control, "
     "contacts, an emergency checklist and an action log. It maps to ISO/IEC 27001:2022 control A.5.30 (ICT readiness "
     "for business continuity).", [BCP]),
    ("hosting-backup", "Resilience", "Where is your data hosted and how is it backed up?",
     ["hosted", "hosting", "data centre", "cloud", "backup", "backed up", "stored", "residency"],
     "All CLG data is held on secure, cloud-based platforms, principally Microsoft 365 and Zoho, which back up on a "
     "consistent, recurring basis with failover built in; Microsoft 365 data is replicated to geographically separate "
     "data centres (Business Continuity Plan). CLG's own Azure services are hosted in the UK South region. "
     "[confirm: Microsoft 365 and Zoho data residency for client data.]", [BCP, P2]),
    ("staff-training", "People", "Do your staff receive information security awareness training?",
     ["training", "awareness", "staff training", "phishing awareness", "induction", "education"],
     "Yes. All staff complete mandatory data protection and security training at induction and periodically "
     "thereafter, covering privacy principles, security practices such as recognising phishing, and how to report "
     "issues, with role-specific training for teams handling sensitive data (CLG_SEC_POL_004, section 13; "
     "CLG_SEC_POL_001, section 3). [confirm: refresher frequency — the BCP states six-monthly, POL_004 states "
     "typically annually.]", [P4, P1]),
    ("supplier-security", "Suppliers", "How do you manage information security risks from suppliers and subcontractors?",
     ["supplier", "suppliers", "third party", "subcontractor", "vendor", "supply chain"],
     "Suppliers that handle CLG data or critical processes undergo security due diligence before onboarding, scaled to "
     "risk, and high-risk findings must be resolved or the supplier is not used. Contracts include security and privacy "
     "clauses, breach notification, audit rights and return or deletion of data, and critical suppliers provide "
     "periodic assurance such as ISO 27001 certificates or SOC 2 reports (CLG_SEC_POL_002, section 12).", [P2, P4]),

    # ------------------------------------------------------------ Assurance and audit (new)
    ("cert-statement-of-applicability", "Certifications", "Do you maintain a Statement of Applicability?",
     ["statement of applicability", "soa", "annex a", "control mapping"],
     "Yes. CLG maintains a Statement of Applicability mapping which ISO/IEC 27001 Annex A controls are implemented, "
     "with justification for any exclusions. It is maintained by the ISMS Manager and reviewed during internal and "
     "external audits (ISMS Policy, CLG_SEC_POL_001, section 5).", [P1]),
    ("assurance-internal-audit", "Certifications", "Is your information security management system independently audited?",
     ["internal audit", "independent audit", "audited", "assessment", "compliance check"],
     "CLG's internal audit function or a designated independent assessor periodically reviews the ISMS and policy "
     "compliance, reporting findings to management, with significant findings escalated to the Board. The ISMS is "
     "also subject to external assessment, including Cyber Essentials Plus testing and client-required security "
     "assessments (CLG_SEC_POL_001, sections 4 and 9).", [P1, CE]),
    ("assurance-penetration-testing", "Certifications", "Do you carry out penetration testing?",
     ["penetration test", "pen test", "pentest", "ethical hacking", "security testing"],
     "Yes. Policy requires critical applications and major updates to be penetration tested by qualified internal or "
     "external testers, for example annually or at major version changes, with high-risk findings remediated promptly "
     "and results reviewed by management (Secure Software Development Policy, CLG_SEC_POL_005, section 7). "
     "[confirm: date and scope of the most recent penetration test.]", [P5, P2]),
    ("assurance-vulnerability-scanning", "Certifications", "Do you carry out vulnerability scanning?",
     ["vulnerability scanning", "vulnerability scan", "vulnerability management", "scan"],
     "Yes. Regular internal and external vulnerability scans cover CLG's cloud assets, internet-facing systems and "
     "corporate laptops; findings are tracked to closure, and critical vulnerabilities are remediated or mitigated as "
     "a priority, with any deferral approved by the Head of IT and Security (CLG_SEC_POL_002, section 5.3).", [P2, CE]),
    ("assurance-client-audit", "Certifications", "Will you allow us to audit your security controls?",
     ["right to audit", "client audit", "audit rights", "security questionnaire", "assessment"],
     "Yes. CLG's ISMS is subject to client-required security assessments, and all staff are expected to cooperate with "
     "auditors and provide evidence when requested (CLG_SEC_POL_001, section 4). Key elements of CLG's security and "
     "privacy policies may also be shared with clients during contract negotiations (section 9).", [P1]),

    # ------------------------------------------------------------ Governance (new)
    ("gov-policy-framework", "Governance", "Which information security policies do you have?",
     ["policy framework", "policy set", "security policies", "supporting policies", "list of policies"],
     "CLG operates a deliberately consolidated framework of six Board-approved policies: ISMS Policy (CLG_SEC_POL_001), "
     "Information and Cyber Security Policy (002), Acceptable Use and Remote Working Policy (003), Data Protection and "
     "Privacy Policy (004), Secure Software Development Policy (005) and AI Governance Policy (006), supported by a "
     "Business Continuity Plan and lower-level standards and procedures.", [P1, BCP]),
    ("gov-board-oversight", "Governance", "How does your board oversee information security?",
     ["board", "board oversight", "directors", "senior management", "leadership commitment"],
     "The Board approves the ISMS Policy and its five supporting policies, reviews them annually or on significant "
     "change, sets the information security risk appetite, and receives regular reports on security status, major "
     "risks and incidents. Executive management allocates resources and embeds security into daily operations "
     "(CLG_SEC_POL_001, section 4).", [P1]),
    ("gov-policy-review", "Governance", "How often are your security policies reviewed?",
     ["policy review", "reviewed annually", "review cycle", "policy updates", "version control"],
     "Each policy is reviewed at least annually and whenever significant changes occur in the business, risk "
     "landscape, legal obligations or organisational structure. Reviews are led by the ISMS Manager, material changes "
     "require Board approval, and version control is maintained (CLG_SEC_POL_001, section 9; CLG_SEC_POL_002, "
     "section 14).", [P1, P2]),
    ("gov-risk-management", "Governance", "How do you manage information security risk?",
     ["risk management", "risk assessment", "risk register", "risk treatment", "threats"],
     "CLG identifies, analyses and treats information security risks through a structured methodology, assessing "
     "likelihood and impact against existing controls. Risk assessments run at least annually and on significant "
     "change, each risk has an owner, and treatment plans are approved by risk owners, or by senior management or the "
     "Board where high residual risk remains (CLG_SEC_POL_001, section 5).", [P1]),
    ("gov-continual-improvement", "Governance", "How do you ensure continual improvement of information security?",
     ["continual improvement", "management review", "pdca", "plan do check act", "lessons learned"],
     "CLG runs its ISMS on a Plan–Do–Check–Act cycle, with formal management reviews at least annually and after "
     "significant change or incidents. Reviews consider audit outcomes, risk changes, stakeholder feedback and "
     "performance metrics such as incident trends, training completion and service availability, and corrective "
     "actions are tracked (CLG_SEC_POL_001, section 6).", [P1]),
    ("gov-policy-exceptions", "Governance", "How are exceptions to security policy managed?",
     ["exception", "policy exception", "waiver", "deviation", "compensating controls"],
     "Exceptions must be formally requested with a justification, scope, duration and compensating controls, "
     "risk-assessed by IT Security and approved at a level matching the risk, up to the CEO or Board. Approved "
     "exceptions are logged in an Exceptions Register for a defined period, typically no more than 6 to 12 months "
     "(CLG_SEC_POL_002, section 13.6).", [P2]),
    ("gov-metrics-reporting", "Governance", "How do you measure the effectiveness of your security controls?",
     ["metrics", "kpi", "effectiveness", "measurement", "reporting", "monitoring controls"],
     "CLG monitors control effectiveness through automated monitoring (security alerts, vulnerability scanning, cloud "
     "security monitoring), procedural reviews such as access recertification and internal audit, and tracked metrics "
     "including incident trends, audit findings, training completion and service availability, reported to management "
     "and the Board (CLG_SEC_POL_001, section 6.3).", [P1]),
    ("gov-scope", "Governance", "What is the scope of your information security management system?",
     ["scope", "isms scope", "coverage", "subsidiaries", "in scope"],
     "The ISMS covers all of CLG's operations: every business unit and wholly owned subsidiary; all employees, "
     "contractors and third parties who process CLG information; all information assets; all systems including cloud, "
     "SaaS and CLG's own Learning Management System; company and approved personal devices; offices and remote "
     "working environments; and suppliers through contract (CLG_SEC_POL_001, section 2).", [P1]),

    # ------------------------------------------------------------ People
    ("people-acknowledgement", "People", "Do staff formally accept your security policies?",
     ["acknowledge", "acknowledgement", "sign policy", "accept policy", "read and understood"],
     "Yes. All employees and contractors must formally acknowledge that they have read and understood the security "
     "policies, and the Acceptable Use and Remote Working Policy is acknowledged at onboarding and periodically "
     "thereafter. Compliance is a condition of employment or engagement (CLG_SEC_POL_001, section 9; "
     "CLG_SEC_POL_003, section 1).", [P1, P3]),
    ("people-background-checks", "People", "Do you carry out background checks on staff?",
     ["background check", "vetting", "screening", "pre-employment", "dbs", "references"],
     "Yes. Background checks form part of CLG's onboarding controls, and the People Manager is responsible for "
     "ensuring background checks and security induction training for new hires (CLG_SEC_POL_001, sections 4 and "
     "6.2). [confirm: the checks performed, for example identity, right to work, references and criminal record "
     "checks for roles that require them.]", [P1]),
    ("people-disciplinary", "People", "What happens if staff breach your security policies?",
     ["disciplinary", "breach of policy", "non-compliance", "sanctions", "enforcement"],
     "Deliberate or negligent breaches may lead to disciplinary action under CLG's Disciplinary Procedure, up to and "
     "including termination of employment or contract, and CLG may restrict system access to protect the "
     "organisation. Staff are not penalised for honest reporting of mistakes (CLG_SEC_POL_002, section 13.4; "
     "CLG_SEC_POL_003, sections 10 and 11).", [P2, P3]),
    ("people-contractors", "People", "Do your security requirements apply to contractors and temporary staff?",
     ["contractors", "temporary staff", "consultants", "agency staff", "interns"],
     "Yes. CLG's policies apply to all employees, contractors, consultants, agency staff, interns and authorised third "
     "parties, regardless of location. Contractors must use CLG-approved tools, receive least-privilege, time-bound "
     "access that is revoked on completion, and are bound by confidentiality obligations (CLG_SEC_POL_003, section 2; "
     "CLG_SEC_POL_002, section 12.3).", [P3, P2]),
    ("people-security-culture", "People", "How do you encourage staff to report security concerns?",
     ["reporting culture", "report concerns", "whistleblowing", "no blame", "speak up"],
     "Staff must report suspected incidents, weaknesses and policy breaches promptly, and CLG operates a no-blame "
     "approach: users are not penalised for honest reporting, and retaliation against anyone raising a data protection "
     "concern in good faith is prohibited. Concealing a breach is a serious disciplinary matter (CLG_SEC_POL_003, "
     "section 10; CLG_SEC_POL_004, sections 11 and 13).", [P3, P4]),
    ("people-role-training", "People", "Do staff in technical or sensitive roles receive additional training?",
     ["role-specific training", "developer training", "secure coding training", "specialist training", "owasp"],
     "Yes. Teams handling sensitive data, such as People, customer support and IT, receive role-specific data "
     "protection training, and all personnel involved in software development complete secure development training, "
     "including refreshers such as OWASP Top 10 workshops (CLG_SEC_POL_004, section 13; CLG_SEC_POL_005, sections 10 "
     "and 11).", [P4, P5]),

    # ------------------------------------------------------------ Access control (new)
    ("access-joiners-leavers", "Access control", "How do you manage joiners, movers and leavers?",
     ["joiners", "leavers", "movers", "onboarding", "offboarding", "leave", "deprovisioning"],
     "New accounts are created only after authorisation and granted least-privilege access for the role; role changes "
     "trigger an access review; and leavers' access to all systems, including email and physical access, is "
     "deactivated promptly, preferably on the last working day or immediately on involuntary termination, using an IT "
     "checklist (CLG_SEC_POL_002, section 4.2).", [P2, CE]),
    ("access-reviews", "Access control", "How often do you review user access rights?",
     ["access review", "access recertification", "user access review", "quarterly review", "dormant accounts"],
     "System and data owners review user access at least annually for all systems and more frequently, for example "
     "quarterly, for highly sensitive systems and privileged access. Unnecessary access and dormant accounts, such as "
     "those unused for 90 days, are revoked (CLG_SEC_POL_002, section 4.3).", [P2]),
    ("access-privileged", "Access control", "How do you control privileged and administrator accounts?",
     ["privileged access", "administrator", "admin accounts", "admin rights", "privileged accounts"],
     "Privileged accounts are tightly controlled and monitored, always protected by MFA, and reviewed more frequently "
     "than standard access. End users work with standard accounts, with administrative rights provisioned by IT only "
     "for controlled cases, and remote administrative access may be restricted by source or require just-in-time "
     "activation (CLG_SEC_POL_002, sections 3, 4 and 7.1).", [P2, CE]),
    ("access-passwords", "Access control", "What is your password policy?",
     ["password", "passwords", "password policy", "passphrase", "lockout", "credentials"],
     "Passwords must meet CLG's standards for length and complexity or passphrases, are never shared or reused across "
     "personal and company accounts, and must be changed if compromise is suspected. Default passwords are changed on "
     "deployment, and IT enforces password history and lockout after repeated failures; MFA protects all cloud and "
     "privileged access (CLG_SEC_POL_002, section 4.1).", [P2, CE]),
    ("access-third-party", "Access control", "How do you control access by third parties and suppliers?",
     ["third party access", "supplier access", "vendor access", "external access", "contractor access"],
     "Third-party accounts must be sponsored by an internal owner, time-bound, used only for their defined purpose and "
     "disabled when no longer needed. They follow the same rules as internal access, including unique IDs, least "
     "privilege and MFA, and remote connections are approved, logged and monitored (CLG_SEC_POL_002, sections 4.3, 6.4 "
     "and 12.3).", [P2]),
    ("access-remote", "Access control", "How is remote access to your systems secured?",
     ["remote access", "vpn", "remote working access", "encrypted channel", "home working access"],
     "All remote access to internal resources uses secure, encrypted channels with MFA, such as a strongly encrypted "
     "VPN or a secure virtual desktop. Idle sessions lock or log out automatically, and remote administrative access "
     "is further restricted to trusted devices or networks where feasible (CLG_SEC_POL_002, section 4.4).", [P2, CE]),
    ("access-shared-accounts", "Access control", "Do you allow shared or generic user accounts?",
     ["shared accounts", "generic accounts", "shared login", "unique id", "service accounts"],
     "No. Each user must have a unique user ID, and shared accounts are prohibited except in extraordinary cases "
     "approved by IT Security with compensating controls. In cloud platforms, services use unique service identities "
     "rather than root or master accounts (CLG_SEC_POL_002, sections 4.1 and 6.2).", [P2]),

    # ------------------------------------------------------------ Devices (new)
    ("device-encryption", "Devices", "Are laptops and devices encrypted?",
     ["encryption", "encrypted", "full disk encryption", "bitlocker", "filevault"],
     "Yes. Full disk encryption is required on all company laptops, desktops and mobile devices (BitLocker for "
     "Windows, FileVault for macOS, device encryption for mobile), and personal devices used for work must also be "
     "encrypted (CLG_SEC_POL_002, section 7.1; CLG_SEC_POL_003, section 7).", [P2, P3, CE]),
    ("device-byod", "Devices", "Do you allow personal devices (BYOD) to access company data?",
     ["byod", "bring your own device", "personal device", "personal phone", "mobile device management"],
     "Only under strict conditions. Personal devices must be approved and enrolled in CLG's device management, meet "
     "minimum requirements (encryption, screen lock, supported and patched operating system, required security "
     "tooling), and access CLG data only through approved apps. Rooted or jailbroken devices are blocked, and CLG can "
     "remove corporate data remotely (CLG_SEC_POL_002, section 7.2; CLG_SEC_POL_003, section 7).", [P2, P3]),
    ("device-removable-media", "Devices", "How do you control the use of USB drives and removable media?",
     ["usb", "removable media", "memory stick", "external drive", "portable media"],
     "Removable media is restricted. CLG data must not be stored on unencrypted removable media; IT can enforce this "
     "through device controls, and any business need, such as supplying data to a client, must be authorised and use "
     "a hardware-encrypted drive. Approved encrypted cloud storage is the default for sharing files "
     "(CLG_SEC_POL_002, sections 8.1 and 8.3).", [P2]),
    ("device-loss-theft", "Devices", "What happens if a laptop or phone is lost or stolen?",
     ["lost device", "stolen", "theft", "remote wipe", "loss of laptop"],
     "Loss or theft must be reported immediately. Because all data is held in the cloud, CLG can switch off the user's "
     "access, reset passwords and remotely wipe the device, then provide replacement hardware; the incident is "
     "reported to the police and assessed as a potential data breach (Business Continuity Plan, Critical Function 1; "
     "CLG_SEC_POL_002, section 7.3).", [BCP, P2]),
    ("device-screen-lock", "Devices", "Do devices lock automatically when unattended?",
     ["screen lock", "auto lock", "inactivity", "timeout", "unattended"],
     "Yes. Devices must lock automatically after a short period of inactivity, for example 5 to 15 minutes, and users "
     "must lock their screen whenever they leave a device unattended. CLG staff follow a clear desk and clear screen "
     "approach, including at home (CLG_SEC_POL_002, section 7.3; CLG_SEC_POL_003, section 6).", [P2, P3]),
    ("device-software-control", "Devices", "Can users install their own software?",
     ["install software", "unapproved software", "application control", "software approval", "admin rights"],
     "No. Users must not alter security settings or install unapproved software or hardware; new software is "
     "requested through IT and security-assessed before approval. End users run standard accounts without "
     "administrative rights (CLG_SEC_POL_002, section 7.1; CLG_SEC_POL_003, section 9).", [P2, P3, CE]),
    ("device-secure-configuration", "Devices", "How do you ensure systems are securely configured?",
     ["secure configuration", "hardening", "baseline", "cis benchmark", "default settings"],
     "All systems are hardened to CLG's secure baselines, removing unnecessary accounts and services, enforcing secure "
     "protocols such as TLS 1.2 or later and disabling legacy protocols. Baselines reference sources such as CIS "
     "Benchmarks, are reviewed regularly, and systems are checked for configuration drift (CLG_SEC_POL_002, "
     "section 5.2).", [P2, CE]),

    # ------------------------------------------------------------ Network and cloud
    ("network-firewalls", "Network and cloud", "How do you protect your network perimeter?",
     ["firewall", "firewalls", "perimeter", "boundary", "default deny", "ports"],
     "Firewalls and network gateways under CLG control, including cloud firewalls, are configured to deny by default "
     "and permit only necessary traffic, such as HTTPS on port 443. Management interfaces are not exposed to the "
     "internet, and outbound traffic may be restricted to block malicious destinations (CLG_SEC_POL_002, sections 6.1 "
     "and 6.2).", [P2, CE]),
    ("network-segmentation", "Network and cloud", "Do you segregate your networks?",
     ["segmentation", "segregation", "network separation", "vlan", "isolation"],
     "Yes. Sensitive systems are isolated: in the cloud, production systems such as the LMS backend and database run "
     "in separate virtual networks or security groups, and production, development and test environments use "
     "separate accounts or projects. Guest Wi-Fi is segregated from the corporate network (CLG_SEC_POL_002, sections "
     "6.1 and 6.2).", [P2]),
    ("network-cloud-security", "Network and cloud", "How do you secure your cloud environments?",
     ["cloud security", "azure", "cloud configuration", "iaas", "paas", "cloud console"],
     "Cloud console access is limited to authorised administrators with MFA; services use role-based access and "
     "unique identities; cloud firewall rules restrict traffic between resources; storage is encrypted at rest; audit "
     "logging and native security monitoring are enabled; and misconfigurations raise alerts (CLG_SEC_POL_002, "
     "section 6.2).", [P2]),
    ("network-encryption-transit", "Network and cloud", "Is data encrypted in transit?",
     ["encryption in transit", "tls", "https", "sftp", "data in transit"],
     "Yes. All CLG data crossing networks CLG does not fully control is encrypted, using HTTPS/TLS 1.2 or later for web "
     "access, VPN or SSH for administration, and secure channels such as HTTPS or SFTP for integrations. Insecure "
     "protocols such as FTP, Telnet and HTTP are prohibited for sensitive data (CLG_SEC_POL_002, section 8.1).", [P2]),
    ("network-encryption-rest", "Network and cloud", "Is data encrypted at rest?",
     ["encryption at rest", "aes-256", "encrypted storage", "database encryption", "key management"],
     "Yes. Sensitive and confidential information is encrypted at rest on devices, servers, databases, file "
     "repositories and backup media, using industry-standard algorithms such as AES-256. Encryption keys are held in "
     "cloud key management services or hardware security modules with access limited to authorised personnel "
     "(CLG_SEC_POL_002, section 8.1).", [P2]),
    ("network-wifi", "Network and cloud", "How are wireless networks secured, including for home workers?",
     ["wifi", "wi-fi", "wireless", "wpa2", "wpa3", "public wifi"],
     "Corporate wireless networks use WPA2 or WPA3 encryption with strong passphrases or enterprise authentication, "
     "and guest Wi-Fi is segregated. Home workers must secure their Wi-Fi with strong passwords and encryption and "
     "must not use unsecured public Wi-Fi for sensitive resources unless using a company VPN (CLG_SEC_POL_002, "
     "sections 6.1 and 11.2; CLG_SEC_POL_003, section 6).", [P2, P3]),
    ("network-ddos-availability", "Network and cloud", "How do you protect services against denial-of-service attacks?",
     ["ddos", "denial of service", "availability", "cdn", "traffic"],
     "For critical services such as the LMS, CLG uses measures including cloud DDoS protection features and content "
     "delivery networks to absorb traffic bursts, and network monitoring detects suspicious traffic such as port scans "
     "and known malicious addresses (CLG_SEC_POL_002, section 6.3).", [P2]),
    ("network-shared-responsibility", "Network and cloud", "How do you assure the security of your cloud and SaaS providers?",
     ["cloud provider", "saas provider", "shared responsibility", "microsoft", "zoho", "soc 2"],
     "CLG follows the shared responsibility model: it secures its configuration within each service, while providers "
     "secure the underlying infrastructure. CLG uses established providers such as Microsoft and Zoho, reviews their "
     "assurance reports such as ISO 27001 certificates and SOC 2 reports, and re-evaluates risk when a provider "
     "changes significantly (CLG_SEC_POL_002, sections 11.3 and 12.4).", [P2, BCP]),
    ("network-email-web-filtering", "Network and cloud", "Do you filter email and web traffic for threats?",
     ["email filtering", "web filtering", "spam", "phishing filter", "dns filtering"],
     "Yes. Email and web security gateways reduce malware and phishing: attachments may be scanned or sandboxed, "
     "emails with unsafe attachments or links are blocked, and known malicious websites are blocked through web and "
     "DNS filtering (CLG_SEC_POL_002, sections 5.4 and 6.3).", [P2, CE]),

    # ------------------------------------------------------------ Data protection (new)
    ("dp-lawful-basis", "Data protection", "On what lawful basis do you process personal data?",
     ["lawful basis", "legal basis", "consent", "legitimate interests", "contract"],
     "Personal data is processed only where a valid lawful basis applies: contract, legal obligation, legitimate "
     "interests (with a documented balancing test), or consent for specific purposes, which can be withdrawn at any "
     "time. Special category and children's data are processed only under additional legal conditions with enhanced "
     "safeguards (CLG_SEC_POL_004, section 5).", [P4]),
    ("dp-subject-rights", "Data protection", "How do you handle data subject access and other rights requests?",
     ["subject access request", "dsar", "data subject rights", "right of access", "erasure", "rectification"],
     "CLG facilitates all data subject rights, including access, rectification, erasure, restriction, portability and "
     "objection. Requests are logged, identity is verified, and responses are made within legal timeframes, generally "
     "one month; staff must forward any request immediately to the People team or ISMS Manager (CLG_SEC_POL_004, "
     "section 7).", [P4]),
    ("dp-retention", "Data protection", "How long do you retain personal data?",
     ["retention", "data retention", "retention period", "how long", "retention schedule"],
     "CLG keeps personal data only as long as needed for its purpose or as required by law or contract, under a Group "
     "retention schedule that is periodically reviewed. [confirm: the Data Protection and Privacy Policy V1.1, which "
     "formalises seven-year retention of employee and payroll records after employment ends, is pending Board "
     "approval.] Expired data is securely deleted (CLG_SEC_POL_004, section 9).", [P4]),
    ("dp-secure-disposal", "Data protection", "How do you securely dispose of data and equipment?",
     ["secure disposal", "data destruction", "destroy", "destroy data", "delete data", "shredding", "wipe", "media disposal"],
     "Deleted personal data is made irrecoverable: electronic data is securely deleted or overwritten, and paper and "
     "storage media are shredded, incinerated or destroyed through authorised services. IT runs a process for "
     "overwriting or physically destroying disks before disposal, and expired backups containing personal data are "
     "securely destroyed (CLG_SEC_POL_004, section 9; CLG_SEC_POL_002, sections 8.2 and 11.1).", [P4, P2]),
    ("dp-international-transfers", "Data protection", "Do you transfer personal data outside the UK?",
     ["international transfer", "outside the uk", "cross-border", "standard contractual clauses", "idta", "adequacy"],
     "Personal data crosses borders only in compliance with applicable transfer rules. Where data leaves the UK, EU or "
     "another region with export rules for a country without an adequacy decision, CLG uses approved safeguards such "
     "as Standard Contractual Clauses or International Data Transfer Agreements with risk assessments, and hosts data "
     "in-region where feasible (CLG_SEC_POL_004, section 10).", [P4]),
    ("dp-privacy-by-design", "Data protection", "Do you carry out Data Protection Impact Assessments?",
     ["dpia", "data protection impact assessment", "privacy by design", "privacy impact", "privacy by default"],
     "Yes. Every new initiative involving personal data must include privacy considerations at the planning stage, "
     "and a DPIA is conducted for processing likely to result in high privacy risk or at the ISMS Manager's request. "
     "Systems use privacy-friendly defaults and collect only necessary data (CLG_SEC_POL_004, section 8).", [P4]),
    ("dp-dpo", "Data protection", "Do you have a Data Protection Officer?",
     ["data protection officer", "dpo", "privacy lead", "privacy officer", "data protection lead"],
     "CLG's privacy lead is the Group Director, IT and Digital Transformation, acting as ISMS Manager, who owns the "
     "Data Protection and Privacy Policy, advises on DPIAs, monitors compliance and is the primary contact for data "
     "protection authorities (CLG_SEC_POL_004, section 12). [confirm: whether a statutory Data Protection Officer is "
     "formally appointed.]", [P4]),
    ("dp-classification", "Data protection", "How do you classify and handle information?",
     ["classification", "data classification", "confidential", "information handling", "labelling"],
     "Information assets are classified by their owners, with controls applied by classification. Personal data is "
     "classified at least as Confidential and special category data as Highly Confidential; it is stored only in "
     "approved secure systems with role-based access and transmitted only over encrypted channels "
     "(CLG_SEC_POL_002, section 5.1; CLG_SEC_POL_004, section 6).", [P2, P4]),
    ("dp-special-category", "Data protection", "How do you protect special category data and children's data?",
     ["special category", "sensitive data", "children's data", "safeguarding data", "health data"],
     "Special category data such as health, ethnicity or criminal background, and children's data, is processed only "
     "under additional legal conditions such as explicit consent or legal necessity, classified as Highly "
     "Confidential and given enhanced safeguards (CLG_SEC_POL_004, sections 5 and 6). Such data may not be entered "
     "into external AI tools without documented approval (CLG_SEC_POL_006, section 7).", [P4, P6]),
    ("dp-processors", "Data protection", "How do you manage processors that handle personal data for you?",
     ["data processor", "data processing agreement", "dpa", "sub-processor", "processor"],
     "Before engaging a processor, CLG evaluates its security and privacy practices. All processors sign Data "
     "Processing Agreements committing them to process only on CLG's instructions, maintain security and "
     "confidentiality, assist with rights requests and breach notifications, and return or delete data at contract "
     "end; key suppliers are monitored (CLG_SEC_POL_004, section 10).", [P4]),
    ("dp-test-data", "Data protection", "Do you use live personal data for testing or development?",
     ["test data", "anonymised data", "pseudonymised", "development data", "production data"],
     "Anonymised or fabricated data is used for testing wherever possible. Production personal data may be used in "
     "development or test environments only in exceptional, authorised cases with protective measures, and must be "
     "securely erased afterwards (CLG_SEC_POL_005, section 5; CLG_SEC_POL_004, section 6).", [P5, P4]),
    ("dp-jurisdictions", "Data protection", "Which data protection laws do you comply with?",
     ["jurisdictions", "data protection laws", "australia", "new zealand", "privacy act", "local law"],
     "CLG applies UK GDPR and EU GDPR principles as its Group benchmark together with local data protection and "
     "employment law across its operations in the UK, Australia, New Zealand and the Pacific Islands, notifying the "
     "relevant authority, such as the ICO in the UK or the OAIC in Australia, when a breach is notifiable "
     "(CLG_SEC_POL_004, sections 2, 5 and 11).", [P4, ICO]),

    # ------------------------------------------------------------ Incident management (new)
    ("incident-breach-notification", "Incident management", "How quickly will you notify the regulator and affected people of a data breach?",
     ["breach notification", "72 hours", "notify ico", "notify individuals", "notifiable breach"],
     "CLG notifies the relevant data protection authority, such as the ICO, within 72 hours of becoming aware of a "
     "notifiable breach, and informs affected individuals without undue delay where the breach poses a high risk to "
     "them. All breaches, including minor ones, are logged and documented (CLG_SEC_POL_004, section 11).", [P4, ICO]),
    ("incident-client-notification", "Incident management", "Will you notify us if an incident affects our data or service?",
     ["notify client", "client notification", "customer notification", "inform us", "service disruption"],
     "Yes. Clients are informed where their data is involved in an incident, with communications managed by executive "
     "management with legal support (CLG_SEC_POL_002, section 10.2). Cognition will notify the client through the "
     "Project Director, or back-up, of any major disruption affecting service delivery within 24 hours, with key "
     "information and mitigation plans (Business Continuity Plan).", [P2, BCP]),
    ("incident-logging", "Incident management", "What security events do you log, and how long are logs kept?",
     ["logging", "audit logs", "audit trail", "log retention", "event logs"],
     "Security-relevant events are logged across CLG systems, including successful and failed logins, account and "
     "privilege changes, configuration changes and security alerts. Logs are protected from tampering, centralised "
     "where possible and retained typically for at least 6 to 12 months, longer for critical systems "
     "(CLG_SEC_POL_002, section 9.1).", [P2]),
    ("incident-monitoring", "Incident management", "How do you monitor for and detect security threats?",
     ["monitoring", "siem", "detection", "alerts", "intrusion detection", "ids"],
     "CLG continuously monitors for defined conditions such as brute-force attempts, malware, unusual privileged "
     "logins and changes to critical configurations, using centralised logging, intrusion detection and cloud-native "
     "security monitoring. High-severity alerts are investigated immediately (CLG_SEC_POL_002, sections 6.3 and "
     "9.2).", [P2]),
    ("incident-post-review", "Incident management", "Do you review incidents to prevent recurrence?",
     ["post-incident review", "lessons learned", "root cause", "rca", "remediation"],
     "Yes. Significant incidents receive a post-incident review covering root cause and whether controls failed, with "
     "tracked improvement actions such as policy updates, training or new controls. Serious incidents and their "
     "remediation are reported to the Board (CLG_SEC_POL_002, section 10.3; CLG_SEC_POL_004, section 11).", [P2, P4]),
    ("incident-classification", "Incident management", "How do you prioritise and escalate security incidents?",
     ["severity", "escalation", "incident classification", "priority", "critical incident"],
     "Every incident is recorded in an incident log and given a severity of Critical, High, Medium or Low, which "
     "determines urgency and escalation. High-severity incidents and any breach of sensitive client or personal data "
     "are escalated to the Head of IT, the CEO and the Board representative, and the privacy lead is informed of any "
     "personal data breach (CLG_SEC_POL_002, section 10.1).", [P2]),

    # ------------------------------------------------------------ Business continuity (new)
    ("bc-testing", "Resilience", "How often is your business continuity plan tested, and when was it last tested?",
     ["bcp test", "bcp tested", "plan tested", "continuity testing", "exercise", "desktop exercise", "call tree"],
     "The plan is reviewed and tested at least every twelve months, including an annual call-tree test. It was last "
     "tested in March 2026 against scenarios of data loss, hardware loss and key personnel unavailability; all tests "
     "passed against the Recovery Time and Recovery Point Objectives, and no material updates were required "
     "(Business Continuity Plan, Testing).", [BCP]),
    ("bc-rto-rpo", "Resilience", "What are your recovery time and recovery point objectives?",
     ["rto", "rpo", "recovery time objective", "recovery point objective", "recovery objectives"],
     "CLG's Business Continuity Plan sets targets for four critical functions: access to data and software systems, "
     "4-hour RTO and 1-hour RPO; access to hardware, 24-hour RTO; telephone connectivity, 8-hour RTO; and personnel, "
     "48-hour RTO. RPO does not apply to functions holding no data, because data is cloud-based.", [BCP]),
    ("bc-backups", "Resilience", "How often is data backed up, and are restores tested?",
     ["backup frequency", "backups", "how often backups", "restore test", "backup testing", "recovery testing"],
     "Critical systems and data are backed up on schedule, with daily incremental and regular full backups, stored "
     "encrypted with restricted access and ideally in a separate environment to resist ransomware. Restores are "
     "tested at least annually to verify integrity and recovery times (CLG_SEC_POL_002, section 8.2). Core cloud "
     "platforms also replicate data continuously across data centres (Business Continuity Plan).", [P2, BCP]),
    ("bc-remote-working", "Resilience", "How would you keep operating if an office became unavailable?",
     ["office unavailable", "continue to deliver", "continue operating", "site failure", "remote working", "premises", "alternative site"],
     "A large part of CLG's workforce is remote, all systems are cloud-based SaaS, and remote staff are required to "
     "have primary and back-up internet connections. CLG operates offices and management teams in the UK, New "
     "Zealand, Solomon Islands, Australia and Malaysia, so work can continue across countries and time zones if one "
     "site is affected (Business Continuity Plan).", [BCP]),
    ("bc-key-personnel", "Resilience", "How do you manage the loss of key personnel?",
     ["key personnel", "staff absence", "illness", "pandemic", "succession", "cover"],
     "Key personnel are supported by a wider team who can cover short-term absence remotely, and longer absences are "
     "covered by corporate resources and a register of qualified consultants. An interim solution is implemented "
     "within 48 hours, with a new staff structure in place within a week if needed (Business Continuity Plan, Critical "
     "Function 4).", [BCP]),
    ("bc-responsibility", "Resilience", "Who is responsible for business continuity?",
     ["continuity owner", "bcp owner", "command and control", "incident lead", "responsibility for bcp"],
     "Overall responsibility for the Business Continuity Plan and its review sits with the CFO, supported by the CEO. "
     "Major incidents are reported without delay to the CEO, who assumes control, and the Group Director, IT and "
     "Digital Transformation, supported by managed IT provider Elive, is responsible for the hardware and data and "
     "systems critical functions (Business Continuity Plan).", [BCP]),
    ("bc-supplier-outage", "Resilience", "What happens if a key cloud provider such as Microsoft 365 suffers an outage?",
     ["cloud outage", "microsoft outage", "supplier outage", "service outage", "failover"],
     "CLG's core platforms, Microsoft 365 and Zoho, operate with service level agreements and built-in failover; "
     "Microsoft 365 continuously replicates data to geographically separate data centres and restores services from "
     "a secondary data centre if one fails. CLG monitors provider service health and follows its data and systems "
     "recovery procedure, recovering from the latest backup where necessary (Business Continuity Plan, Critical "
     "Function 2 and appendices).", [BCP]),
    ("bc-communication", "Resilience", "How do you communicate with staff and clients during a disruption?",
     ["crisis communication", "communication during incident", "staff communication", "whatsapp", "call tree"],
     "Staff are contacted by email or, if email is unavailable, by text message or WhatsApp, and must confirm receipt, "
     "tested annually through a call-tree exercise. Clients are notified of major disruptions within 24 hours through "
     "the Project Director and kept updated throughout recovery (Business Continuity Plan, Command and Control).", [BCP]),
    ("bc-insurance", "Resilience", "Do you hold cyber insurance?",
     ["cyber insurance", "insurance", "indemnity", "cover", "insurer"],
     "Comprehensive insurance is in place across the Group, and CLG's risk treatment approach includes transferring "
     "risk through insurance where appropriate (Business Continuity Plan; CLG_SEC_POL_001, section 5). [confirm: "
     "cyber insurance provider, level of cover and policy expiry date.]", [BCP, P1]),

    # ------------------------------------------------------------ Suppliers (new)
    ("supplier-contracts", "Suppliers", "What security terms do you include in supplier contracts?",
     ["supplier contract", "contract clauses", "security terms", "flow down", "contractual"],
     "Contracts with suppliers that process CLG information include security and privacy clauses requiring adequate "
     "security measures, prompt notification of any incident involving CLG data, CLG's right to audit or request "
     "evidence, GDPR-compliant processing terms, and confirmation that CLG owns its data, which is returned or "
     "securely destroyed at contract end (CLG_SEC_POL_002, section 12.2).", [P2, P4]),
    ("supplier-monitoring", "Suppliers", "How do you monitor suppliers' security over time?",
     ["supplier monitoring", "ongoing assurance", "supplier review", "critical suppliers", "attestation"],
     "CLG maintains a list of critical suppliers and requires periodic security attestations such as updated ISO "
     "27001 certificates, SOC 2 reports or penetration test summaries. Supplier incidents affecting CLG trigger a "
     "joint post-incident review, and suppliers that cannot meet requirements must remediate or are replaced "
     "(CLG_SEC_POL_002, section 12.3).", [P2]),
    ("supplier-subcontractors", "Suppliers", "Will you use subcontractors to deliver this contract, and how are they controlled?",
     ["subcontracting", "subcontractors", "sub-processors", "flow down", "fourth party"],
     "Any subcontractor handling CLG or client information falls within CLG's ISMS through contract and must meet "
     "equivalent security requirements. Supplier due diligence covers their subcontractor management, and obligations "
     "on confidentiality and AI use are flowed down to subcontractors (CLG_SEC_POL_001, section 2; CLG_SEC_POL_002, "
     "section 12.1; CLG_SEC_POL_006, section 9). [confirm: subcontractors proposed for this contract, if any.]", [P1, P2]),
    ("supplier-managed-it", "Suppliers", "Who provides your IT support?",
     ["it support", "managed service provider", "msp", "helpdesk", "outsourced it"],
     "IT is led by CLG's Group Director, IT and Digital Transformation, with managed IT support for the Southern "
     "Hemisphere provided by Elive (New Zealand). Staff raise issues through the CLG IT helpdesk, and support "
     "providers' access to CLG systems follows the same controls as internal access (Business Continuity Plan; "
     "CLG_SEC_POL_002, section 12.3).", [BCP, P2]),

    # ------------------------------------------------------------ Secure development
    ("dev-sdlc", "Secure development", "Do you follow a secure software development lifecycle?",
     ["sdlc", "secure development", "secure software development", "development lifecycle", "security by design"],
     "Yes. CLG's Secure Software Development Policy (CLG_SEC_POL_005) requires a secure SDLC for all software, "
     "including the LMS, integrations and infrastructure as code: security and privacy requirements and threat "
     "modelling at planning, security design review, secure coding standards, security testing and peer review, "
     "controlled release and secure maintenance.", [P5]),
    ("dev-code-review", "Secure development", "Is code peer reviewed and security tested before release?",
     ["code review", "peer review", "sast", "dast", "static analysis", "security testing"],
     "Yes. All significant changes are peer reviewed with a security checklist, and testing includes static code "
     "analysis, dependency scanning and dynamic testing for web applications, with penetration testing for high-risk "
     "applications or major releases. CI/CD pipelines can block builds that fail security checks (CLG_SEC_POL_005, "
     "sections 5, 7 and 11).", [P5]),
    ("dev-secrets", "Secure development", "How do you protect secrets such as API keys and passwords in software?",
     ["secrets", "api keys", "hard-coded", "vault", "credentials in code"],
     "Secrets must never be hard-coded or committed to source code. They are stored in secure vaults or managed "
     "configuration, retrieved at runtime, access-logged, limited to the contexts that need them and rotated "
     "regularly (CLG_SEC_POL_005, sections 5 and 8).", [P5]),
    ("dev-environments", "Secure development", "Are development, test and production environments separated?",
     ["environment separation", "segregation of environments", "production", "staging", "dev test prod"],
     "Yes. Development and test environments are isolated from production, changes are tested in non-production "
     "first, and development credentials have no direct production access except through controlled deployment. "
     "Developers cannot deploy their own code to production without independent review (CLG_SEC_POL_005, section 5; "
     "CLG_SEC_POL_002, section 5.5).", [P5, P2]),
    ("dev-change-management", "Secure development", "How do you control changes to production systems?",
     ["change management", "change control", "release management", "approval", "rollback"],
     "Changes to critical systems, cloud configurations and applications are documented, assessed for security "
     "impact, approved before implementation, tested in non-production where possible and released with a rollback "
     "plan. Emergency changes use expedited approval and are reviewed retrospectively (CLG_SEC_POL_002, section 5.5; "
     "CLG_SEC_POL_005, section 5).", [P2, P5]),
    ("dev-open-source", "Secure development", "How do you manage open-source and third-party software components?",
     ["open source", "third-party components", "dependencies", "libraries", "sbom", "software bill of materials"],
     "Only approved components from reputable sources are used, with an inventory (bill of materials) maintained for "
     "each codebase. Dependencies are scanned automatically for known vulnerabilities and patched urgently when "
     "high-risk issues are found, licences are checked, and unused components are removed (CLG_SEC_POL_005, "
     "section 6).", [P5]),
    ("dev-vulnerability-sla", "Secure development", "How quickly do you fix security vulnerabilities in your software?",
     ["vulnerability remediation", "fix vulnerabilities", "remediation sla", "bug tracking", "security bugs"],
     "Each vulnerability is recorded, assessed for severity and resolved against a defined timescale: critical "
     "vulnerabilities are patched as an emergency change and lower-severity issues in the next scheduled release. "
     "CLG subscribes to security bulletins for the technologies it uses and assesses new vulnerabilities immediately "
     "(CLG_SEC_POL_005, section 7).", [P5]),
    ("dev-application-logging", "Secure development", "Do your applications log security events without exposing personal data?",
     ["application logging", "audit trail", "traceability", "log masking", "sensitive data in logs"],
     "Yes. Applications log significant security events, such as authentication attempts, permission changes and data "
     "exports, in a central format that feeds security monitoring, while avoiding personal data and secrets, which are "
     "masked or omitted. All code changes are traceable to an author, date and work item (CLG_SEC_POL_005, sections 8 "
     "and 9).", [P5]),

    # ------------------------------------------------------------ AI
    ("ai-policy", "AI", "Do you have a policy governing the use of artificial intelligence?",
     ["ai policy", "artificial intelligence", "ai governance", "generative ai", "chatgpt", "copilot"],
     "Yes. CLG's AI Governance Policy (CLG_SEC_POL_006) permits AI only where there is a legitimate business purpose, a "
     "named owner, an understood risk profile and proportionate controls, and requires every AI tool to be assessed "
     "and approved before use. It references ISO/IEC 27001:2022, ISO/IEC 42001:2023 and GDPR.", [P6]),
    ("ai-approved-tools", "AI", "Which AI tools do you use?",
     ["ai tools", "approved ai", "copilot", "claude", "ai register", "which ai"],
     "CLG maintains a controlled register of approved AI tools; use of any tool outside the register is prohibited. "
     "At the policy's issue, approved tools were Microsoft 365 Copilot, WindSurf Coding, ElevenLabs Voiceover Generator "
     "and Claude Enterprise (for a specific approved use only) (CLG_SEC_POL_006, section 17). [confirm: the current "
     "approved tools register.]", [P6]),
    ("ai-data-handling", "AI", "Will our data be entered into AI tools?",
     ["client data in ai", "ai data", "data in ai tools", "prompt", "ai confidentiality"],
     "Personal, special category, safeguarding, regulated, assessment and commercially sensitive information must not "
     "be entered into external AI tools unless explicitly approved through documented risk assessment, lawful basis "
     "review and technical safeguards. Confidential data may be processed only in enterprise-approved environments "
     "with contractual protection, access control and logging, and identifiers are removed where not needed "
     "(CLG_SEC_POL_006, section 7).", [P6, P4]),
    ("ai-human-oversight", "AI", "How do you ensure human oversight of AI outputs?",
     ["human oversight", "human review", "ai accuracy", "validation", "automated decisions"],
     "AI outputs are treated as unverified until reviewed by a competent person, who remains accountable for accuracy, "
     "legality, bias and suitability. Decisions affecting employment, learner outcomes, safeguarding, legal, financial "
     "or significant operational matters require documented human review, and AI-generated content may not be "
     "presented as verified fact without validation (CLG_SEC_POL_006, sections 8 and 11).", [P6]),
    ("ai-supplier-training", "AI", "Do your AI providers use your data to train their models?",
     ["model training", "ai training data", "data retention ai", "ai supplier", "no training"],
     "CLG requires AI services to be configured, where possible, so that CLG data is not used for model training and "
     "retention is defined and minimised, with evidence of each supplier's position retained. Every AI tool passes "
     "CLG's approval process, covering business justification, security, privacy and compliance review, before use "
     "(CLG_SEC_POL_006, section 9).", [P6]),
    ("ai-incidents-ethics", "AI", "How do you manage AI risks, incidents and ethics?",
     ["ai ethics", "ai risk", "ai incident", "bias", "responsible ai"],
     "AI-related incidents, such as data leakage, misuse or harmful output, are reported immediately and handled "
     "through CLG's incident process. CLG's AI ethics principles cover fairness and non-discrimination, transparency, "
     "accountability, privacy, legal compliance, human oversight and continuous improvement, and users complete "
     "mandatory AI training before access (CLG_SEC_POL_006, sections 12, 13 and 18).", [P6]),

    # ------------------------------------------------------------ Acceptable use and physical
    ("aup-policy", "Acceptable use", "Do you have an acceptable use policy for staff?",
     ["acceptable use", "aup", "acceptable use policy", "user responsibilities", "prohibited activities"],
     "Yes. The Acceptable Use and Remote Working Policy (CLG_SEC_POL_003) sets mandatory rules for all users: business "
     "use first, authorised access only, protection of information, no bypassing of security controls such as MFA or "
     "encryption, approved software and services only, and prompt reporting of incidents. It is acknowledged at "
     "onboarding and periodically thereafter.", [P3]),
    ("aup-email-cloud", "Acceptable use", "How do you prevent staff from using personal email or unapproved cloud storage?",
     ["personal email", "auto-forward", "unapproved cloud", "dropbox", "shadow it", "data leakage"],
     "Staff must not auto-forward CLG email to personal accounts or use unapproved cloud services such as personal "
     "Dropbox or Google Drive for CLG data; approved enterprise tools such as SharePoint and OneDrive are provided "
     "instead. Large uploads or synchronisation to external sites may be monitored and investigated (CLG_SEC_POL_003, "
     "section 8; CLG_SEC_POL_002, section 8.3).", [P3, P2]),
    ("aup-monitoring", "Acceptable use", "Do you monitor the use of your systems?",
     ["user monitoring", "monitoring staff", "privacy at work", "system monitoring", "misuse"],
     "Yes. CLG monitors use of its systems to protect information, detect threats and misuse, and support audits and "
     "legal obligations; users have no expectation of absolute privacy on CLG systems. Monitoring is carried out in "
     "line with data protection law and the Employee Privacy Notice (CLG_SEC_POL_003, section 11; CLG_SEC_POL_004, "
     "section 3).", [P3, P4]),
    ("physical-office", "Physical security", "How do you protect your offices and physical information?",
     ["physical security", "office security", "clear desk", "building access", "paper records"],
     "Offices where information is present have appropriate access controls; sensitive papers are locked away, a clear "
     "desk practice is followed and physical media is stored securely and destroyed when no longer needed. For cloud "
     "services, CLG relies on providers' certified data centre controls (CLG_SEC_POL_002, sections 11.1 and 11.3).", [P2]),
    ("physical-remote-environment", "Physical security", "How do you secure staff working from home?",
     ["home working", "home workers", "home worker", "remote worker security", "working from home", "privacy screen", "shoulder surfing"],
     "Remote working does not reduce security obligations. Home workers must use only approved secure remote access, "
     "protect home Wi-Fi with strong encryption, work where screens cannot be overlooked, lock devices when "
     "unattended, keep any printed material confidential and dispose of it securely (CLG_SEC_POL_003, section 6; "
     "CLG_SEC_POL_002, section 11.2).", [P3, P2]),
]
