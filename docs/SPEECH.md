# ReconAgent — 5-Minute Video Script

Timed for **~140 words/minute**, ~700 words = ~5:00. Written to be *said*,
not read — like you're telling someone what you built and why, not
presenting slides. Pair with [`PITCH.md`](PITCH.md) for on-screen cues.

---

### 0:00 – 0:45 — How I got here

> So I want to tell you about a problem I didn't fully understand until I
> started building for it.
>
> Every business that takes online payments ends up with three separate
> records of the same money — their own sales ledger, the payment gateway's
> settlement report, and the bank statement. I assumed these would basically
> match. They don't. Fees come in a little different than the contract says.
> A refund shows up in one place and never gets recorded in another. A payout
> that should've landed on Tuesday is still missing two weeks later.
>
> And nobody's stealing anything. It's just... messy. Quietly, constantly
> messy.

---

### 0:45 – 1:30 — Why nobody catches it

> What got me was realizing why this never gets fixed. It's not one big
> obvious error — it's dozens of tiny ones, buried across three files that
> don't even use the same format. A two-hundred-rupee overcharge on one
> transaction looks like nothing. But that same overcharge, repeating on
> every transaction, every day, for months — that's real money, and someone
> would have to sit and manually cross-check three spreadsheets, row by row,
> to ever find it.
>
> Nobody has time for that. So it just... doesn't get done.

---

### 1:30 – 2:15 — What I decided to build

> So I built ReconAgent to do that checking automatically — every time,
> without anyone opening a spreadsheet.
>
> You hand it the three files. It lines them all up, matches every
> transaction, and in seconds tells you what agrees and what doesn't. And
> when something's off, it doesn't just say "mismatch." It tells you what's
> wrong, how much money it's worth, and what to actually do next — in plain
> language, not error codes.

*[On screen: run a live sample — watch the numbers populate.]*

> On a real batch, about ninety-two percent of it resolves on its own. What's
> left is the small handful that genuinely needs a person to look at it.

---

### 2:15 – 3:00 — The decision I kept coming back to

> Here's the thing I was most careful about, honestly. I did not want an AI
> deciding money outcomes. I've seen what happens when a model confidently
> gets a number wrong.
>
> So I split the job in two. A plain, deterministic piece of code — no AI
> involved — does the actual matching and the actual math. It's exact, and
> you can trace every number back to where it came from. The AI's only job is
> to explain what that code already found, in a way a human can quickly
> understand — and if a number looks off to it, to say so instead of quietly
> going along with it.
>
> Nothing gets auto-approved unless it's both confident *and* small enough in
> rupee terms to be safe. Everything that actually matters goes to a person,
> with the explanation already written for them.

---

### 3:00 – 3:30 — Where this actually helps

> This is for the finance team that's currently doing this by hand once a
> month — the ones losing a full day to spreadsheets they'd rather not open.
> It's for the founder who has no idea a fee's been slightly wrong for six
> months, because nobody had time to check. Anywhere real money moves through
> a gateway, this pays for itself the first time it catches something.

---

### 3:30 – 4:35 — How I actually built it

> A few things mattered while building this. I didn't want to lock this into
> one AI company, so instead of one model, it's a chain — Gemini, then Groq,
> then OpenRouter, all on free tiers. If one's rate-limited, it just moves to
> the next. If every single one is down, the system doesn't break — it just
> sends more items to a human instead of guessing.
>
> I also didn't want to invent fake data. There's no public dataset of real
> reconciliation records — nobody publishes their confidential financials —
> so instead I built a generator that produces real *formats*: actual
> Razorpay settlement reports, Stripe balance files, SWIFT bank statements —
> with real economics behind them, fees and taxes calculated the way they
> actually work in India, the US, and Europe.
>
> Underneath, it's a Python backend doing the matching, a Next.js dashboard
> you actually want to look at, and MongoDB holding every record and every
> decision so nothing's a black box. And the whole thing runs for free — no
> infrastructure cost, nothing standing between someone and actually using it.

---

### 4:35 – 5:00 — Why I think this matters

> I didn't build this to replace anyone's finance team. I built it so they
> stop spending their time on the ninety percent that's routine, and only see
> the ten percent that actually needs their judgment — already explained,
> already sized, ready for a decision.
>
> That's the whole idea. Thanks for watching.

---

## Recording notes

- **~680 words / ~5:00** at 140 wpm. Read it once with a timer — natural
  conversational pace runs a little faster (150–160 wpm), so you may land
  closer to 4:15–4:30, which leaves room to breathe or add a pause over a
  chart.
- Say it like you're explaining it to a friend, not presenting it. A few
  stumbles and "honestly" / "so" are fine — that's what makes it sound like
  you, not a script.
- If you need to cut time, trim the "How I actually built it" section first
  — it's the most detail-heavy and least essential to the story.
