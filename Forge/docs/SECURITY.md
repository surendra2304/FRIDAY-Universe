# 🛡️ Project FORGE — Security Architecture & Guidelines

Project FORGE is engineered with a **Security-First** philosophy. Every autonomously generated codebase is audited against multi-vector static security scanners and dependency vulnerability databases before delivery.

---

## 1. Security-First Architecture Overview

```
                                [Project Specification]
                                           │
                                           ▼
                              [Security-Aware Prompts]
                     • Strict typed input validation
                     • Parameterized SQL bindings (no string concatenation)
                     • Stack trace shielding on error responses
                     • Secure defaults & least privilege access
                     • CSRF & Security Headers (CSP, X-Frame-Options)
                                           │
                                           ▼
                                [Generated Codebase]
                                           │
                                           ▼
                              [OutputSecurityScanner]
                     (Runs BEFORE standard verification battery)
                                           │
         ┌───────────────────┬─────────────┴─────────────┬───────────────────┐
         ▼                   ▼                           ▼                   ▼
  [Secrets Scan]      [Dangerous AST]             [Injection Checks]  [CVE Dependency Scan]
   • AWS / OpenAI      • eval() / exec()           • SQL f-strings     • Local CVE DB match
   • Private keys      • os.system()               • SQL concat        • requirements.txt
   • Database URIs     • shell=True                • DOM innerHTML     • package.json
   • Redacted logs     • pickle.loads()            • React dangerously • Auto-remediation
                                           │
                                           ▼
                              [Severity Gating Engine]
                     • CRITICAL / HIGH ──► Blocks Delivery & Triggers Re-Synthesis
                     • MEDIUM / LOW    ──► Documented in verification_manifest.json
```

---

## 2. Scanner Severity Levels & Gating Semantics

| Severity | Definition | Delivery Impact | Action Required |
| :--- | :--- | :---: | :--- |
| **`CRITICAL`** | Direct remote code execution, SQL injection, exposed high-value private keys, or known critical CVEs. | 🚫 **BLOCKS DELIVERY** | Must be remediated before completion. Triggers automatic re-synthesis attempt. |
| **`HIGH`** | Command injection risks, insecure deserialization (`pickle`), shell invocations, or missing authentication on state-changing endpoints. | 🚫 **BLOCKS DELIVERY** | Must be remediated before completion. |
| **`MEDIUM`** | Information disclosure (e.g. stack trace leaks), potential XSS vectors (`dangerouslySetInnerHTML`), unpinned dependencies. | ⚠️ **ALLOWED WITH WARNING** | Documented as warnings in `verification_manifest.json`. |
| **`LOW`** | Informational security notices, recommended security headers, style warnings. | ℹ️ **INFORMATIONAL** | Documented in manifest. |

---

## 3. Core Scanning Capabilities

### A. Hardcoded Secrets & Credentials
- **Patterns Detected:** AWS access keys (`AKIA...`), OpenAI API keys (`sk-...`), Anthropic tokens, GitHub PATs, RSA/OpenSSH private keys, plaintext database connection URIs with passwords, and generic password assignments.
- **Automatic Redaction:** All evidence and log outputs automatically mask matched secrets with `***REDACTED***` to prevent accidental credential leakage in reports.

### B. Dangerous Function AST Analysis
- **Python AST Inspection:**
  - `eval()` and `exec()`: Flagged as `CRITICAL`.
  - `subprocess.*(..., shell=True)`: Flagged as `CRITICAL`.
  - `os.system(...)`: Flagged as `HIGH`.
  - `pickle.loads(...)` on untrusted input: Flagged as `HIGH`.
  - `yaml.load(...)` without `Loader=SafeLoader`: Flagged as `HIGH`.
- **JavaScript AST Inspection:**
  - Dynamic `eval()`: Flagged as `CRITICAL`.
  - `child_process.exec()`: Flagged as `HIGH`.

### C. Injection Vulnerability Patterns
- **SQL Injection:**
  - Detects f-strings in queries: `cursor.execute(f"SELECT * FROM users WHERE id = {user_id}")`
  - Detects string concatenation in queries: `cursor.execute("SELECT * FROM users WHERE name = '" + name + "'")`
  - Detects string formatting `%` or `.format()` in SQL.
- **Cross-Site Scripting (XSS):**
  - Detects unescaped assignments to `.innerHTML`.
  - Detects React `dangerouslySetInnerHTML` usage.

### D. Dependency Vulnerability & CVE Scanning
- **Knowledge Base:** Embedded database mapping popular packages (`urllib3`, `requests`, `flask`, `jinja2`, `pillow`, `pyyaml`, `cryptography`, `lodash`, `express`, `jsonwebtoken`, `axios`) to published CVE IDs and safe patched versions.
- **Auto-Remediation:** The engine automatically updates `requirements.txt` / `package.json` to the secure patched version and produces verified lockfiles (`requirements.lock`, `package-lock.json`).

### E. Authentication Bypass & Information Disclosure
- Detects unauthenticated state-changing routes (`POST`, `PUT`, `DELETE`) in administrative/management controllers.
- Detects leaked stack traces (`traceback.format_exc()`) in client error responses.

---

## 4. Remediation Guidance for Common Findings

### 1. Hardcoded Credentials
- **Insecure:**
  ```python
    API_KEY = "<REDACTED_SECRET_EXAMPLE>"
  ```
- **Secure:**
  ```python
  import os
  API_KEY = os.getenv("FORGE_API_KEY", "")
  ```

### 2. SQL Injections
- **Insecure:**
  ```python
  cursor.execute(f"SELECT * FROM accounts WHERE username = '{username}'")
  ```
- **Secure:**
  ```python
  cursor.execute("SELECT * FROM accounts WHERE username = ?", (username,))
  ```

### 3. Dynamic Code Execution
- **Insecure:**
  ```python
  result = eval(user_expression)
  ```
- **Secure:**
  ```python
  import ast
  result = ast.literal_eval(user_expression)  # or json.loads()
  ```

### 4. DOM Cross-Site Scripting (XSS)
- **Insecure:**
  ```javascript
  document.getElementById("user-bio").innerHTML = userInput;
  ```
- **Secure:**
  ```javascript
  document.getElementById("user-bio").textContent = userInput;
  ```

---

## 5. Security in the Verification Manifest

All security scan findings are included in `verification_manifest.json`:

```json
{
  "name": "[CRITICAL] SQL Injection Pattern (f-string)",
  "category": "security",
  "status": "fail",
  "evidence": {
    "file": "app/db.py",
    "line": 42,
    "snippet": "cursor.execute(f\"SELECT * FROM users WHERE id = {user_id}\")",
    "description": "SQL query constructed via f-string interpolation rather than parameterized query."
  },
  "fix_suggestions": [
    "Use parameterized query placeholders (?, %s, or :param) with parameter bindings tuple."
  ]
}
```

---
*Maintained by Project FORGE Engineering & Security Architecture.*
