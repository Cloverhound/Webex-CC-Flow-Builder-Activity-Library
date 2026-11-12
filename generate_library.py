#!/usr/bin/env python3
"""
Generate draw.io XML library for WxCC (Webex Contact Center) flow nodes.

Architecture: swimlane + childLayout=stackLayout
  • Container: swimlane with colored header (fillColor = category header_bg)
  • Header value: HTML table with badge div + name + subtitle + blue dot
  • Rows: native draw.io child mxCells stacked below header (one per exit)
  • Section header rows (bold, gray bg) separate groupings in variable nodes
  • No custom connection circles — rows use portConstraint=eastwest

Output: WxCC-Nodes.xml — import via File > Open Library from > This Device
"""

import argparse
import base64
import html as html_mod
import json
import re
import subprocess
import sys
import urllib.parse
import urllib.request
import zlib
from pathlib import Path

MOMENTUM   = str(Path.home() / ".local/bin/momentum")
PROJECT_ID = "5e5c9ad6d61f870d6d778c1b"
API_BASE   = "https://api.wxcc-us1.cisco.com"

CARD_W    = 230
HDR_H     = 56   # swimlane startSize (badge 36px + 10px pad top + 10px pad bottom)
ROW_H     = 30   # height of each stackLayout child row
DETAILS_H = 60   # height of the editable details content row

# ── Category colours ──────────────────────────────────────────────────────────
CAT = {
    "action":      {"header_bg": "#faf5fe", "badge_fill": "#E2CAFC", "badge_arc": 7},
    "gateway":     {"header_bg": "#fff6e6", "badge_fill": "#FFCE73", "badge_arc": 7},
    "terminating": {"header_bg": "#fff5f7", "badge_fill": "#FFC7D2", "badge_arc": 50},
    "end":         {"header_bg": "#fff5f7", "badge_fill": "#FFC7D2", "badge_arc": 50},
    "start":       {"header_bg": "#f0fdf4", "badge_fill": "#BCE36F", "badge_arc": 7},
    "event":       {"header_bg": "#f0fefb", "badge_fill": "#74E8D1", "badge_arc": 7},
    "subflow":     {"header_bg": "#edf9ff", "badge_fill": "#99DDFF", "badge_arc": 7},
    "function":    {"header_bg": "#fff3e8", "badge_fill": "#FEBA7F", "badge_arc": 7},
}

# Exit IDs that represent the primary (happy-path) output
PRIMARY_EXIT_IDS = {"default", "out", "ENDED", "true", "workingHours", "success"}

# Human-readable label for primary exits (exit label field is empty in NODES)
PRIMARY_EXIT_LABEL = {
    "default":      "Default",
    "out":          "Out",
    "ENDED":        "Ended",
    "true":         "True",
    "workingHours": "Working Hours",
    "success":      "Success",
}

# ── Connection-point dot styles (hollow = unconnected, colored by exit type) ──
_TIMEOUT_COLOR_KEYS = {"timeout", "noInputTimeout", "invalid"}
_ERROR_COLOR_KEYS   = {"error", "failure", "undefinedErrors", "insufficientdata"}

def _dot_uri(fill: str, stroke: str) -> str:
    svg = (
        f"<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 8 8'>"
        f"<circle cx='4' cy='4' r='3.5' fill='{fill}' stroke='{stroke}' stroke-width='1'/>"
        f"</svg>"
    )
    return "data:image/svg+xml," + urllib.parse.quote(svg)

_DOT_NORMAL  = _dot_uri("#ffffff", "#0353a8")  # hollow blue  — happy path
_DOT_ERROR   = _dot_uri("#ffffff", "#ab0a15")  # hollow red   — error/failure
_DOT_TIMEOUT = _dot_uri("#ffffff", "#7d4705")  # hollow brown — timeout

def _exit_row_type(color_key: str) -> str:
    if color_key in _TIMEOUT_COLOR_KEYS:
        return "exit_timeout"
    if color_key in _ERROR_COLOR_KEYS:
        return "exit_error"
    return "exit_normal"

# ── Momentum icon map  node_id → (name, weight) ───────────────────────────────
ICON_MAP = {
    "start-flow":               ("play-circle",          "bold"),
    "event-new-contact":        ("headset",              "bold"),
    "event-agent-offer":        ("headset",              "bold"),
    "event-contact-predial":    ("headset",              "bold"),
    "event-campaign-result":    ("headset",              "bold"),
    "event-ani-updated":        ("headset",              "bold"),
    "event-callback-failed":    ("headset",              "bold"),
    "event-contact-ended":      ("headset",              "bold"),
    "event-agent-assigned":     ("headset",              "bold"),
    "event-reservation":        ("headset",              "bold"),
    "event-last-agent":         ("headset",              "bold"),
    "event-global-error":       ("headset",              "bold"),
    "menu":                     ("list-numbered",        "bold"),
    "case":                     ("share-c-native-adr",   "bold"),
    "percent-allocation":       ("simple-promotion",     "bold"),
    "play-message":             ("play-circle",          "bold"),
    "collect-digits":           ("display-input",        "bold"),
    "queue-contact":            ("call-handling",        "bold"),
    "callback":                 ("audio-call",           "bold"),
    "screen-pop":               ("pop-out",              "bold"),
    "play-music":               ("ringtone",             "bold"),
    "get-queue-info":           ("search",               "bold"),
    "advanced-queue-info":      ("search",               "bold"),
    "queue-to-agent":           ("queue-contact",        "bold"),
    "http-request":             ("code-block",           "bold"),
    "set-variable":             ("set-variable",         "bold"),
    "bre-request":              ("server",               "bold"),
    "parse":                    ("parse",                "bold"),
    "subflow":                  ("link",                 "bold"),
    "function":                 ("text-code-block",      "bold"),
    "recording-control":        ("record-active",        "bold"),
    "record":                   ("microphone",           "bold"),
    "bridged-transfer":         ("exchange",             "bold"),
    "wait":                     ("alarm",                "bold"),
    "feedback":                 ("announcement",         "bold"),
    "set-caller-id":            ("audio-call",           "bold"),
    "escalate-cdg":             ("queue-contact",        "bold"),
    "start-media-stream":       ("audio-broadcast",      "bold"),
    "call-progress-analysis":   ("call-request",        "bold"),
    "set-announcement":         ("announcement",         "bold"),
    "send-digits":              ("display-input",        "bold"),
    "set-whisper-announcement": ("active-speaker-alert", "bold"),
    "set-contact-priority":     ("call-handling",        "bold"),
    "schedule-callback":        ("audio-call",           "bold"),
    "upload-audio":             ("cloud-upload",         "bold"),
    "condition":                ("conditional-block",    "bold"),
    "business-hours":           ("calendar-month",       "bold"),
    "virtual-agent":            ("headset",              "bold"),
    "virtual-agent-v2":         ("headset",              "bold"),
    "feedback-v2":              ("announcement",         "bold"),
    "cryptographic-hash":       ("security",             "bold"),
    "generate-otp":             ("display-input",        "bold"),
    "verify-otp":               ("check-circle",         "bold"),
    "end-subflow":              ("error-legacy",         "bold"),
    "event-contact-cleanup":    ("headset",              "bold"),
    "event-invite-participant": ("headset",              "bold"),
    "event-contact-park":       ("headset",              "bold"),
    "event-contact-updated":    ("headset",              "bold"),
    "event-stop-workflow":      ("headset",              "bold"),
    "event-generic-action":     ("headset",              "bold"),
    "event-flow-test":          ("headset",              "bold"),
    "blind-transfer":           ("call-forward-settings","bold"),
    "disconnect-contact":       ("call-private",         "bold"),
    "end-flow":                 ("error-legacy",         "bold"),
    "goto":                     ("forward-message",      "bold"),
    "receive-message":          ("chat-active",          "bold"),
    "send-chat":                ("chat",                 "bold"),
    "send-email":               ("email",                "bold"),
    "send-sms":                 ("sms",                  "bold"),
    "send-custom-message":      ("message",              "bold"),
    "set-customer-identity":    ("assign-host",          "bold"),
}

_icon_cache: dict = {}

def _fetch_icon(node_id: str) -> str:
    """Return black-filled SVG as a url-encoded data URI, or '' on failure."""
    entry = ICON_MAP.get(node_id)
    if not entry:
        return ""
    name, weight = entry
    key = (name, weight)
    if key in _icon_cache:
        return _icon_cache[key]
    try:
        r = subprocess.run(
            [MOMENTUM, "icons", "get", name, "--stdout", "--weight", weight],
            capture_output=True, text=True, timeout=15,
        )
        svg = r.stdout.strip()
        if not svg.startswith("<svg"):
            _icon_cache[key] = ""
            return ""
        svg = re.sub(r'\sfill="[^"]*"', '', svg)
        svg = svg.replace("<svg ", '<svg fill="black" ')
        uri = "data:image/svg+xml," + urllib.parse.quote(svg)
        _icon_cache[key] = uri
        return uri
    except Exception:
        _icon_cache[key] = ""
        return ""


# ── Node Catalog ───────────────────────────────────────────────────────────────
NODES = [
    # ── Start / Event ──────────────────────────────────────────────────────────
    {"id": "start-flow",    "display": "Start Flow",    "subtitle": "NewContact",
     "style_key": "start",  "variable": False, "entry": False,
     "exits": [{"id": "out", "label": "", "color_key": "out"}]},

    # ── Event Handlers ─────────────────────────────────────────────────────────
    {"id": "event-new-contact",      "display": "New Contact",          "subtitle": "NewPhoneContact",
     "style_key": "event", "variable": False, "entry": True,
     "exits": [{"id": "out", "label": "", "color_key": "out"}]},

    {"id": "event-agent-offer",      "display": "Agent Offer",          "subtitle": "AgentOfferContact",
     "style_key": "event", "variable": False, "entry": True,
     "exits": [{"id": "out", "label": "", "color_key": "out"}]},

    {"id": "event-contact-predial",  "display": "Contact Predial",      "subtitle": "ContactPredial",
     "style_key": "event", "variable": False, "entry": True,
     "exits": [{"id": "out", "label": "", "color_key": "out"}]},

    {"id": "event-campaign-result",  "display": "Campaign Result",      "subtitle": "ContactOutboundCampaignResult",
     "style_key": "event", "variable": False, "entry": True,
     "exits": [{"id": "out", "label": "", "color_key": "out"}]},

    {"id": "event-ani-updated",      "display": "ANI Updated",          "subtitle": "ContactAniUpdated",
     "style_key": "event", "variable": False, "entry": True,
     "exits": [{"id": "out", "label": "", "color_key": "out"}]},

    {"id": "event-callback-failed",  "display": "Callback Failed",      "subtitle": "ContactCallbackFailed",
     "style_key": "event", "variable": False, "entry": True,
     "exits": [{"id": "out", "label": "", "color_key": "out"}]},

    {"id": "event-contact-ended",    "display": "Contact Ended",        "subtitle": "ContactEnded",
     "style_key": "event", "variable": False, "entry": True,
     "exits": [{"id": "out", "label": "", "color_key": "out"}]},

    {"id": "event-agent-assigned",   "display": "Agent Assigned",       "subtitle": "AgentContactAssigned",
     "style_key": "event", "variable": False, "entry": True,
     "exits": [{"id": "out", "label": "", "color_key": "out"}]},

    {"id": "event-reservation",      "display": "Reservation Start",    "subtitle": "ContactReservationStarted",
     "style_key": "event", "variable": False, "entry": True,
     "exits": [{"id": "out", "label": "", "color_key": "out"}]},

    {"id": "event-last-agent",       "display": "Last Agent Removed",   "subtitle": "ContactLastAgentRemoved",
     "style_key": "event", "variable": False, "entry": True,
     "exits": [{"id": "out", "label": "", "color_key": "out"}]},

    {"id": "event-global-error",     "display": "Global Errors",        "subtitle": "GlobalErrorHandling",
     "style_key": "event", "variable": False, "entry": True,
     "exits": [{"id": "out", "label": "", "color_key": "out"}]},

    {"id": "event-contact-cleanup",  "display": "Contact Cleanup",       "subtitle": "ContactCleanup",
     "style_key": "event", "variable": False, "entry": True,
     "exits": [{"id": "out", "label": "", "color_key": "out"}]},

    {"id": "event-invite-participant", "display": "Invite Participant",  "subtitle": "ContactInviteParticipant",
     "style_key": "event", "variable": False, "entry": True,
     "exits": [{"id": "out", "label": "", "color_key": "out"}]},

    {"id": "event-contact-park",     "display": "Contact Park",          "subtitle": "ContactPark",
     "style_key": "event", "variable": False, "entry": True,
     "exits": [{"id": "out", "label": "", "color_key": "out"}]},

    {"id": "event-contact-updated",  "display": "Contact Updated",       "subtitle": "ContactUpdated",
     "style_key": "event", "variable": False, "entry": True,
     "exits": [{"id": "out", "label": "", "color_key": "out"}]},

    {"id": "event-stop-workflow",    "display": "Stop Workflow",         "subtitle": "ContactStopWorkflow",
     "style_key": "event", "variable": False, "entry": True,
     "exits": [{"id": "out", "label": "", "color_key": "out"}]},

    {"id": "event-generic-action",   "display": "Generic Action",        "subtitle": "GenericActionStartWorkflow",
     "style_key": "event", "variable": False, "entry": True,
     "exits": [{"id": "out", "label": "", "color_key": "out"}]},

    {"id": "event-flow-test",        "display": "Flow Test",             "subtitle": "FlowTestEvent",
     "style_key": "event", "variable": False, "entry": True,
     "exits": [{"id": "out", "label": "", "color_key": "out"}]},

    # ── Actions ────────────────────────────────────────────────────────────────
    {"id": "play-message", "display": "Play Message", "subtitle": "play-message",
     "style_key": "action", "variable": False, "entry": True,
     "exits": [{"id": "default", "label": "", "color_key": "default"},
               {"id": "error",   "label": "Error",   "color_key": "error"}]},

    {"id": "collect-digits", "display": "Collect Digits", "subtitle": "ivr-collectdigits",
     "style_key": "action", "variable": False, "entry": True,
     "exits": [{"id": "default", "label": "",         "color_key": "default"},
               {"id": "timeout", "label": "Timeout",  "color_key": "timeout"},
               {"id": "invalid", "label": "Invalid",  "color_key": "invalid"},
               {"id": "error",   "label": "Error",    "color_key": "error"}]},

    {"id": "queue-contact", "display": "Queue Contact", "subtitle": "queue-contact",
     "style_key": "action", "variable": False, "entry": True,
     "exits": [{"id": "default", "label": "",         "color_key": "default"},
               {"id": "failure", "label": "Failure",  "color_key": "failure"}]},

    {"id": "callback", "display": "Callback", "subtitle": "callback",
     "style_key": "action", "variable": False, "entry": True,
     "exits": [{"id": "default", "label": "",         "color_key": "default"},
               {"id": "failure", "label": "Failure",  "color_key": "failure"}]},

    {"id": "screen-pop", "display": "Screen Pop", "subtitle": "screen-pop",
     "style_key": "action", "variable": False, "entry": True,
     "exits": [{"id": "default", "label": "", "color_key": "default"}]},

    {"id": "play-music", "display": "Play Music", "subtitle": "play-music",
     "style_key": "action", "variable": False, "entry": True,
     "exits": [{"id": "default", "label": "",      "color_key": "default"},
               {"id": "error",   "label": "Error", "color_key": "error"}]},

    {"id": "get-queue-info", "display": "Get Queue Info", "subtitle": "queue-lookup",
     "style_key": "action", "variable": False, "entry": True,
     "exits": [{"id": "default",          "label": "",              "color_key": "default"},
               {"id": "insufficientdata", "label": "Insuff. Data",  "color_key": "insufficientdata"},
               {"id": "failure",          "label": "Failure",       "color_key": "failure"}]},

    {"id": "advanced-queue-info", "display": "Adv. Queue Info",
     "subtitle": "advanced-queue-info",
     "style_key": "action", "variable": False, "entry": True,
     "exits": [{"id": "default", "label": "",        "color_key": "default"},
               {"id": "failure", "label": "Failure", "color_key": "failure"}]},

    {"id": "queue-to-agent", "display": "Queue to Agent", "subtitle": "queue-to-agent",
     "style_key": "action", "variable": False, "entry": True,
     "exits": [{"id": "default", "label": "",      "color_key": "default"},
               {"id": "error",   "label": "Error", "color_key": "error"}]},

    {"id": "http-request", "display": "HTTP Request", "subtitle": "http-request-v2",
     "style_key": "action", "variable": False, "entry": True,
     "exits": [{"id": "default", "label": "",         "color_key": "default"},
               {"id": "success", "label": "Success",  "color_key": "success"},
               {"id": "out",     "label": "Out",      "color_key": "out"},
               {"id": "timeout", "label": "Timeout",  "color_key": "timeout"},
               {"id": "failure", "label": "Failure",  "color_key": "failure"},
               {"id": "error",   "label": "Error",    "color_key": "error"}]},

    {"id": "set-variable", "display": "Set Variable", "subtitle": "set-variable",
     "style_key": "action", "variable": False, "entry": True,
     "exits": [{"id": "out",   "label": "",      "color_key": "out"},
               {"id": "error", "label": "Error", "color_key": "error"}]},

    {"id": "bre-request", "display": "BRE Request", "subtitle": "bre-request",
     "style_key": "action", "variable": False, "entry": True,
     "exits": [{"id": "default", "label": "", "color_key": "default"}]},

    {"id": "parse", "display": "Parse", "subtitle": "parse-activity",
     "style_key": "action", "variable": False, "entry": True,
     "exits": [{"id": "default", "label": "",      "color_key": "default"},
               {"id": "out",     "label": "Out",   "color_key": "out"},
               {"id": "error",   "label": "Error", "color_key": "error"}]},

    {"id": "subflow", "display": "Subflow", "subtitle": "subflow-handoff",
     "style_key": "subflow", "variable": False, "entry": True,
     "exits": [{"id": "default", "label": "",      "color_key": "default"},
               {"id": "out",     "label": "Out",   "color_key": "out"},
               {"id": "error",   "label": "Error", "color_key": "error"}]},

    {"id": "function", "display": "Function", "subtitle": "fn-activity",
     "style_key": "function", "variable": False, "entry": True,
     "exits": [{"id": "default", "label": "",      "color_key": "default"},
               {"id": "error",   "label": "Error", "color_key": "error"}]},

    {"id": "recording-control", "display": "Recording Control",
     "subtitle": "RecordingControl",
     "style_key": "action", "variable": False, "entry": True,
     "exits": [{"id": "default", "label": "",        "color_key": "default"},
               {"id": "failure", "label": "Failure", "color_key": "failure"}]},

    {"id": "record", "display": "Record", "subtitle": "record",
     "style_key": "action", "variable": False, "entry": True,
     "exits": [{"id": "default",         "label": "",         "color_key": "default"},
               {"id": "noInputTimeout",  "label": "No Input", "color_key": "noInputTimeout"},
               {"id": "undefinedErrors", "label": "Errors",   "color_key": "undefinedErrors"}]},

    {"id": "bridged-transfer", "display": "Bridged Transfer", "subtitle": "bridged-transfer",
     "style_key": "action", "variable": False, "entry": True,
     "exits": [{"id": "default", "label": "",        "color_key": "default"},
               {"id": "failure", "label": "Failure", "color_key": "failure"}]},

    {"id": "wait", "display": "Wait", "subtitle": "wait-activity",
     "style_key": "action", "variable": False, "entry": True,
     "exits": [{"id": "default", "label": "",      "color_key": "default"},
               {"id": "error",   "label": "Error", "color_key": "error"}]},

    {"id": "feedback", "display": "Feedback", "subtitle": "Feedback",
     "style_key": "action", "variable": False, "entry": True,
     "exits": [{"id": "default", "label": "", "color_key": "default"}]},

    {"id": "set-caller-id", "display": "Set Caller ID", "subtitle": "SetCallerID",
     "style_key": "action", "variable": False, "entry": True,
     "exits": [{"id": "default", "label": "", "color_key": "default"}]},

    {"id": "escalate-cdg", "display": "Escalate CDG", "subtitle": "escalate-cdg",
     "style_key": "action", "variable": False, "entry": True,
     "exits": [{"id": "default", "label": "",      "color_key": "default"},
               {"id": "error",   "label": "Error", "color_key": "error"}]},

    {"id": "start-media-stream", "display": "Start Media Stream",
     "subtitle": "start-media-stream",
     "style_key": "action", "variable": False, "entry": True,
     "exits": [{"id": "default", "label": "",        "color_key": "default"},
               {"id": "failure", "label": "Failure", "color_key": "failure"}]},

    {"id": "call-progress-analysis", "display": "Call Progress",
     "subtitle": "call-progress-analysis",
     "style_key": "action", "variable": False, "entry": True,
     "exits": [{"id": "default", "label": "",        "color_key": "default"},
               {"id": "failure", "label": "Failure", "color_key": "failure"}]},

    {"id": "set-announcement", "display": "Set Announcement",
     "subtitle": "set-announcement",
     "style_key": "action", "variable": False, "entry": True,
     "exits": [{"id": "default", "label": "",      "color_key": "default"},
               {"id": "error",   "label": "Error", "color_key": "error"}]},

    {"id": "send-digits", "display": "Send Digits", "subtitle": "send-digits",
     "style_key": "action", "variable": False, "entry": True,
     "exits": [{"id": "default", "label": "",        "color_key": "default"},
               {"id": "failure", "label": "Failure", "color_key": "failure"}]},

    {"id": "set-whisper-announcement", "display": "Set Whisper Ann.",
     "subtitle": "set-whisperannouncement",
     "style_key": "action", "variable": False, "entry": True,
     "exits": [{"id": "default", "label": "",      "color_key": "default"},
               {"id": "error",   "label": "Error", "color_key": "error"}]},

    {"id": "set-contact-priority", "display": "Set Priority",
     "subtitle": "set-contact-priority",
     "style_key": "action", "variable": False, "entry": True,
     "exits": [{"id": "default", "label": "",        "color_key": "default"},
               {"id": "failure", "label": "Failure", "color_key": "failure"}]},

    {"id": "schedule-callback", "display": "Schedule Callback",
     "subtitle": "scheduled-callback",
     "style_key": "action", "variable": False, "entry": True,
     "exits": [{"id": "default", "label": "",        "color_key": "default"},
               {"id": "failure", "label": "Failure", "color_key": "failure"}]},

    {"id": "upload-audio", "display": "Upload Audio", "subtitle": "upload-audio",
     "style_key": "action", "variable": False, "entry": True,
     "exits": [{"id": "default", "label": "",      "color_key": "default"},
               {"id": "error",   "label": "Error", "color_key": "error"}]},

    # ── Gateways – fixed exits ─────────────────────────────────────────────────
    {"id": "condition", "display": "Condition", "subtitle": "condition-activity",
     "style_key": "gateway", "variable": False, "entry": True,
     "exits": [{"id": "true",  "label": "",      "color_key": "true"},
               {"id": "false", "label": "False", "color_key": "false"},
               {"id": "error", "label": "Error", "color_key": "error"}]},

    {"id": "business-hours", "display": "Business Hours", "subtitle": "business-hours",
     "style_key": "gateway", "variable": False, "entry": True,
     "exits": [{"id": "workingHours", "label": "",         "color_key": "workingHours"},
               {"id": "holidays",     "label": "Holidays", "color_key": "holidays"},
               {"id": "override",     "label": "Override", "color_key": "override"},
               {"id": "default",      "label": "Default",  "color_key": "info"},
               {"id": "error",        "label": "Error",    "color_key": "error"}]},

    {"id": "virtual-agent", "display": "Virtual Agent",
     "subtitle": "ivr-virtualassistant",
     "style_key": "gateway", "variable": False, "entry": True,
     "exits": [{"id": "ENDED",   "label": "Handled",   "color_key": "ENDED"},
               {"id": "ESCALATE","label": "Escalated", "color_key": "ESCALATE"},
               {"id": "error",   "label": "Error",     "color_key": "error"}]},

    {"id": "virtual-agent-v2", "display": "Virtual Agent V2",
     "subtitle": "ivr-virtualassistantvoice",
     "style_key": "gateway", "variable": False, "entry": True,
     "exits": [{"id": "ENDED",   "label": "Handled",   "color_key": "ENDED"},
               {"id": "ESCALATE","label": "Escalated", "color_key": "ESCALATE"},
               {"id": "error",   "label": "Error",     "color_key": "error"}]},

    # ── Gateways – variable exits ──────────────────────────────────────────────
    {"id": "menu", "display": "Menu", "subtitle": "ivr-menu",
     "style_key": "gateway", "variable": True, "entry": True,
     "variable_type": "menu",
     "default_exits": ["Option 0", "Option 1", "Option 2"],
     "error_exits": [
         {"id": "timeout", "label": "No-Input Timeout", "color_key": "timeout"},
         {"id": "invalid", "label": "Unmatched Entry",  "color_key": "invalid"},
         {"id": "error",   "label": "Undefined Error",  "color_key": "error"},
     ]},

    {"id": "case", "display": "Case", "subtitle": "case-statement",
     "style_key": "gateway", "variable": True, "entry": True,
     "variable_type": "case",
     "default_exits": ["Case 1", "Case 2", "Case 3"],
     "error_exits": [
         {"id": "default", "label": "Default", "color_key": "info"},
         {"id": "error",   "label": "Error",   "color_key": "error"},
     ]},

    {"id": "percent-allocation", "display": "% Allocation",
     "subtitle": "percent-allocation",
     "style_key": "gateway", "variable": True, "entry": True,
     "variable_type": "percent",
     "default_exits": ["Path 1 (50%)", "Path 2 (50%)"],
     "error_exits": [
         {"id": "error", "label": "Error", "color_key": "error"},
     ]},

    # ── Digital / Omnichannel ──────────────────────────────────────────────────
    {"id": "receive-message", "display": "Receive Message", "subtitle": "ReceiveMessage",
     "style_key": "action", "variable": False, "entry": True,
     "exits": [{"id": "timeout", "label": "Timeout", "color_key": "timeout"},
               {"id": "error",   "label": "Error",   "color_key": "error"}]},

    {"id": "send-chat", "display": "Send Chat", "subtitle": "SendChat",
     "style_key": "action", "variable": False, "entry": True,
     "exits": [{"id": "timeout", "label": "Timeout", "color_key": "timeout"},
               {"id": "error",   "label": "Error",   "color_key": "error"}]},

    {"id": "send-email", "display": "Send Email", "subtitle": "SendEmail",
     "style_key": "action", "variable": False, "entry": True,
     "exits": [{"id": "timeout", "label": "Timeout", "color_key": "timeout"},
               {"id": "error",   "label": "Error",   "color_key": "error"}]},

    {"id": "send-sms", "display": "Send SMS", "subtitle": "SendSMS",
     "style_key": "action", "variable": False, "entry": True,
     "exits": [{"id": "timeout", "label": "Timeout", "color_key": "timeout"},
               {"id": "error",   "label": "Error",   "color_key": "error"}]},

    {"id": "send-custom-message", "display": "Send Custom Message",
     "subtitle": "SendCustomMessage",
     "style_key": "action", "variable": False, "entry": True,
     "exits": [{"id": "error", "label": "Error", "color_key": "error"}]},

    {"id": "set-customer-identity", "display": "Set Customer Identity",
     "subtitle": "SetCustomerIdentity",
     "style_key": "action", "variable": False, "entry": True,
     "exits": [{"id": "error", "label": "Error", "color_key": "error"}]},

    {"id": "feedback-v2", "display": "Feedback V2", "subtitle": "Feedback-V2",
     "style_key": "action", "variable": False, "entry": True,
     "exits": [{"id": "error", "label": "Error", "color_key": "error"}]},

    {"id": "cryptographic-hash", "display": "Cryptographic Hash",
     "subtitle": "cryptographic-hash",
     "style_key": "action", "variable": False, "entry": True,
     "exits": [{"id": "error", "label": "Error", "color_key": "error"}]},

    {"id": "generate-otp", "display": "Generate OTP", "subtitle": "generate-otp",
     "style_key": "action", "variable": False, "entry": True,
     "exits": [{"id": "error", "label": "Error", "color_key": "error"}]},

    {"id": "verify-otp", "display": "Verify OTP", "subtitle": "verify-otp",
     "style_key": "action", "variable": False, "entry": True,
     "exits": [{"id": "error",   "label": "Error",   "color_key": "error"},
               {"id": "failure", "label": "Failure", "color_key": "failure"}]},

    # ── Terminating ────────────────────────────────────────────────────────────
    {"id": "blind-transfer", "display": "Blind Transfer", "subtitle": "blind-transfer",
     "style_key": "terminating", "variable": False, "entry": True,
     "exits": [{"id": "failure", "label": "Failure", "color_key": "failure"}]},

    {"id": "disconnect-contact", "display": "Disconnect Contact",
     "subtitle": "disconnect-contact",
     "style_key": "terminating", "variable": False, "entry": True,
     "exits": []},

    {"id": "end-subflow", "display": "End Subflow", "subtitle": "end-subflow",
     "style_key": "terminating", "variable": False, "entry": True,
     "exits": []},

    # ── End nodes ──────────────────────────────────────────────────────────────
    {"id": "end-flow", "display": "End Flow", "subtitle": "end",
     "style_key": "end", "variable": False, "entry": True,
     "exits": []},

    {"id": "goto", "display": "GoTo", "subtitle": "hand-off",
     "style_key": "end", "variable": False, "entry": True,
     "exits": [{"id": "error", "label": "Error", "color_key": "error"}]},
]


# ── HTML / XML helpers ────────────────────────────────────────────────────────

def _esc(s: str) -> str:
    return html_mod.escape(str(s))

def _xa(s: str) -> str:
    return html_mod.escape(str(s), quote=True)


# ── Header HTML ───────────────────────────────────────────────────────────────

def _header_html(node: dict) -> str:
    """Build the HTML rendered inside the swimlane startSize header area."""
    cat        = CAT[node["style_key"]]
    badge_fill = cat["badge_fill"]
    badge_arc  = cat["badge_arc"]
    border_radius = "50%" if badge_arc >= 50 else f"{max(2, round(36 * badge_arc / 100))}px"
    display  = _esc(node["display"])
    subtitle = _esc(node["subtitle"])
    icon_uri = _fetch_icon(node["id"])

    badge_css = (
        f"width:36px;height:36px;border-radius:{border_radius};"
        f"background-color:{badge_fill};"
    )
    if icon_uri:
        badge_css += (
            f"background-image:url('{icon_uri}');"
            "background-size:22px 22px;"
            "background-position:center center;"
            "background-repeat:no-repeat;"
        )

    # table-layout:fixed is required for text-overflow:ellipsis to work in TD cells
    return (
        '<table width="100%" cellpadding="0" cellspacing="0" border="0" '
        'style="border-collapse:collapse;font-family:Helvetica Neue,Arial,sans-serif;'
        'table-layout:fixed;overflow:hidden;">'
        '<tr>'
        '<td width="56" valign="middle" style="padding-left:10px;flex-shrink:0;">'
        f'<div style="{badge_css}"></div>'
        '</td>'
        '<td valign="middle" style="padding-left:8px;overflow:hidden;min-width:0;">'
        f'<b style="font-size:13px;color:#111827;display:block;'
        f'overflow:hidden;text-overflow:ellipsis;white-space:nowrap;" '
        f'title="{_xa(node["display"])}">{display}</b>'
        f'<span style="font-size:11px;color:#6b7280;display:block;'
        f'overflow:hidden;text-overflow:ellipsis;white-space:nowrap;" '
        f'title="{_xa(node["subtitle"])}">{subtitle}</span>'
        '</td>'
        '</tr>'
        '</table>'
    )


# ── Section / row builders ────────────────────────────────────────────────────

_DETAILS_ROW_PX  = 15   # px per input field row
_DETAILS_HEAD_PX = 20   # px for the table header row
_DETAILS_PAD_PX  = 8    # top+bottom padding inside the details cell

def _build_inputs_html(inputs: list) -> tuple:
    """Return (html_string, height_px) for a Details cell given an API inputs list.
    Flattens top-level inputs and their immediate children (depth-1 only).
    """
    flat = []
    for inp in inputs:
        flat.append((inp["name"], inp["type"], inp.get("required", False), 0))
        for child in inp.get("children", []):
            flat.append((child["name"], child["type"], child.get("required", False), 1))

    h = _DETAILS_HEAD_PX + len(flat) * _DETAILS_ROW_PX + _DETAILS_PAD_PX
    h = max(h, DETAILS_H)

    rows_html = ""
    for name, typ, req, indent in flat:
        pad = "&nbsp;&nbsp;" * indent
        req_cell = '<span style="color:#059669;">&#x2713;</span>' if req else ""
        rows_html += (
            f"<tr>"
            f'<td style="padding:1px 3px;">{pad}{_esc(name)}</td>'
            f'<td style="padding:1px 3px;color:#6b7280;">{_esc(typ)}</td>'
            f'<td style="padding:1px 3px;text-align:center;">{req_cell}</td>'
            f"</tr>"
        )

    html = (
        '<table width="100%" cellpadding="0" cellspacing="0" border="0" '
        'style="border-collapse:collapse;font-family:Arial,sans-serif;font-size:9px;">'
        '<tr style="background-color:#f3f4f6;">'
        '<td style="font-weight:bold;padding:2px 3px;border-bottom:1px solid #e5e7eb;">Field</td>'
        '<td style="font-weight:bold;padding:2px 3px;border-bottom:1px solid #e5e7eb;">Type</td>'
        '<td style="font-weight:bold;padding:2px 3px;border-bottom:1px solid #e5e7eb;">Req</td>'
        "</tr>"
        + rows_html
        + "</table>"
    )
    return html, h


def _build_event_html(ev: dict) -> tuple:
    """Return (html, height_px) for an event node's Details cell from an event-spec record."""
    rows = [("Source", ev.get("eventSourceName", "")),
            ("Classification", ev.get("eventClassificationName", "")),
            ("Event name", ev.get("eventSpecificationName", ""))]
    body = "".join(
        f'<tr><td style="padding:1px 3px;font-weight:bold;">{_esc(k)}</td>'
        f'<td style="padding:1px 3px;color:#6b7280;">{_esc(v)}</td></tr>'
        for k, v in rows
    )
    html = (
        '<table width="100%" cellpadding="0" cellspacing="0" border="0" '
        'style="border-collapse:collapse;font-family:Arial,sans-serif;font-size:9px;">'
        + body + "</table>"
    )
    return html, max(len(rows) * _DETAILS_ROW_PX + _DETAILS_PAD_PX, DETAILS_H)


def _get_sections(node: dict, api_inputs: list = None, api_event: dict = None) -> list:
    """Return list of section dicts: {label, rows: [(label, row_type)], collapsed, details_h}
    row_type: 'exit_normal' | 'exit_error' | 'exit_timeout' | 'details'
    """
    if api_event is not None:
        details_html, details_h = _build_event_html(api_event)
    elif api_inputs is not None:
        details_html, details_h = _build_inputs_html(api_inputs)
    else:
        details_html, details_h = "", DETAILS_H

    sections = [
        {"label": "Details", "rows": [(details_html, "details")],
         "collapsed": True, "details_h": details_h},
    ]

    if node["variable"]:
        vtype     = node.get("variable_type", "")
        sec_label = {"menu": "Options", "case": "Cases", "percent": "Allocations"}.get(vtype, "Exits")
        sections.append({
            "label":     sec_label,
            "rows":      [(lbl, "exit_normal") for lbl in node.get("default_exits", [])],
            "collapsed": False,
        })
        err_exits = node.get("error_exits", [])
        if err_exits:
            sections.append({
                "label":     "Error handling",
                "rows":      [(ex["label"], _exit_row_type(ex["color_key"])) for ex in err_exits],
                "collapsed": False,
            })
    else:
        exits   = node.get("exits", [])
        primary = [e for e in exits if e["id"] in PRIMARY_EXIT_IDS]
        errors  = [e for e in exits if e["id"] not in PRIMARY_EXIT_IDS]
        exit_rows = []
        for ex in primary:
            lbl = ex["label"] or PRIMARY_EXIT_LABEL.get(ex["id"], ex["id"].capitalize())
            exit_rows.append((lbl, _exit_row_type(ex["color_key"])))
        for ex in errors:
            lbl = ex["label"] or ex["id"].capitalize()
            exit_rows.append((lbl, _exit_row_type(ex["color_key"])))
        if exit_rows:
            sections.append({"label": "Connections", "rows": exit_rows, "collapsed": False})

    return sections


def _section_content_h(sec: dict) -> int:
    """Height of a section's content rows (excluding the section header)."""
    total = 0
    for _, rt in sec["rows"]:
        total += sec.get("details_h", DETAILS_H) if rt == "details" else ROW_H
    return total


def _section_total_h(sec: dict) -> int:
    """Total height of a section cell: header + content (or just header if collapsed)."""
    return ROW_H if sec["collapsed"] else ROW_H + _section_content_h(sec)


# ── Cell XML builders ─────────────────────────────────────────────────────────

def _swimlane_container(cid: str, value_html: str, h: int, hdr_bg: str, entry_y: float,
                        tooltip: str = "") -> str:
    pts = json.dumps([[0, entry_y]], separators=(",", ":"))
    style = (
        f"swimlane;fontStyle=0;childLayout=stackLayout;horizontal=1;"
        f"startSize={HDR_H};horizontalStack=0;resizeParent=1;resizeParentMax=0;"
        f"resizeLast=0;collapsible=1;marginBottom=0;whiteSpace=wrap;html=1;"
        f"shadow=1;rounded=1;arcSize=3;align=left;"
        f"fillColor={hdr_bg};strokeColor=#d1d5db;swimlaneFillColor=#ffffff;"
        f"points={pts};portConstraint=fixed;"
    )
    tooltip_attr = f' tooltip="{_xa(tooltip)}"' if tooltip else ""
    return (
        f'<mxCell id="{cid}" value="{_xa(value_html)}" style="{_xa(style)}"'
        f'{tooltip_attr} vertex="1" parent="1">'
        f'<mxGeometry x="0" y="0" width="{CARD_W}" height="{h}" as="geometry"/>'
        f'</mxCell>'
    )


def _section_cell(cid: str, parent_id: str, label: str, y: int, h: int, collapsed: bool) -> str:
    style = (
        f"swimlane;fontStyle=1;fontSize=11;childLayout=stackLayout;horizontal=1;"
        f"startSize={ROW_H};horizontalStack=0;resizeParent=1;resizeParentMax=0;"
        f"resizeLast=0;collapsible=1;marginBottom=0;whiteSpace=wrap;html=1;"
        f"fillColor=#f3f4f6;strokeColor=none;swimlaneFillColor=#ffffff;align=left;"
        f"points=[];"
    )
    collapsed_attr = ' collapsed="1"' if collapsed else ''
    return (
        f'<mxCell id="{cid}" value="{_xa(label)}" style="{_xa(style)}"'
        f' vertex="1"{collapsed_attr} parent="{parent_id}">'
        f'<mxGeometry x="0" y="{y}" width="{CARD_W}" height="{h}" as="geometry"/>'
        f'</mxCell>'
    )


def _row_cell(cid: str, parent_id: str, label: str, y: int, row_type: str = "exit_normal",
              height: int = None) -> str:
    if row_type == "details":
        if height is None:
            height = DETAILS_H
        style = (
            "text;strokeColor=#d1d5db;fillColor=none;"
            "align=left;verticalAlign=top;whiteSpace=wrap;html=1;"
            "spacingLeft=4;spacingRight=4;spacingTop=4;fontSize=9;rotatable=0;"
            "fontColor=#000000;"
        )
        connectable, width = "0", CARD_W
    else:
        height = ROW_H
        dot = {"exit_error": _DOT_ERROR, "exit_timeout": _DOT_TIMEOUT}.get(row_type, _DOT_NORMAL)
        error_flag = ";wxccError=1" if row_type in {"exit_error", "exit_timeout"} else ""
        style = (
            "label;strokeColor=none;fillColor=none;"
            "align=left;verticalAlign=middle;"
            "spacingLeft=17;spacingRight=13;fontSize=11;rotatable=0;"
            "points=[[1,0.5]];portConstraint=fixed;"
            f"image={dot};imageWidth=8;imageHeight=8;"
            f"imageAlign=right;imageVerticalAlign=middle;spacing=-9;wxccDot=1{error_flag};"
        )
        connectable, width = "1", CARD_W
    return (
        f'<mxCell id="{cid}" value="{_xa(label)}" style="{_xa(style)}"'
        f' vertex="1" connectable="{connectable}" parent="{parent_id}">'
        f'<mxGeometry x="0" y="{y}" width="{width}" height="{height}" as="geometry"/>'
        f'</mxCell>'
    )


# ── Node assembler ────────────────────────────────────────────────────────────

def build_node(node: dict, api_inputs: list = None, api_event: dict = None) -> tuple:
    sections = _get_sections(node, api_inputs, api_event)
    h = HDR_H + sum(_section_total_h(s) for s in sections)

    cat         = CAT[node["style_key"]]
    header_html = _header_html(node)
    entry_y     = round((HDR_H / 2) / h, 3)

    container_id = "2"
    tooltip = f"{node['display']} ({node['subtitle']})"
    cells = _swimlane_container(container_id, header_html, h, cat["header_bg"], entry_y, tooltip)

    cid   = 3
    sec_y = HDR_H
    for sec in sections:
        sec_h = _section_total_h(sec)
        cells += _section_cell(str(cid), container_id, "&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;" + sec["label"], sec_y, sec_h, sec["collapsed"])
        sec_parent = str(cid)
        cid   += 1
        row_y  = ROW_H  # relative to section parent (below its own header)
        for label, row_type in sec["rows"]:
            rh = sec.get("details_h", DETAILS_H) if row_type == "details" else ROW_H
            cells += _row_cell(str(cid), sec_parent, label, row_y, row_type, rh)
            cid   += 1
            row_y += rh
        sec_y += sec_h

    return cells, CARD_W, h


# ── Compression & output ───────────────────────────────────────────────────────

def _compress(xml: str) -> str:
    url_enc      = urllib.parse.quote(xml, safe='')
    raw_deflated = zlib.compress(url_enc.encode('utf-8'), level=9)[2:-4]
    return base64.b64encode(raw_deflated).decode('ascii')


def _wrap(cells: str) -> str:
    return (
        '<mxGraphModel><root>'
        '<mxCell id="0"/><mxCell id="1" parent="0"/>'
        + cells
        + '</root></mxGraphModel>'
    )


# Library event subtitle → API eventSpecificationName where they differ
EVENT_API_ALIASES = {"ContactLastAgentRemoved": "FCAsk(ContactLastAgentRemoved)"}

_EDGE_CONNECTORS = [
    ("Normal Path",  "#1170cf"),
    ("Error Path",   "#ab0a15"),
    ("Timeout Path", "#7d4705"),
]

def _edge_item(title: str, stroke: str) -> dict:
    style = (
        f"rounded=1;orthogonalLoop=1;jettySize=auto;"
        f"edgeStyle=orthogonalEdgeStyle;"
        f"strokeColor={stroke};strokeWidth=2;fillColor=none;"
        f"startArrow=oval;startFill=1;startSize=6;"
        f"endArrow=block;endFill=1;fontSize=11;"
    )
    xml = (
        '<mxGraphModel><root>'
        '<mxCell id="0"/><mxCell id="1" parent="0"/>'
        f'<mxCell id="2" value="" style="{style}" edge="1" parent="1">'
        '<mxGeometry relative="1" as="geometry">'
        '<mxPoint x="0" y="20" as="sourcePoint"/>'
        '<mxPoint x="160" y="20" as="targetPoint"/>'
        '</mxGeometry>'
        '</mxCell>'
        '</root></mxGraphModel>'
    )
    return {"title": title, "w": 160, "h": 40, "xml": _compress(xml)}


def generate(output_path: str, api_data: dict = None, api_events: dict = None) -> None:
    """api_data: activityName → activity object; api_events: eventSpecificationName → event spec."""
    items = []

    print("  Connectors:")
    for title, stroke in _EDGE_CONNECTORS:
        items.append(_edge_item(title, stroke))
        print(f"  ✓  {title:35s}  connector")

    print("\n  Nodes:")
    for node in NODES:
        api_inputs = None
        if api_data:
            activity = api_data.get(node["subtitle"])
            if activity:
                api_inputs = activity.get("inputs", [])
        ev_key = EVENT_API_ALIASES.get(node["subtitle"], node["subtitle"])
        api_event = (api_events or {}).get(ev_key) if node["style_key"] == "event" else None
        cells, w, h = build_node(node, api_inputs, api_event)
        items.append({
            "title":  node["display"],
            "w":      w,
            "h":      h,
            "aspect": "fixed",
            "xml":    _compress(_wrap(cells)),
        })
        print(f"  ✓  {node['display']:35s}  {w}\xd7{h}")

    lib = f"<mxlibrary>{json.dumps(items, separators=(',', ':'))}</mxlibrary>"
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(lib)
    print(f"\nWrote {len(items)} items ({len(_EDGE_CONNECTORS)} connectors + {len(NODES)} shapes) → {output_path}")


# ── API discovery ─────────────────────────────────────────────────────────────

def _org_from_token(token: str) -> str:
    """Extract the org ID from a WxCC bearer token (last _-delimited segment)."""
    return token.split("_")[-1]


def _ssl_ctx():
    import ssl
    try:
        import certifi
        return ssl.create_default_context(cafile=certifi.where())
    except ImportError:
        pass
    ctx = ssl.create_default_context()
    # On macOS, Python may not have the system cert bundle installed.
    # If this raises SSLCertVerificationError, run:
    #   /Applications/Python\ 3.x/Install\ Certificates.command
    # or:  pip install certifi
    return ctx


def _api_get(path: str, token: str) -> object:
    url = f"{API_BASE}{path}"
    req = urllib.request.Request(url, headers={"Authorization": f"Bearer {token}"})
    try:
        with urllib.request.urlopen(req, timeout=15, context=_ssl_ctx()) as resp:
            return json.loads(resp.read())
    except urllib.error.HTTPError as e:
        print(f"  HTTP {e.code} from {url}", file=sys.stderr)
        raise


def fetch_api_activities(token: str) -> list:
    org = _org_from_token(token)
    return _api_get(f"/{org}/project/{PROJECT_ID}/v2/activities", token)


def fetch_api_events(token: str) -> list:
    org = _org_from_token(token)
    data = _api_get(f"/{org}/project/{PROJECT_ID}/v2/event-specifications", token)
    return data.get("specifications", data) if isinstance(data, dict) else data


def diff_api(token: str) -> None:
    """Fetch live activity/event lists and report gaps vs the NODES catalog."""

    # Internal-only activity names that are not user-facing flow nodes
    INTERNAL_ACTIVITIES = {"NewSubFlowStart", "Event", "NewContact"}

    # Library subtitle → API activityName aliases where the names differ,
    # or subtitles to suppress from the stale check (platform-level nodes).
    SUBTITLE_ALIASES = {
        "fn-activity": "function",   # Function node — platform-level, not in activity API
    }
    # Additional subtitles never returned by the activity API
    SKIP_STALE = {"fn-activity"}

    # Event spec names we deliberately omit (internal/test or covered by other nodes)
    INTERNAL_EVENTS = {
        "TestEventPleaseDelete",
        "ContactDelete",
        "ContactStartWorkflow",             # represented as Start Flow node
        "FCAsk(ContactLastAgentRemoved)",   # variant of Last Agent Removed
    }

    print("Fetching activities from API…")
    activities = fetch_api_activities(token)
    events     = fetch_api_events(token)
    print(f"  API returned {len(activities)} activities, {len(events)} events\n")

    # --- Activity diff (non-event nodes only) ---
    lib_activity_subtitles = {
        n["subtitle"] for n in NODES if n["style_key"] != "event"
    }
    missing_activities = [
        a for a in activities
        if a["activityName"] not in lib_activity_subtitles
        and a["activityName"] not in INTERNAL_ACTIVITIES
    ]
    if missing_activities:
        print(f"⚠  {len(missing_activities)} API activities not in library:")
        for a in missing_activities:
            ports = [(p["condition"], "ERR" if p.get("isErrorPath") else "OK")
                     for p in a.get("outputPorts", [])]
            print(f"   {a['activityName']:35s} [{a['group']}]  ports={ports}")
    else:
        print("✓  All API activities are represented in the library.")

    # Library action nodes whose subtitle doesn't appear in the API
    api_names = {a["activityName"] for a in activities}
    stale = [
        n for n in NODES
        if n["style_key"] not in {"event", "start", "end"}
        and n["subtitle"] not in api_names
        and SUBTITLE_ALIASES.get(n["subtitle"], n["subtitle"]) not in api_names
        and n["subtitle"] not in SKIP_STALE
    ]
    if stale:
        print(f"\n⚠  {len(stale)} library nodes not found in API (possibly renamed/removed):")
        for n in stale:
            print(f"   {n['id']:35s} subtitle={n['subtitle']}")

    # --- Event spec diff ---
    lib_event_subtitles = {n["subtitle"] for n in NODES if n["style_key"] == "event"}
    api_event_names     = {e["eventSpecificationName"] for e in events}
    missing_events = api_event_names - lib_event_subtitles - INTERNAL_EVENTS
    if missing_events:
        print(f"\n⚠  {len(missing_events)} API events not in library:")
        for e in sorted(missing_events):
            print(f"   {e}")
    else:
        print("\n✓  All API events are represented in the library.")
    print()


# ── Entry point ───────────────────────────────────────────────────────────────

if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Generate WxCC draw.io shape library.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "Examples:\n"
            "  python3 generate_library.py\n"
            "  python3 generate_library.py --token <bearer_token>\n"
            "  python3 generate_library.py out.xml --token <bearer_token>\n"
        ),
    )
    parser.add_argument("output", nargs="?", default="WxCC-FlowBuilder-Activities.xml",
                        help="Output .xml path (default: WxCC-FlowBuilder-Activities.xml)")
    parser.add_argument("--token", "-t", metavar="BEARER_TOKEN",
                        help="WxCC bearer token — fetches live activities and diffs against library")
    args = parser.parse_args()

    api_data = None
    api_events = None
    if args.token:
        org = _org_from_token(args.token)
        print(f"Org ID : {org}")
        print(f"Project: {PROJECT_ID}\n")
        diff_api(args.token)
        print("Fetching activity inputs for field tables…")
        activities = fetch_api_activities(args.token)
        api_data = {a["activityName"]: a for a in activities}
        api_events = {e["eventSpecificationName"]: e for e in fetch_api_events(args.token)}
        print(f"  Loaded inputs for {len(api_data)} activities, {len(api_events)} events\n")

    print(f"Generating WxCC draw.io library → {args.output}\n")
    generate(args.output, api_data, api_events)
