"""
Knowledge Base v2 — 30 starter articles
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
