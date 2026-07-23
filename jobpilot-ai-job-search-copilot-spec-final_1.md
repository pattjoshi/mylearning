# Project 3: JobPilot AI — Resume-to-Offer Job Search Copilot

**Target users:** Job seekers doing an active, high-volume job search (like you, right now) who need matching, tailored resumes, outreach, and tracking in one place instead of five spreadsheets and browser tabs.

**Elevator pitch (for resume/interview):** "An end-to-end job search platform: it ingests my resume, finds and ranks the top 50 relevant jobs daily using AI-based semantic matching, generates ATS-optimized resumes tailored per job description as compiled LaTeX PDFs, sends templated cold outreach emails in rate-limited batches, and tracks every application through to interview outcome."

**Why this is a strong interview project (unlike a generic CRUD app):** it touches scheduled background jobs, resilient external API integration, AI/embeddings-based ranking, document generation (LaTeX compilation as a service — genuinely uncommon and memorable), email deliverability engineering, and a real security concern (LaTeX injection) that most candidates have never even heard of. This is a good project to lead with.

---

## 1. Tech Stack

| Layer | Technology | Notes |
|---|---|---|
| Frontend | Next.js 14+ (App Router) | Dashboard is mostly CSR/logged-in, but the landing page (if you add one) can be SSR — same "why Next.js" reasoning as SkillForge |
| Styling | Tailwind CSS + shadcn/ui | |
| State/data fetching | TanStack Query | |
| Backend | Node.js + Express.js | Separate service from Next.js |
| Database | PostgreSQL | |
| ORM | Prisma | |
| Vector store | **pgvector extension on the same Postgres** | Used for resume↔job semantic matching — no separate vector DB service needed |
| Auth | JWT + refresh tokens, bcrypt | Single-user or small-team tool — keep auth simple but correct |
| AI/LLM | **Google Gemini API** (free tier) | Resume parsing, JD understanding, resume tailoring, embeddings, match scoring/reasoning |
| Embeddings | Gemini `text-embedding-004` | Resume chunks + job description embeddings for cosine similarity ranking |
| **Job data sources (core, free, ToS-safe)** | **Adzuna API** (free, needs free app_id/app_key) + **Remotive API** (free, no key) + **Arbeitnow API** (free, no key) | Combined to get both remote-global listings and India-specific city listings — see Section 5.1 for why these three, why not scraping, and why not Google Jobs |
| **Job data sources (optional, off by default)** | **JSearch** (via RapidAPI) | Legitimate commercial API aggregating Google for Jobs + LinkedIn + Indeed + Glassdoor. A volume booster, not a replacement — see Section 5.1.1 |
| Resume parsing | `pdf-parse` (extract text from uploaded PDF resume) | |
| Resume generation | **LaTeX** (a proven ATS-friendly template, e.g. a Jake's-Resume-style single-column layout) compiled to PDF via **Tectonic** (self-contained LaTeX engine, ~300MB, no full TeXLive install needed) | Explained in detail in Section 5.4 |
| Email sending | **Brevo (formerly Sendinblue) free tier** — 300 emails/day, dedicated transactional email API, doesn't risk your personal Gmail account | Explained in Section 5.6 |
| Background jobs | BullMQ + Redis (self-hosted in Docker) | Daily job-aggregation cron, resume tailoring jobs, batch email sending with rate limiting |
| Scheduler | `node-cron` inside the Express API container, triggering a BullMQ job at 21:00 IST daily | Matches your stated "9:00 PM daily" requirement |
| File storage | AWS S3 (Free Tier: 5GB) | Uploaded resumes (original PDFs) + generated tailored resume PDFs |
| Hosting | AWS Free Tier only: Next.js on **AWS Amplify Hosting**, API + Redis + Tectonic in Docker on one **EC2 t3.micro**, Postgres on **RDS db.t3.micro** | Same proven pattern as your other two projects — Section 7 |
| CI/CD | GitHub Actions (free) | |
| Containerization | Docker + docker-compose | |
| Testing | Jest + Supertest | |
| **Observability (new)** | Structured logging (pino) + a lightweight `/api/admin/source-health` endpoint | Section 5.5 — cheap, high interview-signal addition |

---

## 2. Feature List (Prioritized)

### 🔴 Feature 1 — Daily Top-50 Job Matcher (Dynamic Location Split, Fault-Tolerant)

- User uploads resume once (PDF) → parsed and embedded, stored as their "matching profile"
- **Daily cron at 9:00 PM IST**: pulls fresh listings from all *enabled* sources (the core three, plus JSearch if turned on), filters to relevant tech roles, embeds each job description, runs cosine similarity against the user's resume embedding, ranks and stores the **top 50** for that day
- **Per-source isolation (new):** each source is fetched inside its own try/catch. If one source API is down, times out, or rate-limits you, the pipeline logs it, marks that source "degraded" for the run, and continues with whatever sources succeeded — a bad day from one of three-to-four APIs never fails the entire daily run. This is the single most realistic production failure mode for this feature, and handling it explicitly is a good story to tell in an interview.
- **Dynamic 70/30 split**: target ~70% remote, ~30% Bangalore/Pune/Hyderabad (or any other Indian tech city you configure) — but this ratio is a *target, not a hard rule*. If, on a given day, only 55 strong remote matches exist and 10 strong Bangalore matches exist, the algorithm fills what's genuinely available and adjusts the actual percentage accordingly, rather than padding with weak matches just to hit 70/30 exactly. Store both the *target* ratio and the *actual achieved* ratio per day — genuinely useful transparency, and a good thing to explain in an interview ("I designed it to prefer match quality over rigidly hitting the ratio").
- **24-hour freshness rule**: a job is only eligible to appear in "today's top 50" if it was posted or last-seen-updated by the source API within the last 24 hours. Older listings roll out automatically — implemented via a `firstSeenAt`/`lastSeenAt` timestamp updated every time the aggregator re-fetches, plus a scheduled query that expires stale entries from the "active" pool (not deleted — kept for historical analytics).
- **Cross-source dedup (new, previously hand-waved):** a normalized `dedupKey` (lowercased, whitespace-collapsed, punctuation-stripped `title + company + location`) catches the same job posted to two different sources, not just re-fetches of the same listing from one source — see Section 5.2.
- Each job in the list shows: match score %, why it matched (top overlapping skills — from the AI reasoning step), source, location, remote/onsite, and a direct apply link
- Manual "re-run matching now" button, rate-limited both to protect the Gemini free-tier quota and enforced via a Redis-tracked daily usage counter (Section 5.5)

### 🔴 Feature 2 — AI-Tailored ATS Resume Generator (LaTeX → PDF)

- User uploads their base resume (PDF) + pastes a job description
- Gemini analyzes both, and rewrites the resume content (bullet points, keyword emphasis, summary) to better match the JD's required skills and phrasing — **without fabricating experience**, only rephrasing/reordering/emphasizing what's genuinely in the original resume (an explicit, important instruction to bake into the prompt)
- Output is injected into a proven **ATS-friendly LaTeX template** (single column, no tables/graphics/columns that ATS parsers choke on, standard section headers: Experience, Education, Skills, Projects)
- LaTeX is compiled server-side to a downloadable PDF
- User can view/edit the generated LaTeX source directly before final compile (a genuinely nice feature for someone who knows LaTeX, and a good technical flex — "the user can see and tweak the exact source, not just a black-box PDF")
- Version history: every generated resume is saved and linked to the job/application it was tailored for

### 🔴 Feature 3 — Batch Cold Email Outreach

- User creates reusable **email templates** with merge fields (e.g. `{{recruiterName}}`, `{{companyName}}`, `{{jobTitle}}`)
- User uploads or pastes a list of recipient emails (CSV or manual entry), each optionally tagged with merge-field values, and optionally attaches the tailored resume PDF from Feature 2
- User selects a template + recipient list → previews a couple of rendered emails → sends as a **rate-limited batch job** (e.g. 1 email every 8–10 seconds via BullMQ, not all 50 at once) — this single detail is important both for staying within Brevo's free daily quota gracefully and for not looking like spam to receiving mail servers
- Every batch includes an auto-generated unsubscribe/opt-out note (basic ethical/compliance hygiene for cold outreach — worth having regardless of legal requirement)
- Tracks per-email status: queued → sent → failed (bounce), and basic open tracking if easily available via Brevo's webhook (optional, mark as 🟡)

### 🔴 Feature 4 — Job Application Tracker (Simple CRUD, Teal-style)

Modeled deliberately after **Teal's Job Application Tracker** (tealhq.com/tools/job-tracker) rather than a full Kanban pipeline engine — a spreadsheet-like table you add rows to, edit inline, and re-sort, not a project-management board. This is a better fit for the actual use case (fast daily upkeep during a job search) and noticeably less to build than the original Kanban design.

- **Standard CRUD, not a state machine:** Create a tracked application (from Feature 1's matched list with one click, or manually via "+ Add Job" for anything found outside the aggregator), Read it in a sortable/filterable table, Update any field inline, Delete if no longer relevant. No stage-transition rules or workflow engine — any field can be edited any time, the same way a spreadsheet works.
- **Table view is the primary (and only required) UI** — one row per application, editable in place:

| Column | Notes |
|---|---|
| Company + Title | Pulled from the linked `JobListing` if matched, or typed manually |
| Status | Simple dropdown: `Saved`, `Applied`, `Interviewing`, `Offer`, `Rejected`, `Ghosted` — a flat enum, not an ordered pipeline the user has to move through in sequence |
| Excitement rating | 1–5 stars or similar, mirroring Teal's "excitement level" — lets the user prioritize which saved jobs to actually pursue first, since not every saved job is equally wanted |
| Date applied | Optional date field |
| Resume used | Optional link to a `Resume` version from Feature 2 |
| Notes | A single free-text field per application (not per-stage) — good enough for "waiting on round 2," "recruiter said Friday," etc. |
| Source | Auto-filled if it came from Feature 1's matcher, blank if manually added |

- **Sorting/filtering**, not drag-and-drop: sort by date applied, status, or excitement; filter by status. This alone covers what most job seekers actually do with a tracker day-to-day, and is dramatically simpler to build and test than a Kanban board with per-stage history and keyboard-accessible drag-and-drop.
- **Quick-add from anywhere:** the same "🟡 Chrome-extension-style quick save bookmarklet" idea from the Extras list becomes more central here — a one-click "+ Add Job" (paste a URL or fill a small form) is the direct equivalent of Teal's browser-extension bookmarking, without needing an actual browser extension for a portfolio project.
- Simple analytics: applications this week, response rate %, interview conversion rate — still genuinely useful personally, still a good demonstrable "data" feature, and just as easy to compute from a flat status column as from a Kanban history.

**What was deliberately cut from the original Kanban design, and why:**
- No multi-stage `stageHistory` audit log — a single `notes` field and a `status` dropdown cover real daily usage without the extra data modeling.
- No drag-and-drop board, and therefore no keyboard-accessibility requirement for drag-and-drop (Section 12.3's original callout on this no longer applies).
- No automated "7+ days stale, nudge the user" reminder engine — genuinely nice-to-have, but adds a background job and a rule set for a feature Teal itself doesn't really do either (their tracker's value is being fast to update, not surveilling your inaction). If you want it back later, it's a small, isolated addition on top of this simpler model, not a redesign.

### 🟡 Extra Feature Ideas (build if time allows — these make it noticeably more "feature-heavy" without huge extra effort)

5. **Weekly digest email** — every Sunday evening, email yourself a summary: new top matches this week, applications pending follow-up, response rate trend. (Reuses the same BullMQ scheduler + Brevo integration you already built — very low marginal effort for a nice feature.)
6. **Resume A/B insight** — if you generate multiple tailored resume versions for similar JDs over time, surface which phrasing/keywords correlate with higher response rates (simple correlation, not deep ML — but a genuinely interesting, discussable feature).
7. **Chrome-extension-style "quick save" bookmarklet** — a tiny script/bookmarklet that lets you save a job URL you found manually (outside the aggregator) straight into the tracker. Shows range beyond the "obvious" three features.
8. **JD keyword gap report** — before generating a tailored resume, show a simple diff: "this JD mentions Kubernetes, Redis, and GraphQL — your resume doesn't currently mention these" — helps you decide what to genuinely add if you do have that experience, rather than blindly trusting the AI rewrite.

### ⚪ Roadmap Only

9. LinkedIn/Naukri integration (blocked by ToS — see Section 5.1)
10. Multi-user/team version, browser autofill for application forms, mobile app

---

## 3. Database Schema (PostgreSQL via Prisma + pgvector)

```prisma
model User {
  id            String   @id @default(uuid())
  name          String
  email         String   @unique
  passwordHash  String
  resumes       Resume[]
  applications  Application[]
  emailTemplates EmailTemplate[]
  emailBatches  EmailBatch[]
  createdAt     DateTime @default(now())
}

model Resume {
  id           String   @id @default(uuid())
  user         User     @relation(fields: [userId], references: [id])
  userId       String
  isBase       Boolean  @default(false)     // true = the original uploaded resume
  rawText      String                        // extracted text
  pdfUrl       String?                        // S3 url of the PDF (base or generated)
  latexSource  String?                        // for AI-tailored versions
  embedding    Unsupported("vector(768)")?    // for matching
  tailoredForJobId String?                     // null if this is the base resume
  createdAt    DateTime @default(now())
}

model JobListing {
  id            String   @id @default(uuid())
  source        String                        // "adzuna" | "remotive" | "arbeitnow" | "jsearch"
  externalId    String                         // id from the source API
  title         String
  company       String
  description   String
  location      String                         // "Remote" | "Bengaluru" | "Pune" | "Hyderabad" | ...
  isRemote      Boolean
  applyUrl      String
  embedding     Unsupported("vector(768)")?
  firstSeenAt   DateTime @default(now())
  lastSeenAt    DateTime @default(now())
  active        Boolean  @default(true)        // false once it rolls out of the 24h window
  dedupKey      String                         // normalized title+company+location hash — catches cross-source duplicates (Section 5.2)
  alsoSeenOn    Json?                          // nice-to-have: other sources this same job was also found on
  matches       JobMatch[]
  applications  Application[]

  @@unique([source, externalId])
  @@index([active, lastSeenAt])
  @@index([dedupKey])
}

model JobMatch {
  id           String     @id @default(uuid())
  user         User       @relation(fields: [userId], references: [id])
  userId       String
  job          JobListing @relation(fields: [jobId], references: [id])
  jobId        String
  matchScore   Float                          // cosine similarity, 0-1
  matchReasons Json                           // e.g. ["Node.js", "PostgreSQL", "3+ years backend"]
  matchDate    DateTime   @default(now())      // which day's top-50 run this belongs to

  @@index([userId, matchDate])
}

// Tracks per-run health of each job source — powers the source-health dashboard (Section 5.5)
model AggregationRun {
  id            String   @id @default(uuid())
  runDate       DateTime @default(now())
  sourceResults Json                           // e.g. { adzuna: { status: "ok", fetched: 340, ms: 1200 }, remotive: { status: "timeout", fetched: 0 } }
  totalActive   Int                            // jobs in the active pool after this run
  remotePct     Float                          // actual achieved remote/city ratio
  cityPct       Float
}

model EmailTemplate {
  id         String   @id @default(uuid())
  user       User     @relation(fields: [userId], references: [id])
  userId     String
  name       String
  subject    String                          // supports {{mergeFields}}
  body       String                          // supports {{mergeFields}}
  createdAt  DateTime @default(now())
}

model EmailBatch {
  id           String        @id @default(uuid())
  user         User          @relation(fields: [userId], references: [id])
  userId       String
  template     EmailTemplate @relation(fields: [templateId], references: [id])
  templateId   String
  status       BatchStatus   @default(QUEUED)
  recipients   EmailRecipient[]
  createdAt    DateTime      @default(now())
}

enum BatchStatus {
  QUEUED
  SENDING
  COMPLETED
  FAILED
}

model EmailRecipient {
  id          String      @id @default(uuid())
  batch       EmailBatch  @relation(fields: [batchId], references: [id])
  batchId     String
  email       String
  mergeData   Json                              // { recruiterName, companyName, jobTitle }
  status      RecipientStatus @default(PENDING)
  sentAt      DateTime?
  errorMsg    String?
}

enum RecipientStatus {
  PENDING
  SENT
  FAILED
  BOUNCED
}

// Simple CRUD tracker (Teal-style) — a flat status enum + one notes field,
// not a multi-stage pipeline with history. See Section 2, Feature 4.
model Application {
  id             String   @id @default(uuid())
  user           User     @relation(fields: [userId], references: [id])
  userId         String
  job            JobListing? @relation(fields: [jobId], references: [id])   // null if manually added, not matched
  jobId          String?
  companyName    String                          // set directly if manually added (no JobListing to pull from)
  jobTitle       String
  resumeUsed     Resume?  @relation(fields: [resumeId], references: [id])
  resumeId       String?
  status         ApplicationStatus @default(SAVED)
  excitement     Int?                            // 1-5 rating, mirrors Teal's "excitement level" — nullable, optional to set
  dateApplied    DateTime?
  notes          String?                         // single free-text field, not per-stage history
  source         String?                          // "matcher" | "manual" | null
  lastUpdatedAt  DateTime @updatedAt
  createdAt      DateTime @default(now())

  @@index([userId, status])
}

enum ApplicationStatus {
  SAVED
  APPLIED
  INTERVIEWING
  OFFER
  REJECTED
  GHOSTED
}
```

> Same pgvector note as the SkillForge project: define the `vector` columns via a raw SQL migration (`ALTER TABLE ... ADD COLUMN embedding vector(768);` after `CREATE EXTENSION vector;`), query similarity with `$queryRaw` using the `<=>` operator.

---

## 4. API Endpoints (REST)

```
Auth
  POST   /api/auth/signup
  POST   /api/auth/login
  POST   /api/auth/refresh

Resume
  POST   /api/resume/upload                 (base resume upload + parse + embed)
  GET    /api/resume/base
  POST   /api/resume/tailor                 (body: jobDescription or jobId → async job, returns jobId to poll)
  GET    /api/resume/:id                     (view generated LaTeX + PDF url)
  PUT    /api/resume/:id/latex               (user edits LaTeX before recompiling)
  POST   /api/resume/:id/recompile

Jobs
  GET    /api/jobs/today                     (today's top 50, with match score/reasons)
  POST   /api/jobs/refresh-now               (manual re-run, rate-limited)
  GET    /api/jobs/:id
  GET    /api/admin/source-health            (last N aggregation runs — per-source status/latency/volume)

Email
  POST   /api/email-templates
  GET    /api/email-templates
  POST   /api/email-batches                 (create + queue a batch send)
  GET    /api/email-batches/:id              (status per recipient)

Applications (simple CRUD — see Section 2, Feature 4)
  POST   /api/applications                  (create — from a matched job, or manually with company/title typed in)
  GET    /api/applications                  (table data — sortable/filterable by status, excitement, date applied)
  GET    /api/applications/:id
  PUT    /api/applications/:id               (update any field — status, excitement, notes, dateApplied, resumeId — inline edit, no stage-transition rules)
  DELETE /api/applications/:id
  GET    /api/applications/dashboard         (analytics: response rate, weekly counts)
```

---

## 5. The Hard Problems (be ready to explain all six)

### 5.1 Job Sourcing — Why These Three (Core) + One Optional, and Why Not Google Jobs

**Scraping LinkedIn or Naukri directly is explicitly against their Terms of Service**, and is also technically fragile (they change their HTML/anti-bot measures constantly, breaking your scraper unpredictably) — not a good foundation for a "production-level" project, and a bad thing to describe doing in an interview at a company that cares about legal risk.

**On Google Jobs specifically — investigated and rejected, here's the reasoning to have ready in an interview:** Google officially shut down its public Google Jobs API in **May 2021**. It doesn't exist today. What's marketed as a "Google Jobs API" by third-party vendors (Scrapingdog, SerpApi, Scrapfly, and similar) is a paid wrapper around scraping Google's search results page (the `ibp=htl;jobs` widget) — the same ToS/fragility problem already flagged for LinkedIn, just laundered through a vendor and now costing money too. Separately, Google Cloud's **Cloud Talent Solution** is a real, current Google product, but it's the *inverse* of what's needed here: it's for job boards to power their *own* search using Google's ML ranking over listings *they* supply — not a way to pull Google's aggregated job data out — and it's a paid enterprise GCP product with no meaningful free tier for this use case. **Verdict: don't use it, and know why not.** That's a stronger interview answer than pretending a Google Jobs API is still viable, or not knowing it was discontinued.

Instead, combine three legitimate, free, public APIs as the always-on core:
- **Adzuna** (`api.adzuna.com`) — free tier with `app_id`/`app_key`, supports country-scoped search (`country=in`), good for Bangalore/Pune/Hyderabad on-site listings
- **Remotive** (`remotive.com/api/remote-jobs`) — free, no API key required, global remote tech jobs
- **Arbeitnow** (`arbeitnow.com/api/job-board-api`) — free, no key required, remote + international listings, decent tech job coverage

This combination genuinely gets you enough volume to fill a real top-50 daily list, entirely within free, ToS-compliant usage.

#### 5.1.1 Optional 4th source: JSearch (off by default)

**JSearch** (via RapidAPI) is a legitimate commercial API — not scraping — that aggregates postings from Google for Jobs, LinkedIn, Indeed, Glassdoor, and more, since Google licenses that aggregation legitimately at the platform level. It's the closest available way to get "what Google Jobs shows" without touching Google's search results directly.

Trade-offs to weigh honestly (and be ready to explain if asked):
- Its free tier is meaningfully smaller than Adzuna/Remotive/Arbeitnow's, and RapidAPI quotas can change without much notice — verify current limits before relying on it as more than a supplement.
- Using it beyond the free tier costs money, which breaks the "100% free tier" story for the core project.
- It's a third-party single point of failure the way any 4th vendor is.

**Recommendation:** implement it as a **toggleable, isolated source** behind a feature flag (`JSEARCH_ENABLED=false` by default). This gives you a genuine "here's how I'd scale source coverage if I needed to" answer without committing the core project to a paid dependency or a shakier quota.

### 5.2 Cross-Source Deduplication

Storage-level dedup (`@@unique([source, externalId])`) only catches the same job re-fetched from the *same* source. It does nothing for the same job posted to, say, both Adzuna and Remotive. Fix:

1. On ingest, compute a `dedupKey` = normalized (lowercased, whitespace-collapsed, punctuation-stripped) `title + company + location`.
2. Before inserting a new listing, query existing *active* listings with the same `dedupKey` within the last 48 hours.
3. If a match is found, treat it as a duplicate: keep the first-seen listing, but merge source info into an `alsoSeenOn` `Json` field on that record (nice-to-have) rather than creating a second row.
4. This is O(1) per new listing thanks to `@@index([dedupKey])`, not an expensive fuzzy-match pass over the whole table — worth stating explicitly in an interview, since "how would this scale" is a near-certain follow-up.

### 5.3 Resume ↔ Job Matching (AI-Powered, Explained Simply)

1. On upload, the base resume's text is chunked (by section — Experience, Skills, Projects) and each chunk embedded via Gemini's embedding model, or simpler: embed the whole resume as one vector for portfolio-project scope (mention chunked-per-section as the "how would you scale/improve this" answer).
2. Each fetched job description is embedded the same way.
3. Cosine similarity (`pgvector`'s `<=>` operator) ranks jobs against the resume vector — this gives you a fast numeric score across potentially hundreds of fetched jobs without an LLM call per job (LLM calls are slower and would burn your free-tier quota fast at this volume).
4. For only the **top 50** (after the cheap vector-based ranking narrows it down), make **one Gemini call per job** (or a single batched call for all 50) asking it to return a short list of matching skills/reasons — this is what powers the "why this matched" explanation in the UI, done only for the shortlisted set to control API usage.

**This two-stage design (cheap vector math first, expensive LLM reasoning only on the shortlist) is a real, industry-standard RAG/ranking pattern and a strong thing to explain if asked "how would this scale to thousands of jobs."**

### 5.4 LaTeX Resume Generation — Compilation AND a Real Security Issue

**The generation flow:**
1. Gemini rewrites resume content based on the JD (explicit prompt instruction: rephrase/reorder/emphasize only, never invent new experience)
2. The rewritten content (bullet points, summary, skills list) gets injected into a fixed LaTeX template's placeholder sections
3. **Tectonic** (a self-contained LaTeX engine, much smaller than a full TeXLive install — fits comfortably in your EC2 free tier's storage and doesn't need a giant Docker image) compiles the `.tex` file to `.pdf` server-side
4. PDF uploaded to S3, URL returned to the user

**The real security issue — LaTeX injection:** LaTeX has special characters (`\`, `{`, `}`, `$`, `%`, `&`, `#`, `_`, `^`, `~`) that have command/control meaning in the document. If a job description or AI-generated text contains any of these unescaped and you insert it directly into the `.tex` source, at best the compile breaks, at worst — since LaTeX can execute shell commands via packages like `\write18` if enabled — a malicious JD (or the AI producing unexpected output) could inject LaTeX/shell commands that run on your server during compilation.

**The fix (both parts matter, mention both in an interview):**
- **Escape every piece of dynamic content** before inserting into the `.tex` template — replace each special character with its LaTeX-safe escaped form (e.g. `&` → `\&`, `%` → `\%`) using a small, well-tested escaping function (don't hand-roll this carelessly; get the character list right)
- **Disable shell-escape** (`\write18`) entirely when invoking Tectonic/the compiler — this closes off the "compiler runs arbitrary shell commands" attack surface regardless of what text sneaks through, and is a one-line compiler flag, not a difficult fix

This is a genuinely uncommon thing for a portfolio candidate to know and mention — it signals real security awareness, not just "I called an API."

### 5.5 Operational Resilience & Observability

A senior engineer reviewing this project will ask "what happens when a dependency fails at 9pm and you're not watching?" Answer that before they ask:

- **Per-source try/catch isolation** in the aggregation job — one source's failure is logged and skipped, not fatal to the run (Section 2, Feature 1).
- **`AggregationRun` record per daily run** — stores per-source status/latency/volume and the actual achieved remote/city split. Turns "did today's job run work?" from a database-diving exercise into one query.
- **`/api/admin/source-health` endpoint** — surfaces the last N runs. Cheap to build (it's just reading `AggregationRun`), disproportionately useful for demoing operational maturity, not just features.
- **Quota guardrails, made explicit:** track daily Gemini embedding + reasoning call counts in Redis with a TTL-based counter; if a day's usage approaches the free-tier ceiling, the manual "re-run matching now" button gets disabled with a clear message, rather than silently failing or silently exceeding a paid threshold.
- **Minimal but real alerting:** if *all* sources fail in a single run (vs. just one), send yourself an email via the existing Brevo integration — near-zero marginal cost given the plumbing already exists, and it prevents a silent, multi-day matching outage during an active job search, exactly the failure mode that would hurt you most as the actual user of this tool.

### 5.6 Batch Email Sending Without Looking Like Spam

- Send through **BullMQ with a rate limiter** (e.g. `limiter: { max: 1, duration: 8000 }` — one email per 8 seconds) rather than firing all recipients at once. Both because Brevo's free tier has a daily cap you don't want to blow through in one burst, and because receiving mail servers are more likely to flag a sudden burst of near-identical emails as spam than a slow, human-paced trickle.
- Personalize beyond just the name — merge fields for company/job title reduce the "obviously mass-blasted" pattern that spam filters key on.
- Always include a genuine unsubscribe/opt-out line — good practice regardless of exact legal requirement in your jurisdiction, and a detail worth having ready if asked about your approach to cold outreach ethics in an interview.

---

## 6. AI Prompt Examples

**Resume tailoring prompt:**
```
You are helping tailor a resume to a specific job description. You must
ONLY rephrase, reorder, or emphasize content that already exists in the
candidate's original resume below. Do NOT invent new skills, employers,
projects, or experience that isn't present in the original.

Original resume:
{resume_text}

Job description:
{job_description}

Return the tailored content as JSON with these fields: summary, skills
(array), experience (array of {company, title, bullets: []}), projects
(array of {name, bullets: []}).
```

**Job match reasoning prompt (batched for the top 50):**
```
For each job below, given this candidate resume summary, list up to 4
short reasons why it's a good match (specific overlapping skills or
experience), or say "Weak match" if the overlap is thin. Return as JSON
array in the same order as the input jobs.

Resume summary: {resume_summary}
Jobs: {list_of_50_job_descriptions}
```

---

## 7. AWS Architecture — 100% Free Tier

Same proven pattern as your other two projects:

```
                     ┌────────────────────────┐
                     │  AWS Amplify Hosting     │  Next.js frontend
                     │  (Always Free tier)      │  (dashboard)
                     └────────────────────────┘

                     ┌────────────────────────┐
                     │  EC2 t3.micro             │
                     │  (Free Tier: 750 hrs/mo)  │
                     │                            │
                     │  ┌──────────────────────┐ │
                     │  │ Nginx reverse proxy    │ │
                     │  └──────────┬─────────────┘ │
                     │             │                │
                     │  ┌──────────▼─────────────┐ │
                     │  │ Docker: Express API      │ │
                     │  │ (includes Tectonic for   │ │
                     │  │  LaTeX compilation)       │ │
                     │  └──────────┬─────────────┘ │
                     │             │                │
                     │  ┌──────────▼─────────────┐ │
                     │  │ Docker: Redis (BullMQ)    │ │
                     │  └───────────────────────────┘ │
                     └───────────────┬───────────────┘
                                     │
                     ┌───────────────▼────────────────┐
                     │  RDS Postgres db.t3.micro          │
                     │  + pgvector, Single-AZ, 20GB          │
                     │  (Free Tier: 750 hrs/mo, 12 months)   │
                     └────────────────────────────────────────┘

                     ┌──────────────────────────┐
                     │  S3 (Free Tier: 5GB, 12mo) │  resume PDFs
                     └──────────────────────────┘

External (all free tier / no card): Gemini API, Adzuna API, Remotive API,
Arbeitnow API, Brevo email API. JSearch API key (RapidAPI) added only if
JSEARCH_ENABLED=true.
```

**Notable addition vs. your other two projects:** Tectonic (the LaTeX engine) lives inside the same Express API Docker container/image — no separate service needed, but it does make that Docker image noticeably larger (~300-400MB extra), which is fine on EC2/S3 but worth knowing when you're optimizing image build time in CI/CD.

Same DNS/Route 53/12-month caveats as your other two projects apply identically here — no need to repeat, you already have that story down.

---

## 8. Docker Setup

**`Dockerfile` (backend, includes Tectonic):**
```dockerfile
FROM node:20-slim AS base
# Install Tectonic (self-contained LaTeX engine) - much lighter than full texlive
RUN apt-get update && apt-get install -y wget && \
    wget -qO- https://drop-sh.fullyjustified.net | sh && \
    mv tectonic /usr/local/bin/tectonic && \
    apt-get remove -y wget && apt-get autoremove -y

WORKDIR /app
COPY package*.json ./
RUN npm ci
COPY . .
RUN npx prisma generate
EXPOSE 4000
CMD ["node", "src/server.js"]
```

**`docker-compose.yml` (local dev):**
```yaml
version: "3.9"
services:
  api:
    build: ./backend
    ports: ["4000:4000"]
    env_file: ./backend/.env
    depends_on: [postgres, redis]
  postgres:
    image: pgvector/pgvector:pg16
    environment:
      POSTGRES_USER: jobpilot
      POSTGRES_PASSWORD: jobpilot_pass
      POSTGRES_DB: jobpilot_db
    ports: ["5432:5432"]
    volumes: ["pgdata:/var/lib/postgresql/data"]
  redis:
    image: redis:7-alpine
    ports: ["6379:6379"]
volumes:
  pgdata:
```

---

## 9. CI/CD Pipeline (GitHub Actions) — Free Tier

1. **On PR:** lint, Jest unit tests, Supertest API tests, including:
   - a test that feeds deliberately special-character-laden input through the LaTeX escaping function and asserts it compiles safely
   - a test that simulates a single job source throwing/timing out and asserts the aggregation run still completes using the other sources' data — the direct test for the Section 5.5 resilience claim (write it, don't just claim it)
2. **On merge to `main`:**
   - Build backend Docker image in the runner
   - `prisma migrate deploy` against RDS
   - SSH deploy to EC2 (`appleboy/ssh-action`), `docker-compose up -d --build`
   - Amplify auto-deploys the frontend on push (built-in, no extra step)
   - Smoke test: hit `/api/health`, and a dedicated `/api/health/latex` endpoint that compiles a trivial test document to confirm Tectonic still works post-deploy (a nice, specific health check worth having given how central LaTeX compilation is to this project)

---

## 10. Security Checklist

- Passwords hashed with bcrypt; JWT access (short-lived) + httpOnly refresh cookie
- Input validation (Zod) on every endpoint, especially resume upload (file type + size limits — reject anything that isn't a genuine PDF)
- **LaTeX escaping on every dynamic field inserted into a `.tex` template — no exceptions** (Section 5.4)
- **Shell-escape disabled** on the LaTeX compiler invocation
- Rate limiting on: `/api/jobs/refresh-now` (protect Gemini quota), `/api/email-batches` creation (protect Brevo quota + prevent abuse), auth endpoints (brute-force protection)
- Gemini/Adzuna/Brevo (and JSearch, if enabled) API keys stored in **AWS SSM Parameter Store** (free), never committed — no special-casing a 4th vendor's secret handling
- CORS restricted to your frontend origin, Helmet.js headers
- Uploaded resume PDFs scanned for basic file-type validity (magic-byte check, not just extension) before being handed to `pdf-parse`

---

## 11. Testing Strategy

- **Unit tests:** LaTeX escaping function (feed it every special character and assert correct escaped output), match-score calculation, 24-hour freshness expiry logic, dynamic 70/30 ratio calculation under varying "available matches" scenarios, `dedupKey` normalization (case folding, punctuation stripping, whitespace collapsing) and cross-source match-then-merge logic
- **Integration tests:** full resume-tailoring flow with a mocked Gemini response, LaTeX compile-and-validate (assert a real PDF byte stream comes back), batch email queue processes at the configured rate limit, aggregation job with one source mocked to fail — assert the run still produces a top-50 list from the remaining sources and that the failure is recorded in `AggregationRun`, not silently swallowed
- **E2E (Playwright):** upload resume → see today's top 50 → generate a tailored resume for one job → mark it "Applied" → see the row appear, correctly populated, in the application tracker table

---

## 12. UI/UX Design System

**Direction:** corporate/professional — this is a tool you'll personally rely on daily during an active job search, so clarity and low-friction data entry matter more than visual flair. Think "a calm, focused command center," not a marketing site.

### 12.1 Design Tokens

| Token | Hex | Use |
|---|---|---|
| `--ink-900` | `#171923` | Primary text |
| `--slate-600` | `#4A5568` | Secondary text |
| `--surface-0` | `#FFFFFF` | Cards |
| `--surface-50` | `#F7F8FA` | App background |
| `--border` | `#E2E4E9` | Dividers |
| `--brand-700` | `#1E4B8F` | Primary actions, nav — a steady, focused blue distinct from both other projects' palettes (avoids the three projects looking like a matching set) |
| `--brand-100` | `#E4ECF9` | Tinted backgrounds |
| `--match-high` | `#1E8E5A` | Match score 80%+ |
| `--match-mid` | `#B5730A` | Match score 50-79% |
| `--match-low` | `#8A8F98` | Match score below 50% (muted, not alarming — it's just a low score, not an error) |
| `--danger` | `#C0392B` | Rejected applications, failed sends |

**Typography:** Inter throughout (headings 600-700, body 400-500) with `tabular-nums` for match-score percentages and dashboard counts — same reasoning as Project 1, this is a data-dense dashboard tool.

### 12.2 Key Screens

1. **Today's Top 50** — a scannable list/card view, match score as a colored badge (using the tokens above) + a short "why this matched" chip list, one-click "Save" or "Applied" action per card, filter by remote/city
2. **Resume Tailor** — split view: JD input on the left, live-updating LaTeX source + rendered PDF preview on the right (this split-pane, "see the source and the output together" layout is the signature element of this project — it makes the LaTeX-generation feature feel powerful and transparent rather than a black box)
3. **Email Batch Composer** — template picker → recipient list (table, editable merge fields inline) → a clear preview of exactly what recruiter #1 and recruiter #2 will actually receive before sending → a visible, honest queue/progress indicator once sending starts (shows the rate-limited pacing happening — "sent 4 of 50, next in 6s" builds trust that it's not just blasting spam)
4. **Application Tracker (Table, Teal-style)** — a spreadsheet-like table, one row per application: company/title, status dropdown, excitement rating, date applied, linked resume version, notes — all editable inline, sortable/filterable by column, "+ Add Job" for anything found outside the aggregator. No drag-and-drop, no per-stage history — just fast, low-friction CRUD, matching how tools like Teal's job tracker actually get used day-to-day
5. **Dashboard/Analytics** — simple, honest charts: applications per week, response rate, funnel from Applied → Interview → Offer
6. **Source Health (internal/admin)** — a simple internal-only table reading `/api/admin/source-health`: source name, last run status, jobs fetched, latency. Not part of the design system proper — this is a debugging tool for you, not a user-facing screen — but worth having for demos.

### 12.3 Static/Performance & Accessibility

- Dashboard is CSR (no SEO need); if you add a public landing/marketing page later, that alone would be SSR on Next.js
- The Resume Tailor split-pane PDF preview should lazy-render (don't re-compile LaTeX on every keystroke — debounce, or require an explicit "Preview" click) to avoid hammering the Tectonic compiler
- Application Tracker table fully keyboard-operable (inline edit via keyboard focus + Enter/Tab, not mouse-only — no drag-and-drop to make accessible since the table replaced the Kanban board)
- Color is never the only signal for match score or application status — pair with text/icons

---

## 13. Suggested Build Order (feature-heavy — budget realistically, this is bigger than your other two projects)

1. Days 1-2: Auth, Postgres/Prisma + pgvector setup, resume upload + parsing + embedding
2. Days 3-5: Job aggregation — **build the three core sources with per-source try/catch isolation from day one** (don't bolt on resilience later), dedup via `dedupKey`, embedding, cosine-similarity ranking, 24h freshness logic, dynamic 70/30 split, node-cron scheduling, `AggregationRun` logging — **budget the most time here, it's the most moving parts of any single feature across all three of your projects**
3. Day 5.5 (small, high-value): `/api/admin/source-health` endpoint + the all-sources-failed email alert — cheap now, expensive to retrofit later
4. Days 6-7: AI resume tailoring + LaTeX template + Tectonic compilation + escaping/security (Section 5.4 — do not skip the escaping while "just getting it working")
5. Days 8-9: Email templates + Brevo integration + BullMQ rate-limited batch sending
6. Days 10-11: Application tracker (simple CRUD table, Teal-style — see Section 2, Feature 4) + dashboard analytics — noticeably faster to build than a Kanban pipeline would have been
7. Day 12: Docker + docker-compose local setup
8. Day 12.5 (optional, only if time allows): JSearch integration behind a feature flag — genuinely optional, don't let it delay the core build
9. Days 13-14: Deploy to AWS Free Tier, GitHub Actions CI/CD
10. Remaining days: polish UI per Section 12, write tests per Section 11, README with architecture diagram (include the source-resilience design — it's a good diagram), demo video, seed realistic demo data (a real base resume, a few real job descriptions) so the demo looks convincing rather than empty

---

## Appendix: One-line answers for likely interview follow-ups

- *"Why not use Google's Jobs API?"* → "It was shut down in 2021; what's sold as one now is paid scraping of Google's search results, which has the same ToS risk I already avoided for LinkedIn — so I looked at Cloud Talent Solution too, but that's for publishing listings, not consuming them, and isn't free."
- *"What happens if Adzuna is down during your 9pm run?"* → "The aggregation job isolates each source in its own try/catch, logs a degraded status to an `AggregationRun` record, and still produces a top-50 from whatever sources succeeded — it doesn't fail the whole day over one dependency."
- *"How do you avoid the same job showing up twice from two sources?"* → "A normalized `dedupKey` on title+company+location, indexed, checked before insert — O(1) per job, not a fuzzy pass over the whole table."
- *"How would you add more job volume later?"* → "JSearch is already wired in behind a feature flag as an aggregator over Google for Jobs/LinkedIn/Indeed/Glassdoor — legitimate API, not scraping — I just kept it optional because its free tier is smaller and I didn't want a paid dependency in the core free-tier build."
- *"How would this scale to thousands of jobs?"* → "Two-stage ranking: cheap pgvector cosine similarity narrows the field first, expensive Gemini reasoning calls only run on the shortlisted top 50 — the same pattern real RAG/ranking systems use."
