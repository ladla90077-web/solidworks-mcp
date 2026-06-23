---
name: Setup Full Simulation
description: Configure a complete simulation from geometry to ready-to-solve.
---

# Setup Full Simulation

## What You're Actually Doing

You're building a model of reality. Every simulation is an approximation - the goal is to capture enough of the physics to answer the engineer's question, without capturing so much that it becomes unwieldy or unsolvable.

A good simulation setup isn't the most detailed one possible. It's the simplest one that answers the question reliably.

Before touching any settings, be crystal clear on: **What question is this simulation supposed to answer?** Everything flows from that.

## When to Check In (And Why)

### 1. After Understanding the Question

Before any setup, confirm:
- What are they trying to learn? ("Will it break?" "How hot will it get?" "What's the safety factor?")
- What does success look like? (Pass/fail criteria, comparison targets, accuracy needs)
- What's the context? (Design stage, certification, troubleshooting)

**Why this matters:** The question determines the analysis type, what simplifications are acceptable, what boundary conditions matter, and how accurate the results need to be. A thermal analysis and a stress analysis of the same part are completely different setups.

### 2. When Making Modeling Decisions

Key decisions that shape the simulation:
- Analysis type (static, transient, linear, nonlinear, coupled)
- Geometry simplifications (symmetry, feature suppression, 2D vs 3D)
- Material model complexity (linear elastic, plasticity, temperature-dependent)
- Contact and connections (bonded, frictional, bolted joints)

**Why this matters:** These aren't just settings - they're assumptions about reality. The engineer needs to know what assumptions you're making and agree they're appropriate. A linear analysis when the part yields gives wrong answers. A nonlinear analysis when linear would suffice wastes time.

### 3. Before Solving - Get Explicit Approval

Review the complete setup with the user and get explicit approval before solving. Summarize:
- What's being analyzed and why (confirm the question)
- Key modeling choices and assumptions made
- Loads, constraints, and materials applied
- Expected solve time and output
- Any concerns or limitations

**Do not solve without user approval.** Solves consume time and computational resources. The user should consciously decide to proceed, not discover a solve running unexpectedly.

**Why this matters:** This is the last chance to catch errors before committing resources. It also ensures the user knows exactly what's being simulated - no surprises when results come back.

## How to Think About Setup

### Start with the Question, Work Backward

| Question | Likely Analysis | Key Considerations |
|----------|-----------------|-------------------|
| "Will it break under this load?" | Static structural | Stress vs. yield/ultimate, safety factors |
| "How much will it deflect?" | Static structural | Deformation limits, stiffness requirements |
| "Will it overheat?" | Thermal (steady/transient) | Temperature limits, heat paths, cooling |
| "Are there resonance concerns?" | Modal | Natural frequencies vs. excitation frequencies |
| "How long will it last?" | Fatigue | Load cycles, stress ranges, life targets |
| "What happens during assembly?" | Nonlinear static | Large deformation, contact, sequence |
| "How does it respond to impact?" | Explicit dynamics | Energy absorption, peak accelerations |

### Geometry: Model What Matters

**Simplify aggressively, but not where it counts:**
- Remove features that don't affect results (logos, text, small cosmetic details)
- Keep features that drive the physics (fillets at stress concentrations, cooling channels)
- Use symmetry when appropriate (cuts model size significantly)
- Consider 2D if the geometry and loading support it

**Common simplification decisions:**
- Bolted joints -> bonded contact or beam connections (if joint behavior isn't the question)
- Thin parts -> shell elements (if through-thickness stress isn't critical)
- Assemblies -> single part with averaged properties (for stiffness studies)

### Materials: Match the Physics

**Questions to answer:**
- What material properties does this analysis need? (E, v for structural; k, c, p for thermal)
- Is linear elastic sufficient, or will the material yield?
- Are properties temperature-dependent in the operating range?
- For composites: is smeared properties okay, or do you need laminate detail?

**Common mistakes:**
- Missing Poisson's ratio (causes wrong stress distribution)
- Using room temperature properties at elevated temperature
- Linear elastic when stress exceeds yield
- Wrong units (GPa vs MPa is a 1000x error)

### Boundary Conditions: Represent Reality

**Constraints should reflect how the part is actually held:**
- What's actually fixed, and what can move?
- Are supports rigid, or do they have compliance?
- Is a fully fixed constraint realistic, or should it be a support/spring?
- Over-constraining hides real stress; under-constraining causes rigid body motion

**Loads should reflect what actually happens:**
- What forces, pressures, temperatures actually act on this?
- How are loads transferred? (Through contact? Directly applied? Via fasteners?)
- Are there load combinations or sequences that matter?
- Units check: is that force in N or lbf? Pressure in Pa or MPa?

### Connections: How Parts Talk to Each Other

**For assemblies, define how parts interact:**
- Bonded: welded, glued, or simplification of tight fit
- No separation: can slide but not pull apart
- Frictional: can slide and separate, with friction
- Contact: can separate and close, affects load path

**Connection choices affect results significantly:**
- Bonded overstates stiffness if parts can actually separate
- Missing contact means loads don't transfer correctly
- Wrong friction coefficient changes slip behavior

### Solver Settings: Usually Defaults Work

**But verify for special cases:**
- Nonlinear: load stepping, convergence criteria, line search
- Transient: time step size relative to physics (thermal time constant, wave speed)
- Large deformation: appropriate formulation enabled
- Contact: appropriate algorithm, stabilization if needed

## Setup Checklist

Before solving, verify:

**Geometry**
- [ ] Appropriate simplifications made and documented
- [ ] Critical features preserved
- [ ] No unintended gaps or interferences

**Materials**
- [ ] All bodies have materials assigned
- [ ] Properties appropriate for analysis type
- [ ] Properties appropriate for operating conditions
- [ ] Units consistent

**Mesh**
- [ ] Quality verified in critical regions
- [ ] Refinement where needed for accuracy
- [ ] Element types appropriate for the physics

**Boundary Conditions**
- [ ] Constraints represent physical supports
- [ ] No over-constraining or under-constraining
- [ ] Loads applied to correct surfaces/bodies
- [ ] Load magnitudes and directions verified
- [ ] Units verified

**Connections**
- [ ] Contact defined between parts that interact
- [ ] Contact type matches physical behavior
- [ ] No missing connections

**Solver**
- [ ] Analysis type matches the question
- [ ] Settings appropriate for the physics
- [ ] Output requests include needed results

## Failure Modes to Avoid

**Solving the wrong problem.** A perfect setup for the wrong analysis type is useless. Confirm the question first.

**Over-complicating.** Nonlinear contact with friction when bonded would suffice. Full 3D when 2D captures the physics. Match complexity to need.

**Under-specifying.** Missing loads, missing constraints, missing materials. The simulation doesn't know what you forgot to tell it.

**Trusting defaults blindly.** They're reasonable starting points, not always correct. Verify critical settings.

**Unit chaos.** Mixed units cause silent errors. Verify: is that GPa or MPa? N or kN? mm or m?

**Ignoring warnings.** Setup warnings exist for a reason. Address them or consciously accept the implications.

## Adapt to Context

**Early design exploration:** Simpler setup, faster turnaround, directional accuracy is fine.

**Design validation:** More careful setup, verified assumptions, document what's modeled and what's not.

**Certification/qualification:** Rigorous setup, mesh convergence, sensitivity studies, full documentation.

**Troubleshooting a failure:** Match the actual conditions closely, less room for simplification.

Match the setup rigor to how the results will be used.
