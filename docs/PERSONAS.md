# Personas — Who They Are and Why They're Here

MOA's 14 personas aren't random names. Each one represents a specific philosophy about building software, products, or businesses. When you ask `--persona "Rich Hickey"`, the model adopts that person's actual thinking framework — not a generic "expert" voice.

---

## Code Review Personas

### Martin Fowler
**Philosophy:** Code should tell a clear story. If it's hard to read, refactor it.

Fowler literally wrote the book on refactoring. He identifies "code smells" — patterns that indicate deeper problems. When MOA reviews as Fowler, it looks for long methods, feature envy, data clumps, and suggests specific refactoring patterns.

**What he catches that others miss:** "This code works, but it'll be impossible to change in 6 months."

**Key works:**
- [Refactoring (2nd Edition, 2018)](https://martinfowler.com/books/refactoring.html)
- [Patterns of Enterprise Application Architecture](https://martinfowler.com/books/eaa.html)
- [martinfowler.com/bliki](https://martinfowler.com/bliki/) — decades of software design thinking

```bash
moa review --staged --persona "Martin Fowler"
```

---

### Kent Beck
**Philosophy:** Write the test first. Then write the simplest code that passes. Then refactor.

Beck invented Test-Driven Development (TDD) and Extreme Programming (XP). His core question is always: "What is the simplest thing that could possibly work?" When MOA reviews as Beck, it asks where the tests are, whether YAGNI (You Ain't Gonna Need It) applies, and if the code is simpler than it needs to be.

**What he catches that others miss:** "You built an abstraction for a problem you don't have yet."

**Key works:**
- [Test-Driven Development By Example](https://www.oreilly.com/library/view/test-driven-development/0321146530/)
- [Extreme Programming Explained](https://www.oreilly.com/library/view/extreme-programming-explained/0321278658/)
- [@KentBeck on X](https://x.com/KentBeck) — still actively thinking about software craft

```bash
moa review --staged --persona "Kent Beck"
```

---

### Rich Hickey
**Philosophy:** Simple is not the same as easy. Most software is accidentally complex.

Hickey created [Clojure](https://clojure.org/) and gave one of the most influential programming talks ever: ["Simple Made Easy"](https://www.infoq.com/presentations/Simple-Made-Easy/). His core distinction: "easy" means familiar or convenient, "simple" means not intertwined. When MOA reviews as Hickey, it asks whether you're complecting (intertwining) unrelated concerns, whether you're mutating state unnecessarily, and whether your abstractions are genuinely simple or just familiar.

**What he catches that others miss:** "You're confusing easy with simple. This is three concerns braided together."

**Key works:**
- [Simple Made Easy (talk, 2011)](https://www.infoq.com/presentations/Simple-Made-Easy/) — watch this first
- [Are We There Yet? (talk, 2009)](https://www.infoq.com/presentations/Are-We-There-Yet-Rich-Hickey/)
- [Clojure Rationale](https://clojure.org/about/rationale)

```bash
moa review --staged --persona "Rich Hickey"
```

---

### Sandi Metz
**Philosophy:** Small objects, small methods, strict rules. Measure complexity with hard numbers, not feelings.

Metz wrote [Practical Object-Oriented Design in Ruby (POODR)](https://www.poodr.com/) and is known for concrete, enforceable rules: classes under 100 lines, methods under 5 lines, no more than 4 parameters per method, controllers instantiate one object. When MOA reviews as Metz, it counts lines and parameters and tells you exactly where you're violating the rules.

**What she catches that others miss:** "This class has 7 constructor parameters. The limit is 4. Here's how to decompose it."

**Key works:**
- [Practical Object-Oriented Design (POODR)](https://www.poodr.com/)
- [99 Bottles of OOP](https://sandimetz.com/99bottles)
- [Sandi Metz' Rules (blog post)](https://thoughtbot.com/blog/sandi-metz-rules-for-developers)

```bash
moa review --staged --persona "Sandi Metz"
```

---

## Architecture Personas

### Kelsey Hightower
**Philosophy:** Infrastructure should be invisible. If your infra is more complex than your business logic, something is wrong.

Hightower was a principal engineer at Google and one of the most respected voices in cloud-native infrastructure. He's known for questioning whether you actually need Kubernetes, advocating for operational simplicity, and pushing 12-factor principles. When MOA reviews as Hightower, it asks whether your infrastructure choices match your team size.

**What he catches that others miss:** "You have 3 engineers and a Kubernetes cluster. That's a red flag."

**Key works:**
- [Kubernetes the Hard Way](https://github.com/kelseyhightower/kubernetes-the-hard-way) — the canonical K8s tutorial
- [No Code](https://github.com/kelseyhightower/nocode) — satirical "best way to write software is to not write any"
- [His talks and interviews](https://www.youtube.com/results?search_query=kelsey+hightower) on simplicity in infrastructure

```bash
moa ask --persona "Kelsey Hightower" "Do we need Kubernetes for this?"
```

---

### Martin Kleppmann
**Philosophy:** Understand what happens when the network partitions. Most distributed systems bugs are consistency bugs.

Kleppmann wrote [Designing Data-Intensive Applications (DDIA)](https://dataintensive.net/), widely considered the best book on distributed systems for practitioners. When MOA thinks as Kleppmann, it asks about your consistency model, what happens during network partitions, whether you've thought about event ordering, and whether your data pipeline guarantees are actually what you think they are.

**What he catches that others miss:** "Your system assumes exactly-once delivery, but your message broker guarantees at-least-once. What happens when a message is processed twice?"

**Key works:**
- [Designing Data-Intensive Applications](https://dataintensive.net/) — read this book
- [martin.kleppmann.com](https://martin.kleppmann.com/) — academic papers made practical
- [His talks on CRDTs and distributed data](https://www.youtube.com/results?search_query=martin+kleppmann)

```bash
moa ask --persona "Martin Kleppmann" "Review our event sourcing architecture"
```

---

### DHH (David Heinemeier Hansson)
**Philosophy:** Ship the monolith. You don't need microservices, you don't need Kubernetes, you don't need a SPA. Ship it with Rails and Postgres.

DHH created [Ruby on Rails](https://rubyonrails.org/) and runs [37signals](https://37signals.com/) (Basecamp, HEY). He's the most vocal advocate for monolithic architectures, server-rendered HTML, and questioning every layer of complexity. When MOA thinks as DHH, it's provocative — it will aggressively challenge your architectural assumptions and ask "Could you ship this with Rails and a Postgres database?"

**What he catches that others miss:** "You're cargo-culting Netflix's architecture. You're not Netflix."

**Key works:**
- [Ruby on Rails](https://rubyonrails.org/)
- [The Majestic Monolith](https://m.signalvnoise.com/the-majestic-monolith/) — his manifesto against microservices
- [HEY.com](https://hey.com) — email service built as a monolith
- [@dhh on X](https://x.com/dhh)

```bash
moa ask --persona "DHH" "Should we break this into microservices?"
```

---

## Product & Strategy Personas

### Shreya Doshi
**Philosophy:** High-leverage work over busy work. Pre-mortems over post-mortems. Decision quality over decision speed.

Doshi is a product leader (Stripe, Twitter) known for frameworks on [high-leverage product management](https://www.linkedin.com/in/shreyadoshi/). Her impact-vs-effort analysis cuts through feature requests to find what actually moves metrics. When MOA thinks as Doshi, it asks about leverage, whether this is a one-way or two-way door, and what the pre-mortem would reveal.

**What she catches that others miss:** "You're spending 3 months on a feature that moves a metric by 2%. Is there a 1-week version that gets you 80% of the impact?"

```bash
moa ask --persona "Shreya Doshi" "Is this feature high-leverage or just busy work?"
```

---

### Marty Cagan
**Philosophy:** Empowered product teams do discovery, not delivery. Feature factories ship features. Product teams ship outcomes.

Cagan wrote [Inspired](https://www.svpg.com/inspired/) and [Empowered](https://www.svpg.com/empowered/), the definitive books on product management. His core question: are you validating risk before building, or are you just taking stakeholder orders and shipping them? When MOA thinks as Cagan, it asks whether you've done discovery — have you talked to users, tested assumptions, identified the riskiest unknowns?

**What he catches that others miss:** "You built exactly what the stakeholder asked for. But did anyone verify that customers want it?"

**Key works:**
- [Inspired (2nd Edition)](https://www.svpg.com/inspired/)
- [Empowered](https://www.svpg.com/empowered/)
- [svpg.com](https://www.svpg.com/) — Silicon Valley Product Group blog

```bash
moa ask --persona "Marty Cagan" "We're building what the CEO asked for. Is that a problem?"
```

---

### April Dunford
**Philosophy:** Positioning is not messaging. It's the context that makes your product make sense. Get the category wrong and no amount of features will save you.

Dunford wrote [Obviously Awesome](https://www.aprildunford.com/obviously-awesome), the standard reference on product positioning. Her framework: what's your competitive alternative, what are your unique attributes, what value do they enable, who cares about that value, and what market category does that put you in? When MOA thinks as Dunford, it asks who your real competitor is (hint: it's often "do nothing" or "use a spreadsheet") and whether your positioning makes your product's value obvious.

**What she catches that others miss:** "You're positioning against Notion, but your real competitor is a Google Sheet. That changes everything."

**Key works:**
- [Obviously Awesome](https://www.aprildunford.com/obviously-awesome)
- [aprildunford.com](https://www.aprildunford.com/)
- [Her talk on positioning](https://www.youtube.com/results?search_query=april+dunford+positioning)

```bash
moa ask --persona "April Dunford" "How should we position this against the market leader?"
```

---

## Content & Writing Personas

### David Ogilvy
**Philosophy:** The headline is 80% of the ad. Be specific. Make a promise. Long copy sells.

Ogilvy founded Ogilvy & Mather and is considered the father of modern advertising. He hated cleverness without clarity — every headline should promise a benefit, every claim should be specific, and long-form copy that actually says something beats short-form copy that sounds nice. When MOA thinks as Ogilvy, it evaluates headlines for specificity and benefit, checks whether claims are backed by evidence, and pushes for direct response principles.

**What he catches that others miss:** "Your headline is clever but it doesn't tell me what I get. Nobody buys clever."

**Key works:**
- [Ogilvy on Advertising](https://www.ogilvy.com/ideas/ogilvy-advertising)
- [Confessions of an Advertising Man](https://www.goodreads.com/book/show/66009.Confessions_of_an_Advertising_Man)

```bash
moa ask --persona "David Ogilvy" "Write 5 headlines for this landing page"
```

---

### Ann Handley
**Philosophy:** Would a real person say this out loud? If not, rewrite it. Every sentence should earn its place.

Handley wrote [Everybody Writes](https://annhandley.com/books/) and champions clarity, empathy, and voice in content marketing. Her test is simple: read it out loud. If it sounds like a corporate press release, it fails. When MOA thinks as Handley, it cuts jargon, checks for conversational tone, and asks whether the reader would actually care about each sentence.

**What she catches that others miss:** "This paragraph has four sentences and none of them say anything a human would say at dinner."

**Key works:**
- [Everybody Writes (2nd Edition)](https://annhandley.com/books/)
- [annhandley.com](https://annhandley.com/)
- [Total Annarchy newsletter](https://annhandley.com/newsletter/)

```bash
moa ask --persona "Ann Handley" "Review this email. Does it sound human?"
```

---

## Builder & Solopreneur Personas

### Pieter Levels
**Philosophy:** Ship in a weekend. Revenue before features. No venture capital, no team, no excuses.

Levels is the most successful solo developer in the world — he built [Nomad List](https://nomadlist.com/), [Remote OK](https://remoteok.com/), [Photo AI](https://photoai.com/), and others, all as a solo developer generating millions in revenue. His approach: launch before it's ready, use the simplest possible tech stack (often just PHP + SQLite), skip databases when you can use flat files, and optimize for shipping speed over architectural purity.

**What he catches that others miss:** "You spent 3 months building something you could have validated with a landing page in a day."

**Key works:**
- [MAKE: Bootstrapper's Handbook](https://makebook.io/)
- [@levelsio on X](https://x.com/levelsio)
- [His open revenue dashboard](https://x.com/levelsio)

```bash
moa ask --persona "Pieter Levels" "Can I build this without a database?"
```

---

### Daniel Vassallo
**Philosophy:** Small bets. Portfolio strategy. Sell before you build. The minimum viable test is smaller than you think.

Vassallo left a $500K/year job at AWS to become an independent creator. He advocates for a portfolio approach to projects: instead of one big bet, run multiple small experiments. Test demand before building — sell the idea, take pre-orders, see if anyone cares. His framework: what's the smallest thing you can do to test whether this idea has legs?

**What he catches that others miss:** "You're about to spend 6 months building something. Have you tried selling it first? Even a tweet asking 'would anyone pay for X?' is a signal."

**Key works:**
- [The Small Bets community](https://dvassallo.gumroad.com/)
- [@dvassallo on X](https://x.com/dvassallo)
- [His AWS departure story](https://danielvassallo.com/only-intrinsic-motivation-lasts/)

```bash
moa ask --persona "Daniel Vassallo" "What's the minimum viable test for this idea?"
```
