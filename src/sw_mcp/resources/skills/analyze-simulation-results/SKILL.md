---
name: Analyze Simulation Results
description: Analyze and interpret simulation results to answer engineering questions.
---

# Analyze Simulation Results

## What You're Actually Doing

You're helping an engineer answer a question. Every simulation exists to answer something: "Will this break?" "Is cooling adequate?" "Does this meet the spec?" Your job is to help them get to that answer with confidence.

This is not about producing a document. The report is a byproduct - a record of the reasoning that led to a conclusion. If you focus on filling out report sections, you'll produce something thorough but useless. If you focus on answering the engineer's actual question, the report writes itself.

**The goal shifts based on context:**
- Sometimes it's a quick sanity check: "Does this look reasonable?"
- Sometimes it's decision support: "Pass or fail against these requirements?"
- Sometimes it's investigation: "Why is this region showing high stress?"
- Sometimes it's documentation: "Create a record for stakeholders"

Read the situation. A 50-page report for a sanity check is a failure. A one-liner for a certification analysis is also a failure.

---

## When to Check In (And Why)

Check-ins exist for one reason: **when you need user input to proceed correctly.**

Don't check in to show progress. Don't check in because you finished a "phase." Check in when your next action depends on information or judgment only the user can provide.

There are three natural decision points:

### 1. After Understanding the Setup

Before you do any analysis, make sure you understand:
- What's being analyzed and under what conditions
- What question the engineer is trying to answer
- What "success" looks like (requirements, allowables, or just "reasonable")

**Why this matters:** If you misunderstand the goal, everything downstream is wasted work. Five minutes of alignment here saves hours of rework.

**What to confirm:**
> "It looks like you're evaluating [geometry] under [loading] to determine [question]. Is that right? And are there specific requirements I should compare against?"

If the setup is obvious from context or they've already told you, don't ask again.

### 2. If Something Blocks a Valid Conclusion

As you examine the model and results, you might find things that undermine confidence:
- Mesh quality issues in critical regions
- Solver warnings or convergence problems
- Boundary conditions that don't match reality
- Results that look non-physical

**Why this matters:** You can identify these issues, but you can't decide what to do about them. That depends on context you don't have - timeline, stakes, whether a rerun is feasible.

**What to share:**
> "I found [issue] which could affect [specific consequence]. Do you want to proceed with this caveat noted, or address it first?"

If everything looks sound, don't interrupt just to say "mesh looks fine." Proceed.

### 3. Before Finalizing Conclusions

This is the most important check-in. You've done physics-based reasoning to interpret the results. But:
- Your interpretation could be wrong
- The engineer knows context you don't
- What looks like a failure might be acceptable (or vice versa)

**Why this matters:** Engineering judgment. You can explain what the numbers mean physically, but the engineer decides what to do about it.

**What to share:**
> "Here's what I'm seeing: [key findings with reasoning]. My assessment is [pass/fail/conditional]. Does this align with your expectations?"

---

## How to Think About the Analysis

### Start with the Question

Before extracting any results, be clear on what you're trying to answer. This shapes everything:
- Which results matter (von Mises? Principal stress? Temperature?)
- What regions to focus on
- What constitutes "concerning"
- How detailed the report needs to be

### Validate Before You Trust

Results from a bad model are worse than no results - they create false confidence. Before interpreting anything, assess:

**Mesh quality** - Are there issues in regions that matter? A poor mesh far from critical areas might be fine. A poor mesh at a stress concentration invalidates those results.

**Boundary conditions** - Do they represent reality? Over-constrained models show artificially low stress. Under-constrained models don't converge or show rigid body motion.

**Convergence** - Did the solver actually find a solution? Warnings matter.

Don't just check boxes. Ask: "Is there anything here that would make me distrust the results in the regions I care about?"

### Extract What Matters

Based on the analysis type and the question being answered:

| Analysis Type | Primary Results | Key Question |
|---------------|-----------------|--------------|
| Static Structural | Stress, deformation, safety factor | Will it break or deform too much? |
| Modal | Natural frequencies, mode shapes | Resonance concerns? |
| Thermal | Temperature distribution, gradients | Will it overheat? |
| CFD | Velocity, pressure drop, flow rates | Is flow adequate? |
| Fatigue | Life, damage, safety factor | How long will it last? |

Focus on what answers the question. Don't extract everything just because you can.

### Identify What's Critical

Not every high value is a concern. Look for:
- Locations of global extremes
- Stress concentrations (and whether they're real or numerical artifacts)
- Regions near or exceeding allowables
- Anything unexpected that doesn't match physics

**Distinguish artifacts from reality:**
- Stress singularities at sharp corners are numerical, not physical - infinite stress in zero volume isn't real
- Single-element peaks at boundaries are often mesh-dependent
- If a concerning result persists across multiple elements, it's more likely real

### Interpret with Physics

Don't just report numbers. Explain why they make sense (or don't):

- "The stress concentration at the fillet is expected - geometric discontinuities amplify local stress"
- "The hot spot is at the board center because that's where high-power components cluster with limited conduction paths"
- "This peak is a singularity at a sharp corner - not a real failure point"

If you can't explain why a result occurs, that's a flag. Either dig deeper or note the uncertainty.

### Be Quantitative

"High stress" means nothing. "285 MPa, which is 95% of yield" means something. Always include:
- Actual values with units
- Comparison to allowables or material limits
- Margins or safety factors where relevant

---

## The Report Itself

Build it as you go - don't wait until the end. This makes progress visible and lets you incorporate feedback. Default to markdown, so you can imbed figures. Keep the workspace clean by putting the figures in a folder unless the user asks otherwise.

**Structure it for the reader:**

1. **Executive Summary** - The answer, in 3-5 sentences. What was analyzed, what was found, pass/fail, main recommendation. Someone should be able to read only this and know the outcome.

2. **Model Description** - What was analyzed and how. Geometry, materials, loads, boundary conditions.

3. **Model Validation** - Why the results should be trusted (or caveats if not). Mesh quality, convergence, any concerns.

4. **Results** - What the simulation showed. Key values, critical regions, visualizations.

5. **Interpretation** - What it means. Physics-based reasoning, comparison to requirements, assessment.

6. **Conclusions** - The answer and what to do next. Pass/fail, recommendations, confidence level.

**Visualizations matter.** A good contour plot communicates more than paragraphs of text. Include:
- Overall distribution plots
- Zoomed views of critical regions
- Deformed shapes (for structural)

---

## Failure Modes to Avoid

**Producing a 50-page report nobody reads.** Match depth to need. A sanity check doesn't need exhaustive documentation.

**Checking in too often.** If you're asking questions that don't change what you do next, you're just creating interruptions.

**Following the template mechanically.** The structure exists to serve communication, not the other way around. Skip sections that don't apply. Expand on what matters.

**Flagging things that aren't concerning.** Not every mesh imperfection matters. Not every stress concentration is a failure. Use judgment about what actually affects the conclusion.

**Burying the lede.** The most important information should be the most prominent. Don't make the engineer hunt for the answer.

**Missing the actual question.** If they wanted to know about thermal performance and you wrote 10 pages about stress, you failed regardless of how thorough the stress analysis was.

---

## Adapt to Context

**Quick sanity check:** Minimal validation, focus on the specific question, short report or even just a verbal summary.

**Formal deliverable:** Thorough validation, comprehensive documentation, all sections complete, professional formatting.

**Investigation:** Deep dive on specific regions, may not need full report structure, focus on understanding the "why."

**Comparison study:** Side-by-side results, relative differences matter more than absolute values, clear recommendation on which option is better.

Read what the engineer actually needs. Ask if you're not sure.
