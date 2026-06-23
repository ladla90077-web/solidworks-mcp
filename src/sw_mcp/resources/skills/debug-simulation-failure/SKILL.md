---
name: Debug Simulation Failure
description: Debug and resolve simulation failures or unexpected results.
---

# Debug Simulation Failure

## What You're Actually Doing

You're helping an engineer get from "this isn't working" to either a working simulation or a clear understanding of why it can't work. The goal isn't to produce a debugging report - it's to solve the problem.

**Two distinct situations:**
1. **Simulation won't run** - errors, crashes, non-convergence. The engineer has no results.
2. **Simulation ran but results are wrong** - unexpected values, non-physical behavior, results that don't match intuition or test data.

These require different approaches. The first is about mechanics (what's preventing the solver from working). The second is about physics (what's wrong with the model's representation of reality).

## When to Check In (And Why)

### 1. After Understanding the Problem

Before debugging, make sure you understand:
- What did they expect to happen?
- What actually happened? (Error messages, unexpected values, non-convergence)
- Has this model/simulation ever worked before? What changed?

**Why this matters:** "It's broken" could mean many things. A convergence failure in a nonlinear analysis is a different problem than wrong stress values in a linear static. You need to know what you're debugging.

### 2. When You've Identified Likely Causes

Once you've examined the model and logs, share your diagnosis before changing anything:
- What you think is wrong and why
- What you'd like to try first
- What the risk/impact of the change is

**Why this matters:** You can identify issues, but the engineer knows context you don't - maybe that "problem" is intentional, or maybe there's a reason they can't change it. And changes to a simulation model shouldn't be made without the engineer's knowledge.

### 3. After Attempting a Fix

Verify the fix actually worked:
- Did the simulation run successfully?
- Do the results make physical sense?
- Did the fix introduce new problems?

**Why this matters:** "It runs now" isn't the same as "it's correct." A simulation that converges to wrong answers is worse than one that fails to converge.

## How to Think About Debugging

### Start with the Error

Read the actual error messages and solver output. This sounds obvious, but it's often skipped. The solver usually tells you what went wrong:

- **Convergence failures** - Often point to specific elements, time steps, or load increments where things went wrong
- **Negative pivot / singular matrix** - Usually rigid body motion (under-constrained) or collapsed elements
- **Element distortion** - Mesh quality issues or excessive deformation
- **Material errors** - Properties out of range or inappropriate for the analysis type

Don't guess. Read what the solver is telling you.

### Categories of Failure

Most simulation failures fall into a few buckets:

**Mesh Problems**
- Poor element quality in critical regions
- Insufficient refinement for the physics
- Distorted elements that can't handle the deformation

**Boundary Condition Problems**
- Under-constrained: rigid body motion, singular matrix
- Over-constrained: artificially stiff behavior, stress concentrations at constraints
- Unrealistic constraints: fully fixed when should be supported, point loads when should be distributed

**Solver Settings**
- Time step too large for the physics
- Convergence criteria too tight or too loose
- Wrong solver type for the problem (linear vs nonlinear, implicit vs explicit)

**Material Definition**
- Missing properties required for the analysis type
- Properties out of realistic range
- Inappropriate material model for the loading

**Geometry Issues**
- Interferences or gaps in assemblies
- Sliver surfaces or small features causing mesh problems
- Contact surfaces not properly defined

**Load Definition**
- Magnitude errors (wrong units, missing factors)
- Application method issues (force vs pressure, ramping)
- Load path problems in nonlinear analysis

### The Debugging Process

1. **Reproduce and characterize** - Make sure you understand exactly what's failing and when
2. **Read the output** - Error messages, solver logs, convergence history
3. **Form a hypothesis** - Based on the evidence, what's most likely wrong?
4. **Test the hypothesis** - Make a targeted change to verify
5. **Verify the fix** - Confirm it actually solved the problem without introducing new ones

Resist the urge to change multiple things at once. You won't know what fixed it (or what made it worse).

## "It Runs But Results Are Wrong"

This is harder than "it won't run" because there's no error message pointing you to the problem.

**Compare against expectations:**
- Hand calculations for simple cases
- Previous working models
- Test data or published results
- Physical intuition (does this even make sense?)

**Common causes of wrong results:**
- Unit mismatches (GPa vs MPa, mm vs m)
- Missing or wrong material properties
- Boundary conditions that don't represent reality
- Mesh too coarse in critical regions
- Wrong analysis type for the physics (linear when nonlinear needed)
- Contact not properly defined

**Sanity checks:**
- Are reaction forces in equilibrium with applied loads?
- Is strain energy reasonable?
- Do deformations look physically plausible?
- Are stress patterns what you'd expect from the loading?

## Failure Modes to Avoid

**Changing things randomly.** Without a hypothesis, you're just hoping to get lucky. Even if it works, you won't know why.

**Missing the obvious.** Read the error message. Check the units. Verify the constraints. The problem is often simpler than you think.

**Over-engineering the fix.** If a coarse mesh is the problem, refine the mesh. Don't redesign the entire model.

**Declaring victory too soon.** "It converged" doesn't mean it's right. Verify the results make physical sense.

**Hiding the real problem.** Loosening convergence criteria or adding artificial damping might make it "work" but mask a real modeling issue.

## Adapt to Context

**Quick triage:** Engineer just needs to know if this is fixable or needs a complete redo.

**Collaborative debugging:** Work through the problem together, explaining what you're checking and why.

**Teaching moment:** Engineer is learning - explain the debugging process, not just the fix.

**Critical deadline:** Focus on getting it working, document the shortcuts taken so they can be addressed later.

Read what the engineer needs. Sometimes they want to understand the root cause deeply; sometimes they just need it to run before a meeting.
