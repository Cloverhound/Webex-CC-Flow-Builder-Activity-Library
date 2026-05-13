# WxCC Draw.io Library

A draw.io shape library containing 53 nodes that mirror the activity palette in Webex Contact Center (WxCC) Flow Designer.

![Sample Flow](SampleFlow.png) Each shape is pre-styled with the correct category color, badge icon, section layout, and connection ports so diagrams look like the real designer without needing a live environment.

---

## Importing the Library

1. Open [app.diagrams.net](https://app.diagrams.net) or the draw.io desktop app.
2. Go to **File > Open Library from > This Device**.
3. Select `WxCC-FlowBuilder-Activities.xml` from this repository.
4. The **WxCC** panel appears in the left sidebar. Drag any shape onto the canvas to use it.

---

## Node Categories

| Category | Badge Color | Example Nodes |
|---|---|---|
| Event | Teal (`#74E8D1`) | New Contact, Agent Offer, Contact Ended |
| Action | Purple (`#E2CAFC`) | Play Message, Collect Digits, Queue Contact, HTTP Request |
| Gateway | Yellow (`#FFCE73`) | Menu, Case, % Allocation, Condition, Business Hours |
| Subflow | Blue (`#99DDFF`) | Subflow |
| Function | Orange (`#FEBA7F`) | Function |
| Terminating | Pink (`#FFC7D2`, pill) | Blind Transfer, Disconnect Contact |
| End | Pink (`#FFC7D2`, pill) | End Flow, GoTo |

---

## Node Anatomy

Each node is a stacked swimlane card divided into three sections:

```
+--------------------------------------------------+
|  [badge]  Node Name              (header)        |
|           subtitle                               |
+--------------------------------------------------+
|  Details                         (collapsed)     |
+--------------------------------------------------+
|  Connections                     (expanded)      |
|    Default                              >        |
|    Error                                >        |
+--------------------------------------------------+
```

- **Header** — displays the category badge icon and the node name. The entry connection point is on the left edge of the header.
- **Details** — a collapsible section with a free-text content area for notes (collapsed by default).
- **Connections** — lists each exit path. Each row has a connection port on its right edge (`>`).

Variable-exit nodes (Menu, Case, % Allocation) have an additional **Options / Cases / Allocations** section with one row per configurable path, followed by an **Error handling** section.

---

## Connecting Nodes

- **Entry point** — the left edge of the header row. Hover over the header until the blue connection dot appears on the left, then drag to the source node's exit port.
- **Exit ports** — the right edge of each row in the Connections section. Hover over a row to reveal its port dot, then drag to the target node's entry point.

draw.io will route edges automatically. Use **View > Connection Points** to show all ports while editing.

---

## Editing the Details Section

Click the **Details** section header to expand it. Double-click inside the content area to type notes — configuration values, variable names, prompt text, or anything relevant to the node's configuration. The section collapses back to a single row in the stacked layout.

---

## Adding and Removing Rows

Variable-exit nodes (Menu, Case, % Allocation) support editable exit rows:

- **Add a row** — right-click the node and choose **Duplicate** on an existing option row, or drag a standalone row shape from the panel beneath the node.
- **Remove a row** — select the row cell and press Delete. The stack layout reflows automatically.
- **Rename a row** — double-click the row label text and type the new name.

Fixed-exit nodes (Play Message, Collect Digits, etc.) have pre-defined exits that match the WxCC designer. Avoid deleting these rows unless the exit genuinely does not apply to your flow.

