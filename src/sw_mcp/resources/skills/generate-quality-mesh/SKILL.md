---
name: Generate Quality Mesh
description: Create a quality mesh appropriate for the analysis type and critical regions.
---

# Generate Quality Mesh

## What You're Actually Doing

You're creating a mesh that's good enough for the analysis - accurate where it matters, efficient where it doesn't. A good mesh isn't the finest mesh possible; it's one that gives reliable results without wasting computational resources.

Mesh quality is always relative to what you're solving. A mesh that's perfect for a thermal analysis might be completely inadequate for stress concentrations. The question isn't "is this mesh good?" but "is this mesh good enough for this specific analysis?"

## When to Check In (And Why)

### 1. After Understanding the Requirements

Before meshing, understand:
- What analysis will this mesh support? (Static, modal, thermal, CFD, nonlinear...)
- Where are the critical regions? (Stress concentrations, contact zones, areas of interest)
- Are there accuracy requirements or element count constraints?
- Any geometric features that need attention? (Thin sections, fillets, small features)

**Why this matters:** A mesh for a linear static stress analysis needs refinement at fillets and notches. A mesh for a thermal analysis needs refinement at interfaces and boundaries. Meshing blind produces either waste or inaccuracy.

### 2. After Quality Verification Fails

If quality checks reveal issues, share before re-meshing:
- What failed and where
- Why it matters for this analysis
- What you'd change to fix it

**Why this matters:** Not all quality failures are equal. Poor aspect ratio far from critical regions might be acceptable. Poor aspect ratio at a stress concentration is a problem. The engineer should know what tradeoffs are being made.

### 3. When Facing Tradeoffs

Sometimes you can't have it all:
- Finer mesh = longer solve times
- Capturing small features = more elements
- Multiple critical regions competing for refinement budget

**Why this matters:** These are engineering decisions, not meshing decisions. The engineer needs to weigh accuracy vs. computational cost based on their timeline and requirements.

## How to Think About Meshing

### Start with the Physics

Different analyses have different mesh requirements:

| Analysis Type | Critical Mesh Requirements |
|---------------|---------------------------|
| Static Structural | Refinement at stress concentrations (fillets, notches, holes), adequate through-thickness elements for bending |
| Contact | Fine mesh at contact interfaces, matched mesh or appropriate contact formulation |
| Thermal | Refinement at boundaries and interfaces, adequate resolution for gradients |
| Modal | Enough elements to capture mode shapes, no need for stress concentration refinement |
| CFD | Boundary layer resolution, refinement in regions of interest, quality for convergence |
| Nonlinear | Quality to survive large deformations, refinement where plasticity or damage expected |

### Critical Regions First

Identify where mesh quality actually matters:
- Locations where you need accurate results (stress hot spots, measurement points)
- Geometric features that create gradients (fillets, notches, thickness transitions)
- Contact interfaces and boundary condition application zones
- Areas where the physics is complex (plasticity, large deformation, flow separation)

Refine these regions. Be more relaxed elsewhere.

### Quality Metrics That Matter

Run these verifiers and understand what they mean:

**Aspect Ratio**
- Ratio of longest to shortest element dimension
- High values (>20) cause inaccurate gradients
- Critical in regions with stress/temperature gradients

**Skewness**
- How far element shape deviates from ideal
- High values (>0.9) cause numerical issues
- Especially important for CFD and nonlinear analysis

**Jacobian**
- Measures element distortion
- Negative values mean inverted elements (fatal)
- Low positive values (<0.2) cause accuracy problems

**Element Size Transition**
- How abruptly element size changes
- Rapid transitions (>2x size change between neighbors) cause artificial stress gradients

**Through-Thickness Elements**
- For bending-dominated problems, need multiple elements through thickness
- Rule of thumb: 3+ elements for bending, 1 may be fine for membrane

### The Meshing Process

1. **Understand the analysis** - What physics, what regions matter
2. **Set global controls** - Base element size appropriate for the geometry
3. **Add local refinement** - Sizing controls at critical regions
4. **Generate and verify** - Run quality checks
5. **Iterate if needed** - Fix issues in regions that matter
6. **Document** - Note any compromises or areas needing attention

## Verification Checklist

After meshing, run quality checks and assess:

**Hard failures (must fix):**
- Negative Jacobian elements
- Disconnected mesh regions (unintended)
- Missing mesh on critical geometry

**Likely problems (fix in critical regions):**
- Aspect ratio > 100 anywhere, > 20 in critical regions
- Skewness > 0.95 anywhere, > 0.75 in critical regions
- Rapid size transitions at region boundaries

**Worth noting (context dependent):**
- Total element count vs. computational budget
- Element types appropriate for the analysis
- Mesh density adequate for expected gradients

## Failure Modes to Avoid

**Uniform refinement everywhere.** You'll run out of elements or patience. Refine where it matters, be coarse where it doesn't.

**Ignoring quality in critical regions.** A great average quality metric means nothing if the stress concentration has terrible elements.

**Chasing perfect metrics.** Some quality issues don't affect results. Don't spend hours fixing aspect ratio in a region you don't care about.

**Forgetting the analysis type.** A mesh validated for static stress might be wrong for nonlinear. Re-verify when the analysis changes.

**Accepting the default.** Auto-meshers make assumptions that may not match your needs. Always verify, especially in critical regions.

## Adapt to Context

**Quick feasibility study:** Coarser mesh is fine, focus on not missing major features.

**Design iteration:** Balance accuracy with turnaround time, refine the region being changed.

**Final validation:** Mesh convergence study, higher quality standards, document thoroughly.

**Nonlinear or contact:** More conservative quality requirements, expect to iterate.

Match mesh investment to how the results will be used.
