"""
generate_architecture_diagram.py

Generates a Lucidchart-importable CSV architecture diagram
specifically for the API Designer Agent project.

Run:
    python generate_architecture_diagram.py

Output:
    api_designer_architecture.csv  — import into Lucidchart
    api_designer_architecture.html — open directly in browser (no import needed)
"""

import csv
import io
import json


# ── Architecture definition for API Designer Agent ────────────────────────────
ARCHITECTURE = {
    "title": "API Designer Agent — Architecture",
    "version": "1.0.0",
    "frontend": {
        "name": "React Frontend",
        "tech": "React 19 + Vite + TypeScript",
        "url": "http://127.0.0.1:5173",
        "color": "#1e40af",
        "bg": "#eff6ff",
    },
    "auth": {
        "name": "JWT Auth",
        "tech": "python-jose + bcrypt",
        "endpoints": [
            "POST /api/auth/register",
            "POST /api/auth/login",
            "GET  /api/auth/me",
        ],
        "color": "#6d28d9",
        "bg": "#f5f3ff",
    },
    "backend": {
        "name": "FastAPI Backend",
        "tech": "Python 3.14 + Uvicorn",
        "url": "http://localhost:8000",
        "color": "#0369a1",
        "bg": "#e0f2fe",
    },
    "services": [
        {
            "name": "Designer Service",
            "tag": "designer",
            "color": "#059669",
            "bg": "#ecfdf5",
            "endpoints": [
                ("POST", "/api/designer/generate",             "Generate OpenAPI Spec"),
                ("POST", "/api/designer/validate",             "Validate OpenAPI Spec"),
                ("POST", "/api/designer/artifact",             "Export YAML/JSON/Postman"),
                ("POST", "/api/designer/extract-requirements", "Extract from Word Doc"),
                ("POST", "/api/designer/swagger-docs",         "Generate Swagger HTML"),
                ("POST", "/api/designer/data-models",          "Generate Data Models"),
            ],
        },
        {
            "name": "Azure DevOps",
            "tag": "azure",
            "color": "#0078d4",
            "bg": "#e8f4fd",
            "endpoints": [
                ("POST", "/api/azure/fetch-stories", "Fetch Work Items via WIQL"),
            ],
        },
        {
            "name": "Jira Service",
            "tag": "jira",
            "color": "#0052cc",
            "bg": "#e6f0ff",
            "endpoints": [
                ("POST", "/api/jira/fetch-stories", "Fetch Issues via JQL"),
            ],
        },
        {
            "name": "Confluence",
            "tag": "confluence",
            "color": "#172b4d",
            "bg": "#e8edf5",
            "endpoints": [
                ("POST", "/api/confluence/fetch-stories", "Fetch Pages"),
            ],
        },
        {
            "name": "Excel Service",
            "tag": "excel",
            "color": "#217346",
            "bg": "#e8f5e9",
            "endpoints": [
                ("POST", "/api/excel/extract-requirements", "Extract from Spreadsheet"),
                ("POST", "/api/excel/debug",                "Debug Column Mapping"),
            ],
        },
    ],
    "external": [
        {
            "name": "Groq AI",
            "tech": "LLaMA 3.3 70B",
            "url": "api.groq.com",
            "color": "#b45309",
            "bg": "#fef3c7",
        },
        {
            "name": "Azure DevOps API",
            "tech": "REST API v7.0",
            "url": "dev.azure.com",
            "color": "#0078d4",
            "bg": "#e8f4fd",
        },
        {
            "name": "Jira REST API",
            "tech": "Atlassian REST v3",
            "url": "*.atlassian.net",
            "color": "#0052cc",
            "bg": "#e6f0ff",
        },
        {
            "name": "Confluence API",
            "tech": "Atlassian REST",
            "url": "*.atlassian.net",
            "color": "#172b4d",
            "bg": "#e8edf5",
        },
    ],
}

METHOD_COLORS = {
    "GET":    "#ecfdf5",
    "POST":   "#eff6ff",
    "PUT":    "#fef3c7",
    "PATCH":  "#f5f3ff",
    "DELETE": "#fee2e2",
}


# ─────────────────────────────────────────────────────────────────────────────
# 1. Generate Lucidchart CSV
# ─────────────────────────────────────────────────────────────────────────────
def generate_lucidchart_csv() -> str:
    output = io.StringIO()
    writer = csv.writer(output)

    writer.writerow([
        "Id", "Name", "Shape Library", "Page ID",
        "Contained By", "Line Source", "Line Destination",
        "Source Arrow", "Destination Arrow",
        "Text Area 1", "Text Area 2",
        "Width", "Height", "X Pos", "Y Pos",
        "Fill Color", "Line Color", "Text Color",
        "Font Size", "Bold"
    ])

    shapes = []
    lines  = []
    sid    = 1
    lid    = 9000

    def shape(text1, text2, w, h, x, y, fill, stroke, color="#1e293b", bold="FALSE", fs=11):
        nonlocal sid
        shapes.append([
            sid, text1, "General", 1,
            "", "", "", "", "",
            text1, text2,
            w, h, x, y,
            fill, stroke, color, fs, bold
        ])
        _id = sid
        sid += 1
        return _id

    def line(src, dst, label="", stroke="#94a3b8"):
        nonlocal lid
        lines.append([
            lid, "", "General", 1,
            "", src, dst,
            "none", "arrow",
            label, "",
            "", "", "", "",
            "", stroke, "#64748b", 9, "FALSE"
        ])
        lid += 1

    # ── Title ─────────────────────────────────────────────────────────────────
    shape("API Designer Agent — Architecture v1.0.0",
          "FastAPI + React + JWT + Groq AI",
          960, 55, 20, 10,
          "#0f172a", "#020617", "#ffffff", "TRUE", 15)

    # ── Frontend ──────────────────────────────────────────────────────────────
    fe = ARCHITECTURE["frontend"]
    fe_id = shape(fe["name"], fe["tech"] + "\n" + fe["url"],
                  160, 80, 30, 100,
                  fe["bg"], fe["color"], "#1e293b", "TRUE", 12)

    # ── Auth Box ──────────────────────────────────────────────────────────────
    auth = ARCHITECTURE["auth"]
    auth_id = shape(auth["name"],
                    auth["tech"] + "\n" + "\n".join(auth["endpoints"]),
                    180, 110, 750, 80,
                    auth["bg"], auth["color"], "#1e293b", "TRUE", 11)

    # Frontend → Auth
    line(fe_id, auth_id, "Login / Register", auth["color"])

    # ── Backend Gateway ───────────────────────────────────────────────────────
    be = ARCHITECTURE["backend"]
    be_id = shape(be["name"], be["tech"] + "\n" + be["url"],
                  180, 75, 400, 100,
                  be["bg"], be["color"], "#1e293b", "TRUE", 12)

    # Frontend → Backend
    line(fe_id, be_id, "HTTP + Bearer Token", be["color"])

    # Auth → Backend
    line(auth_id, be_id, "Validates JWT", "#6d28d9")

    # ── Health endpoint ───────────────────────────────────────────────────────
    health_id = shape("GET /api/health", "Public — no auth",
                      160, 45, 400, 210,
                      "#f0fdf4", "#16a34a", "#15803d", "FALSE", 10)
    line(be_id, health_id, "", "#16a34a")

    # ── Services ──────────────────────────────────────────────────────────────
    svc_x = 30
    svc_y = 310

    for svc in ARCHITECTURE["services"]:
        ep_count   = len(svc["endpoints"])
        box_height = 55 + ep_count * 52
        box_width  = 175

        # Service group box
        grp_id = shape(svc["name"], f"{ep_count} endpoints",
                       box_width, box_height, svc_x, svc_y,
                       svc["bg"], svc["color"], "#1e293b", "TRUE", 12)

        # Backend → Service
        line(be_id, grp_id, "", svc["color"])

        # Individual endpoint rows
        ep_y = svc_y + 52
        for method, path, summary in svc["endpoints"]:
            ep_fill = METHOD_COLORS.get(method, "#f8fafc")
            shape(f"{method} {path}", summary,
                  155, 44, svc_x + 10, ep_y,
                  ep_fill, svc["color"], "#1e293b", "FALSE", 9)
            ep_y += 50

        svc_x += box_width + 20

    # ── External Services ─────────────────────────────────────────────────────
    ext_x  = 30
    ext_y  = svc_y + max(
        55 + len(s["endpoints"]) * 52
        for s in ARCHITECTURE["services"]
    ) + 50

    # Section label
    shape("External Services / APIs", "",
          960, 40, 20, ext_y - 48,
          "#1e293b", "#0f172a", "#ffffff", "TRUE", 13)

    for ext in ARCHITECTURE["external"]:
        ext_id = shape(ext["name"], ext["tech"] + "\n" + ext["url"],
                       200, 75, ext_x, ext_y,
                       ext["bg"], ext["color"], "#1e293b", "TRUE", 11)

        # Connect relevant service to external
        if ext["name"] == "Groq AI":
            # Designer service connects to Groq
            line(2, ext_id, "LLM API calls", ext["color"])
        elif ext["name"] == "Azure DevOps API":
            line(3, ext_id, "WIQL + REST", ext["color"])
        elif ext["name"] == "Jira REST API":
            line(4, ext_id, "JQL search", ext["color"])
        elif ext["name"] == "Confluence API":
            line(5, ext_id, "Page fetch", ext["color"])

        ext_x += 230

    # ── Write CSV ─────────────────────────────────────────────────────────────
    for row in shapes:
        writer.writerow(row)
    for row in lines:
        writer.writerow(row)

    return output.getvalue()


# ─────────────────────────────────────────────────────────────────────────────
# 2. Generate standalone HTML diagram (open in browser directly)
# ─────────────────────────────────────────────────────────────────────────────
def generate_html_diagram() -> str:

    services_html = ""
    for svc in ARCHITECTURE["services"]:
        eps = "".join(
            f'<div class="endpoint" style="background:{METHOD_COLORS.get(m,"#f8fafc")};border-left:3px solid {svc["color"]}">'
            f'<span class="method" style="background:{svc["color"]};color:#fff">{m}</span>'
            f'<span class="path">{p}</span>'
            f'<span class="summary">{s}</span></div>'
            for m, p, s in svc["endpoints"]
        )
        services_html += f"""
        <div class="service-box" style="border-color:{svc['color']};background:{svc['bg']}">
            <div class="service-title" style="color:{svc['color']}">{svc['name']}</div>
            <div class="service-tag">/{svc['tag']}</div>
            {eps}
        </div>"""

    external_html = "".join(
        f'<div class="ext-box" style="border-color:{e["color"]};background:{e["bg"]}">'
        f'<div class="ext-title" style="color:{e["color"]}">{e["name"]}</div>'
        f'<div class="ext-tech">{e["tech"]}</div>'
        f'<div class="ext-url">{e["url"]}</div></div>'
        for e in ARCHITECTURE["external"]
    )

    auth_eps = "".join(
        f'<div class="auth-ep">{ep}</div>'
        for ep in ARCHITECTURE["auth"]["endpoints"]
    )

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8"/>
<title>API Designer Agent — Architecture</title>
<style>
  * {{ box-sizing: border-box; margin: 0; padding: 0; }}
  body {{
    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
    background: #f1f5f9;
    padding: 24px;
    font-size: 12px;
    color: #1e293b;
  }}
  .title-banner {{
    background: linear-gradient(90deg, #0f172a, #1e3a5f);
    color: #fff;
    padding: 16px 24px;
    border-radius: 10px;
    margin-bottom: 20px;
    display: flex;
    align-items: center;
    justify-content: space-between;
  }}
  .title-banner h1 {{ font-size: 20px; font-weight: 900; }}
  .title-banner p  {{ font-size: 12px; color: #94a3b8; margin-top: 4px; }}
  .badge {{
    padding: 4px 12px;
    border-radius: 999px;
    font-size: 11px;
    font-weight: 700;
    background: #4f46e5;
    color: #fff;
  }}

  /* Layer rows */
  .layer {{ margin-bottom: 16px; }}
  .layer-label {{
    font-size: 10px;
    font-weight: 800;
    text-transform: uppercase;
    letter-spacing: 0.08em;
    color: #64748b;
    margin-bottom: 8px;
    padding-left: 4px;
  }}
  .layer-row {{
    display: flex;
    gap: 16px;
    align-items: flex-start;
    flex-wrap: wrap;
  }}

  /* Arrows between layers */
  .arrow-row {{
    display: flex;
    justify-content: center;
    align-items: center;
    gap: 8px;
    margin: 4px 0;
    color: #94a3b8;
    font-size: 11px;
  }}
  .arrow {{ font-size: 20px; color: #cbd5e1; }}

  /* Frontend box */
  .frontend-box {{
    background: #eff6ff;
    border: 2px solid #1e40af;
    border-radius: 10px;
    padding: 14px 20px;
    min-width: 200px;
  }}
  .frontend-box .box-title {{ font-weight: 800; color: #1e40af; font-size: 13px; }}
  .frontend-box .box-sub   {{ color: #64748b; font-size: 11px; margin-top: 4px; }}
  .frontend-box .box-url   {{ color: #2563eb; font-size: 11px; margin-top: 6px; font-weight: 600; }}

  /* Auth box */
  .auth-box {{
    background: #f5f3ff;
    border: 2px solid #6d28d9;
    border-radius: 10px;
    padding: 14px 20px;
    min-width: 220px;
  }}
  .auth-box .box-title {{ font-weight: 800; color: #6d28d9; font-size: 13px; }}
  .auth-box .box-sub   {{ color: #64748b; font-size: 11px; margin-top: 4px; }}
  .auth-ep {{
    font-size: 10px;
    color: #5b21b6;
    margin-top: 4px;
    font-family: monospace;
  }}

  /* Backend box */
  .backend-box {{
    background: #e0f2fe;
    border: 2px solid #0369a1;
    border-radius: 10px;
    padding: 14px 20px;
    min-width: 200px;
  }}
  .backend-box .box-title {{ font-weight: 800; color: #0369a1; font-size: 13px; }}
  .backend-box .box-sub   {{ color: #64748b; font-size: 11px; margin-top: 4px; }}
  .backend-box .box-url   {{ color: #0284c7; font-size: 11px; margin-top: 6px; font-weight: 600; }}

  /* Health */
  .health-box {{
    background: #f0fdf4;
    border: 1.5px solid #16a34a;
    border-radius: 8px;
    padding: 8px 14px;
    font-size: 11px;
    color: #15803d;
    font-weight: 600;
  }}

  /* Service boxes */
  .service-box {{
    border: 2px solid;
    border-radius: 10px;
    padding: 12px;
    min-width: 190px;
    flex: 1;
  }}
  .service-title {{
    font-weight: 800;
    font-size: 12px;
    margin-bottom: 2px;
  }}
  .service-tag {{
    font-size: 10px;
    color: #64748b;
    margin-bottom: 8px;
    font-family: monospace;
  }}
  .endpoint {{
    display: flex;
    align-items: center;
    gap: 6px;
    padding: 5px 8px;
    border-radius: 5px;
    margin-bottom: 5px;
    flex-wrap: wrap;
  }}
  .method {{
    padding: 2px 6px;
    border-radius: 4px;
    font-size: 9px;
    font-weight: 900;
    letter-spacing: 0.04em;
    flex-shrink: 0;
  }}
  .path {{
    font-family: monospace;
    font-size: 10px;
    color: #1e293b;
    font-weight: 600;
  }}
  .summary {{
    font-size: 10px;
    color: #64748b;
    margin-left: auto;
  }}

  /* External boxes */
  .ext-box {{
    border: 2px solid;
    border-radius: 10px;
    padding: 12px 16px;
    min-width: 180px;
    flex: 1;
  }}
  .ext-title {{ font-weight: 800; font-size: 12px; margin-bottom: 4px; }}
  .ext-tech  {{ font-size: 10px; color: #64748b; }}
  .ext-url   {{ font-size: 10px; font-family: monospace; color: #475569; margin-top: 4px; }}

  /* JWT flow note */
  .jwt-note {{
    background: #fefce8;
    border: 1px solid #ca8a04;
    border-radius: 8px;
    padding: 10px 16px;
    font-size: 11px;
    color: #92400e;
    margin-bottom: 16px;
  }}
  .jwt-note strong {{ color: #78350f; }}
</style>
</head>
<body>

<!-- Title -->
<div class="title-banner">
  <div>
    <h1>API Designer Agent — Architecture</h1>
    <p>FastAPI + React 19 + JWT Auth + Groq AI (LLaMA 3.3 70B)</p>
  </div>
  <span class="badge">v1.0.0</span>
</div>

<!-- JWT Flow Note -->
<div class="jwt-note">
  <strong>Auth Flow:</strong>
  Register → Login → Receive JWT Token → Send <code>Authorization: Bearer &lt;token&gt;</code>
  with every API request → Backend validates token → Access granted
</div>

<!-- Layer 1: Client + Auth -->
<div class="layer">
  <div class="layer-label">Layer 1 — Client + Authentication</div>
  <div class="layer-row">
    <div class="frontend-box">
      <div class="box-title">React Frontend</div>
      <div class="box-sub">React 19 + Vite + TypeScript</div>
      <div class="box-url">http://127.0.0.1:5173</div>
    </div>
    <div class="auth-box">
      <div class="box-title">JWT Authentication</div>
      <div class="box-sub">python-jose + bcrypt</div>
      {auth_eps}
    </div>
    <div class="health-box">GET /api/health — Public</div>
  </div>
</div>

<div class="arrow-row">
  <span class="arrow">↓</span>
  <span>HTTP Requests + Authorization: Bearer &lt;token&gt;</span>
  <span class="arrow">↓</span>
</div>

<!-- Layer 2: Backend -->
<div class="layer">
  <div class="layer-label">Layer 2 — FastAPI Backend</div>
  <div class="layer-row">
    <div class="backend-box">
      <div class="box-title">FastAPI Backend</div>
      <div class="box-sub">Python 3.14 + Uvicorn + CORS Middleware</div>
      <div class="box-url">http://localhost:8000</div>
    </div>
  </div>
</div>

<div class="arrow-row">
  <span class="arrow">↓</span>
  <span>Routes to service routers (all protected by JWT)</span>
  <span class="arrow">↓</span>
</div>

<!-- Layer 3: Services -->
<div class="layer">
  <div class="layer-label">Layer 3 — API Service Routers (JWT Protected)</div>
  <div class="layer-row">
    {services_html}
  </div>
</div>

<div class="arrow-row">
  <span class="arrow">↓</span>
  <span>External API calls</span>
  <span class="arrow">↓</span>
</div>

<!-- Layer 4: External -->
<div class="layer">
  <div class="layer-label">Layer 4 — External Services</div>
  <div class="layer-row">
    {external_html}
  </div>
</div>

</body>
</html>"""


# ─────────────────────────────────────────────────────────────────────────────
# Main
# ─────────────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    # 1. Generate Lucidchart CSV
    csv_path = "api_designer_architecture.csv"
    csv_content = generate_lucidchart_csv()
    with open(csv_path, "w", newline="", encoding="utf-8") as f:
        f.write(csv_content)
    print(f"Lucidchart CSV saved  : {csv_path}")
    print("  -> Open https://lucid.app -> New Document -> File -> Import Data -> CSV")

    # 2. Generate HTML diagram
    html_path = "api_designer_architecture.html"
    html_content = generate_html_diagram()
    with open(html_path, "w", encoding="utf-8") as f:
        f.write(html_content)
    print(f"HTML diagram saved    : {html_path}")
    print("  -> Open directly in browser — no import needed")
