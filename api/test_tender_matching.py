"""Matching accuracy over 50 realistic tender questions against the full answer library.
Run: python test_tender_matching.py (fails if accuracy drops below 90%)."""
from tender_store import InMemoryTenderStore
from tender_api import match_question, confidence_label
A=InMemoryTenderStore().list_answers()
CASES = {
"Does your organisation hold a current Cyber Essentials Plus certificate?":{"cert-cyber-essentials-plus"},
"Please confirm you hold Cyber Essentials.":{"cert-cyber-essentials"},
"Are you ISO 27001 certified? If so provide your certificate.":{"cert-iso-27001"},
"Please provide your ICO registration number.":{"dp-ico-registration"},
"Is two-factor authentication enforced for remote access?":{"access-mfa","access-remote"},
"Describe how you comply with UK GDPR.":{"dp-uk-gdpr","dp-jurisdictions"},
"How do you ensure laptops are encrypted and managed?":{"device-management","device-encryption"},
"What is your process for reporting a data breach to the client?":{"incident-client-notification","incident-breach-notification","incident-response"},
"Where will our data be stored, and is it backed up?":{"hosting-backup"},
"How is access removed when staff leave the organisation?":{"access-joiners-leavers"},
"How do you vet subcontractors who will access our data?":{"supplier-subcontractors","supplier-security"},
"What anti-virus software do you use?":{"malware-patching"},
"How quickly are critical security patches applied?":{"malware-patching","dev-vulnerability-sla"},
"Who in your organisation is accountable for information security?":{"gov-security-responsibility"},
"Do you have a business continuity plan? When was it last tested?":{"business-continuity","bc-testing"},
"What are your RTO and RPO for our service?":{"bc-rto-rpo"},
"How often are backups taken and tested?":{"bc-backups"},
"Do you carry out regular penetration testing?":{"assurance-penetration-testing"},
"How often are user access rights reviewed?":{"access-reviews"},
"How do you manage privileged administrator accounts?":{"access-privileged"},
"Describe your password policy.":{"access-passwords"},
"Do you permit staff to use personal devices?":{"device-byod"},
"How do you control USB storage devices?":{"device-removable-media"},
"What happens if a staff laptop is stolen?":{"device-loss-theft"},
"Do you use firewalls to protect your network?":{"network-firewalls"},
"Is data encrypted at rest and in transit?":{"network-encryption-rest","network-encryption-transit"},
"How long do you retain personal data?":{"dp-retention"},
"How do you securely destroy data at end of contract?":{"dp-secure-disposal","supplier-contracts"},
"Will any personal data be transferred outside the UK?":{"dp-international-transfers"},
"Do you conduct Data Protection Impact Assessments?":{"dp-privacy-by-design"},
"Please provide details of your Data Protection Officer.":{"dp-dpo"},
"How do you handle subject access requests?":{"dp-subject-rights"},
"Do staff receive annual security awareness training?":{"staff-training"},
"Are employees subject to background checks?":{"people-background-checks"},
"Do you have an acceptable use policy?":{"aup-policy"},
"How do you use artificial intelligence, and will our data be used in AI tools?":{"ai-data-handling","ai-policy","ai-approved-tools"},
"Do you have an AI policy?":{"ai-policy"},
"Do you follow a secure development lifecycle?":{"dev-sdlc"},
"How are changes to production systems controlled?":{"dev-change-management"},
"How do you monitor your systems for security threats?":{"incident-monitoring"},
"How long are audit logs retained?":{"incident-logging"},
"What security clauses are included in your supplier contracts?":{"supplier-contracts"},
"How do you protect home workers?":{"physical-remote-environment","bc-remote-working"},
"Do you hold cyber insurance? Provide the level of cover.":{"bc-insurance"},
"Do you have a Statement of Applicability?":{"cert-statement-of-applicability"},
"Is your ISMS independently audited?":{"assurance-internal-audit"},
"How would you continue to deliver if your office was unavailable?":{"bc-remote-working"},
"Will you allow us to audit your security controls?":{"assurance-client-audit"},
"What is your annual turnover?":set(),
"Describe your approach to carbon reduction.":set(),
"Do you have a modern slavery policy?":set(),
"Do you have an equality and diversity policy?":set(),
"Do you have a health and safety policy?":set(),
"Which information security policies do you have in place?":{"gov-policy-framework","gov-information-security-policy"},
}
ok=0; bad=[]
for q,want in CASES.items():
    r=match_question(q,A); got=r[0][0].answer_id if r else None
    good=(got in want) if want else (got is None)
    ok+=good
    if not good: bad.append((q,got,[(a.answer_id,round(s,2)) for a,s in r[:3]],want))
print(f"{ok}/{len(CASES)} correct")
for b in bad: print("MISS:",b[0],"->",b[1],"| top3",b[2],"| want",b[3])
assert ok / len(CASES) >= 0.9, f"matching accuracy fell to {ok}/{len(CASES)}"
print("PASS: matching accuracy", f"{ok}/{len(CASES)}")

# Guard: a single generic word as a keyword makes unrelated questions match
# (e.g. "policies" matched "Do you have a health and safety policy?").
import tender_api as _t
GENERIC = {"policy", "data", "security", "inform", "information", "process", "staff", "system", "service", "plan", "use"}
offenders = [(a.answer_id, kw) for a in A for kw in a.keywords if len(_t.tokens(kw)) == 1 and _t.tokens(kw)[0] in GENERIC]
assert not offenders, f"generic single-word keywords: {offenders}"
print(f"PASS: no answer uses a generic single-word keyword ({len(A)} answers checked)")
