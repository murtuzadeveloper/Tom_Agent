# murtuzadeveloper Smart Leads
### AI-Powered Screen Intelligence & Professional Contact Extraction for Windows 11

**murtuzadeveloper Smart Leads** is a professional desktop application designed to inspect visible screen content, extract verified professional contact records, and persist them directly into an Excel-compatible CSV file and a local SQLite repository.

---

## 1. System Architecture & Target Hardware

Optimized specifically for:
- **Operating System:** Windows 11 x64
- **Processor:** Intel Core i7-9850H @ 2.60 GHz (6 Cores, 12 Threads)
- **System Memory:** 16 GB RAM
- **Dedicated GPU:** NVIDIA GeForce MX150 (2 GB GDDR5 VRAM)
- **Local AI Runtime:** LM Studio hosting **Gemma 4 12B QAT** (or fallback multimodal models such as `qwen2.5-vl-3b-instruct`)

### Memory-Conscious Design:
Given the 2 GB VRAM limit of the NVIDIA MX150, the application implements:
- **Strict 1-at-a-time Model Concurrency:** Prevents out-of-memory crashes on host GPU and CPU.
- **OCR-First Pre-Filtering:** Analyzes screen text using lightweight OCR before invoking heavy vision inference.
- **Lightweight Perceptual Change Detection:** Compares 64×64 grayscale thumbnails to bypass static/unchanged screens.
- **Resolution Downscaling:** Automatically scales vision screenshots to max 1280px with JPEG compression (quality 80).
- **Bounded Frame Queues:** Drops stale frames if processing lags, maintaining system responsiveness.

---

## 2. Technology Stack

- **Desktop Framework:** PySide6 (Qt 6 for Python) with custom dark UI styling
- **Screen Capture:** MSS (Multi-Screen Screen shot) & Windows GDI
- **Local AI Inference:** OpenAI-compatible endpoint in LM Studio (`http://127.0.0.1:1234/v1`)
- **Data Validation:** Pydantic v2 schemas, `email-validator`, and Google's `phonenumbers`
- **Deduplication & Storage:** SQLite (WAL mode) and Excel-compatible CSV (`utf-8-sig`)
- **Security & Shielding:** Formula injection protection and automated credential/PII scrubbers

---

## 3. Screen Capture Modes & Automated Scrolling

1. **Mode A: Current Screen / Active Window**
   - Captures the primary display or active foreground window at a configurable interval (default: 3.0 seconds).
   - Skips identical frames when difference is below `change_threshold_percent` (default: 2.5%).
2. **Mode B: Selected Screen Region**
   - Displays an interactive translucent fullscreen overlay with crosshairs.
   - Click and drag a rectangle around a contact card, directory profile, or message header.
3. **Mode C: Controlled Webpage Scrolling**
   - Automatically navigates and scrolls supported public webpages in bounded increments (600px) using Playwright.
   - Gracefully falls back to manual controlled scrolling with change detection for other desktop applications.

### 🔄 Automated Scrolling Feature:
- Check **"Automatically Scroll Down After Each Capture"** in the Capture Mode view.
- **Universal Windows Scrolling:** Uses Windows `MOUSEEVENTF_WHEEL` synthetic wheel scrolls to automatically scroll down any active application (Chrome, Edge, WhatsApp Desktop, directory lists, spreadsheets, or PDFs).
- **Controlled Browser Scrolling:** Uses Playwright JavaScript evaluation to scroll web pages in bounded increments.
- **Auto-Stop at Page End:** When the screen reaches the bottom and stops changing, the change detector senses repeated unchanged frames and automatically pauses the session.

---

## 4. LM Studio Configuration Guide

### Step 1: Install & Launch LM Studio
1. Download LM Studio for Windows from [lmstudio.ai](https://lmstudio.ai/).
2. Search and download **Gemma 4 12B QAT** or **Qwen2.5-VL-3B-Instruct** (multimodal GGUF).

### Step 2: Configure Hardware Offload (MX150 2GB Tuning)
Because the MX150 has 2 GB VRAM, do not offload all 12B model layers to the GPU:
- In LM Studio Model Loading Settings:
  - **GPU Offload:** Set GPU layers to `8 - 12` (or CPU-only if loading full context), allowing system RAM (16 GB) to handle the rest.
  - **Context Length:** 2048 - 4096 tokens.

### Step 3: Start the Local Server
1. Click the **Local Server** tab (double-arrow icon) in LM Studio.
2. Select your loaded model from the dropdown.
3. Enable **Cross-Origin-Resource-Sharing (CORS)**.
4. Click **Start Server** on port `1234` (`http://127.0.0.1:1234`).
5. In **murtuzadeveloper Smart Leads**, click **Test LM Studio** on the dashboard.

---

## 5. CSV Output Specification

- **Default Location:** `%USERPROFILE%\Desktop\murtuzadeveloper_Smart_Leads.csv`
- **Encoding:** UTF-8 with BOM (`utf-8-sig`) for Excel compatibility.
- **Formula Injection Shield:** Automatically prepends `'` to any cell starting with `=`, `+`, `-`, or `@`.
- **Lock Recovery:** If Excel locks the CSV while open, pending writes are safely queued in the SQLite database and flushed automatically once unlocked.

### CSV Columns:
| # | Column Name | Description |
|---|---|---|
| 1 | `record_id` | Unique UUID4 identifier |
| 2 | `collected_at` | ISO 8601 UTC timestamp |
| 3 | `person_or_profile_name` | Name of person or professional profile |
| 4 | `job_title` | Verified job title or position |
| 5 | `organization_name` | Company or organization name |
| 6 | `business_email` | Validated business email address |
| 7 | `contact_number` | Original raw contact number |
| 8 | `normalized_phone` | Standardized E.164 phone format |
| 9 | `website_url` | Company or professional website |
| 10 | `social_profile_url` | LinkedIn, Twitter/X, or GitHub profile |
| 11 | `source_application` | Application name (e.g. Chrome, WhatsApp) |
| 12 | `source_url` | Webpage URL if available |
| 13 | `evidence` | Text evidence snippet supporting extraction |
| 14 | `email_validation_status` | `VALID_SYNTAX` / `INVALID` / `UNCHECKED` |
| 15 | `phone_validation_status` | `VALID_E164` / `POSSIBLE` / `INVALID` |
| 16 | `review_status` | `PENDING` / `APPROVED` / `REJECTED` |

---

## 6. Quick Start & Execution

### Option A: One-Click Windows Launcher
Double-click `run.bat` in the project root:
- Automatically creates `.venv` virtual environment if missing.
- Installs dependencies from `requirements.txt`.
- Starts the PySide6 desktop application.

### Option B: Manual Command Line
```powershell
# 1. Create and activate virtual environment
python -m venv .venv
.venv\Scripts\activate

# 2. Install dependencies
pip install -r requirements.txt

# 3. Launch application
python main.py
```

---

## 7. Running Unit & Integration Tests

Execute the comprehensive automated test suite:
```powershell
pytest tests/ -v
```

Tests cover:
- Email syntax validation & phone normalization (`test_validator.py`)
- Multi-tier deduplication without merging distinct colleagues (`test_deduplication.py`)
- CSV UTF-8 BOM encoding, formula escaping, and file-locking recovery (`test_csv_service.py`)
- Frame change detection and auto-pause (`test_change_detector.py`)
- LM Studio markdown parsing and offline fallback (`test_lm_studio.py`)
- End-to-end extraction pipeline with synthetic card fixtures (`test_pipeline_mock.py`)

---

## 8. Standalone Windows Packaging (PyInstaller)

To build a standalone executable:
```cmd
build.bat
```
The resulting executable will be located at:
`dist\murtuzadeveloper Smart Leads\murtuzadeveloper Smart Leads.exe`

---

## 9. Security & Compliance Safeguards

- **Zero Covert Surveillance:** Screen capture only runs when the user explicitly clicks **Start Capture** or **Capture Now**, with continuous visual indicators.
- **Immediate Termination:** Global Stop button halts all background threads instantly.
- **Process Blocklist:** Automatically refuses to capture sensitive software (e.g., `1password.exe`, `bitwarden.exe`, `keepass.exe`, banking portals).
- **Credential Scrubbing:** Automatically redacts credit card numbers, passwords, and API tokens before passing text to the model.
- **Data Sovereignty:** All inference occurs locally on your machine via LM Studio; no screen data or contact details are sent to external cloud AI services.

---

## 10. Troubleshooting

| Issue | Resolution |
|---|---|
| **LM Studio: Offline badge** | Ensure LM Studio Local Server is running on port 1234. Verify URL in Settings is `http://127.0.0.1:1234/v1`. |
| **Model returns 400 on image** | Some model backends do not support multimodal image URLs. The client automatically falls back to text-only OCR mode. |
| **PermissionError on CSV write** | Excel has locked the file for editing. The application safely queues records in SQLite; close Excel or use the "Open CSV" button to view flushed records. |
| **High Memory Pressure** | Enable **Low-Memory Mode** in Settings to downscale screenshots to 1280px and limit concurrent model requests. |
