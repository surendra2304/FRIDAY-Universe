# Your First 100 Subscribers — Chapter 5 (Draft)

## Chapter 5 — Day 5: The Tools Setup, Free Tier Only

Yesterday you wrote the words. Today you wire them up so they send themselves.

This is the least glamorous chapter in the book, and one of the most important.
A welcome sequence that lives in a document helps nobody. One connected to a
real signup page, sending itself to every new subscriber, works while you sleep.
The good news is that everything here can be done on a free tier, in one
sitting, with no code and no credit card. The bad news is that the setup has a
few fiddly steps, and skipping one is the difference between landing in the
inbox and landing in spam. So we will go slowly, in order, and test everything
before we call it done.

Get one thing straight first: the tool does not make the list. Today is plumbing, not strategy — pick a tool that works, set it up properly, and get back to writing.

### Choosing an email platform on the free tier

Most email platforms offer a free tier aimed at beginners. They differ in what
they emphasise, not in what they fundamentally do: every one stores a list,
sends emails to it, and can send a series of emails automatically when someone
joins. Compare them on five things — and on nothing else, for now:

1. **The free tier, as it stands today.** Free tiers change, so do not trust a blog post, a video, or this book for the current numbers — open the platform's own pricing page and read it. Can you have a list of your size, send the emails you plan to send each week, and use automated sequences without paying? Check the current free tier on the day you sign up, and write down what it includes.
2. **Automation on the free tier.** This is the question most beginners forget, and it matters more than any other. Some free tiers include automated sequences; some reserve them for paying customers. You need five emails, in order, with a delay between each — so confirm the free tier includes that before you build anything. A platform that is free but cannot send your welcome sequence is not free for your purposes; it is the wrong tool.
3. **Deliverability basics.** When this platform sends your email, does it usually arrive in the inbox? You cannot measure this yourself at your size, and you should not trust any platform's own claims about it. Pick an established platform with a real reputation to protect — one that small businesses and creators use every day, that deals with spam complaints seriously, and that gives you the authentication settings this chapter explains. 
4. **Getting your list back out.** Before you put a single address into a platform, check that you can export your list — every subscriber, with address and join date — in a plain file you can open yourself. Your list is your asset, not the platform's. If exporting is difficult, hidden, or only available on a paid plan, walk away.
5. **Whether you can actually use it.** Open the free account, look at the screen where you write an email, and ask: can I do this every week without dreading it? If the interface confuses you in the first ten minutes, it will not get better. Pick the one you understand — you need five automated emails and one email a week, not a marketing suite.


### Connecting the form to the list

On Day 3 you built a signup page: a headline, three bullets, one field, one button. Today that page has to do its real job — when someone types their email and clicks the button, the address must land in your list and the sequence must start. Three pieces: the **form** (where the address is typed), the **list** (the named collection inside your platform), and the **automation** (the sequence that starts when someone joins). The form feeds the list; the list triggers the automation. If any link is missing, the system fails silently: the person thinks they subscribed, and nothing happens.

1. **Make the list first.** Inside your platform, create one list — or audience,
   or group; the name varies — and call it something clear, like "Main list".
   Do not create five lists for five ideas. One list. Everything else hangs
   off it.
2. **Connect the form to that list.** If you built the page with your platform's own page builder, this is usually a dropdown: pick the list, and the form feeds it. If you built the page somewhere else, your platform will give you a small piece of code or a link to paste into the page. Follow the platform's own current help page — it changes often. The test at the end of this chapter will prove whether it worked.
3. **Ask for the email address only.** Your Day-3 page asked for one field, and
   that is still right. Every extra field costs you subscribers. If your
   platform's form asks for a first name by default, keep it only if you
   genuinely use it in your emails; the email address is the only field that
   matters.
4. **Set the confirmation page.** After subscribing, the reader should land somewhere that says what happens next: "Check your inbox — your [lead magnet name] is on its way." If they see a blank page or an error, they will assume it did not work — and they will be right.
5. **Decide about double opt-in.** Many platforms offer a setting where a new subscriber gets an email asking them to confirm before joining. It keeps mistyped addresses and uninterested people off your list, at the cost of slower growth — some people never click the confirmation. Either setting is defensible for a small list built from real invitations — just know which one you picked, and make sure the confirmation email sounds like you. It is the first email your subscriber ever gets from
   you.

### Setting up the welcome-sequence automation, step by step

This is the heart of the chapter: making the five emails from Chapter 4 send themselves, in order, without you touching them. Every platform names the pieces differently — workflow, journey, automation, sequence — but the shape is the same everywhere. If you get lost in the menus, look for "when someone joins" and "send email".

1. **Create the automation and name it clearly.** Something like "Welcome sequence — 5 emails". In six months you need to find it at a glance, not guess between three things called "Automation 1".
2. **Set the trigger: when someone joins the list.** The automation starts when
   a new subscriber is added to the list you made above — and only then. Pick
   the specific list, not "subscribes via any form". If the trigger is wrong,
   the sequence will either never start or start for the wrong people.
3. **Add Email 1, with no delay.** The first step after the trigger sends Email 1
   — the delivery email — immediately. Paste in the filled-in Email 1 skeleton
   from Chapter 4, and attach the lead magnet the way you planned on Day 2: a
   link to the file, or the file itself. Check the link works before moving on.
4. **Add a delay, then Email 2 — and repeat.** After Email 1, add a waiting step — one day, or two days if you chose the every-other-day rhythm — and then Email 2. The delay is a step in the automation, not a setting on the email: forget it, and all five emails go out at once, the single most common automation mistake beginners make. Repeat: delay, Email 3; delay, Email 4; delay, Email 5.
5. **Check the order and the delays.** Read the automation top to bottom, like a
   recipe: trigger, Email 1, delay, Email 2, delay, Email 3, delay, Email 4,
   delay, Email 5, end. Five emails, four delays. If there are five delays, one
   is wrong. If an email appears twice, one is wrong.
6. **Test before you call it done.** Do not switch the automation on and hope.
   Run the test-send protocol at the end of this chapter first. An automation
   that has never been tested is not finished; it is a guess.


### The three settings that decide whether you land in spam

This is the part most beginners skip, and the part that matters most. When your email arrives, the reader's provider asks one question: is this really from who it claims to be from? If the answer is unclear, the email goes to spam. Three settings answer that question. Each is a simple idea — set them up once, correctly, and forget about them.

First, the decision these settings depend on: **send from an address on a domain you own.** From a free address, like Gmail or Outlook, you cannot set them up properly, because you do not own that domain. You want an address like hello@yourbusiness.com. If you do not have a domain yet, getting one is a small, one-off job — your domain provider or platform's help pages will walk you through it — and it is worth doing before you send to real subscribers. Everything below assumes your own domain. If you do not have one, fix that first, then come back.

**1. SPF — the list of approved senders.** Think of SPF as a guest list pinned to your domain's door: a short public note saying "these services are allowed to send email as me." When your platform sends from your address, the receiving inbox checks the list. On it, the email passes the first check; off it, the email looks like a forgery. Setting it up means adding one line of text to your domain's settings — your platform tells you exactly what line, word for word. Copy it exactly: one wrong character and the check fails silently.

**2. DKIM — the wax seal.** Think of DKIM as a wax seal on a letter. Your platform stamps each email with a private seal only it can make; the receiving inbox checks it against a public copy you placed on your domain. If the seal matches, the email was not tampered with on the way. The platform generates the line of text, you paste it into your domain's settings, then press the platform's "verify" button — and do not move on until it says the seal is working.

**3. DMARC — the instruction for failures.** Think of DMARC as the note you leave with the doorman: "If an email claims to be from me but fails the guest list or the wax seal, here is what to do with it." Start with the gentle instruction — roughly, "just report it, and deliver the email anyway" — which in the jargon is a policy of "none". That gives you the protection of knowing what is happening without risking your own real emails being rejected over a setup mistake. Later, when SPF and DKIM have worked for a while, you can tighten it. Not today.

Three practical notes. **Where the settings live:** in your domain provider's settings, in a section usually called "DNS". Use the exact text your own platform gives you — never copy these entries from a video or a blog post, because they are generated for your account. **Changes take time to spread:** after you save a setting, it can take a while before every inbox can see it. If verification says "not found" straight after you save, wait and try again — do not keep changing the entry. **You only do this once:** these settings belong to your domain, not to any one email, so every email you send from that domain benefits.

### The test-send protocol

Never send to a real subscriber until you have sent to yourself. Run this protocol in full every time you change anything in the sequence — not just the first time.

1. **Subscribe through your real signup page**, with your own address — and a
   second one on a different provider if you have it. Do not add yourself
   inside the platform; that skips the form, and the form is half of what you
   are testing.
2. **Check Email 1 arrives, and how fast.** Within a few minutes. Open it: is the lead magnet link in the first two lines, and does it work? Does it look right on your phone, not just your computer?
3. **Check the spam folder** — and the promotions tab, and any filtered folder.
   If your own email is there, your subscribers' emails will be there too.
   Stop, fix the three settings above, and test again. Do not just move it to
   the inbox and carry on.
4. **Click every link, and reply to the email.** Every link should go where it says it goes. Reply to Email 1 and check the reply arrives in the inbox you actually read — if replies go somewhere you never check, you will miss the conversations Chapter 4 worked to start.
5. **Check the sender name and address.** Your name, from your own domain — not
   "noreply", not your platform's domain.
6. **Walk the whole sequence.** Use your platform's preview or test mode to read Emails 2 to 5 as a subscriber would — or temporarily shorten the delays to a few minutes, run a second test subscriber through, and put the delays back. Read each email on your phone, check subject lines, links, and order, then restore the delays and check the order once more.


If anything fails, fix it and run the whole protocol again from the top. The
protocol is short; a broken welcome sequence sent to your first real
subscribers is not.

### What to do if your test lands in spam

Do not panic, and do not change everything at once. Work through the causes in order, changing one thing and re-testing: **check the three settings** — most failures at this stage are one of them, usually a copied line with a typo, or a setting that has not had time to spread. Fix it, wait, verify, test again. **Check the sender address** — are you sending from your own domain? **Check the content of Email 1** — a delivery email full of links, images, and sales language looks like spam; yours is short, has one link, and reads like a person wrote it. If it does not, go back to Chapter 4 and simplify it.

If the tests pass, you are done for today: the sequence is live, the form feeds the list, the list triggers the sequence, and the settings give your emails the best chance of arriving. That is a working system — built in a week, on a free tier, with no ads and no code. Tomorrow, Day 6, you invite your first real people to it.

### Your finished asset: the test-send checklist

Copy this checklist somewhere you will see it. Run it in full every time you change the sequence, the form, or the sender settings — not just today.

**Test-send checklist — run before any real subscriber sees the sequence:**

- [ ] Subscribed through the real signup page with my own address (and a second address on a different provider, if I have one)
- [ ] Email 1 arrived within a few minutes, and the lead magnet link works
- [ ] Email 1 is NOT in spam, promotions, or any filtered folder, in either inbox
- [ ] Email 1 reads correctly on my phone — link in the first two lines
- [ ] Every link in every email goes where it says it goes
- [ ] I replied to Email 1 and the reply arrived in the inbox I actually read
- [ ] Sender name is mine and the address is on my own domain — not "noreply", not the platform's domain
- [ ] SPF verified, DKIM verified, DMARC set to the gentle ("none") policy
- [ ] Automation reads: trigger, Email 1, delay, Email 2, delay, Email 3, delay, Email 4, delay, Email 5 — five emails, four delays
- [ ] I walked the whole sequence in preview or test mode and read Emails 2 to 5 on my phone
- [ ] Delays are back to my Chapter 4 rhythm (daily, or every other day)
- [ ] My list exports cleanly — every subscriber, with address and join date, in a file I can open

Tick every box, and the sequence is live. Leave a box unticked, and it is not finished yet — fix it, and run the checklist again from the top.

*End of Chapter 5 draft.*
