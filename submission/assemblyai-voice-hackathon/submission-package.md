# Neta Gym Voice - AssemblyAI Voice Agent Hackathon Submission Package
Event: https://lablab.ai/ai-hackathons/assemblyai-voice-agent-hackathon (deadline Sep 30, 2026, 11:00 AM EDT)
Rules checked: https://lablab.ai/hackathon-rules
Status: REVIEW COPY ONLY. Nothing here has been submitted to lablab.

Every number below was pulled live from the deployed API (https://netagym-voice.onrender.com/api/ask) on Sep 8, 2026 - not from memory.

---

## 1. Lablab entry form copy

**Project title**
Neta Gym Voice - Ask Any Indian MP About Their Record

**Short description**
A phone-call-style voice agent, built on AssemblyAI, that answers plain-language questions about any of 786 Indian MPs - attendance, questions asked, debates, criminal cases, assets, and a 0-100 transparency score - from public Parliament data. No app, no jargon, just ask.

**Long description**
India's Parliament publishes rich data on every MP - attendance, questions, debates, declared assets, criminal cases - but it sits in PDFs and databases almost no voter ever opens. Neta Gym Voice turns that data into a conversation.

Call the agent and ask, in plain words: "What is Rajiv Pratap Rudy's attendance?" The agent (built on AssemblyAI's Voice Agent API) transcribes the question, resolves the MP, and speaks the answer with the source: "Rajiv Pratap Rudy, BJP MP from Saran, Bihar, has attended 100 percent of Parliament sittings, with 36 questions asked. Full record at neta-gym.github.io/mp-transparency-tracker."

Under the hood:
- AssemblyAI Voice Agent API handles the real-time speech loop (streaming STT, LLM turn-taking, TTS).
- The agent's brain is a deterministic tool, not a black box: a rules-based parser maps the question to one of 786 MP records built from public sources (PRS Legislative Research, Lok Sabha/Rajya Sabha portals, ADR affidavits, myneta.info). No LLM invents numbers - every figure the agent speaks is a database lookup with a source.
- Honest by design: when data is missing (for example, a minister who does not mark attendance, or a PRS coverage gap like Rahul Gandhi's attendance), the agent says so out loud instead of guessing.
- A 0-100 transparency score per MP, computed from public metrics only, party-neutral, with the full breakup published on the web tracker.

Why it matters: 786 MPs indexed, 784 scored. A first-time voter in Saran and a journalist in Delhi get the same instant, sourced answer. The text interface already answers the same questions on the web; the voice agent makes it accessible to anyone who can make a phone call, in the language they speak.

Built in public: full source at https://github.com/neta-gym/mp-transparency-tracker

**Live app URL**
https://netagym-voice.onrender.com/talk (voice) | https://netagym-voice.onrender.com (text)

**GitHub repo**
https://github.com/neta-gym/mp-transparency-tracker (public)

**Cover image plan (16:9, PNG)**
Left: Neta Gym wordmark + tagline "Ask any MP about their record." Center: phone-call waveform mid-answer with the spoken line "100 percent attendance, 36 questions asked." Right: mini report card for Rajiv Pratap Rudy (Saran, BJP) showing attendance ring at 100%. Dark background, saffron/green accent pair, party-neutral. No real person photos (avoid likeness issues) - icon + data only. Exact size 1280x720.

---

## 2. Demo video script (target 3:30, hard cap 5:00)

Format: screen recording of https://netagym-voice.onrender.com/talk with live mic; single take per scene, stitched. Voiceover = the agent itself plus a calm human narrator. All agent answers below are the verified live outputs.

SCENE 1 - The problem (0:00-0:25)
Visual: montage of Parliament PDFs / dense PRS tables.
Narrator: "India publishes everything its MPs do in Parliament. Attendance. Questions. Debates. Assets. But it is buried in PDFs almost no voter ever opens. What if you could just... call and ask?"

SCENE 2 - The product (0:25-0:40)
Visual: clean /talk page, press Start call.
Agent greeting (live): "Namaste! Neta Gym Voice. Ask me about any Indian MP's record. Hindi ya English, dono chalega."
Narrator: "Neta Gym Voice. A voice agent built on AssemblyAI that answers questions about 786 Indian MPs from public data."

SCENE 3 - Live Q&A demo (0:40-2:40) - the core; all answers are real lookups
Q1 (user, live mic): "What is the attendance of Rajiv Pratap Rudy?"
Agent (verified live): "Rajiv Pratap Rudy, Bharatiya Janata Party MP from Saran, Bihar has attended 100 percent of Parliament sittings, with 36 questions asked. Full record at neta-gym.github.io/mp-transparency-tracker."
Q2: "How many questions has Asaduddin Owaisi asked?"
Agent (verified live): "Asaduddin Owaisi, All India Majlis-E-Ittehadul Muslimeen MP from Hyderabad, Telangana has asked 29 questions in Parliament and taken part in 15 debates."
Q3: "Tell me about Sanjay Kumar Jha."
Agent (verified live): "Sanjay Kumar Jha, Janata Dal (United) MP from Rajya Sabha (Bihar) scores 69.6 out of 100 on transparency."
Q4 - the honesty beat: "What is the attendance of Rahul Gandhi?"
Agent (verified live): "We don't have a reliable public source for Rahul Gandhi's attendance yet. The full report card is at neta-gym.github.io/mp-transparency-tracker."
Narrator over Q4: "When the data is not there, the agent says so. No hallucinated numbers - every figure is a database lookup with a source."

SCENE 4 - Under the hood (2:40-3:20)
Visual: simple architecture diagram - caller -> AssemblyAI Voice Agent API (STT/LLM/TTS) -> deterministic ask tool -> MP database (PRS, Parliament portals, ADR/myneta) -> spoken answer. Show GitHub repo and the web tracker briefly.
Narrator: "AssemblyAI runs the real-time speech loop. The brain is deliberately boring: a rules-based tool over 786 MP records from public sources. No LLM invents a number. Ministers and missing data come back as honest nulls. And every MP gets a party-neutral transparency score from zero to one hundred."

SCENE 5 - Why it matters + close (3:20-3:45)
Visual: /talk page on a phone; end card with repo + live URL.
Narrator: "A first-time voter in Saran and a journalist in Delhi get the same instant, sourced answer. Neta Gym Voice - ask any MP about their record. Source and live demo in the links."

Demo risk notes for the shoot:
- Render free tier cold-starts ~30s. Load /talk, wait for the page, THEN start recording.
- Record in Safari or Chrome desktop, not an in-app browser (mic can be silently blocked).
- Wait for the full greeting before speaking - speaking over the greeting is handled now, but a clean take reads better.
- Do NOT demo: fund utilization (null in current data), side-by-side comparisons (single-MP answers only today), or Devanagari-script name lookup (English/Hinglish names only - see limitations).

---

## 3. PDF deck outline (8 slides, 16:9)

1. Title - Neta Gym Voice: Ask Any Indian MP About Their Record. Voice agent built on AssemblyAI. Team: Neta Gym. Live URL + repo.
2. Problem - Parliament publishes rich MP data; voters never see it (screenshot of a dense PRS PDF).
3. Product - 30-sec story: call, ask, get a sourced spoken answer. Screenshot of the live /talk UI.
4. Live answers - the 4 verified Q&A pairs from the video (Rudy 100%/36Q, Owaisi 29Q/15 debates, Jha 69.6 score, Rahul Gandhi honest null).
5. Architecture - diagram: AssemblyAI Voice Agent API (STT -> turn-taking -> TTS) with a deterministic ask tool; 786 MP records; no LLM in the data path.
6. Data & honesty - sources (PRS, Parliament portals, ADR/myneta); honest-null policy; ministers null by design; 786 indexed / 784 scored.
7. Why it wins - civic access: phone-call UX beats PDFs; party-neutral; bilingual speech layer with an English-first data brain (roadmap: Indic name matching, funds data).
8. Roadmap + links - outbound call support, WhatsApp bot, more languages; live app, repo, web tracker URLs.

---

## 4. Known limitations (go in the long description or deck - honesty is a feature)

- Fund utilization (MPLADS) answers return honest nulls in the current dataset; not demoed.
- Comparison questions answer one MP at a time.
- Devanagari-script names do not resolve yet (STT handles Hindi; the name index is English-first). Hinglish works for common names.
- AssemblyAI free tier: $49.85 of $50 credits remaining, no card on file. Render free tier cold start ~30s.

## 5. Distribution plan (GLM lesson: the last winner won on X views)

- Primary: X/Twitter thread from @Jupy_NY at submission time - hook tweet with the Rudy 100% answer clip, then the honesty-null clip (Rahul Gandhi), then architecture + links. Tag @AssemblyAI and @lablabai.
- Short vertical cuts of Scene 3 Q&A for X/LinkedIn/YouTube Shorts.
- LinkedIn post (Shridhar's account) aimed at civic-tech + India-policy audience.
- Ask AssemblyAI devrel for a retweet via their Discord hackathon channel; lablab Discord showcase channel post.
- Timing: submit ~Sep 25-28 so distribution runs into the Sep 30 deadline, not after it.
