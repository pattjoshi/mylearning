# Project 2: SkillForge — AI-Powered Learning Management System

**Target users:** Instructors who want to create/sell courses, students who want to learn with AI-assisted support.

**Elevator pitch (for resume/interview):** "A full LMS with an AI layer built on RAG (Retrieval-Augmented Generation) — students get a doubt-solving chatbot that answers strictly from the course's own content, and instructors get AI-generated quizzes and lesson summaries from their uploaded material."

**Why Next.js here specifically:** course landing/marketing pages benefit from SSR/SEO (a course page ranking on Google is a real business need, unlike the salon dashboard). Also gives you a legitimate story for choosing Next.js over plain React — interviewers will ask "why Next.js for this and React for the other," and "SEO for public course pages + SSR for faster first load, vs. a pure logged-in dashboard tool that doesn't need SEO" is a genuinely correct, senior-level answer.

---

## 1. Tech Stack

| Layer | Technology | Notes |
|---|---|---|
| Frontend | Next.js 14+ (App Router) | SSR for public course pages, CSR for logged-in dashboard/learning views |
| Styling | Tailwind CSS + shadcn/ui | |
| State/data fetching | React Query (TanStack Query) + Server Actions where suitable | |
| Backend | Node.js + Express.js (separate service from Next.js) | Keep API separate — cleaner for a portfolio project to show backend skills distinctly |
| Database | PostgreSQL | |
| ORM | Prisma | |
| Vector store | **pgvector extension on the same Postgres** | Avoids needing a separate Pinecone account; a strong, current, "I know how to do RAG without extra infra" answer |
| Auth | JWT + refresh tokens, Google OAuth (NextAuth.js on frontend, or custom) | |
| AI/LLM | Google Gemini API (generous free tier) or OpenAI API | Used for: quiz generation, summarization, RAG chat responses |
| Embeddings | Gemini `text-embedding-004` or OpenAI `text-embedding-3-small` | |
| File storage | AWS S3 | Videos, PDFs, course thumbnails |
| Video | Upload to S3 + serve via CloudFront signed URLs, OR embed YouTube unlisted for MVP simplicity | Signed URLs = more "senior" but more work; mention both, pick based on time |
| Background jobs | BullMQ + Redis | Quiz generation, summarization, embedding generation — all async so UI never blocks |
| Real-time (optional) | Socket.io | Streaming AI chat responses token-by-token |
| Hosting | AWS: Next.js on Amplify or ECS Fargate, API on ECS Fargate, Postgres on RDS | Details in Section 7 |
| CI/CD | GitHub Actions | |
| Containerization | Docker + docker-compose | |
| PDF processing | `pdf-parse` (text extraction) | To feed lesson PDFs into AI features |
| Testing | Jest + Supertest, React Testing Library, Playwright | |

---

## 2. Feature List (Prioritized)

### 🔴 Must-Build — Core LMS

1. **Auth & roles** — `INSTRUCTOR`, `STUDENT`, `ADMIN`. Google OAuth + email/password.
2. **Course creation (instructor)** — course → modules → lessons hierarchy. Lesson types: video, text/article, PDF attachment, quiz.
3. **Course catalog (public, SSR)** — `/courses` and `/courses/[slug]` pages, server-rendered for SEO, with search/filter by category.
4. **Enrollment** — student enrolls (free for MVP; mark payment as roadmap item).
5. **Learning player** — video/text player with **progress tracking** (mark lesson complete, resume from last position for video).
6. **Quiz engine** — MCQ quizzes per module, auto-graded, stores attempt history and scores.
7. **Student dashboard** — enrolled courses, % progress per course, quiz scores.
8. **Instructor dashboard** — enrollments count, average completion rate, average quiz scores per course.
9. **Certificate generation** — auto-generate a PDF certificate on 100% course completion.

### 🔴 Must-Build — AI Features (this is the differentiator, do not skip these)

10. **AI Quiz Generator**
    - Instructor uploads a lesson's PDF or pastes lesson text.
    - Backend extracts text (`pdf-parse`) → sends to LLM with a structured prompt requesting N multiple-choice questions with 4 options + correct answer, **returned strictly as JSON**.
    - Parse and validate the JSON response, let instructor review/edit before publishing.
    - Runs as a background job (BullMQ) so the instructor isn't stuck waiting on a slow API call.

11. **AI Lesson Summarizer**
    - For every text/PDF lesson, auto-generate a 3-5 bullet-point summary + key takeaways, shown to students as a collapsible "Quick Summary" box above the lesson.

12. **AI Doubt-Solving Chatbot (RAG) — your flagship feature**
    - **Ingestion pipeline:** when a lesson is published, its content (transcript/text/PDF text) is chunked (e.g. 500-token chunks with slight overlap) → each chunk sent to the embeddings API → store `(chunk_text, embedding_vector, lesson_id)` in Postgres using `pgvector`.
    - **Query pipeline:** student asks a question in the course chat → embed the question → run a cosine-similarity search (`pgvector`'s `<=>` operator) against chunks **scoped to that course only** → take top-k (e.g. 4) most relevant chunks → build a prompt like:
      ```
      You are a helpful tutor for this course. Answer the student's question
      using ONLY the context below. If the answer isn't in the context, say
      you don't have that information in the course material.

      Context:
      {retrieved_chunks}

      Student question: {question}
      ```
    - Send to LLM, stream response back to the student (Socket.io or Next.js streaming response).
    - Store chat history per student per course.
    - **This is the feature to be able to whiteboard in an interview.** Know exactly why scoping matters (prevents hallucination and off-topic answers), why chunking size matters (too big = irrelevant context included, too small = loses meaning), and why you chose pgvector over a dedicated vector DB (simplicity, one less service to run, good enough at portfolio scale — but mention Pinecone/Weaviate as the answer for a "how would you scale this" follow-up).

### 🟡 Build If Time Allows

13. Personalized recommendations — after a quiz, recommend which earlier lesson to revisit based on which questions were wrong (map questions → source lesson chunks)
14. AI-generated flashcards from lesson content
15. Instructor analytics: which lessons have the most doubt-chat questions (signals confusing content)

### ⚪ Roadmap Only

16. Course purchase/payments (Razorpay/Stripe)
17. Live classes (WebRTC/Zoom SDK integration)
18. Discussion forums / peer Q&A
19. Mobile app

---

## 3. Database Schema (PostgreSQL via Prisma + pgvector)

```prisma
model User {
  id           String   @id @default(uuid())
  name         String
  email        String   @unique
  passwordHash String?
  googleId     String?
  role         Role     @default(STUDENT)
  createdCourses Course[] @relation("Instructor")
  enrollments  Enrollment[]
  quizAttempts QuizAttempt[]
  chatMessages ChatMessage[]
  createdAt    DateTime @default(now())
}

enum Role {
  ADMIN
  INSTRUCTOR
  STUDENT
}

model Course {
  id           String   @id @default(uuid())
  title        String
  slug         String   @unique
  description  String
  thumbnailUrl String?
  category     String
  instructor   User     @relation("Instructor", fields: [instructorId], references: [id])
  instructorId String
  modules      Module[]
  enrollments  Enrollment[]
  published    Boolean  @default(false)
  createdAt    DateTime @default(now())
}

model Module {
  id         String   @id @default(uuid())
  course     Course   @relation(fields: [courseId], references: [id])
  courseId   String
  title      String
  order      Int
  lessons    Lesson[]
}

model Lesson {
  id            String       @id @default(uuid())
  module        Module       @relation(fields: [moduleId], references: [id])
  moduleId      String
  title         String
  type          LessonType
  contentText   String?      // article text / extracted PDF text
  videoUrl      String?
  pdfUrl        String?
  order         Int
  summary       String?      // AI-generated
  quiz          Quiz?
  chunks        ContentChunk[]  // for RAG
  progress      LessonProgress[]
}

enum LessonType {
  VIDEO
  ARTICLE
  PDF
}

model ContentChunk {
  id          String                 @id @default(uuid())
  lesson      Lesson                 @relation(fields: [lessonId], references: [id])
  lessonId    String
  courseId    String                 // denormalized for fast scoped search
  chunkText   String
  embedding   Unsupported("vector(768)")   // pgvector column; dimension depends on embedding model
  createdAt   DateTime               @default(now())

  @@index([courseId])
}

model Quiz {
  id         String       @id @default(uuid())
  lesson     Lesson       @relation(fields: [lessonId], references: [id])
  lessonId   String       @unique
  questions  QuizQuestion[]
  aiGenerated Boolean     @default(false)
}

model QuizQuestion {
  id            String   @id @default(uuid())
  quiz          Quiz     @relation(fields: [quizId], references: [id])
  quizId        String
  questionText  String
  options       Json      // ["Option A", "Option B", "Option C", "Option D"]
  correctOption Int       // index into options
}

model QuizAttempt {
  id         String   @id @default(uuid())
  user       User     @relation(fields: [userId], references: [id])
  userId     String
  quiz       Quiz     @relation(fields: [quizId], references: [id])
  quizId     String
  score      Int
  answers    Json
  attemptedAt DateTime @default(now())
}

model Enrollment {
  id         String   @id @default(uuid())
  user       User     @relation(fields: [userId], references: [id])
  userId     String
  course     Course   @relation(fields: [courseId], references: [id])
  courseId   String
  enrolledAt DateTime @default(now())
  completedAt DateTime?

  @@unique([userId, courseId])
}

model LessonProgress {
  id          String   @id @default(uuid())
  lesson      Lesson   @relation(fields: [lessonId], references: [id])
  lessonId    String
  userId      String
  completed   Boolean  @default(false)
  videoPositionSec Int? 

  @@unique([lessonId, userId])
}

model ChatMessage {
  id         String   @id @default(uuid())
  user       User     @relation(fields: [userId], references: [id])
  userId     String
  courseId   String
  role       String    // "user" | "assistant"
  content    String
  createdAt  DateTime @default(now())

  @@index([userId, courseId])
}
```

> Note: Prisma doesn't natively support `vector` type yet — you'll define it via a raw migration (`CREATE EXTENSION vector;` + `ALTER TABLE ... ADD COLUMN embedding vector(768)`) and query it with `$queryRaw` for the similarity search. This is worth knowing and explaining — it shows you understand when an ORM's abstraction needs to be stepped around.

---

## 4. API Endpoints (REST)

```
Auth
  POST   /api/auth/signup
  POST   /api/auth/login
  POST   /api/auth/google
  POST   /api/auth/refresh

Courses
  GET    /api/courses                    (public catalog, filter/search)
  GET    /api/courses/:slug              (public detail)
  POST   /api/courses                    (instructor)
  PUT    /api/courses/:id
  POST   /api/courses/:id/publish

Modules & Lessons
  POST   /api/courses/:id/modules
  POST   /api/modules/:id/lessons
  POST   /api/lessons/:id/upload         (video/pdf to S3)
  PUT    /api/lessons/:id/progress       (mark complete / save video position)

Quizzes
  POST   /api/lessons/:id/quiz/generate-ai   (async — returns jobId, poll or websocket for result)
  POST   /api/quizzes/:id/questions          (instructor manual add/edit)
  POST   /api/quizzes/:id/attempt            (student submits answers)
  GET    /api/quizzes/:id/attempts/me

Enrollment
  POST   /api/courses/:id/enroll
  GET    /api/me/enrollments

AI Features
  POST   /api/lessons/:id/summarize          (async job — generates summary)
  POST   /api/courses/:id/chat               (RAG chat — send question, get answer)
  GET    /api/courses/:id/chat/history

Dashboard
  GET    /api/instructor/dashboard/:courseId
  GET    /api/student/dashboard
```

---

## 5. RAG Pipeline — Detailed Flow (Your Flagship Feature)

**Ingestion (runs when instructor publishes a lesson):**
1. Extract raw text: video → transcript (if you have one) / article → `contentText` / PDF → `pdf-parse` extraction
2. Chunk text: split into ~500-token pieces with ~50-token overlap (use a simple sentence-aware splitter, not a hard character cut)
3. For each chunk: call embeddings API → get a vector (e.g. 768 dimensions) → insert into `ContentChunk` table
4. This whole step runs as a **BullMQ background job** — instructor gets a "processing" status, doesn't wait

**Query (student asks a question):**
1. Student sends question via chat UI, scoped to a specific `courseId`
2. Backend embeds the question using the same embedding model
3. Run similarity search:
   ```sql
   SELECT chunk_text, 1 - (embedding <=> $1) AS similarity
   FROM "ContentChunk"
   WHERE "courseId" = $2
   ORDER BY embedding <=> $1
   LIMIT 4;
   ```
4. Build the final prompt (system instructions + retrieved chunks + chat history + question)
5. Call LLM, stream tokens back to frontend as they arrive (Server-Sent Events or Socket.io)
6. Save both the question and answer to `ChatMessage` for history

**Things to be ready to explain in an interview:**
- Why RAG instead of fine-tuning: cheaper, instantly updatable when course content changes, no retraining needed
- Why scope by `courseId`: prevents answers leaking content from other courses, keeps answers relevant
- Chunk size trade-off: too small loses context, too big dilutes relevance and wastes tokens
- What happens when no relevant chunk is found (similarity below a threshold) → the prompt explicitly tells the LLM to say "not in course material" rather than hallucinate
- Cost control: cache repeated/similar questions, limit chat history length sent per request

---

## 6. AI Prompt Examples (for reference/documentation)

**Quiz generation prompt (send with lesson text):**
```
You are creating a quiz for an online course lesson. Based on the lesson
content below, generate exactly 5 multiple-choice questions. Each question
must have 4 options with exactly one correct answer. Return ONLY valid JSON,
no other text, in this exact format:

[
  {
    "question": "...",
    "options": ["...", "...", "...", "..."],
    "correctIndex": 0
  }
]

Lesson content:
{lesson_text}
```

**Summary prompt:**
```
Summarize the following lesson content into 3-5 concise bullet points
capturing the key takeaways a student should remember. Return plain text
bullet points only.

Lesson content:
{lesson_text}
```

---

## 7. AWS Architecture

```
                     ┌─────────────────┐
                     │   Route 53 (DNS) │
                     └────────┬─────────┘
                              │
                ┌─────────────┴──────────────┐
                │                             │
      ┌─────────▼─────────┐        ┌──────────▼──────────┐
      │  Next.js frontend   │        │  Express API (ECS)   │
      │  (Amplify Hosting    │       │  behind ALB           │
      │  or ECS Fargate)     │        └──────────┬───────────┘
      └──────────────────────┘                   │
                                     ┌─────────────┼─────────────┐
                                     │             │              │
                            ┌────────▼───────┐ ┌───▼────┐ ┌───────▼────────┐
                            │ RDS Postgres     │ │ Redis  │ │ S3 (videos,    │
                            │ + pgvector        │ │(BullMQ)│ │ PDFs, thumbs)  │
                            └───────────────────┘ └────────┘ └─────────────────┘
                                                                        │
                                                              ┌─────────▼─────────┐
                                                              │   CloudFront CDN   │
                                                              │ (signed URLs for   │
                                                              │  video streaming)  │
                                                              └────────────────────┘

External: Gemini/OpenAI API (called from backend only — never expose API key to frontend)
```

**Services and why:**
- **AWS Amplify Hosting** for Next.js — handles SSR out of the box, simpler than configuring Fargate for SSR. Alternative: ECS Fargate with a Node server running `next start` if you want everything in one deployment paradigm as Project 1 for consistency (a reasonable "senior" trade-off to mention).
- **RDS Postgres with pgvector extension** — confirm the RDS Postgres version supports pgvector (PG 15+ typically does)
- **S3 + CloudFront with signed URLs** — protects paid/private video content from being accessed by non-enrolled users directly via public URL
- **ElastiCache Redis** — BullMQ job queue for embedding generation, quiz generation, summarization (all slow LLM calls, all async)
- **Secrets Manager** — Gemini/OpenAI API key, JWT secret, DB credentials

**Budget-friendly alternative:** single EC2 instance running both Next.js (via `next start` behind PM2) and the Express API in Docker containers, RDS free-tier Postgres with pgvector, S3 for storage. Same honest note as Project 1: design for the scalable version, deploy the cost-optimized version.

---

## 8. Docker Setup

**`docker-compose.yml` (local dev, both projects can share this pattern):**
```yaml
version: "3.9"
services:
  frontend:
    build: ./frontend
    ports: ["3000:3000"]
    env_file: ./frontend/.env.local
  api:
    build: ./backend
    ports: ["4000:4000"]
    env_file: ./backend/.env
    depends_on: [postgres, redis]
  postgres:
    image: pgvector/pgvector:pg16
    environment:
      POSTGRES_USER: skillforge
      POSTGRES_PASSWORD: skillforge_pass
      POSTGRES_DB: skillforge_db
    ports: ["5432:5432"]
    volumes: ["pgdata:/var/lib/postgresql/data"]
  redis:
    image: redis:7-alpine
    ports: ["6379:6379"]
volumes:
  pgdata:
```

> Note the Postgres image: `pgvector/pgvector:pg16` — a Postgres image with the pgvector extension pre-installed, so `CREATE EXTENSION vector;` works immediately in local dev.

---

## 9. CI/CD Pipeline (GitHub Actions)

1. **On PR:** lint, unit tests (Jest), API integration tests against a Postgres service container with pgvector
2. **On merge to `main`:**
   - Build and push Docker images (frontend + backend) to ECR
   - Run `prisma migrate deploy`
   - Deploy backend: update ECS service
   - Deploy frontend: trigger Amplify build (or push image + update ECS if using that route)
   - Run a smoke test hitting `/api/health` and the homepage post-deploy

---

## 10. Security & Cost Considerations Specific to AI Features

- **Never expose the Gemini/OpenAI API key to the frontend** — all AI calls go through your backend
- **Rate-limit AI endpoints** per user (e.g. max 20 chat questions/hour) to control API cost and prevent abuse
- **Cache identical/near-identical questions** (e.g. hash the question text) to avoid redundant LLM calls
- **Set max token limits** on responses to control cost
- **Log AI usage per user/course** — useful both for cost monitoring and as a feature (instructor sees "most asked questions")
- **Validate LLM JSON output** for the quiz generator — LLMs occasionally return malformed JSON; wrap parsing in try/catch and have a retry-with-correction prompt as fallback

---

## 11. Testing Strategy

- **Unit tests:** chunking function, prompt-building functions, JSON validation for quiz output
- **Integration tests:** full RAG query flow with a seeded course + known chunks (mock the LLM call, assert correct chunks are retrieved)
- **E2E (Playwright):** instructor creates course → publishes lesson → AI generates quiz → student enrolls → takes quiz → asks chatbot a question → gets an answer sourced from the lesson

---

## 12. Suggested Build Order (for your 2-3 week window)

1. Days 1-2: Postgres schema, Prisma + pgvector setup, auth, course/module/lesson CRUD
2. Days 3-4: Course catalog (Next.js SSR pages), enrollment, learning player with progress tracking
3. Day 5: Quiz engine (manual creation first, get grading logic solid)
4. Days 6-7: AI Quiz Generator + Summarizer (background jobs, prompt tuning)
5. Days 8-10: RAG pipeline — ingestion (chunking + embeddings) then query (similarity search + chat UI with streaming). **Budget the most time here — it's the flagship feature and has the most moving parts.**
6. Day 11: Docker + docker-compose local setup
7. Days 12-13: Deploy to AWS, GitHub Actions CI/CD
8. Remaining days: polish, tests, README with architecture diagram + RAG flow diagram, demo video, seed 1-2 real courses with real content for a convincing demo
