# Founder Intelligence System

An end-to-end multi-agent AI pipeline that turns raw signals — meeting transcripts, competitor data, app reviews, Reddit discussions, and YouTube content — into structured product insights, feature briefs, and founder-ready answers.

---

## Problem Definition

Founders and product teams are drowning in unstructured data. User complaints are scattered across app stores, Reddit threads, and support tickets. Competitor intelligence lives in browser tabs. Internal meeting decisions get lost in notes. There is no system that connects all of this into actionable product decisions.

This system solves that by running a chain of specialized AI agents, each responsible for one step of the research-to-decision pipeline — from raw ingestion to a conversational copilot that answers founder questions in seconds.

---

## Models Used

| Agent | Model | Provider | Cost |
|-------|-------|----------|------|
| Agent 1 | gemini-2.0-flash-lite | Google Gemini | Free (1500 req/day) |
| Agent 2 Free | llama-3.3-70b-versatile | Groq | Free |
| Agent 3 Free | Qwen/Qwen2.5-72B-Instruct | HuggingFace | Free |
| Agent 4 | llama-3.3-70b-versatile | Groq | Free |
| Agent 5 | llama-3.3-70b-versatile | Groq | Free |
| Agent 6 | llama-3.3-70b-versatile | Groq | Free |
| Agent 7 | llama-3.3-70b-versatile | Groq | Free |
| Agent 3 (Gemini) | gemini-2.0-flash-lite | Google Gemini | Free (1500 req/day) |

**Groq** — free tier, 10x faster than HuggingFace inference, 131k context window, guaranteed JSON output via `response_format`. Get key at https://console.groq.com

**Gemini** — free tier, 1500 requests/day with gemini-2.0-flash-lite. Get key at https://aistudio.google.com/apikey

**HuggingFace** — free inference API for Qwen2.5-72B. Get token at https://huggingface.co/settings/tokens

---

## How to Run the Pipeline

### Step 1 — Set up environment variables

Copy `.env.example` to `.env` and fill in your keys:

```env
GEMINI_API_KEY=your_gemini_key
GROQ_API_KEY=your_groq_key
HF_TOKEN=your_huggingface_token
APIFY_TOKEN=your_apify_token
```

### Step 2 — Install dependencies

```bash
pip install -r Agent1/requirements.txt
pip install -r Agent2_Free/requirements.txt
pip install -r Agent3_Free/requirements.txt
pip install -r Agent4/requirements.txt
pip install -r Agent5/requirements.txt
pip install -r Agent6/requirements.txt
pip install -r Agent7/requirements.txt
pip install google-play-scraper groq
```

### Step 3 — Start all agents

```bash
python start_all.py
```

This opens each agent in its own terminal window and waits until all are healthy. Once done it prints:

```
✅ All agents ready!

  Agent 1  (Transcript)       → http://localhost:8004/docs
  Agent 2  (Competitor Free)  → http://localhost:8001/docs
  Agent 3  (YouTube/Gemini)   → http://localhost:8002/docs
  Agent 3F (Free)             → http://localhost:8003/docs
  Agent 4  (Insights)         → http://localhost:8005/docs
  Agent 5  (Synthesis)        → http://localhost:8006/docs
  Agent 6  (Briefs)           → http://localhost:8007/docs
  Agent 7  (Copilot)          → http://localhost:8008/docs
  Pipeline (Orchestrator)     → http://localhost:8000/docs
```

### Step 4 — Run the pipeline

Open http://localhost:8000/docs → `POST /pipeline/run` → paste this payload:

```json
{
  "transcript_text": "Product Strategy Meeting...",
  "competitor_name": "Zerodha",
  "competitor_website": "https://zerodha.com",
  "youtube_url": ["https://www.youtube.com/@zerodhaonline"],
  "reddit_url": ["https://www.reddit.com/r/IndiaInvestments/"],
  "app_store_urls": ["https://play.google.com/store/apps/details?id=com.zerodha.kite3"],
  "questions": [
    "What are the top 3 user problems?",
    "What should we build next?",
    "What are competitors doing differently?",
    "What are the onboarding issues?"
  ],
  "save_outputs": true
}
```

The endpoint returns a `run_id` immediately:

```json
{ "run_id": "a1b2c3d4", "status": "starting", "poll_url": "/pipeline/status/a1b2c3d4" }
```

### Step 5 — Poll for results

```
GET http://localhost:8000/pipeline/status/a1b2c3d4
```

Keep polling every 15-30 seconds until `"status": "complete"`. The final response includes:

```json
{
  "status": "complete",
  "problem_count": 6,
  "insight_count": 4,
  "feature_count": 6,
  "copilot_answers": [...],
  "suggested_follow_ups": [...]
}
```

All intermediate outputs are saved to `runs/{run_id}/` folder.

---

## System Architecture

```
Raw Inputs
    │
    ├── Meeting Transcripts
    ├── Competitor Websites
    ├── YouTube Channels / Videos
    ├── Reddit Posts / Subreddits
    └── App Store / Play Store URLs
    │
    ▼
┌─────────────────────────────────────────────────────────┐
│              PIPELINE ORCHESTRATOR  :8000                │
│         Auto-starts all agents on first run              │
└─────────────────────────────────────────────────────────┘
    │
    ├── Agent 1  :8004  Transcript Analysis      (Gemini)
    ├── Agent 2  :8001  Competitor Research       (Groq)
    ├── Agent 3  :8003  YouTube+Reddit+AppStore   (HuggingFace+Apify)
    ├── Agent 4  :8005  Insight Extraction        (Groq)
    ├── Agent 5  :8006  Research Synthesis        (Groq)
    ├── Agent 6  :8007  Product Brief Generation  (Groq)
    └── Agent 7  :8008  Founder Copilot           (Groq)
    │
    ▼
Structured Output  →  runs/{run_id}/
    ├── agent1.json   (transcript analysis)
    ├── agent4.json   (validated problems)
    ├── agent5.json   (product insights)
    ├── agent6.json   (feature briefs)
    └── output.json   (full pipeline result)
```

---

## Agents

### Agent 1 — Transcript Analysis Agent
**Port:** 8004 | **Model:** Gemini 2.0 Flash Lite

Processes raw meeting transcripts and extracts structured intelligence.

**Input:** Raw text transcript
**Output:** Summary, problems identified, major decisions, next steps, tone analysis, speaker contributions, timeline

**Endpoint:** `POST /pipeline/run`

---

### Agent 2 Free — Competitor Research Agent
**Port:** 8001 | **Model:** Groq llama-3.3-70b + DuckDuckGo

Researches a competitor using DuckDuckGo search and website scraping. No paid API keys needed.

**Input:** Company name + website URL
**Output:** Founders, funding, users, revenue, positioning, differentiators, complaints, strategic moves, new features

**Endpoints:** `POST /competitor/research` | `POST /competitor/bulk` | `GET /competitor/presets`

---

### Agent 3 Free — Signal Ingestion Agent
**Port:** 8003 | **Model:** Qwen2.5-72B (HuggingFace) + Apify + google-play-scraper

Scrapes and analyzes YouTube, Reddit, and app stores.

**YouTube:** Video/channel analysis — summary, topics, sentiment, key insights, negative points
**Reddit:** Post/subreddit analysis — sentiment, opinions, controversy level, live monitor
**App Store:** 100 reviews (20 per star rating), metadata, complaints, praises, negative reviews

**Endpoints:** `POST /analyze/video` | `POST /analyze/channel` | `POST /analyze/reddit` | `POST /analyze/subreddit` | `POST /monitor/subreddit` | `POST /analyze/app`

---

### Agent 4 — Insight Extraction Agent
**Port:** 8005 | **Model:** Groq llama-3.3-70b

Converts raw signals from Agents 1, 2, 3 into validated user problems.

**Output per problem:** Problem description, evidence, frequency (Low/Medium/High), user type (Beginner/Intermediate/Advanced), source mix, positive points, negative points

**Endpoints:** `POST /insights/extract` | `POST /insights/from-file`

---

### Agent 5 — Research Synthesis Agent
**Port:** 8006 | **Model:** Groq llama-3.3-70b

Connects related problems to identify root causes and strategic implications.

**Output per insight:** Core insight, supporting problems, evidence, implication, priority, testable hypothesis, recommended action

**Endpoints:** `POST /synthesis/run` | `POST /synthesis/from-files`

---

### Agent 6 — Product Brief Agent
**Port:** 8007 | **Model:** Groq llama-3.3-70b

Converts insights into buildable product feature briefs.

**Output per feature:** Feature name, problem, why it matters, solution, user flow (step-by-step), expected impact, priority, effort, target user

**Endpoints:** `POST /briefs/generate` | `POST /briefs/from-files`

---

### Agent 7 — Founder Copilot
**Port:** 8008 | **Model:** Groq llama-3.3-70b

Answers founder questions over all agent outputs with evidence and confidence levels.

**Example questions:**
- "What are the top 3 user problems?"
- "What should we build next?"
- "What are competitors doing differently?"
- "What are the onboarding issues?"

**Output:** Direct answer, supporting evidence, confidence level, suggested follow-up questions

**Endpoints:** `POST /copilot/load-context` | `POST /copilot/ask` | `POST /copilot/ask-inline`

---

## Testing Individual Agents

**Agent 1**
```json
POST http://localhost:8004/pipeline/run
{ "text": "Meeting: Q2 Review\nAlex (CEO): We need to fix withdrawal delays.\nSarah (CTO): I can patch it in 2 weeks." }
```

**Agent 2 Free**
```json
POST http://localhost:8001/competitor/research
{ "company_name": "Groww", "website": "https://groww.in" }
```

**Agent 3 Free — App**
```json
POST http://localhost:8003/analyze/app
{ "input": "com.zerodha.kite3", "store": "play" }
```

**Agent 3 Free — Reddit**
```json
POST http://localhost:8003/analyze/subreddit
{ "url": "https://www.reddit.com/r/IndiaInvestments/", "max_posts": 10 }
```

**Agent 4**
```json
POST http://localhost:8005/insights/from-file
{ "file_path": "input.json" }
```

**Agent 5**
```json
POST http://localhost:8006/synthesis/from-files
{ "agent1_file": "input_Agent1.json", "agent4_file": "input_Agent2.json" }
```

**Agent 6**
```json
POST http://localhost:8007/briefs/from-files
{ "agent5_file": "input_Agent3.json", "agent4_file": "input_Agent2.json", "agent1_file": "input_Agent1.json" }
```

**Agent 7**
```json
POST http://localhost:8008/copilot/load-context
{ "agent1_file": "input_Agent1.json", "agent4_file": "input_Agent2.json", "agent5_file": "input_Agent3.json", "agent6_file": "input_Agent4.json" }

POST http://localhost:8008/copilot/ask
{ "question": "What should we build next?" }
```

---

## Data Flow

```
Transcript ──────────────────────────────────► Agent 1 (Gemini)
Competitor Name + Website ───────────────────► Agent 2 (Groq + DDG)
YouTube / Reddit / App Store ────────────────► Agent 3 (HF + Apify)
                                                    │
                              All signals combined  │
                                                    ▼
                                          Agent 4 — Problems (Groq)
                                                    │
                                                    ▼
                                          Agent 5 — Insights (Groq)
                                                    │
                                                    ▼
                                          Agent 6 — Features (Groq)
                                                    │
                                                    ▼
                                          Agent 7 — Copilot (Groq)
                                                    │
                                                    ▼
                                     Answers + Suggested Follow-ups
```

---

## Project Structure

```
├── pipeline.py              # Orchestrator (port 8000)
├── start_all.py             # Start all agents with one command
├── shared/
│   └── llm.py               # Shared Groq LLM utility (JSON mode + retry)
├── Agent1/                  # Transcript analysis (port 8004) — Gemini
├── Agent2_Free/             # Competitor research (port 8001) — Groq + DDG
├── Agent3/                  # YouTube analysis (port 8002) — Gemini
├── Agent3_Free/             # YouTube+Reddit+App Store (port 8003) — HF+Apify
├── Agent4/                  # Insight extraction (port 8005) — Groq
├── Agent5/                  # Research synthesis (port 8006) — Groq
├── Agent6/                  # Product briefs (port 8007) — Groq
├── Agent7/                  # Founder copilot (port 8008) — Groq
├── runs/                    # Pipeline outputs (namespaced by run_id)
├── .env                     # API keys
└── README.md
```

---

## Environment Variables

```env
# Google Gemini (Agent 1, Agent 3)
# Free: 1500 req/day — https://aistudio.google.com/apikey
GEMINI_API_KEY=your_key

# Groq (Agents 4-7, Agent 2 Free)
# Free tier — https://console.groq.com
GROQ_API_KEY=your_key

# HuggingFace (Agent 3 Free)
# Free — https://huggingface.co/settings/tokens
HF_TOKEN=your_token

# Apify (Agent 3 Free — Reddit + App Store scraping)
# Free tier — https://console.apify.com/account/integrations
APIFY_TOKEN=your_token
```

---

## Problem Definition

Founders and product teams are drowning in unstructured data. User complaints are scattered across app stores, Reddit threads, and support tickets. Competitor intelligence lives in browser tabs. Internal meeting decisions get lost in notes. There is no system that connects all of this into actionable product decisions.

This system solves that by running a chain of specialized AI agents, each responsible for one step of the research-to-decision pipeline — from raw ingestion to a conversational copilot that answers founder questions in seconds.

---

## System Architecture

```
Raw Inputs
    │
    ├── Meeting Transcripts
    ├── Competitor Websites
    ├── YouTube Channels / Videos
    ├── Reddit Posts / Subreddits
    └── App Store / Play Store URLs
    │
    ▼
┌─────────────────────────────────────────────────────────┐
│                   PIPELINE ORCHESTRATOR                  │
│                   localhost:8000                         │
└─────────────────────────────────────────────────────────┘
    │
    ├── Agent 1  (port 8004)  Transcript Analysis
    ├── Agent 2  (port 8001)  Competitor Research
    ├── Agent 3  (port 8003)  YouTube + Reddit + App Store
    ├── Agent 4  (port 8005)  Insight Extraction
    ├── Agent 5  (port 8006)  Research Synthesis
    ├── Agent 6  (port 8007)  Product Brief Generation
    └── Agent 7  (port 8008)  Founder Copilot
    │
    ▼
Structured Output
    ├── Validated user problems (with frequency + user type)
    ├── Product insights (with root causes + implications)
    ├── Feature briefs (with user flows + expected impact)
    └── Copilot answers (with evidence + confidence level)
```

---

## Agents

### Agent 1 — Transcript Analysis Agent
**Port:** 8004 | **Model:** Gemini 3.1 Flash lite preview

Processes raw meeting transcripts and extracts structured intelligence.

**Input:** Raw text transcript  
**Output:**
- Meeting summary
- Problems identified
- Major decisions
- Next steps with owners
- Tone analysis (positive / negative)
- Speaker contribution breakdown
- Timeline of discussion

**Endpoint:** `POST /pipeline/run`

---

### Agent 2 — Competitor Research Agent
**Port:** 8001 | **Model:** Gemini 3.1 Flash lite preview + SerpAPI

Researches a competitor company using Google Search and website scraping.

**Input:** Company name + website URL  
**Output:**
- Year founded, founders, headquarters
- Funding raised, number of users, annual revenue
- Key positioning and revenue model
- Differentiators and user complaints
- Strategic moves and new features

**Endpoints:**
- `POST /competitor/research` — single competitor
- `POST /competitor/bulk` — multiple competitors
- `GET /competitor/presets` — pre-configured competitor list

#### Agent 2 Free
**Port:** 8001 | **Model:** Qwen 2.5 72B (HuggingFace) + DuckDuckGo

Same output as Agent 2 but requires no paid API keys. Uses DuckDuckGo for search and a free HuggingFace model for analysis.

---

### Agent 3 — Signal Ingestion Agent
**Port:** 8003 | **Model:** Qwen 2.5 72B (HuggingFace) + Apify

Scrapes and analyzes content from YouTube, Reddit, and app stores.

**Capabilities:**

**YouTube Video Analysis**
- Title, channel, upload date, duration, views, likes, comments
- AI summary, main topics, sentiment, key insights, negative points
- Content type, call to action, transcript extraction

**YouTube Channel Analysis**
- Per-video breakdown for last N videos
- Channel summary, content themes, posting pattern
- Audience type, content style, top topics

**Reddit Post Analysis**
- Post metadata (score, upvote ratio, comment count, flair)
- Summary, main topics, overall + community sentiment
- Key opinions, negative points, controversy level, key takeaway

**Subreddit Analysis**
- Last 20 posts with per-post breakdown
- Subreddit mood summary, hot topics, dominant sentiment
- Notable trends, live monitor for new posts

**App Store / Play Store Analysis**
- App metadata: rating, installs, screenshots, description, version
- 100 reviews (20 per star rating: 1★ to 5★)
- AI summary, key features, top complaints, top praises
- Negative reviews sorted by helpful votes
- Recent issues and competitive position

**Endpoints:**
- `POST /analyze/video`
- `POST /analyze/channel`
- `POST /analyze/reddit`
- `POST /analyze/subreddit`
- `POST /monitor/subreddit` — live polling for new posts
- `POST /analyze/app`

#### Agent 3 (Gemini version)
**Port:** 8002 | **Model:** Gemini 3.1 Flash lite preview + yt-dlp

YouTube-only version using Gemini for analysis and yt-dlp for scraping.

---

### Agent 4 — Insight Extraction Agent
**Port:** 8005 | **Model:** Qwen 2.5 72B (HuggingFace)

Converts raw signals from Agents 1, 2, 3 into structured, validated user problems.

**Input:** Combined output from any/all of Agents 1, 2, 3  
**Output per problem:**
- Problem: clear description of the user issue
- Evidence: direct quotes and examples from inputs
- Frequency: Low / Medium / High
- User Type: Beginner / Intermediate / Advanced
- Source Mix: Competitor / Reddit / YouTube / App Store / Internal
- Positive Points: what is working well in this area
- Negative Points: what is broken or painful

**Endpoints:**
- `POST /insights/extract` — pass signals as JSON
- `POST /insights/from-file` — load from a local JSON file

---

### Agent 5 — Research Synthesis Agent
**Port:** 8006 | **Model:** Qwen 2.5 72B (HuggingFace)

Connects related problems to identify root causes and strategic implications.

**Input:** Problems from Agent 4 + competitor signals + internal notes  
**Output per insight:**
- Insight: core underlying issue (the "why behind the what")
- Supporting Problems: list of related problems pointing to this insight
- Evidence: data points that validate the insight
- Implication: what this means for the product
- Priority: Critical / High / Medium / Low
- Hypothesis: testable hypothesis starting with "If we..."
- Recommended Action: single most important next step

**Endpoints:**
- `POST /synthesis/run` — pass data as JSON
- `POST /synthesis/from-files` — load from local files

---

### Agent 6 — Product Brief Agent
**Port:** 8007 | **Model:** Qwen 2.5 72B (HuggingFace)

Converts insights into clear, buildable product feature briefs.

**Input:** Insights from Agent 5 + problems from Agent 4 + internal notes from Agent 1  
**Output per feature:**
- Feature Name: short memorable name
- Problem: specific user issue this solves
- Why It Matters: impact if not solved
- Solution: high-level description of what to build
- User Flow: step-by-step usage (3-5 steps)
- Expected Impact: measurable outcome
- Priority: Critical / High / Medium / Low
- Effort: Low / Medium / High
- Target User: Beginner / Intermediate / Advanced

**Endpoints:**
- `POST /briefs/generate` — pass data as JSON
- `POST /briefs/from-files` — load from local files

---

### Agent 7 — Founder Copilot
**Port:** 8008 | **Model:** Qwen 2.5 72B (HuggingFace)

A conversational query interface over all agent outputs. Answers founder questions with direct answers, evidence, and confidence levels. Automatically answers follow-up questions too.

**Example questions:**
- "What are the top 3 user problems this week?"
- "What should we build next?"
- "What are competitors doing differently?"
- "What do users like most about the product?"
- "What are the onboarding issues?"
- "What are the reliability or downtime concerns?"

**Output per answer:**
- Answer: direct, specific response
- Evidence: 2-4 supporting data points
- Confidence: High / Medium / Low
- Follow-up Questions: 2-3 related questions (auto-answered by pipeline)

**Endpoints:**
- `POST /copilot/load-context` — pre-load all agent files into memory
- `POST /copilot/ask` — ask a question using loaded context
- `POST /copilot/ask-inline` — ask with data passed directly as JSON

---

## Pipeline Orchestrator

**Port:** 8000

Runs all agents in sequence, auto-starts any that aren't running, and passes each agent's output as input to the next.

**Endpoint:** `POST /pipeline/run`

**Input:**
```json
{
  "transcript_text": "raw meeting transcript...",
  "competitor_name": "Zerodha",
  "competitor_website": "https://zerodha.com",
  "youtube_url": ["https://www.youtube.com/@zerodhaonline"],
  "reddit_url": ["https://www.reddit.com/r/IndiaInvestments/"],
  "app_store_urls": ["https://play.google.com/store/apps/details?id=com.zerodha.kite3"],
  "questions": [
    "What are the top 3 user problems?",
    "What should we build next?"
  ],
  "save_outputs": true
}
```

All fields are optional — steps with missing inputs are skipped gracefully.

**Output:**
```json
{
  "status": "complete",
  "steps_run": ["agent1", "agent2", "agent3", "agent4", "agent5", "agent6"],
  "problem_count": 6,
  "insight_count": 4,
  "feature_count": 6,
  "pipeline_summary": { "answer": "...", "evidence": [...] },
  "copilot_answers": [
    {
      "question": "What are the top 3 user problems?",
      "answer": "...",
      "evidence": [...],
      "confidence": "High",
      "follow_up_questions": [...]
    }
  ]
}
```

---

## Setup

### Prerequisites
- Python 3.11+
- [Ollama](https://ollama.com) (optional, for local models)

### Environment Variables

Copy `.env.example` to `.env` and fill in:

```env
# Agent 1 + Agent 3 (Gemini version)
GEMINI_API_KEY=your_gemini_key

# Agent 2 (paid version)
AGENT2_GEMINI_API_KEY=your_gemini_key
SERPAPI_KEY=your_serpapi_key

# Agent 2 Free + Agent 3 Free + Agents 4-7
HF_TOKEN=your_huggingface_token

# Agent 3 Free (app/reddit scraping)
APIFY_TOKEN=your_apify_token
```

**Free tier links:**
- HuggingFace token: https://huggingface.co/settings/tokens
- Apify token: https://console.apify.com/account/integrations (free tier available)
- Gemini key: https://aistudio.google.com/apikey (1500 free requests/day with gemini-1.5-flash)

### Install Dependencies

```bash
pip install -r Agent1/requirements.txt
pip install -r Agent2_Free/requirements.txt
pip install -r Agent3_Free/requirements.txt
pip install -r Agent4/requirements.txt
pip install -r Agent5/requirements.txt
pip install -r Agent6/requirements.txt
pip install -r Agent7/requirements.txt
pip install google-play-scraper
```

---

## Running

### Option 1 — Full Pipeline (auto-starts all agents)
```bash
uvicorn pipeline:app --port 8000
```
Then hit `POST /pipeline/run` at http://localhost:8000/docs

### Option 2 — Individual Agents

| Agent | Command | Swagger UI |
|-------|---------|------------|
| Agent 1 | `uvicorn Agent1.api.main:app --port 8004` | http://localhost:8004/docs |
| Agent 2 Free | `uvicorn Agent2_Free.api.main:app --port 8001` | http://localhost:8001/docs |
| Agent 3 Free | `uvicorn Agent3_Free.api.main:app --port 8003` | http://localhost:8003/docs |
| Agent 4 | `uvicorn Agent4.api.main:app --port 8005` | http://localhost:8005/docs |
| Agent 5 | `uvicorn Agent5.api.main:app --port 8006` | http://localhost:8006/docs |
| Agent 6 | `uvicorn Agent6.api.main:app --port 8007` | http://localhost:8007/docs |
| Agent 7 | `uvicorn Agent7.api.main:app --port 8008` | http://localhost:8008/docs |

---

## Testing Individual Agents

**Agent 1**
```json
POST http://localhost:8004/pipeline/run
{ "text": "Meeting: Q2 Review\nAlex (CEO): We need to fix withdrawal delays.\nSarah (CTO): I can patch it in 2 weeks." }
```

**Agent 2 Free**
```json
POST http://localhost:8001/competitor/research
{ "company_name": "Groww", "website": "https://groww.in" }
```

**Agent 3 Free — App**
```json
POST http://localhost:8003/analyze/app
{ "input": "com.nextbillion.groww", "store": "play" }
```

**Agent 3 Free — Reddit**
```json
POST http://localhost:8003/analyze/subreddit
{ "url": "https://www.reddit.com/r/IndiaInvestments/", "max_posts": 10 }
```

**Agent 4**
```json
POST http://localhost:8005/insights/from-file
{ "file_path": "input.json" }
```

**Agent 5**
```json
POST http://localhost:8006/synthesis/from-files
{ "agent1_file": "input_Agent1.json", "agent4_file": "input_Agent2.json" }
```

**Agent 6**
```json
POST http://localhost:8007/briefs/from-files
{ "agent5_file": "input_Agent3.json", "agent4_file": "input_Agent2.json", "agent1_file": "input_Agent1.json" }
```

**Agent 7**
```json
POST http://localhost:8008/copilot/load-context
{ "agent1_file": "input_Agent1.json", "agent4_file": "input_Agent2.json", "agent5_file": "input_Agent3.json", "agent6_file": "input_Agent4.json" }

POST http://localhost:8008/copilot/ask
{ "question": "What should we build next?" }
```

---

## Data Flow

```
Transcript Text ──────────────────────────────► Agent 1
Competitor Name + Website ────────────────────► Agent 2
YouTube / Reddit / App Store URLs ────────────► Agent 3
                                                    │
                              Agent 1 + 2 + 3 output│
                                                    ▼
                                                Agent 4 (Problems)
                                                    │
                              Agent 4 + 1 + 2 output│
                                                    ▼
                                                Agent 5 (Insights)
                                                    │
                              Agent 5 + 4 + 1 output│
                                                    ▼
                                                Agent 6 (Features)
                                                    │
                        All agent outputs loaded ───┘
                                                    ▼
                                                Agent 7 (Copilot)
                                                    │
                                                    ▼
                                        Founder Questions Answered
```

---

## Project Structure

```
├── pipeline.py              # End-to-end orchestrator (port 8000)
├── Agent1/                  # Transcript analysis (port 8004)
│   ├── api/main.py
│   ├── transcript_pipeline/
│   └── chat/
├── Agent2/                  # Competitor research — paid (Gemini + SerpAPI)
├── Agent2_Free/             # Competitor research — free (HF + DuckDuckGo)
│   ├── api/main.py
│   └── researcher.py
├── Agent3/                  # YouTube analysis — Gemini (port 8002)
├── Agent3_Free/             # YouTube + Reddit + App Store — free (port 8003)
│   ├── api/main.py
│   └── analyzer.py
├── Agent4/                  # Insight extraction (port 8005)
│   ├── api/main.py
│   └── extractor.py
├── Agent5/                  # Research synthesis (port 8006)
│   ├── api/main.py
│   └── synthesizer.py
├── Agent6/                  # Product brief generation (port 8007)
│   ├── api/main.py
│   └── brief_generator.py
├── Agent7/                  # Founder copilot (port 8008)
│   ├── api/main.py
│   └── copilot.py
├── .env                     # API keys (not committed)
├── .env.example             # Template
└── README.md
```
