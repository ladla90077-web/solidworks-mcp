---
description: Part/Assembly/Drawing hierarchy, casting IModelDoc2, and object model navigation.
---

# SolidWorks API: Document Types and Object Model Architecture

The SolidWorks API has a hierarchical organization built around **three core document types**, each with specialized functionality and distinct object models for their contained elements.

### **1. The Three Document Type Hierarchy**

At the top level, SOLIDWORKS has three main document types defined by the `swDocumentTypes_e` enum:

- **swDocPART (1)** - Part documents (.sldprt)
- **swDocASSEMBLY (2)** - Assembly documents (.sldasm)
- **swDocDRAWING (3)** - Drawing documents (.slddrw)

#### **Document Type Interfaces**

Each document type has **two layers of interfaces**:

1. **IModelDoc2** - The common base interface for ALL document types
   - Provides shared functionality: saving, printing, getting file names, selections, feature managers, sketch operations, etc.
   - Every part, assembly, or drawing can be accessed as an IModelDoc2
   - This is the "unified" interface for document-level operations

2. **Document-specific interfaces** - Specialized interfaces for each type:
   - **IPartDoc** - Part-specific operations (creating bodies, features, tessellation, part extents, suppress operations)
   - **IAssemblyDoc** - Assembly-specific operations (adding components, mates, hiding/exploding components, interference detection)
   - **IDrawingDoc** - Drawing-specific operations (creating views, aligning views, accessing sheets, annotations)

The key insight is: **you cast the same document object to different interfaces depending on what operations you need**. For example:
```csharp
ModelDoc2 swModel = swApp.ActiveDoc;  // Common interface
PartDoc swPart = (PartDoc)swModel;    // Cast to part-specific
```

---

### **2. Features: The Universal Building Blocks**

**Features exist in ALL three document types** and represent items in the FeatureManager design tree.

#### **IFeature Interface**
- Provides access to feature type, name, parameters, and tree navigation
- Features appear in:
  - **Parts**: Extrudes, cuts, fillets, holes, sketches, reference geometry
  - **Assemblies**: Mates, assembly features (cuts, holes that affect multiple components), patterns
  - **Drawings**: Tables, annotations, sheets, views (yes, drawing views are features!)

#### **Accessing Features**
Different paths depending on document type:
- **IModelDoc2::FirstFeature** - Gets first feature in any document type
- **IPartDoc::FeatureByName/FeatureById** - Part-specific lookup
- **IAssemblyDoc::FeatureByName** - Assembly-specific lookup
- **IDrawingDoc::FeatureByName** - Drawing-specific lookup
- **IFeature::GetNextFeature** - Tree traversal

Features form a **linked tree structure** with parent-child relationships:
- **IFeature::GetChildren/GetParents** - Feature dependencies
- **IFeature::GetFirstSubFeature/GetNextSubFeature** - Sub-features
- **IComponent2::FirstFeature** - First feature within an assembly component

---

### **3. Components: Assembly Elements**

**Components (IComponent2) exist only in assemblies** and represent instances of parts or sub-assemblies placed within an assembly.

#### **Key Characteristics**
- Each component references a part or sub-assembly document via **IComponent2::GetModelDoc2**
- Components have their own transform (position/orientation) in assembly space via **IComponent2::GetTotalTransform**
- Components can be traversed hierarchically:
  - **IConfiguration::GetRootComponent3** - Starting point for assembly traversal
  - **IComponent2::IGetChildren** - Get child components (sub-assemblies)
  - **IComponent2::GetParent** - Get parent component
  - **IComponent2::IsRoot** - Check if this is the root (assembly itself)

#### **Components vs Parts**
- A **part** (IPartDoc) is a document containing geometry
- A **component** (IComponent2) is an instance/reference of a part (or sub-assembly) placed in an assembly
- The same part can be placed multiple times as different components with different transforms

---

### **4. Drawing Components: Drawing-Specific Representation**

**IDrawingComponent is unique to drawings** and bridges the gap between assembly components and drawing views.

#### **Purpose**
When a drawing shows an assembly:
- **IView** represents the drawing view itself
- **IDrawingComponent** represents each assembly component **as it appears in that specific view**
- This allows control of component visibility, line styles, etc. on a per-view basis

#### **Key Relationships**
- **IView::RootDrawingComponent** - Gets the root drawing component for a view
- **IDrawingComponent::Component** - Gets the corresponding IComponent2 from the assembly
- **IDrawingComponent::View** - Gets the view this drawing component belongs to
- **IDrawingComponent::IGetChildren** - Traverses component hierarchy within the drawing view
- **IDrawingComponent::IsRoot** - Check if root component in view

#### **Drawing Components vs Assembly Components**
- **IComponent2** exists in the assembly document, represents actual component placement
- **IDrawingComponent** exists in the drawing document, represents how that component appears in a specific view
- One IComponent2 can have multiple IDrawingComponents (one per drawing view it appears in)

---

### **5. Bodies: Geometric Elements**

**IBody2 represents actual geometric entities** (solid bodies, surface bodies, wire bodies):
- Exist primarily in parts, but also appear in assemblies (component bodies) and drawings (edge/curve geometry)
- **IFeature::GetBody** - Get body created by a feature
- **IComponent2::IGetBody** - Get body of a component (with assembly-level features applied)
- Bodies contain faces, edges, and vertices

---

### **6. Conceptual Summary**

Here's how these concepts layer together:

```
┌─────────────────────────────────────────────────────────┐
│  SOLIDWORKS APPLICATION (ISldWorks)                     │
└─────────────────────────────────────────────────────────┘
                      │
       ┌──────────────┼──────────────┐
       │              │              │
       ▼              ▼              ▼
   ┌────────┐   ┌─────────┐   ┌──────────┐
   │  PART  │   │ASSEMBLY │   │ DRAWING  │
   │Document│   │Document │   │ Document │
   └────────┘   └─────────┘   └──────────┘
       │              │              │
   IModelDoc2    IModelDoc2     IModelDoc2  ◄── Common Interface
   IPartDoc      IAssemblyDoc   IDrawingDoc ◄── Specific Interface
       │              │              │
       │              │              ├─ ISheet
       │              │              │    └─ IView ─────────┐
       │              │              │         ├─ IDrawingComponent ──┐
       │              │              │         └─ Annotations         │
       │              │              │                                │
       ├─ IFeature    ├─ IFeature    ├─ IFeature                      │
       │   └─ IBody2  │   ├─ Mate    │   └─ Table/View features       │
       │              │   └─ IComponent2 ◄─────────────┬──────────────┘
       │              │        ├─ Transform            │
       │              │        ├─ IGetChildren         │ (references)
       │              │        └─ GetModelDoc2 ────────┤
       │              │             │                  │
       │              │             └─ IPartDoc/IAssemblyDoc
       │              │                  └─ IFeature
       │              │                       └─ IBody2
       └──────────────┴─ Both have features that create geometry
```

---

### **7. Key Distinctions to Remember**

1. **Document Type ≠ Interface**: One document has multiple interface representations (IModelDoc2 + specific type)

2. **Feature Scope**: Features exist everywhere but mean different things:
   - Parts: Geometry-creating operations
   - Assemblies: Mates and assembly-level operations
   - Drawings: Views, sheets, tables, annotations

3. **Component Context**:
   - **IComponent2**: "This part is placed HERE in this assembly"
   - **IDrawingComponent**: "This component is drawn THIS WAY in this view"

4. **Part vs Component**:
   - Part = standalone document with geometry
   - Component = instance of a part within an assembly context

5. **Document Traversal**:
   - **Parts**: Navigate features → bodies → faces/edges
   - **Assemblies**: Navigate components → their documents → their features
   - **Drawings**: Navigate sheets → views → drawing components

---

### **8. Practical Implications for API Usage**

When working with the API, you need to think about:

1. **What document type am I in?** (Part, Assembly, or Drawing)
2. **What level am I working at?** (Document, Feature, Component, Body)
3. **What interface do I need?** (Cast to appropriate type)
4. **What context matters?** (Assembly placement, drawing view representation, etc.)

The fragmentation you mentioned stems from this multi-layered architecture where the same concepts (like "features") mean different things in different document contexts, and relationships between objects (components, drawing components, parts) require careful navigation through the object model hierarchy.