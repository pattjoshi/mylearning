# Project 1: Dukaan Manager — Booking & Management SaaS for Local Service Businesses

**Target users:** Salons, barbershops, repair shops (mobile/electronics/appliance), clinics, spas — any appointment-based local service business in India.

**Elevator pitch (for resume/interview):** "A multi-tenant SaaS that lets small service businesses replace their WhatsApp + notebook workflow with a real booking, staff, and revenue management system, with SMS/WhatsApp reminders built in."

---

## 1. Tech Stack

| Layer | Technology | Notes |
|---|---|---|
| Frontend | React.js (Vite) | CSR is fine here — no SEO need, it's a logged-in dashboard app |
| State management | Redux Toolkit + RTK Query | RTK Query gives you caching/invalidation for free — good talking point |
| Styling | Tailwind CSS + shadcn/ui | Fast, consistent, looks professional out of the box |
| Backend | Node.js + Express.js | REST API |
| Database | PostgreSQL | Relational data (bookings, staff, services) fits SQL better than Mongo |
| ORM | Prisma | Type-safe queries, easy migrations — very interview-friendly |
| Cache/Queue | Redis + BullMQ | Cache slot availability, queue SMS/WhatsApp jobs |
| Auth | JWT (access + refresh tokens), bcrypt | Store refresh token in httpOnly cookie |
| File storage | AWS S3 | Staff photos, shop logos, invoice PDFs |
| SMS/WhatsApp | Twilio (WhatsApp Business API sandbox) | Appointment reminders/confirmations |
| PDF generation | `pdf-lib` or `puppeteer` | GST-style invoices |
| Real-time | Socket.io | Live calendar updates when staff/owner books a slot |
| Hosting | AWS (EC2 or ECS Fargate) + RDS (Postgres) + S3 + CloudFront | Details in Section 6 |
| CI/CD | GitHub Actions | Lint → test → build → docker push → deploy |
| Containerization | Docker + docker-compose | Local dev parity with prod |
| Monitoring/Logs | Winston (app logs) + AWS CloudWatch | Optional: Sentry for error tracking |
| Testing | Jest + Supertest (API), React Testing Library (frontend), Playwright (E2E) | |

---

## 2. Feature List (Prioritized)

### 🔴 Must-Build (Core MVP)

1. **Multi-tenant auth & onboarding**
   - Owner signs up → creates "Business" (shop name, category, address, working hours)
   - Owner can invite staff via email (staff gets a login with limited permissions)
   - Roles: `OWNER`, `STAFF`
2. **Service management** — CRUD for services (name, duration in minutes, price, category e.g. "Haircut", "AC Repair")
3. **Staff management** — CRUD for staff, assign which services each staff member can perform, set individual working hours/leave
4. **Appointment booking (internal)** — Owner/staff can create a booking on behalf of a walk-in customer
5. **Public booking page** — `bookings.yourapp.com/shopname` — no login required for customer:
   - Select service → select staff (or "any available") → see available slots → enter name/phone → confirm
   - **Critical engineering detail:** slot availability must account for service duration + existing bookings + staff working hours + buffer time between appointments. This needs a proper overlap-check query, not just "is this exact time free."
6. **Double-booking prevention** — use a DB-level constraint or transaction with row locking (`SELECT ... FOR UPDATE`) when creating a booking, to prevent race conditions if two customers book the same slot simultaneously. **This is your strongest technical talking point — be ready to explain it in detail.**
7. **Booking reminders** — automated SMS/WhatsApp sent via BullMQ scheduled job: 24h before + 1h before appointment
8. **Owner dashboard**
   - Today's bookings (calendar/agenda view)
   - Revenue this week/month
   - Staff-wise performance (bookings handled, revenue generated)
   - No-show rate
9. **Customer history** — searchable by phone number, shows past visits, notes field ("prefers Rahul", "allergic to X product")
10. **Booking status management** — `PENDING → CONFIRMED → COMPLETED / CANCELLED / NO_SHOW`

### 🟡 Build If Time Allows

11. Inventory tracking for repair shops (parts used per job, low-stock alerts)
12. GST-compliant invoice generation (PDF, downloadable, emailed to customer)
13. Staff attendance (check-in/out) + simple commission/payout calculation
14. Hindi/English language toggle (i18next)
15. Basic review/rating after appointment completion (link sent post-visit)

### ⚪ Roadmap Only (mention in README, don't build)

16. Multi-branch support for the same business
17. Loyalty points / membership packages
18. Online payment collection at booking time (Razorpay)
19. Native mobile app (React Native)

---

## 3. Database Schema (PostgreSQL via Prisma)

```prisma
model Business {
  id           String   @id @default(uuid())
  name         String
  slug         String   @unique   // used in public booking URL
  category     String              // "Salon", "Repair Shop", "Clinic"
  address      String?
  phone        String
  logoUrl      String?
  timezone     String   @default("Asia/Kolkata")
  createdAt    DateTime @default(now())
  owner        User     @relation("BusinessOwner", fields: [ownerId], references: [id])
  ownerId      String
  staff        Staff[]
  services     Service[]
  bookings     Booking[]
  workingHours WorkingHour[]
}

model User {
  id           String   @id @default(uuid())
  name         String
  email        String   @unique
  phone        String?
  passwordHash String
  role         Role     @default(STAFF)
  businesses   Business[] @relation("BusinessOwner")
  staffProfile Staff?
  createdAt    DateTime @default(now())
}

enum Role {
  OWNER
  STAFF
}

model Staff {
  id          String    @id @default(uuid())
  user        User      @relation(fields: [userId], references: [id])
  userId      String    @unique
  business    Business  @relation(fields: [businessId], references: [id])
  businessId  String
  services    StaffService[]
  bookings    Booking[]
  leaves      Leave[]
  active      Boolean   @default(true)
}

model Service {
  id           String    @id @default(uuid())
  business     Business  @relation(fields: [businessId], references: [id])
  businessId   String
  name         String
  durationMins Int
  price        Decimal
  staff        StaffService[]
  bookings     Booking[]
}

model StaffService {
  staff      Staff   @relation(fields: [staffId], references: [id])
  staffId    String
  service    Service @relation(fields: [serviceId], references: [id])
  serviceId  String
  @@id([staffId, serviceId])
}

model WorkingHour {
  id          String   @id @default(uuid())
  business    Business @relation(fields: [businessId], references: [id])
  businessId  String
  dayOfWeek   Int       // 0-6
  openTime    String    // "09:00"
  closeTime   String    // "20:00"
}

model Booking {
  id           String        @id @default(uuid())
  business     Business      @relation(fields: [businessId], references: [id])
  businessId   String
  staff        Staff         @relation(fields: [staffId], references: [id])
  staffId      String
  service      Service       @relation(fields: [serviceId], references: [id])
  serviceId    String
  customerName String
  customerPhone String
  startTime    DateTime
  endTime      DateTime
  status       BookingStatus @default(PENDING)
  notes        String?
  createdAt    DateTime      @default(now())

  @@index([staffId, startTime])   // critical for overlap queries
}

enum BookingStatus {
  PENDING
  CONFIRMED
  COMPLETED
  CANCELLED
  NO_SHOW
}

model Leave {
  id         String   @id @default(uuid())
  staff      Staff    @relation(fields: [staffId], references: [id])
  staffId    String
  date       DateTime
  reason     String?
}
```

---

## 4. API Endpoints (REST)

```
Auth
  POST   /api/auth/signup
  POST   /api/auth/login
  POST   /api/auth/refresh
  POST   /api/auth/logout

Business
  POST   /api/businesses                 (owner creates business)
  GET    /api/businesses/:slug           (public — used by booking page)
  PUT    /api/businesses/:id

Staff
  POST   /api/staff/invite
  GET    /api/staff                      (list for a business)
  PUT    /api/staff/:id
  DELETE /api/staff/:id
  POST   /api/staff/:id/leave

Services
  POST   /api/services
  GET    /api/services
  PUT    /api/services/:id
  DELETE /api/services/:id

Bookings
  GET    /api/bookings                       (internal — filtered by date/staff)
  POST   /api/bookings                       (internal booking creation)
  GET    /api/public/:slug/availability      (public — get open slots for a service+date)
  POST   /api/public/:slug/book              (public — customer books)
  PUT    /api/bookings/:id/status            (confirm/cancel/complete/no-show)

Dashboard
  GET    /api/dashboard/summary              (revenue, bookings, no-show rate)
  GET    /api/dashboard/staff-performance

Customers
  GET    /api/customers?phone=              (search history)
```

---

## 5. The Core Hard Problem: Slot Availability + Double-Booking Prevention

This is the single most important engineering piece to get right and to be able to explain clearly in an interview.

**Approach:**
1. When fetching availability for a staff member on a date, compute all possible slots from `WorkingHour` minus existing `Booking` rows (status `PENDING`/`CONFIRMED`) that overlap, minus `Leave` days.
2. Overlap check logic (pseudocode):
   ```sql
   SELECT * FROM "Booking"
   WHERE staffId = $1
     AND status IN ('PENDING','CONFIRMED')
     AND startTime < $newEndTime
     AND endTime > $newStartTime
   ```
   If any row is returned, the slot conflicts.
3. **Race condition fix:** Wrap the check-and-create in a database transaction with `SELECT ... FOR UPDATE` on the relevant staff's bookings for that day, OR add a Postgres `EXCLUDE` constraint using the `btree_gist` extension so overlapping ranges are rejected at the DB level even under concurrent requests. Mention both approaches — using a DB constraint is the more "senior" answer since it doesn't rely on application-level locking being correct everywhere.

---

## 6. AWS Architecture

```
                     ┌─────────────────┐
                     │   Route 53 (DNS) │
                     └────────┬─────────┘
                              │
                     ┌────────▼─────────┐
                     │   CloudFront CDN  │  (serves React static build)
                     └────────┬─────────┘
                              │
                     ┌────────▼─────────┐
                     │   S3 (static site) │  React build output
                     └───────────────────┘

                     ┌───────────────────┐
                     │ Application Load   │
                     │ Balancer (ALB)     │
                     └────────┬──────────┘
                              │
                  ┌───────────▼────────────┐
                  │  ECS Fargate (Node API) │  2 tasks min for availability
                  │  behind auto-scaling     │
                  └───────────┬────────────┘
                              │
        ┌─────────────────────┼─────────────────────┐
        │                     │                       │
┌───────▼────────┐  ┌─────────▼─────────┐   ┌────────▼────────┐
│  RDS Postgres    │  │ ElastiCache Redis │   │  S3 (uploads,    │
│  (Multi-AZ opt.) │  │ (BullMQ + cache)  │   │  logos, PDFs)    │
└──────────────────┘  └────────────────────┘   └─────────────────┘
```

**Services used and why:**
- **S3 + CloudFront** — hosts the React static build cheaply, globally cached
- **ECS Fargate** — runs the Node/Express API in Docker containers, no server management (good "I understand containers in production" story). Alternative for a resume-only project: a single EC2 instance is cheaper and simpler if Fargate cost is a concern.
- **RDS Postgres** — managed Postgres, automated backups
- **ElastiCache Redis** — used for caching availability lookups and as the BullMQ backing store for reminder jobs
- **Route 53** — domain + DNS
- **CloudWatch** — logs and basic alarms (CPU, error rate)
- **IAM roles** — least-privilege roles for ECS tasks to access S3/RDS (don't hardcode credentials — use IAM roles, this is a real interview question)
- **Secrets Manager** — store DB password, JWT secret, Twilio keys (not in `.env` in prod)

**Budget-friendly alternative** for a portfolio project (since Fargate + Multi-AZ RDS can get expensive): run everything on a single `t3.micro`/`t3.small` EC2 instance with docker-compose (API + Redis containers), and RDS free-tier Postgres. Mention in your README that you *designed* for the Fargate/ALB architecture and *deployed* the cost-optimized version — this is a completely normal and honest thing to say, and shows judgment.

---

## 7. Docker Setup

**`Dockerfile` (backend):**
```dockerfile
FROM node:20-alpine AS builder
WORKDIR /app
COPY package*.json ./
RUN npm ci
COPY . .
RUN npx prisma generate

FROM node:20-alpine
WORKDIR /app
COPY --from=builder /app .
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
    image: postgres:16-alpine
    environment:
      POSTGRES_USER: dukaan
      POSTGRES_PASSWORD: dukaan_pass
      POSTGRES_DB: dukaan_db
    ports: ["5432:5432"]
    volumes: ["pgdata:/var/lib/postgresql/data"]
  redis:
    image: redis:7-alpine
    ports: ["6379:6379"]
volumes:
  pgdata:
```

---

## 8. CI/CD Pipeline (GitHub Actions)

`.github/workflows/deploy.yml` — conceptual stages:
1. **On PR to `main`:** lint (ESLint) → run Jest unit tests → run Supertest API tests against a test Postgres service container
2. **On merge to `main`:**
   - Build Docker image, tag with git SHA
   - Push image to Amazon ECR
   - Run `prisma migrate deploy` against RDS
   - Update ECS service (`aws ecs update-service --force-new-deployment`) — or if using EC2, SSH deploy via `appleboy/ssh-action` and `docker-compose pull && up -d`
   - Frontend: build React app → sync to S3 → invalidate CloudFront cache

---

## 9. Security Checklist

- Passwords hashed with bcrypt (cost factor 12)
- JWT access token short-lived (15 min), refresh token in httpOnly + secure cookie
- Input validation with Zod on every endpoint
- Rate limiting (express-rate-limit or Redis-based) on public booking endpoint to prevent spam bookings
- CORS restricted to known frontend origin
- Helmet.js for HTTP headers
- SQL injection not a concern with Prisma (parameterized), but validate all raw queries if any
- Tenant isolation: every query scoped by `businessId` — write a Prisma middleware that auto-injects this filter so it's impossible to forget

---

## 10. Testing Strategy

- **Unit tests:** slot availability calculation logic, price calculation, date/timezone handling
- **Integration tests:** booking creation with overlap conflict (test the race condition fix with concurrent requests using `Promise.all`)
- **E2E (Playwright):** full flow — owner creates service → customer books via public page → owner sees it on dashboard

---

## 11. Suggested Build Order (for your 2-3 week window)

1. Days 1-2: Postgres schema + Prisma setup, auth, business/staff/service CRUD
2. Days 3-4: Availability calculation + booking creation with conflict prevention (the hard part — budget extra time)
3. Day 5: Public booking page (customer-facing, no auth)
4. Day 6: Dashboard (revenue, bookings summary)
5. Day 7: Twilio SMS/WhatsApp reminders via BullMQ
6. Day 8: Docker + docker-compose local setup
7. Days 9-10: Deploy to AWS (start with EC2 + RDS free tier — simpler), set up GitHub Actions CI/CD
8. Remaining days: polish, tests, README with architecture diagram, demo video, seed data for demo
