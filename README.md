# Webex Flow Designer draw.io Libraries

draw.io shape libraries for designing **Webex Contact Center (WxCC)** and **Webex Connect** flow diagrams. Each library mirrors the activity palette of its respective designer so diagrams look like the real tool without needing a live environment.

---

## Libraries

### Webex Contact Center (WxCC)

`WxCC-FlowBuilder-Activities.xml` — 53 nodes matching the WxCC Flow Builder activity palette.

![WxCC Sample Flow](SampleFlow.png)

### Webex Connect

`WxConnect-Node-Library.xml` — nodes matching the Webex Connect flow designer.

![Webex Connect Sample Flow](WxConnect-SampleFlow.png)

---

## Importing a Library

1. Open [app.diagrams.net](https://app.diagrams.net) or the draw.io desktop app.
2. Go to **File > Open Library from > This Device**.
3. Select the `.xml` file for the library you want to use.
4. The library panel appears in the left sidebar. Drag any shape onto the canvas to use it.

You can import both libraries at the same time — each appears as its own panel.

---

## WxCC Node Categories

| Category | Badge Color | Example Nodes |
|---|---|---|
| Start | Green (`#BCE36F`) | Start Flow |
| Event | Teal (`#74E8D1`) | New Contact, Agent Offer, Contact Ended |
| Action | Purple (`#E2CAFC`) | Play Message, Collect Digits, Queue Contact, HTTP Request |
| Gateway | Yellow (`#FFCE73`) | Menu, Case, % Allocation, Condition, Business Hours |
| Subflow | Blue (`#99DDFF`) | Subflow |
| Function | Orange (`#FEBA7F`) | Function |
| Terminating | Pink (`#FFC7D2`, pill) | Blind Transfer, Disconnect Contact |
| End | Pink (`#FFC7D2`, pill) | End Flow, GoTo |

---

## Node Anatomy (WxCC)

Each WxCC node is a stacked swimlane card divided into collapsible sections:

```
+--------------------------------------------------+
|  [badge]  Node Name              (header)        |
|           subtitle                               |
+--------------------------------------------------+
|  + Details                       (collapsed)     |
+--------------------------------------------------+
|  - Connections                   (expanded)      |
|    Default                              >        |
|    Error                                >        |
+--------------------------------------------------+
```

- **Header** — category badge icon and node name. Entry connection point is on the left edge.
- **Details** — collapsible free-text area for notes, variable names, or config values. Collapsed by default.
- **Connections** — one row per exit path, each with a connection port on the right edge.

Variable-exit nodes (Menu, Case, % Allocation) have an **Options / Cases / Allocations** section and a separate **Error handling** section.

---

## Connecting Nodes

- **Entry point** — left edge of the header. Hover until the connection dot appears, then drag from a source exit port.
- **Exit ports** — right edge of each row in the Connections section. Hover a row to reveal its port, then drag to a target node's entry point.

draw.io routes edges automatically. Use **View > Connection Points** to display all ports while editing.

---

## Editing the Details Section

Click the **+** on the Details header to expand it. Double-click inside the content area to type notes. The section collapses back to a single row when closed.

---

## Adding and Removing Rows

Variable-exit nodes (Menu, Case, % Allocation) support editable exit rows:

- **Add a row** — right-click the node and select **Add Row**, or duplicate an existing row.
- **Remove a row** — select the row and press Delete. The layout reflows automatically.
- **Rename a row** — double-click the row label and type the new name.

Fixed-exit nodes have pre-defined exits that match the WxCC designer. Avoid deleting these unless the exit does not apply to your flow.
