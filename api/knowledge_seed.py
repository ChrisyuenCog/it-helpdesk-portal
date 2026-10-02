"""
Knowledge Base v2 — 68 starter articles
=======================================
Written from CLG_SEC_POL_001–006, the Business Continuity Plan, and standard
Microsoft 365 / Entra / Intune behaviour. Anything specific to how CLG has set
a service up, or not stated in a source document, is a [confirm: …]
placeholder, and an article cannot be published until those are replaced.
All seed articles start as Draft for IT to review and approve.

Body format (rendered safely by web/knowledge/knowledge.js): "## " headings,
"1. " numbered steps, "- " bullets, "**bold**", "[text](https://…)" links,
"> " callouts. Everything else is a paragraph.

Generate the SQL: python knowledge_seed.py > ../db/schema_and_seed_knowledge.sql
"""
import json
import re

P1, P2, P3, P4, P5, P6 = (f"CLG_SEC_POL_00{i}" for i in range(1, 7))
BCP = "CLG Business Continuity Plan"
HELPDESK = "the IT helpdesk [confirm: helpdesk email address and phone number]"


def A(aid, category, a_type, title, summary, keywords, evidence, body, audience="All staff"):
    return {"articleId": aid, "category": category, "articleType": a_type, "title": title, "summary": summary,
            "keywords": keywords, "evidence": evidence, "body": body.strip(), "audience": audience}


SEED_ARTICLES = [
    # ------------------------------------------------------------------ Accounts and sign-in
    A("reset-your-password", "Accounts and sign-in", "How-to", "Reset your password",
      "Reset a forgotten or expired password yourself in a few minutes, without contacting IT.",
      ["reset password", "forgot password", "password expired", "sspr", "change password", "locked out"], [P2],
      """
You can reset your CLG password yourself using Microsoft's self-service password reset, as long as you have set up your security info (see **Set up multi-factor authentication**).

## Reset a forgotten password
1. Go to [aka.ms/sspr](https://aka.ms/sspr), or choose **Can't access your account?** on the Microsoft sign-in page.
2. Enter your CLG email address and complete the picture check.
3. Verify your identity using one of your registered methods, such as your authenticator app or phone.
4. Choose a new password and sign in again on all your devices.

## Choosing a good password
- Use a long passphrase of three or four unrelated words rather than a short complex password.
- Never reuse a password you use for personal accounts, and never share it with anyone, including IT (CLG_SEC_POL_002, section 4.1).
- If you think someone knows your password, change it straight away and report it.

You can also start a reset from **Service Catalogue → Password / SSPR** in this portal.

> If none of your verification methods work, contact the IT helpdesk to have your identity checked and your password reset.
"""),
    A("set-up-mfa", "Accounts and sign-in", "How-to", "Set up multi-factor authentication (MFA)",
      "MFA is required on all CLG cloud services. Set up your verification methods so you can sign in and reset your password.",
      ["mfa", "multi-factor", "2fa", "two-factor", "authenticator", "security info", "verification"], [P2, BCP],
      """
Multi-factor authentication (MFA) is enforced across all CLG cloud services, including Microsoft 365, Zoho and Xero. After your password, you confirm it's you with a second method, usually an app on your phone.

## Set up or update your methods
1. Go to [aka.ms/mysecurityinfo](https://aka.ms/mysecurityinfo) and sign in with your CLG account.
2. Choose **Add sign-in method**.
3. Add an authenticator app [confirm: the app CLG uses, for example Microsoft Authenticator] and follow the on-screen steps to scan the QR code.
4. Add a second method as a backup, such as a phone number, so you can still sign in if you lose your phone.

## Good practice
- Only approve a sign-in request you started yourself. If you get a request you didn't expect, deny it and report it to IT: someone may have your password.
- Keep at least two methods registered.

You can check which methods you have registered from **Service Catalogue → Password / SSPR** in this portal.
"""),
    A("new-phone-mfa", "Accounts and sign-in", "How-to", "Got a new phone? Move your MFA",
      "Move your authenticator to a new phone before you wipe or hand in the old one, so you are not locked out.",
      ["new phone", "replace phone", "lost phone mfa", "authenticator new phone", "move mfa"], [P2],
      """
Your authenticator app is tied to your phone. Move it before you reset or return your old phone.

## If you still have your old phone
1. On a computer, go to [aka.ms/mysecurityinfo](https://aka.ms/mysecurityinfo) and sign in, approving the request on your **old** phone.
2. Choose **Add sign-in method → Authenticator app** and set it up on your **new** phone.
3. Test that sign-in works with the new phone.
4. Delete the old phone from the list of methods.

## If your old phone is lost or broken
Sign in using your backup method, such as a text message, and add the new phone. If you have no other method, contact the IT helpdesk, who will verify your identity and reset your MFA.

> If the phone was lost or stolen, also follow **What to do if your laptop or phone is lost or stolen**.
"""),
    A("locked-out-account", "Accounts and sign-in", "Troubleshooting", "Can't sign in or account locked",
      "Common reasons you can't sign in to Microsoft 365, and how to fix each one.",
      ["cannot sign in", "can't log in", "account locked", "login problem", "sign in error", "locked out"], [P2],
      """
## Symptom
You can't sign in to Outlook, Teams or another CLG service, or you're told your account is locked.

## Check these in order
1. **Caps Lock and keyboard language.** A changed keyboard layout can alter what you type.
2. **Too many wrong attempts.** CLG locks accounts after repeated failed sign-ins to block password guessing (CLG_SEC_POL_002, section 4.1). Wait 15 minutes [confirm: lockout duration] and try again, or reset your password at [aka.ms/sspr](https://aka.ms/sspr).
3. **Forgotten password.** Follow **Reset your password**.
4. **MFA not arriving.** Check your phone has signal or Wi-Fi, open the authenticator app directly, and make sure its time is set automatically.
5. **Is it everyone?** Check the known issues on the Knowledge Base home page. A Microsoft 365 outage affects everyone at once.

## Still stuck?
Contact the IT helpdesk with the exact error message and a screenshot if you can.
"""),
    A("suspicious-sign-in", "Accounts and sign-in", "How-to", "You got an MFA request you didn't start",
      "An unexpected sign-in prompt means someone may have your password. Deny it and act straight away.",
      ["unexpected mfa", "mfa prompt", "suspicious sign in", "mfa fatigue", "approve request", "compromised account"], [P2, P3],
      """
If your authenticator asks you to approve a sign-in you didn't start, **someone else probably has your password.**

## Do this now
1. **Deny** the request. Never approve it to make the prompts stop.
2. Change your password immediately at [aka.ms/sspr](https://aka.ms/sspr).
3. Report it to the IT helpdesk as a security incident, including the time of the prompts.

Reporting a suspected compromise is mandatory, and you won't be penalised for raising it honestly (CLG_SEC_POL_003, sections 5.2 and 10).
"""),

    # ------------------------------------------------------------------ Devices
    A("lost-or-stolen-device", "Devices", "How-to", "What to do if your laptop or phone is lost or stolen",
      "Report it immediately so IT can block access and wipe the device. Your files are safe in the cloud.",
      ["lost laptop", "stolen laptop", "lost phone", "stolen phone", "theft", "remote wipe", "lost device"], [P2, BCP],
      """
Report a lost or stolen CLG device, or a personal device used for work, **immediately**, even if you think it may turn up (CLG_SEC_POL_002, section 7.3).

## Do this straight away
1. Contact the IT helpdesk and say whether the device is a laptop, phone or tablet, and when you last had it.
2. If it was stolen, report it to the police and get a crime reference number.
3. Change your CLG password from another device.

## What IT will do
- Switch off your access to CLG systems, reset your credentials and remotely wipe the device where possible.
- Check whether any data could have been exposed, and record it in the data breach log if needed.
- Arrange replacement hardware. Because your work is stored in Microsoft 365 and other cloud services, you can carry on as soon as you have a new device (Business Continuity Plan, Critical Function 1).

> Speed matters: the sooner IT knows, the sooner the device can be wiped.
"""),
    A("request-new-hardware", "Devices", "How-to", "Request a new laptop or other hardware",
      "Use the Hardware Request form in the Service Catalogue. Your manager approves it and IT handles the rest.",
      ["new laptop", "request hardware", "new equipment", "monitor", "hardware request", "replacement laptop"], [P2],
      """
## How to request hardware
1. In this portal, open **Service Catalogue → Hardware Request**.
2. Choose the item you need and explain the business reason.
3. Submit. Your request goes to your manager for approval, then to IT and procurement.
4. Track progress under **My Requests**.

## When it arrives
- IT builds every device to CLG's secure standard before you receive it: encryption, security software and device management are set up for you (CLG_SEC_POL_002, section 7.1).
- The device is recorded in the IT asset register against your name and shows under **My Devices**.

> Don't buy equipment yourself for CLG work: unmanaged devices can't be secured or supported.
"""),
    A("personal-phone-work-email", "Devices", "How-to", "Use your personal phone for work email (BYOD)",
      "You can use your own phone for CLG email and apps if it meets the security rules and is enrolled in device management.",
      ["byod", "personal phone", "own phone", "work email on phone", "mobile email", "company portal"], [P2, P3],
      """
CLG allows personal devices for work only when they meet minimum security requirements (CLG_SEC_POL_003, section 7).

## Your phone must
- Be encrypted and protected by a PIN, fingerprint or face unlock.
- Run a supported, up-to-date operating system. Rooted or jailbroken phones are blocked.
- Be enrolled in CLG's device management, and use the approved apps (such as Outlook and Teams) for CLG data.

## Set it up
[confirm: enrolment steps, for example install the Intune Company Portal app, sign in with your CLG account and follow the prompts.]

## What CLG can and can't see
CLG manages only the work apps and data on your phone. If your phone is lost, or when you leave CLG, IT can remove CLG data from it (CLG_SEC_POL_002, section 7.2). [confirm: whether CLG uses app-only management or full device enrolment, and what IT can see.]
"""),
    A("install-software", "Devices", "How-to", "Why you can't install software, and how to request it",
      "CLG laptops block unapproved software to keep devices safe. Ask IT for anything you need for your work.",
      ["install software", "admin rights", "administrator", "new app", "software request", "blocked install"], [P2, P3],
      """
CLG laptops run with standard user accounts, so you can't install software yourself. This protects you and CLG from malware and unlicensed software (CLG_SEC_POL_002, section 7.1; CLG_SEC_POL_003, section 9).

## How to get software you need
1. Check whether it's already available: many tools are part of Microsoft 365 or Zoho.
2. If not, request it [confirm: how to request software until the Software Request form is live, for example by contacting the IT helpdesk].
3. Explain what you need it for. IT checks it for security and licensing before approving it.

> Don't use personal accounts or free online tools to get round this, especially for CLG or client data. Only approved services may hold CLG data.
"""),
    A("screen-lock", "Devices", "Policy summary", "Lock your screen when you step away",
      "Devices must lock automatically, and you should lock your screen every time you leave your desk.",
      ["lock screen", "screen lock", "windows key l", "unattended", "clear screen"], [P2, P3],
      """
CLG policy requires devices to lock automatically after a short period of inactivity (5 to 15 minutes), and you must lock your screen whenever you leave your device, even briefly (CLG_SEC_POL_002, section 7.3).

## Quick ways to lock
- **Windows:** press **Windows key + L**.
- **Mac:** press **Control + Command + Q**.
- **Phone:** press the side button.

This applies at home as well as in the office: keep a clear desk and a clear screen wherever you work (CLG_SEC_POL_003, section 6).
"""),
    A("usb-drives", "Devices", "Policy summary", "Using USB drives and removable media",
      "Don't store CLG data on USB sticks. Use OneDrive or SharePoint instead, or ask IT for an encrypted drive.",
      ["usb", "memory stick", "usb stick", "external drive", "removable media", "flash drive"], [P2],
      """
USB drives are easily lost, so CLG restricts their use (CLG_SEC_POL_002, section 8.3).

## The rules
- **Don't** store CLG or client data on an ordinary USB stick or external drive.
- Share files through **OneDrive or SharePoint** instead: it's quicker and safer.
- If you genuinely need removable media, for example to give data to a client, ask IT. It must be authorised and the drive must be hardware-encrypted.
"""),

    # ------------------------------------------------------------------ Security
    A("spot-and-report-phishing", "Security", "How-to", "Spot and report a phishing email",
      "How to recognise a suspicious email and what to do with it. Reporting quickly protects everyone.",
      ["phishing", "suspicious email", "scam email", "fake email", "report phishing", "spam", "clicked link"], [P2, P3],
      """
Phishing emails try to trick you into clicking a link, opening an attachment or giving away your password.

## Warning signs
- Urgency or threats: "your account will be closed today".
- A sender address that doesn't match the organisation, or a familiar name with an odd address.
- Requests to sign in, pay an invoice, change bank details or buy gift cards.
- Links where the address shown when you hover doesn't match the text.

## If you receive one
1. Don't click links, open attachments or reply.
2. Report it [confirm: how to report, for example the Report button in Outlook, or forward to the IT helpdesk as an attachment].
3. Delete it.

## If you already clicked or entered your password
Change your password at [aka.ms/sspr](https://aka.ms/sspr) and report it to the IT helpdesk **immediately**. You won't be penalised for an honest mistake, and quick reporting limits the damage (CLG_SEC_POL_003, section 10).
"""),
    A("report-security-incident", "Security", "How-to", "Report a security incident",
      "Anything that might put CLG systems or data at risk must be reported straight away. Here's what counts and how to report it.",
      ["security incident", "report incident", "data breach", "malware", "virus", "hacked", "something wrong"], [P2, P3, P4],
      """
Report any suspected security incident **immediately** (CLG_SEC_POL_002, section 10.1).

## What counts as an incident
- A lost or stolen device.
- A suspicious email you clicked, or a password you may have given away.
- Signs of malware: pop-ups, security alerts, files you can't open, a very slow device.
- Personal or confidential data sent to the wrong person or shared too widely.
- Anyone accessing systems or data they shouldn't.

## How to report
Contact the IT helpdesk and say what happened, when, and what systems or data may be involved. If you think your device is infected, stop using it for work until IT says it's safe.

## Personal data breaches
CLG may have to tell the ICO within 72 hours, so every hour counts (CLG_SEC_POL_004, section 11). Reporting is never penalised; concealing a breach is a serious disciplinary matter.
"""),
    A("send-files-securely", "Security", "How-to", "Send sensitive files securely",
      "How to share personal or confidential information with colleagues and external people safely.",
      ["send file securely", "share sensitive", "encrypt email", "secure transfer", "send personal data", "confidential file"], [P2, P4],
      """
Personal data must never be sent over unsecured channels such as plain email to external recipients (CLG_SEC_POL_004, section 6).

## Inside CLG
Share a link to the file in OneDrive, SharePoint or Teams rather than attaching a copy. Only people with access can open it.

## To someone outside CLG
1. Check you're allowed to share it, and share only what's needed.
2. Use a OneDrive or SharePoint sharing link limited to **specific people**, and set an expiry date if available.
3. If you must email a file, encrypt it and send the password separately, for example by text message (CLG_SEC_POL_002, section 8.3).
4. Double-check the recipient's address before you press Send.

> Sent something to the wrong person? Report it straight away as a security incident.
"""),
    A("malware-protection", "Security", "How-to", "Security alerts and malware protection on your laptop",
      "Your laptop runs Sophos protection. Never turn it off, and act quickly if it warns you of a threat.",
      ["sophos", "antivirus", "malware", "virus", "security alert", "ransomware", "infected"], [P2, BCP],
      """
Sophos endpoint protection runs on CLG devices, with anti-malware, anti-exploit and anti-ransomware defences (Business Continuity Plan).

## Do
- Leave it switched on and let it update itself. Disabling or interfering with it is not allowed (CLG_SEC_POL_002, section 5.4).
- Restart when updates ask you to.

## If you see a security alert or suspect malware
1. Stop using the device for CLG work.
2. Disconnect it from Wi-Fi if the alert mentions ransomware or files being encrypted.
3. Contact the IT helpdesk. IT will inspect the device and return it once it's confirmed safe.
"""),
    A("sensitive-data-basics", "Security", "Policy summary", "Handling personal and confidential data: the essentials",
      "The key data protection rules every member of staff must follow, in plain English.",
      ["personal data", "gdpr", "confidential", "data protection", "privacy", "data handling"], [P4],
      """
At CLG, personal data is always treated as **Confidential**, and special category data such as health information is **Highly Confidential** (CLG_SEC_POL_004, section 6).

## The essentials
- **Collect only what you need,** and use it only for the purpose it was collected for.
- **Store it only in approved CLG systems,** never in personal email, personal cloud storage or USB sticks.
- **Share it only with people who need it,** using secure methods (see **Send sensitive files securely**).
- **Don't keep it longer than necessary.** Delete it when it's no longer needed.
- **Never enter it into unapproved AI tools** (see **What you must never put into AI tools**).
- **Report mistakes immediately,** such as an email to the wrong person.

## Requests from individuals
If anyone asks for a copy of their data, or asks you to correct or delete it, forward the request straight away to the People team or the ISMS Manager. CLG must normally respond within one month (CLG_SEC_POL_004, section 7).
"""),
    A("acceptable-use-summary", "Security", "Policy summary", "Acceptable use of CLG systems: the essentials",
      "A one-page summary of what you may and may not do with CLG systems and information.",
      ["acceptable use", "aup", "rules", "allowed", "prohibited", "personal use"], [P3],
      """
This summarises the Acceptable Use and Remote Working Policy (CLG_SEC_POL_003), which every user acknowledges at onboarding.

## You may
- Use CLG systems for your work, and for limited, reasonable personal use that doesn't interfere with your job or create risk.

## You must
- Keep your password private and use MFA.
- Use only approved software, apps and cloud services for CLG work.
- Lock your screen and protect your devices, at home as well as in the office.
- Report lost devices, suspicious emails and possible breaches straight away.

## You must not
- Bypass or disable security controls such as MFA, encryption or Sophos.
- Access systems or data you aren't authorised to use.
- Install unapproved software or hardware.
- Auto-forward CLG email to a personal account, or store CLG data in personal cloud storage.
- Share confidential information without authorisation.

CLG monitors use of its systems to protect information, and breaches of the policy may lead to disciplinary action (section 11).
"""),

    # ------------------------------------------------------------------ Working remotely
    A("secure-home-wifi", "Working remotely", "How-to", "Secure your home Wi-Fi",
      "Quick checks to make sure your home network is safe for CLG work.",
      ["home wifi", "wi-fi", "router", "wpa2", "wpa3", "home network"], [P2, P3],
      """
CLG policy requires home networks used for work to be protected with strong passwords and encryption (CLG_SEC_POL_003, section 6).

## Check your router
1. Log in to your router's settings (the address is usually on a sticker on the router).
2. Make sure Wi-Fi security is set to **WPA2** or **WPA3**, not "open" or "WEP".
3. Change the Wi-Fi password if it's still the one printed on the router, and use a long passphrase.
4. Change the router's admin password from its default.
5. Install router updates if your provider offers them.

## Good practice
If your router supports it, put work devices on a separate network from smart TVs and other household gadgets (CLG_SEC_POL_002, section 11.2).
"""),
    A("public-wifi", "Working remotely", "Policy summary", "Working from cafés, hotels and public Wi-Fi",
      "Public Wi-Fi can be watched by others. Here's how to work safely away from home.",
      ["public wifi", "cafe", "hotel wifi", "travel", "hotspot", "airport"], [P2, P3],
      """
## The rules
- Don't use unsecured public Wi-Fi for sensitive CLG resources unless you're connected through a company VPN (CLG_SEC_POL_002, section 6.1). [confirm: whether CLG provides a VPN.] Using your phone's personal hotspot is a safer alternative.
- Sit where others can't see your screen, and don't discuss confidential matters where you can be overheard.
- Never leave your laptop unattended. Keep it in hand luggage when travelling (CLG_SEC_POL_002, section 7.3).
- Lock your screen whenever you step away, even for a moment.
"""),
    A("internet-down", "Working remotely", "Troubleshooting", "Your internet connection is down",
      "Get back online quickly using your phone, and know when to tell IT.",
      ["internet down", "no internet", "internet not working", "broadband down", "connection lost", "tethering", "hotspot", "wifi not working"], [BCP],
      """
## Symptom
You can't reach email, Teams or any website from home.

## Get working again
1. Restart your router: switch it off, wait 30 seconds, switch it on, and wait a few minutes.
2. If that doesn't help, turn on your phone's **personal hotspot** and connect your laptop to it. The BCP expects staff to tether to their phone during an outage.
3. Check your provider's service status page or app for a known fault.

## Your back-up connection
Remote staff are required to have a primary and a back-up internet connection (Business Continuity Plan, Internet Failure). Make sure yours is ready before you need it.

## Tell IT if
- Several colleagues are affected, which may point to a wider problem.
- You can browse the web but can't reach CLG services, as the issue may be on CLG's side.
"""),

    # ------------------------------------------------------------------ Microsoft 365 and Zoho
    A("where-to-save-files", "Microsoft 365 and Zoho", "How-to", "Where to save your files: OneDrive, SharePoint or Teams",
      "Save work files in CLG's approved cloud storage, so they're backed up, shareable and protected.",
      ["where to save", "onedrive", "sharepoint", "teams files", "save files", "file storage", "documents"], [P2, P3],
      """
Only CLG-approved cloud services may be used to store CLG data. Personal Dropbox, Google Drive and USB sticks are not allowed (CLG_SEC_POL_002, section 8.3).

## Which one?
- **OneDrive:** your own working files and drafts. Only you can see them unless you share them.
- **Teams:** files for a team or project you work on together. They're stored in SharePoint behind the scenes.
- **SharePoint:** department documents, policies and anything that needs to outlive one person, such as templates and records.

## Why it matters
Files in Microsoft 365 are stored in Microsoft's resilient data centres, replicated to a second location, and recoverable if deleted (Business Continuity Plan). Files saved only on your laptop's hard drive are not backed up.
"""),
    A("share-with-external", "Microsoft 365 and Zoho", "How-to", "Share a document with someone outside CLG",
      "Give external people access to just the file they need, for only as long as they need it.",
      ["share externally", "external sharing", "share link", "guest access", "share document", "client access"], [P3, P4],
      """
Don't send sensitive information outside CLG without approval and protection (CLG_SEC_POL_003, section 8).

## Share a file safely
1. In OneDrive or SharePoint, select the file and choose **Share**.
2. Choose **Specific people**, and enter only the recipients who need it.
3. Untick **Allow editing** if they only need to read it.
4. Set an expiry date if the option is available.
5. Send.

## Stop sharing
Choose **Manage access** on the file and remove the person or link when the work is finished.

> Share a single file or folder rather than a whole site, and never share personal data unless there is a lawful reason and it has been approved.
"""),
    A("recover-deleted-email-file", "Microsoft 365 and Zoho", "How-to", "Recover a deleted email or file",
      "Deleted something by mistake? You can usually get it back yourself within the retention period.",
      ["recover deleted", "deleted email", "deleted file", "restore", "recycle bin", "undelete"], [BCP],
      """
## Deleted email (Outlook)
1. Look in your **Deleted Items** folder and move the email back to your Inbox.
2. If it's not there, right-click **Deleted Items** and choose **Recover deleted items**. Items stay recoverable for 14 days after leaving Deleted Items, extendable by IT to 30 days (Business Continuity Plan, Exchange Online).
3. Still missing? Contact the IT helpdesk. Administrators can recover purged items within the same period.

## Deleted file (OneDrive, SharePoint or Teams)
1. Open OneDrive or the SharePoint site in your browser and choose **Recycle bin**.
2. Select the file and choose **Restore**.

By default, Microsoft keeps deleted OneDrive and SharePoint files for up to 93 days. [confirm: any different retention CLG has configured.]

## Earlier version of a file
Right-click the file and choose **Version history** to restore an earlier version.
"""),
    A("no-email-forwarding", "Microsoft 365 and Zoho", "Policy summary", "Why you can't forward CLG email to a personal account",
      "Auto-forwarding to personal email is not allowed. Use the Outlook app on your phone instead.",
      ["forward email", "auto forward", "personal email", "gmail", "forwarding rule", "email on phone"], [P3],
      """
CLG policy prohibits auto-forwarding CLG email to personal accounts (CLG_SEC_POL_003, section 8). Forwarded mail leaves CLG's protection and may contain personal or client data.

## Instead
- Install the **Outlook** and **Teams** apps on your phone to read work email on the go (see **Use your personal phone for work email (BYOD)**).
- Use the Outlook web app from any browser.

If a forwarding rule is blocked or removed, this is why. Talk to the IT helpdesk if you have a genuine business need.
"""),
    A("zoho-people-details", "Microsoft 365 and Zoho", "How-to", "Keep your contact and emergency details up to date in Zoho People",
      "CLG uses Zoho People for staff records. Your details are used to contact you in an emergency.",
      ["zoho people", "emergency contact", "next of kin", "contact details", "hr system", "personal details"], [BCP, P4],
      """
CLG uses **Zoho People**, a cloud HR system, for staff information. During a major incident, the business continuity team uses it to reach staff, including home contact and next-of-kin details (Business Continuity Plan, Key Contact Information).

## Update your details
[confirm: steps, for example sign in to Zoho People, open your profile, edit your contact and emergency contact fields, and save.]

## Why it matters
If CLG's email is unavailable during an incident, staff are contacted by text message or WhatsApp, and you'll be asked to confirm you received the message (Business Continuity Plan, Command and Control). Out-of-date details mean you might not be reached.
"""),

    # ------------------------------------------------------------------ AI
    A("approved-ai-tools", "AI", "Policy summary", "Which AI tools you can use at CLG",
      "Only AI tools on CLG's approved register may be used for work. Here's the current list and how to request others.",
      ["ai tools", "copilot", "chatgpt", "claude", "approved ai", "generative ai", "artificial intelligence"], [P6],
      """
You may use AI only through tools on CLG's approved register (CLG_SEC_POL_006, section 17). Using any other tool for CLG work, including personal or free accounts, is prohibited.

## Approved tools
At the policy's issue, the approved tools were:
- **Microsoft 365 Copilot**
- **WindSurf Coding**
- **ElevenLabs Voiceover Generator**
- **Claude Enterprise** (for a specific approved use only)

[confirm: the current approved tools register.]

## Requesting a new AI tool
Complete the AI Tool Request form with the business reason and a risk assessment. IT and Compliance review it, and you'll be told the decision (section 9). Don't start using the tool until it's approved.
"""),
    A("ai-what-not-to-share", "AI", "Policy summary", "What you must never put into AI tools",
      "Some information must never be entered into AI tools, or only into approved enterprise tools.",
      ["ai data", "paste into ai", "ai confidential", "prompt", "ai personal data", "chatgpt data"], [P6, P4],
      """
## Never enter into external or unapproved AI tools
- Personal data about anyone, including learners, clients and colleagues.
- Special category data, safeguarding information or children's data.
- Assessment content, commercially sensitive information or trade secrets.
- Passwords, keys or other credentials.

These may be processed only where explicitly approved through a documented risk assessment (CLG_SEC_POL_006, section 7).

## Confidential business information
Use only enterprise-approved tools, such as Microsoft 365 Copilot, which have contractual protection, access control and logging.

## Always
- Share the minimum needed, and remove names and other identifiers where you can.
- Report it immediately if you think you've entered something you shouldn't have.
"""),
    A("ai-check-output", "AI", "Policy summary", "Check AI output before you use it",
      "AI can be confidently wrong. You remain responsible for anything you use or send.",
      ["ai accuracy", "check ai", "ai mistakes", "hallucination", "verify ai", "human review"], [P6],
      """
AI output is treated as **unverified** until a competent person has checked it (CLG_SEC_POL_006, section 11). You remain accountable for what you use.

## Before you rely on AI output
- Check facts, figures, names and references against a trusted source.
- Look for bias, and for anything misleading or inappropriate.
- Make sure it's complete and suitable for the audience.
- Don't present AI-generated content as verified fact unless you've verified it.

## Decisions about people
Anything affecting employment, learner outcomes, safeguarding, legal, financial or significant operational decisions needs documented human review (section 11).
"""),

    # ------------------------------------------------------------------ Joining and leaving
    A("new-starter-first-day", "Joining and leaving", "How-to", "New starter: your first day IT checklist",
      "Everything you need to set up on your first day so you can work securely.",
      ["new starter", "first day", "onboarding", "new employee", "induction", "getting started"], [P1, P3],
      """
Welcome to CLG. Your account and laptop are set up before you start, after your manager or the People team requests them (CLG_SEC_POL_002, section 4.2).

## On your first day
1. Sign in to your laptop with the details IT gives you, and change your temporary password.
2. Set up multi-factor authentication (see **Set up multi-factor authentication**).
3. Install Outlook and Teams on your phone if you'll use it for work (see **Use your personal phone for work email (BYOD)**).
4. Read and acknowledge CLG's security policies, including the Acceptable Use and Remote Working Policy (CLG_SEC_POL_001, section 9).
5. Complete your security and data protection induction training.
6. Check your details in Zoho People.

## Bookmark these
- This portal, for requests, devices, policies and help.
- [confirm: the IT helpdesk contact details.]
"""),
    A("leaving-clg", "Joining and leaving", "How-to", "Leaving CLG: what happens to your IT",
      "What you need to do before your last day, and what IT does when you leave.",
      ["leaving clg", "last day", "offboarding", "leaver", "return laptop", "resign", "resignation"], [P2, P4],
      """
## Before your last day
1. Move any work files from your laptop into the right SharePoint or Teams location so colleagues can find them.
2. Hand over anything you own in shared systems, and tell your manager about any shared accounts or credentials you know.
3. Return your laptop and any other CLG equipment [confirm: how to return equipment].
4. If you used a personal phone for work, CLG data on it will be removed.

## What IT does
- Your access to all CLG systems is switched off promptly, normally on your last working day (CLG_SEC_POL_002, section 4.2).
- Any shared passwords you knew are changed.
- Your records are kept only as long as required, then securely deleted (CLG_SEC_POL_004, section 9).
"""),

    # ------------------------------------------------------------------ Known issue (IT only)
    A("known-issue-ce-plus-recertification", "Known issues", "Known issue", "Cyber Essentials Plus recertification overdue: don't claim CE+ in bids",
      "CE+ recertification was due on 23 September 2026. Until renewed, tender answers must not claim current CE+ certification.",
      ["cyber essentials plus", "ce+", "recertification", "tender", "bid", "certificate expired"], ["Cyber Essentials Plus", "Cyber Essentials"],
      """
## Status
Cyber Essentials Plus recertification was due on **23 September 2026** and has not yet been renewed. The standard Cyber Essentials certificate remains valid until 9 September 2027.

## Impact
- The Tender Pack blocks any answer that relies on Cyber Essentials Plus until the certificate is renewed.
- Bid teams may state current **Cyber Essentials** certification, but not Cyber Essentials Plus.

## Workaround
Where a tender asks about CE+, say that CLG holds Cyber Essentials and that CE+ recertification is in progress [confirm: expected recertification date].

## Resolution
Update the certificate in Policy & Compliance once the new CE+ certificate is issued, then retire this article.
""", audience="IT only"),
]


# ---------------------------------------------------------------------------
# Second set (37 articles), same writing rules as above.
# ---------------------------------------------------------------------------
SEED_ARTICLES += [
    # ------------------------------------------------------------------ Accounts and access
    A("request-system-access", "Accounts and sign-in", "How-to", "Request access to a system, site or shared folder",
      "Access is granted on a need-to-know basis and approved by your manager or the system owner.",
      ["request access", "need access", "permission", "shared folder access", "sharepoint access", "access denied"], [P2],
      """
CLG grants access on the principle of **least privilege**: you get the access your role needs, and nothing more (CLG_SEC_POL_002, section 3).

## How to request access
1. Ask the owner of the site, folder or system, or your manager, to approve your access.
2. For SharePoint and Teams, the site owner can usually add you directly using **Share** or **Add members**.
3. For business systems, contact the IT helpdesk with the system name, the access you need and who approved it.

## Why it's done this way
Access must be authorised before it's granted, and IT records changes (CLG_SEC_POL_002, section 4.2). Please don't ask a colleague to share their login: shared accounts are not allowed.
"""),
    A("changing-role-access", "Accounts and sign-in", "Policy summary", "Changing role? What happens to your access",
      "When your job changes, your access is reviewed: you gain what the new role needs and lose what it doesn't.",
      ["change role", "promotion", "new team", "transfer", "movers", "access review"], [P2],
      """
When you move role or team, your manager must ask for access you no longer need to be removed, and can request access for the new role (CLG_SEC_POL_002, section 4.2).

## What to expect
- Access to your old team's sites, systems and shared mailboxes may be removed.
- New access is set up for your new role once it's approved.
- If you still need something from your old role for a handover, agree a time limit with your manager.

This keeps access matched to each person's current job, which is a key control for CLG's security certifications.
"""),
    A("shared-accounts", "Accounts and sign-in", "Policy summary", "Why you can't share logins",
      "Every person has their own account. Sharing passwords or accounts is not allowed.",
      ["shared account", "share password", "share login", "generic account", "team login"], [P2, P3],
      """
Every user must have a **unique user ID**, and shared accounts are prohibited except in rare cases approved by IT Security (CLG_SEC_POL_002, section 4.1).

## The rules
- Never share your password or MFA approval with anyone, including colleagues, managers or IT.
- Don't sign in for someone else, or let them use your logged-in session.
- If a team needs a shared mailbox or calendar, IT can set one up that each person opens with their own account.

## Why
Your account is how CLG knows who did what. Shared logins break that trail and are a common route for attackers.
"""),
    A("manager-access-reviews", "Accounts and sign-in", "How-to", "Access reviews: what managers and system owners need to do",
      "Owners check who has access at least once a year, and remove anything no longer needed.",
      ["access review", "recertification", "review access", "system owner", "manager review", "dormant accounts"], [P2],
      """
System and data owners must review who has access at least **annually**, and more often (for example quarterly) for sensitive systems and administrator access (CLG_SEC_POL_002, section 4.3).

## When IT asks you to review
1. Open the list IT sends you, showing each person, their access and when they last signed in.
2. Confirm each person still needs that access for their current role.
3. Mark anyone who has left, changed role, or hasn't used the access for 90 days for removal.
4. Return the list to IT by the date given.

> Third-party and supplier accounts should be time-limited and removed as soon as the work is finished.
""", audience="IT only"),

    # ------------------------------------------------------------------ Devices
    A("bitlocker-encryption", "Devices", "Policy summary", "Why your laptop is encrypted, and what a recovery key is",
      "Every CLG laptop is fully encrypted. If you're asked for a recovery key, contact IT.",
      ["bitlocker", "filevault", "encryption", "recovery key", "encrypted laptop"], [P2],
      """
All CLG laptops use full disk encryption: **BitLocker** on Windows and **FileVault** on Mac (CLG_SEC_POL_002, section 7.1). If a laptop is lost or stolen, its data can't be read without your sign-in.

## If your laptop asks for a recovery key
This can happen after a hardware change, a firmware update or several failed sign-ins.
1. Don't keep guessing.
2. Note the **Recovery key ID** shown on screen.
3. Contact the IT helpdesk, who can find the key for your device. [confirm: whether staff can retrieve their own key, for example from aka.ms/aadrecoverykey.]

> Never write recovery keys down or store them with the laptop.
"""),
    A("updates-and-restarts", "Devices", "How-to", "Install updates and restart your laptop",
      "Updates fix security holes. Restart promptly when your laptop asks, ideally the same day.",
      ["updates", "windows update", "restart", "patch", "reboot", "update pending"], [P2, "Cyber Essentials"],
      """
CLG keeps devices patched on a risk-based timetable: critical security updates within about 14 days, and others within about 30 days (CLG_SEC_POL_002, section 5.3). Updates install automatically, but most need a restart to take effect.

## What to do
- When you see a restart prompt, save your work and restart at the next sensible break, ideally the same day.
- Restart your laptop at least once a week, rather than only closing the lid.
- Don't postpone updates repeatedly or try to switch them off.

## If an update fails
Restart and try again. If it keeps failing, contact the IT helpdesk with a screenshot of the error.
"""),
    A("travelling-with-devices", "Devices", "How-to", "Travelling with a CLG laptop or phone",
      "Keep devices with you, out of sight and locked, especially in airports, hotels and on public transport.",
      ["travel", "travelling", "airport", "hotel", "abroad", "trip", "train"], [P2],
      """
## Before you go
- Make sure your laptop is updated and you can sign in to everything you'll need.
- Take only the CLG data you need. It's all available in the cloud.

## While travelling
- Keep devices in your **hand luggage**, never in checked bags (CLG_SEC_POL_002, section 7.3).
- Don't leave them unattended in public places. In a hotel, lock them in the safe or take them with you.
- Lock your screen whenever you step away, and watch for people looking at your screen.
- Avoid unsecured public Wi-Fi for sensitive work. Use your phone's hotspot instead.

## If a device goes missing
Report it to the IT helpdesk immediately (see **What to do if your laptop or phone is lost or stolen**).
"""),
    A("laptop-acting-strangely", "Devices", "Troubleshooting", "Your laptop is behaving strangely",
      "Pop-ups, slowness or unfamiliar programs can be signs of malware. Stop and tell IT.",
      ["slow laptop", "pop ups", "strange behaviour", "virus", "infected", "hacked", "weird"], [P2],
      """
## Symptoms that may mean malware
- Sudden pop-ups, new browser toolbars or a changed home page.
- Programs you didn't install, or files you can't open or that have new extensions.
- Security warnings from Sophos.
- The laptop becomes very slow, or its fan runs constantly when you're doing little.

## What to do
1. **Stop using the laptop for CLG work** (CLG_SEC_POL_002, section 5.4).
2. If files are being renamed or encrypted, disconnect from Wi-Fi straight away.
3. Contact the IT helpdesk. IT will inspect the device and only return it once it's confirmed safe, re-imaging it if necessary.

> Slowness alone is usually not malware. A restart and installing updates often fixes it. If in doubt, ask.
"""),
    A("personal-use-of-devices", "Devices", "Policy summary", "Personal use of your CLG laptop",
      "Limited, sensible personal use is allowed, as long as it doesn't create risk or interfere with work.",
      ["personal use", "personal browsing", "use laptop for personal", "home use", "family use"], [P2, P3],
      """
CLG devices are provided for business. **Limited personal use** is allowed where it's reasonable, doesn't interfere with your work, and doesn't introduce security or reputational risk (CLG_SEC_POL_003, section 4).

## Please don't
- Download illegal software, games or media, or visit risky websites (CLG_SEC_POL_002, section 7.3).
- Let family or friends use your CLG laptop, or use a personal device for work while someone else is using it.
- Store personal files such as photos or music on your CLG laptop.

Remember that CLG monitors use of its systems, so there's no expectation of complete privacy (CLG_SEC_POL_003, section 11).
"""),
    A("laptop-broken", "Devices", "How-to", "Your laptop is broken or damaged",
      "Report it to IT. Your work is in the cloud, so you can carry on as soon as you have another device.",
      ["broken laptop", "damaged laptop", "cracked screen", "spilled", "wont turn on", "faulty laptop"], [BCP],
      """
## What to do
1. Stop using the device if it's physically damaged, for example after a liquid spill.
2. Contact the IT helpdesk with what happened and when.
3. Carry on working from another device by signing in to Microsoft 365 in a browser, if you have one.

## What IT will do
IT checks whether the repair is covered by warranty or insurance, arranges repair or replacement, and provides a temporary device if needed so there's no disruption to your work (Business Continuity Plan, Critical Function 1). [confirm: how long a replacement typically takes.]
"""),
    A("my-devices", "Devices", "How-to", "Check the devices registered to you",
      "See which CLG laptops and phones are recorded against your name, and report anything that's wrong.",
      ["my devices", "devices registered", "asset", "which laptop", "serial number"], [P2],
      """
CLG keeps an inventory of all IT equipment, with an owner for each item (CLG_SEC_POL_002, section 5.1).

## Check your devices
1. Open **My Devices** in this portal.
2. Check the list matches the equipment you actually have.

## If something's wrong
Contact the IT helpdesk if a device is missing from the list, or if one is listed that you no longer have, for example because you returned it.
"""),

    # ------------------------------------------------------------------ Security
    A("fake-it-calls", "Security", "How-to", "Calls or messages pretending to be from IT or a manager",
      "Attackers impersonate IT, suppliers and senior staff. Never share passwords or MFA codes, whoever asks.",
      ["fake it call", "impersonation", "social engineering", "scam call", "pretending to be it", "ceo fraud"], [P2, P3],
      """
Criminals call, text or message staff pretending to be the IT helpdesk, Microsoft, a supplier or a senior colleague.

## CLG IT will never ask you to
- Tell them your password.
- Read out an MFA code or approve a sign-in request.
- Install remote-control software you weren't expecting.

## If you're unsure
1. End the call or don't reply.
2. Contact the person or team back through a number or address you already know, not one given in the message.
3. Report it to the IT helpdesk, even if you didn't share anything. It helps warn colleagues.

Staying alert to social engineering is a responsibility under CLG_SEC_POL_003, section 5.4.
"""),
    A("payment-fraud", "Security", "How-to", "Requests to change bank details or make urgent payments",
      "Always confirm payment changes by phone using a number you already have. Never trust the email alone.",
      ["bank details", "invoice fraud", "urgent payment", "change bank", "payment request", "gift cards"], [P2],
      """
A common fraud is an email, apparently from a supplier or a senior colleague, asking you to change bank details or make an urgent payment.

## Warning signs
- Pressure to act quickly or keep it confidential.
- A new or changed bank account.
- A slightly different email address, or a reply-to address that doesn't match.
- Requests for gift cards or unusual payment methods.

## What to do
1. **Don't act on the email.**
2. Phone the supplier or colleague on a number you already have, not one in the email, and confirm the request.
3. Report the email to the IT helpdesk as suspected phishing.
4. If a payment has already been made, tell your manager and Finance immediately: speed matters for recovery.
"""),
    A("clear-desk-clear-screen", "Security", "Policy summary", "Clear desk and clear screen",
      "Lock away papers and lock your screen whenever you leave your workspace, in the office and at home.",
      ["clear desk", "clear screen", "paperwork", "lock away", "whiteboard", "desk"], [P2, P3],
      """
CLG follows a **clear desk and clear screen** approach, including when working from home (CLG_SEC_POL_003, section 6).

## In practice
- Lock your screen whenever you leave your device.
- Lock away papers containing sensitive information when you're not using them (CLG_SEC_POL_002, section 11.1).
- Wipe whiteboards and remove notes after meetings.
- Don't leave documents on printers.
- Store any USB drives or printed reports securely, and dispose of them securely when finished.
"""),
    A("printing-and-disposal", "Security", "How-to", "Printing and disposing of paper documents",
      "Print sensitive documents only when you must, collect them straight away, and shred them when done.",
      ["printing", "print", "shredding", "dispose paper", "confidential waste", "paper records"], [P2, P4],
      """
Most CLG work is digital, so avoid printing sensitive information wherever you can.

## If you need to print
- Collect printouts immediately and never leave them unattended (CLG_SEC_POL_002, section 8.3).
- Keep printed personal data locked away when not in use (CLG_SEC_POL_004, section 6).

## Disposing of paper
- In the office, use the secure shredding bins.
- At home, shred documents, or bring them to the office for secure disposal (CLG_SEC_POL_002, section 11.2).
- Never put documents containing personal or confidential information in ordinary recycling.
"""),
    A("report-security-weakness", "Security", "How-to", "Spotted something that looks insecure? Tell IT",
      "Reporting weaknesses before they're exploited is one of the most helpful things you can do.",
      ["security weakness", "vulnerability", "something insecure", "report weakness", "security concern", "bug"], [P2, P3],
      """
You're encouraged to report potential security weaknesses, not only incidents (CLG_SEC_POL_002, section 3).

## Examples worth reporting
- A shared folder or link that more people can open than should.
- A system that doesn't ask for MFA when you'd expect it to.
- A process that relies on sharing a password.
- A supplier asking for data in an unsafe way.

## How to report
Contact the IT helpdesk and describe what you noticed. Please don't test or try to exploit the weakness yourself. You won't be penalised for honest reporting (CLG_SEC_POL_003, section 10).
"""),
    A("security-policies-overview", "Security", "Policy summary", "CLG's security policies explained",
      "A quick guide to the six policies that make up CLG's information security framework.",
      ["security policies", "policy framework", "isms", "iso 27001", "information security policy"], [P1],
      """
CLG keeps a deliberately small set of six Board-approved policies, aligned with ISO/IEC 27001:2022 (CLG_SEC_POL_001, section 7). You can read them all under **Policy & Compliance**.

- **ISMS Policy (001):** the overall framework, objectives and responsibilities.
- **Information and Cyber Security Policy (002):** the technical controls: access, devices, networks, data, monitoring and incidents.
- **Acceptable Use and Remote Working Policy (003):** what every user must and mustn't do, at work and at home.
- **Data Protection and Privacy Policy (004):** how CLG handles personal data under UK GDPR and local law.
- **Secure Software Development Policy (005):** how CLG builds and changes software securely.
- **AI Governance Policy (006):** how AI tools may be used.

Everyone must read and acknowledge the policies, and follow them wherever they work (CLG_SEC_POL_001, section 9).
"""),
    A("what-clg-monitors", "Security", "Policy summary", "What CLG monitors on its systems, and why",
      "CLG monitors its systems to protect information and detect threats. Here's what that means for you.",
      ["monitoring", "privacy at work", "is my activity monitored", "logs", "tracking"], [P2, P3, P4],
      """
CLG monitors use of its systems to protect information, detect security threats and misuse, and support audits and legal obligations (CLG_SEC_POL_003, section 11).

## What this includes
- Security events such as sign-ins, failed sign-ins, account changes and malware alerts (CLG_SEC_POL_002, section 9.1).
- Alerts for unusual activity, such as large uploads to external sites (CLG_SEC_POL_002, section 8.3).

## What it means for you
- There's no expectation of absolute privacy when using CLG systems.
- Monitoring is carried out in line with data protection law, and the Employee Privacy Notice explains how staff data is used (CLG_SEC_POL_004, section 3).
- Logs are protected, and only authorised IT and Security staff can access them.
"""),

    # ------------------------------------------------------------------ Data protection
    A("subject-access-request", "Data protection", "How-to", "Someone has asked for a copy of their personal data",
      "Forward the request straight away. CLG normally has one month to respond.",
      ["subject access request", "sar", "dsar", "copy of my data", "data request", "erasure request", "delete my data"], [P4],
      """
People have the right to ask what personal data CLG holds about them, and to ask for it to be corrected, deleted or restricted (CLG_SEC_POL_004, section 7). Requests can arrive in any form: an email, a letter or even a conversation.

## What to do
1. **Forward the request immediately** to the People team (for staff) or the ISMS Manager (for everyone else). Don't try to answer it yourself.
2. Don't delete or change any data the person may be asking about.
3. Note the date you received it: CLG normally has **one month** to respond, starting from that date.

The responsible team will verify the person's identity before releasing or changing anything.
"""),
    A("wrong-recipient", "Data protection", "How-to", "You sent personal data to the wrong person",
      "Report it straight away. CLG may have 72 hours to tell the ICO, so every hour counts.",
      ["wrong recipient", "sent to wrong person", "misdirected email", "wrong email", "data breach", "mistake email"], [P4, P2],
      """
Sending personal data to the wrong person is a **personal data breach**, even if it was a simple mistake.

## Do this now
1. **Report it immediately** to the IT helpdesk or the ISMS Manager (CLG_SEC_POL_004, section 11).
2. Say what was sent, to whom, how many people's data it included, and when.
3. If you know the recipient, ask them politely to delete it and confirm they've done so, but report it first.

## Why speed matters
If the breach is notifiable, CLG must tell the ICO within **72 hours** of becoming aware of it. You won't be penalised for reporting an honest mistake; concealing a breach is a serious disciplinary matter.
"""),
    A("check-before-you-send", "Data protection", "How-to", "Check before you send: avoiding misdirected emails",
      "A few seconds of checking prevents most data breaches by email.",
      ["check recipient", "autocomplete", "email mistakes", "reply all", "bcc", "before sending"], [P4],
      """
Double-checking email recipients is one of every staff member's data protection duties (CLG_SEC_POL_004, section 12).

## Before you press Send
- **Check every recipient.** Outlook's autocomplete often suggests the wrong person with a similar name.
- **Use Bcc** when emailing many external people who shouldn't see each other's addresses.
- **Think before Reply All.**
- **Check attachments.** Is it the right file, and does it contain more personal data than the recipient needs?
- **Share a link** to a OneDrive or SharePoint file rather than attaching it, so you can remove access if needed.

If you do send something to the wrong person, see **You sent personal data to the wrong person**.
"""),
    A("retention-and-deletion", "Data protection", "Policy summary", "How long to keep personal data",
      "Keep personal data only as long as it's needed, then delete it securely.",
      ["retention", "how long to keep", "delete data", "old data", "retention schedule", "keep records"], [P4],
      """
CLG keeps personal data only as long as necessary for the purpose it was collected for, or as required by law or contract (CLG_SEC_POL_004, section 9).

## In practice
- Check the Group retention schedule for the type of record. Ask the ISMS Manager if you're unsure.
- Don't keep personal data "just in case".
- When it's no longer needed, delete electronic copies and shred paper ones.
- When a client project ends, keep only what's needed for closure and any required retention.

[confirm: the employee and payroll retention period. Data Protection and Privacy Policy V1.1, which sets seven years after employment ends, is pending Board approval.]
"""),
    A("dpia-new-project", "Data protection", "How-to", "Starting a project or system that uses personal data",
      "Build privacy in from the start, and check whether a Data Protection Impact Assessment is needed.",
      ["dpia", "new project", "privacy impact assessment", "privacy by design", "new system", "new process"], [P4],
      """
Any new initiative or change involving personal data must consider privacy from the planning stage (CLG_SEC_POL_004, section 8).

## What to do
1. **Talk to the ISMS Manager early**, before choosing a system or supplier.
2. Collect only the data you genuinely need, and justify each field.
3. Use privacy-friendly defaults, for example limiting who can see personal details.
4. A **Data Protection Impact Assessment (DPIA)** is required for processing likely to be high risk, or whenever the ISMS Manager asks for one.

Examples: a new CRM, an LMS feature that collects new learner data, or a new supplier processing staff data.
"""),
    A("new-supplier-or-tool", "Data protection", "How-to", "Using a new supplier or online tool for CLG data",
      "Any supplier or tool that will handle CLG data must be checked and approved first.",
      ["new supplier", "new tool", "online tool", "saas", "vendor", "free tool", "sign up"], [P2, P4],
      """
Before CLG uses a supplier or online service that will handle CLG data, it must pass a security and privacy check (CLG_SEC_POL_002, section 12.1; CLG_SEC_POL_004, section 10).

## Please don't
Sign up to online tools with your CLG account, or upload CLG data to them, before they're approved. This includes free tools and trials.

## How to get a tool approved
1. Contact the IT helpdesk with the tool's name, what you want to use it for and what data it will hold.
2. IT assesses its security, and suppliers handling personal data must sign a Data Processing Agreement.
3. You'll be told when it's approved, and any conditions of use.

For AI tools, see **Request a new AI tool**.
"""),
    A("sending-data-overseas", "Data protection", "Policy summary", "Sending personal data to another country",
      "Personal data can cross borders only with the right safeguards. Check before you send.",
      ["international transfer", "overseas", "another country", "new zealand", "australia", "transfer data abroad"], [P4],
      """
CLG operates in the UK, Australia, New Zealand and the Pacific Islands, so personal data sometimes moves between countries. This must follow the transfer rules (CLG_SEC_POL_004, section 10).

## The rules
- Send personal data overseas only when there's a business need.
- Transfers from the UK or EU to a country without an "adequacy decision" need approved safeguards, such as Standard Contractual Clauses.
- Use CLG's approved systems rather than emailing files, so data stays protected.
- CLG prefers to host and process data in-region where feasible.

If you're setting up a new regular transfer, or using a supplier in another country, check with the ISMS Manager first.
"""),
    A("sensitive-personal-data", "Data protection", "Policy summary", "Health, safeguarding and other highly sensitive data",
      "Special category and children's data need extra care. Share it only when you must, and only securely.",
      ["special category", "health data", "safeguarding", "children", "medical", "sensitive data"], [P4, P6],
      """
Some personal data is especially sensitive: health, ethnicity, criminal records, safeguarding information and children's data. CLG classifies it as **Highly Confidential** (CLG_SEC_POL_004, section 6).

## Extra rules
- Process it only under the additional legal conditions that apply, such as explicit consent or legal necessity (section 5).
- Limit access strictly to people who need it.
- Never send it by ordinary email to external recipients.
- Never enter it into AI tools unless that specific use has been approved (CLG_SEC_POL_006, section 7).

If you're unsure whether you can use or share such data, ask the ISMS Manager before acting.
"""),

    # ------------------------------------------------------------------ Working remotely and continuity
    A("home-workspace", "Working remotely", "How-to", "Set up a secure home workspace",
      "A few simple steps keep CLG information safe when you work from home.",
      ["home office", "home workspace", "work from home setup", "privacy screen", "family"], [P2, P3],
      """
Remote working doesn't reduce your security obligations: every policy applies at home too (CLG_SEC_POL_003, section 6).

## Your workspace
- Work where others can't easily see your screen or overhear calls. A privacy screen helps if you handle sensitive data (CLG_SEC_POL_002, section 11.2).
- Keep work devices separate from family use.
- Lock your screen whenever you step away.
- Keep any printed material confidential, and shred it when finished.

## Your connection
- Secure your Wi-Fi (see **Secure your home Wi-Fi**).
- Have a back-up connection ready, such as your phone's hotspot (see **Your internet connection is down**).
"""),
    A("cant-get-to-office", "Working remotely", "How-to", "If you can't get to the office",
      "Weather, transport or building problems? Work remotely, and let your manager know.",
      ["office closed", "cant get to office", "snow", "strike", "building closed", "power cut"], [BCP],
      """
Because CLG's systems are all cloud-based and much of the team already works remotely, most work can continue from anywhere (Business Continuity Plan).

## What to do
1. Tell your manager you'll be working remotely.
2. Work from home, or another safe location, using your CLG laptop.
3. If the office has lost power or been locked out, the building manager handles it, and staff may be redeployed to another site (Business Continuity Plan, Site Failure).

## Be prepared
Keep your laptop and phone charged, and take your laptop home when bad weather or disruption is forecast.
"""),
    A("major-incident-communication", "Working remotely", "Policy summary", "What happens in a major incident",
      "How CLG will contact you in an emergency, and what you need to do.",
      ["major incident", "emergency", "business continuity", "call tree", "how will i be contacted", "disaster"], [BCP],
      """
CLG's Business Continuity Plan sets out how the business keeps running during a major incident such as a fire, flood, pandemic or large cyber attack.

## How you'll be contacted
- By **email** first, or by **text message or WhatsApp** if email is unavailable (Business Continuity Plan, Command and Control).
- You'll be asked to **confirm you received the message**. This is tested once a year with a call-tree exercise.

## What to do
- Reply to confirm, and follow the instructions you're given.
- Keep your contact details up to date in Zoho People, so you can be reached.
- Major incidents are led by the CEO, so please don't contact clients about the incident unless you're asked to.
"""),
    A("phones-not-working", "Working remotely", "Troubleshooting", "Your phone or calls aren't working",
      "Switch to another channel straight away, and report the outage.",
      ["phone not working", "voip", "calls not working", "no dial tone", "telephony", "teams calls"], [BCP],
      """
## Symptom
You can't make or receive calls on your work phone line.

## Carry on working
- Use **Teams** calls and chat, or email, which are unaffected by most phone outages.
- Use your mobile phone as a back-up. Calls to an unavailable line can be diverted to a mobile or voicemail (Business Continuity Plan, VoIP Telephony Failure).

## Report it
Contact the IT helpdesk, saying whether it's just you or colleagues too. IT reports the fault to the provider within the first hour and keeps chasing until it's resolved (Business Continuity Plan, Critical Function 3).
"""),

    # ------------------------------------------------------------------ Microsoft 365 and Zoho
    A("microsoft-365-outage", "Microsoft 365 and Zoho", "Troubleshooting", "Microsoft 365 seems to be down",
      "Check whether it's just you, then use the workarounds until service returns.",
      ["microsoft 365 down", "outlook down", "teams down", "outage", "service down", "email not working"], [BCP],
      """
## Is it just you?
1. Check the known issues on the Knowledge Base home page.
2. Ask a colleague whether they're affected.
3. Try Outlook or Teams in a web browser at [outlook.office.com](https://outlook.office.com).

## If everyone is affected
Microsoft 365 runs across multiple data centres and usually recovers quickly. Its uptime was above 99.9% in every quarter from 2020 to 2025 (Business Continuity Plan, Microsoft 365). IT monitors Microsoft's service health dashboard and will post a known issue here.
- Use your phone or text message for anything urgent.
- Don't re-send emails repeatedly; they'll be delivered when the service recovers.

## If it's only you
Restart your laptop, check your internet connection, and see **Can't sign in or account locked**.
"""),
    A("zoho-security", "Microsoft 365 and Zoho", "Policy summary", "Using Zoho apps securely",
      "Zoho holds CLG data, so the same rules apply as for Microsoft 365: MFA, approved use, and your own account.",
      ["zoho", "zoho one", "zoho crm", "zoho desk", "zoho security", "zoho login"], [BCP, P2],
      """
CLG uses Zoho One apps, such as Zoho People, for core business processes, and MFA is enforced on Zoho as on all CLG cloud services (Business Continuity Plan).

## The rules
- Sign in with your own account and MFA. Never share logins.
- Use Zoho only for the CLG purposes it's been set up for.
- Store CLG data only in approved systems, and don't export personal data to spreadsheets you keep on your laptop.
- Report anything unusual, such as unexpected sign-in prompts, to the IT helpdesk.

Zoho publishes its security and performance information at [zoho.com/security](https://www.zoho.com/security.html).
"""),

    # ------------------------------------------------------------------ AI
    A("request-ai-tool", "AI", "How-to", "Request a new AI tool",
      "Every AI tool must be approved before it's used for CLG work. Here's how to ask.",
      ["request ai tool", "new ai tool", "ai approval", "use ai app", "ai request form"], [P6],
      """
No AI tool, feature or automated workflow may be used for CLG information until it's been assessed and approved (CLG_SEC_POL_006, section 4).

## How to request one
1. Complete the **AI Tool Request form** with the business reason and a risk assessment [confirm: where the form is].
2. IT and Compliance review it for security, privacy and compliance risks.
3. The designated authority makes the decision, and you're told the outcome (section 9).

## What reviewers look for
- What information the tool would process, and whether that's allowed (see **What you must never put into AI tools**).
- Whether the supplier uses customer data to train its models, and how long it keeps data.
- Whether it can be accessed with your CLG account, with logging.

Don't start using the tool, including a free trial, until it's approved.
"""),
    A("report-ai-incident", "AI", "How-to", "Report an AI mistake or data exposure",
      "Entered something you shouldn't, or got harmful output? Report it straight away.",
      ["ai incident", "ai mistake", "pasted data", "pasted into", "ai leak", "harmful ai output"], [P6],
      """
Any suspected or actual AI-related incident must be reported immediately through CLG's incident process (CLG_SEC_POL_006, section 12).

## Examples
- You pasted personal or confidential information into an AI tool.
- You used an unapproved AI tool for CLG work.
- An AI tool produced harmful, biased or misleading output that was used or sent.
- An AI tool's account or connection may have been compromised.

## What to do
Contact the IT helpdesk with which tool, what happened and what information was involved. Don't delete the conversation. If personal data was involved, it's handled as a potential data breach, where speed matters.
"""),

    # ------------------------------------------------------------------ Secure development (IT only)
    A("developer-secure-coding", "Secure development", "Policy summary", "Secure development: the essentials for developers",
      "The key rules from the Secure Software Development Policy for anyone writing or changing code.",
      ["secure coding", "developer", "sdlc", "code review", "owasp", "secure development"], [P5],
      """
These apply to all CLG software, including the LMS, integrations, scripts and infrastructure as code (CLG_SEC_POL_005).

## Every change
- Consider security and privacy requirements from the start, with threat modelling for new systems or major changes.
- Follow CLG's secure coding standards: validate input, handle errors safely, and protect against common vulnerabilities such as XSS and SQL injection.
- Get every significant change **peer reviewed** with security in mind, and run the security checks in the pipeline.
- Don't deploy your own code to production without independent review.

## Code and data
- Keep code only in CLG-approved repositories, never in personal or public ones.
- Use anonymised or fabricated test data, not real personal data.
- Keep dependencies up to date, and fix known critical vulnerabilities promptly.
""", audience="IT only"),
    A("secrets-in-code", "Secure development", "How-to", "Never put passwords or keys in code",
      "Secrets in source code are a leading cause of breaches. Use the secret store, and rotate anything exposed.",
      ["secrets", "api key", "password in code", "hard-coded", "key vault", "credentials", "leaked key"], [P5],
      """
Secrets such as passwords, API keys, tokens and certificates must never be hard-coded or committed to source control (CLG_SEC_POL_005, sections 5 and 8).

## Do
- Store secrets in an approved vault, such as Azure Key Vault, and load them at runtime.
- Keep secrets out of logs, error messages and screenshots.
- Rotate secrets regularly.

## If a secret has been committed or shared
1. Treat it as compromised, even if the repository is private.
2. **Rotate it immediately**: create a new secret and revoke the old one.
3. Remove it from the code, and report it to the ISMS Manager as a security incident.
""", audience="IT only"),
    A("contractor-access", "Joining and leaving", "How-to", "Giving a contractor or supplier access to CLG systems",
      "Contractor access must be sponsored, limited, time-bound and removed when the work ends.",
      ["contractor access", "supplier access", "temporary access", "consultant", "guest account", "third party access"], [P2, P6],
      """
Third-party accounts follow the same rules as staff accounts, with extra limits (CLG_SEC_POL_002, sections 4.3 and 12.3).

## As the sponsoring manager
1. Request the account through the IT helpdesk, naming yourself as the internal owner.
2. Ask only for the access the work needs, and give an end date.
3. Make sure a contract or NDA is in place covering confidentiality, and AI use if relevant (CLG_SEC_POL_006, section 9).
4. Tell IT as soon as the work finishes, so the account is disabled.

## The contractor must
- Have their own unique account with MFA. No shared logins.
- Use only CLG-approved tools for CLG data.
- Report any suspected incident immediately.
"""),
]


def _s(v):
    """SQL string literal that survives the Azure portal Query editor.
    That editor splits scripts into batches at the word GO (the SQL Server batch
    separator) wherever it appears, even inside a string such as "1. Go to…", and
    the split leaves an unclosed quote. So: line breaks become NCHAR(10) joins
    (each statement stays on one line), and every standalone "go" is broken into
    two joined pieces, N'G' + N'o', which the editor cannot match."""
    if v is None:
        return "NULL"
    pieces = []
    for line in str(v).split("\n"):
        esc = line.replace("'", "''")
        esc = re.sub(r"(?i)\b(g)(o)\b", r"\1' + N'\2", esc)
        pieces.append("N'" + esc + "'")
    if len(pieces) == 1 and "' + N'" not in pieces[0]:
        return pieces[0]
    return "CAST(N'' AS NVARCHAR(MAX)) + " + " + NCHAR(10) + ".join(pieces)


def render_sql() -> str:
    out = [
        "-- Knowledge Base v2 schema and seed (generated by: python knowledge_seed.py)",
        "-- Safe to re-run: creates tables if missing, inserts new articles, and refreshes only seed",
        "-- articles nobody has edited or approved (updatedBy and approvedBy both NULL).",
        "",
        "IF OBJECT_ID('dbo.knowledge_article', 'U') IS NULL",
        "CREATE TABLE dbo.knowledge_article (",
        "    articleId   NVARCHAR(100)  NOT NULL PRIMARY KEY,",
        "    title       NVARCHAR(400)  NOT NULL,",
        "    summary     NVARCHAR(1000) NOT NULL,",
        "    category    NVARCHAR(200)  NOT NULL,",
        "    articleType NVARCHAR(50)   NOT NULL,",
        "    body        NVARCHAR(MAX)  NOT NULL,",
        "    keywords    NVARCHAR(MAX)  NOT NULL,  -- JSON array",
        "    evidence    NVARCHAR(MAX)  NOT NULL,  -- JSON array of Policy & Compliance title keys",
        "    audience    NVARCHAR(50)   NOT NULL,",
        "    status      NVARCHAR(50)   NOT NULL,  -- Draft | Approved | Retired",
        "    owner       NVARCHAR(400)  NOT NULL,",
        "    reviewDate  DATE           NULL,",
        "    version     INT            NOT NULL DEFAULT 1,",
        "    views       INT            NOT NULL DEFAULT 0,",
        "    approvedBy  NVARCHAR(400)  NULL,",
        "    approvedAt  DATETIME2      NULL,",
        "    updatedBy   NVARCHAR(400)  NULL,",
        "    updatedAt   DATETIME2      NOT NULL DEFAULT SYSUTCDATETIME()",
        ");",
        "",
        "IF OBJECT_ID('dbo.knowledge_feedback', 'U') IS NULL",
        "CREATE TABLE dbo.knowledge_feedback (",
        "    feedbackId  NVARCHAR(64)   NOT NULL PRIMARY KEY,",
        "    articleId   NVARCHAR(100)  NOT NULL,",
        "    helpful     BIT            NOT NULL,",
        "    reason      NVARCHAR(50)   NULL,",
        "    comment     NVARCHAR(1000) NULL,",
        "    userName    NVARCHAR(400)  NULL,",
        "    createdAt   DATETIME2      NOT NULL DEFAULT SYSUTCDATETIME()",
        ");",
        "",
        "IF OBJECT_ID('dbo.knowledge_search_log', 'U') IS NULL",
        "CREATE TABLE dbo.knowledge_search_log (",
        "    id          BIGINT IDENTITY(1,1) NOT NULL PRIMARY KEY,",
        "    query       NVARCHAR(400)  NOT NULL,  -- query text only; who searched is never stored",
        "    resultCount INT            NOT NULL,",
        "    createdAt   DATETIME2      NOT NULL DEFAULT SYSUTCDATETIME()",
        ");",
        "",
    ]
    for a in SEED_ARTICLES:
        v = {k: _s(a[k]) for k in ("articleId", "title", "summary", "category", "articleType", "body", "audience")}
        kw, ev = _s(json.dumps(a["keywords"])), _s(json.dumps(a["evidence"]))
        out.append(f"IF NOT EXISTS (SELECT 1 FROM dbo.knowledge_article WHERE articleId = {v['articleId']})")
        out.append(
            "    INSERT INTO dbo.knowledge_article (articleId, title, summary, category, articleType, body, keywords, evidence, audience, status, owner) "
            f"VALUES ({v['articleId']}, {v['title']}, {v['summary']}, {v['category']}, {v['articleType']}, {v['body']}, {kw}, {ev}, {v['audience']}, N'Draft', N'IT');"
        )
        out.append("ELSE")
        out.append(
            f"    UPDATE dbo.knowledge_article SET title = {v['title']}, summary = {v['summary']}, category = {v['category']}, "
            f"articleType = {v['articleType']}, body = {v['body']}, keywords = {kw}, evidence = {ev}, audience = {v['audience']}, "
            f"updatedAt = SYSUTCDATETIME() WHERE articleId = {v['articleId']} AND updatedBy IS NULL AND approvedBy IS NULL;"
        )
    out += ["", "SELECT status, COUNT(*) AS articles FROM dbo.knowledge_article GROUP BY status;"]
    return "\n".join(out) + "\n"


if __name__ == "__main__":
    print(render_sql(), end="")
