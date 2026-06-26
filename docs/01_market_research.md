# Tier Zero — Market Research & Sizing

*Working name: **Tier Zero** — the voice + vision agent that resolves IT tickets before they reach Tier 1.*

Beta Fund AI Agents Hackathon · June 26, 2026 · Track: Agents for Hire / Workflow & Operations

---

## 1. The problem, in money

Most IT tickets are not hard. They're repetitive: password resets, VPN, drive mapping, "how do I export," sign-in loops, printer issues. The problem is they still cost a human to resolve.

- **Tier-1 tickets are 50–80% of all support volume.** (Mosaic AI)
- **A Tier-1 ticket costs ~$20 to resolve in-house** (industry average for a call to L1 support; commonly cited HDI/MetricNet mean is in the low $20s). Outsourced L1 runs $6–$13. (NetGain, ScienceSoft)
- That cost is almost entirely **labor on problems a user could solve themselves with the right instruction at the right moment.**

A mid-size company with 4,000 L1 tickets/month is spending **~$80,000/month (~$960K/year)** resolving things a good self-service layer should deflect.

## 2. Why existing self-service doesn't fully solve it

Knowledge bases and text chatbots already exist — and they cap out. Real-world AI deflection lands at **35–66%**, not 100%:

- Cynet: 47% Tier-1 deflection after AI self-service (CSAT 79 → 93). (Kustomer)
- Freshservice Freddy: 66% deflection. (Fini Labs)
- Forethought: 40–60% on Tier-1. Kustomer: 35–55%.
- Password resets specifically: 60–80% deflection when well-configured. (eesel)

The gap — the 30–60% that *don't* deflect — is dominated by **non-technical and frontline users who can't use a text knowledge base**, because:

1. **They don't know the words.** They can't search "remap network drive" — they can only say "the folder thing is gone." Text search fails on vocabulary; a knowledge base assumes you already know what to ask.
2. **They can't follow text steps.** Reading step 4 while doing step 3 loses them. They need to be *talked through it*, slowly, with the ability to ask "wait, which button?"
3. **The agent can't see their screen.** A text bot answers in the abstract. It can't say "you're on the wrong tab."

**This is Tier Zero's wedge: voice + vision.** The user talks (Deepgram), the agent talks back calmly and slowly, the user sends a screenshot, and the agent reads the actual screen and points to the exact thing — by drawing on the image they just sent. It meets the panicked, non-technical user where text self-service abandons them.

## 3. Market size

| Layer | Figure | Source |
|---|---|---|
| Agentic AI market (2025) | **$7.06B**, → $93.2B by 2032 (44.6% CAGR) | Astute / MarketsandMarkets |
| Agentic AI dev-platform market (2025) | $10.58B → $215B by 2035 | Astute Analytica |
| Proxy SAM — IT service desk labor on L1 | 50–80% of a multi-billion-dollar global helpdesk spend | derived |

**Bottom-up SAM (cleaner for a pitch than top-down TAM):**
US knowledge-worker companies generate hundreds of millions of L1 tickets/year. At ~$20/ticket with even a conservative 40% deflectable share, the *recoverable* spend is in the **billions of dollars per year** — and that's the budget Tier Zero competes for, priced as a fraction of cost-per-ticket-saved.

## 4. Comparables — and why the timing is now

The category just had two exits inside nine months:

| Company | Outcome | Signal |
|---|---|---|
| **Moveworks** | Acquired by **ServiceNow for $2.85B** (Mar 2025). Was >$100M ARR, 350+ enterprises, 5M+ end-users. | Category is proven and valuable. |
| **Aisera** | Acquired by **Automation Anywhere** (Nov 2025). Had raised $180M; ~$638M valuation in 2022. | Second leader gone. |
| Microsoft Copilot Studio, Salesforce Agentforce, Google Gemini Enterprise, Sierra, Kore.ai | Active | Big platforms compete on breadth, not on the non-technical voice+vision niche. |

**The pitch line:** *"The two companies that owned L1 deflection just got acquired off the board. The incumbents left are text-first and built for technical users. Tier Zero takes the wedge they never served — voice + vision for the frontline worker who can't use a chatbot — and lists it on AgentBox so any company can hire it per-seat tomorrow."*

## 5. Business model

- **Pricing:** per-seat/month or per-resolution, priced well under the ~$20 human cost-per-ticket (e.g. $2–5 per deflected ticket → buyer keeps the spread, you capture margin on near-zero marginal cost).
- **The compounding story (investors love this):** every resolved ticket is cached in Redis as *symptom → fix*. Repeat issues resolve instantly and cost ~nothing, so **deflection rate climbs and unit cost falls the longer a customer runs it.** Land-and-expand built in.
- **Go-to-market via AgentBox:** free to list, usage-based, live in front of enterprise buyers on publish. Zero idle cost — you only pay when it works.

## 6. The slide numbers (memorize these)

- Tier-1 = **50–80%** of tickets.
- ~**$20** to resolve one L1 ticket by hand.
- Current AI deflection caps at **~47–66%** — the rest is the non-technical long tail Tier Zero targets.
- One 4,000-ticket/month customer = **~$960K/yr** of L1 spend; deflecting 40% = **~$384K/yr saved**.
- Category just printed a **$2.85B** exit (Moveworks).

## 7. Honest risks (have answers ready)

- **"Why not just Google it?"** → People who *could* don't, because they lack the vocabulary and the confidence to start. Voice removes both.
- **"Won't Copilot/Agentforce eat this?"** → They're text-first and aimed at technical users inside one suite. The voice+vision frontline niche is underserved, and AgentBox lets you be hired across suites.
- **"Hallucinated instructions are dangerous in IT."** → Constrain to a curated playbook + retrieval; the agent only gives vetted steps, escalates anything outside the library to a human. Vision confirms state before each step.

---

### Sources
- [NetGain — The Cost of Tier 1 Help Desk Tickets](https://www.netgainit.com/blogs/the-cost-of-tier-1-help-desk-tickets/)
- [ScienceSoft — Help Desk Pricing 2026](https://www.scnsoft.com/it-operations/help-desk/pricing)
- [Mosaic AI — Tier 1 ticket deflection guide](https://getmosaic.ai/blog/tier-1-ticket-deflection)
- [Kustomer — AI-powered ticket deflection 2026](https://www.kustomer.com/resources/blog/ai-powered-ticket-deflection/)
- [eesel AI — AI for password reset requests](https://www.eesel.ai/blog/ai-for-password-reset-requests)
- [Fini Labs — AI self-service deflection platforms](https://www.usefini.com/guides/ai-platforms-self-service-deflection-ticket-reduction)
- [Contrary Research — Moveworks breakdown](https://research.contrary.com/company/moveworks)
- [CorePiper — Moveworks & Aisera acquired](https://corepiper.com/blog/moveworks-aisera-acquired-enterprise-ai-buyers/)
- [Astute Analytica — Agentic AI development platform market](https://www.astuteanalytica.com/industry-report/agentic-ai-development-platform-market)
- [MarketsandMarkets — Agentic AI market report](https://www.marketsandmarkets.com/Market-Reports/agentic-ai-market-208190735.html)
