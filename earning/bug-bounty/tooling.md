# Bug-Bounty Tooling — The Free Toolkit

Everything below is free (open-source or free tier) and legal to own and to use
on authorised targets. The tool is never the authorisation — the programme scope
is (see `scope-and-legal-rules.md`). During the 30-day plan these tools point
only at PortSwigger labs and Hack The Box machines.

## Core (learn these first)

| Tool | Cost | What it's for |
|---|---|---|
| **Burp Suite Community Edition** | Free | The workhorse: intercepting proxy to see and modify your browser's requests to a target you are authorised to test. PortSwigger's Academy is built around it. |
| **Firefox / Chromium with proxy config** | Free | A dedicated "hunting browser" profile routed through Burp, kept separate from personal browsing. |
| **PortSwigger Web Security Academy** | Free | Not just labs — its learning paths *are* the curriculum for the 30-day plan. |

## Recon and mapping (in-scope assets only)

| Tool | Cost | What it's for |
|---|---|---|
| **nmap** | Free / open source | Port and service discovery — only against in-scope hosts, and only where the programme permits scanning. |
| **subfinder / amass** | Free / open source | Enumerating subdomains of an in-scope root domain. |
| **httpx** | Free / open source | Checking which enumerated hosts are live web services. |
| **gobuster / ffuf** | Free / open source | Discovering hidden directories/files on an in-scope web app — rate-limit yourself; many programmes cap request rates. |

## Analysis and testing support

| Tool | Cost | What it's for |
|---|---|---|
| **sqlmap** | Free / open source | Automated SQL-injection confirmation — for labs freely; on live programmes only where automation is explicitly allowed. |
| **OWASP ZAP** | Free / open source | Open-source alternative/complement to Burp for scanning your lab targets. |
| **jwt_tool / browser devtools** | Free | Inspecting tokens and client-side behaviour in your own test accounts. |
| **CyberChef** | Free (web) | Encoding/decoding and data-format wrangling while analysing requests. |
| **Obsidian or plain Markdown notes** | Free | The findings notebook: every lab and (later) every programme gets a page — target, scope snapshot, what was tried, what worked. Discipline here is what turns practice into reports. |

## What is deliberately NOT in the toolkit

- No paid scanners, no "AI hacker" subscription tools (free-only rule).
- No credential-stuffing, phishing, or social-engineering tooling — out of scope
  for this lane permanently.
- No exploit frameworks pointed at production: lab learning uses the Academy's
  and HTB's own environments.

## Setup order (Day 1 of the plan)

1. Create the PortSwigger Academy account; install Burp Community; configure the
   hunting browser profile through Burp's proxy; complete Burp's built-in
   getting-started flow inside an Academy lab.
2. Install nmap, ffuf, OWASP ZAP locally (all from their official sources).
3. Start the notes notebook with the scope-rules page copied at the front.
