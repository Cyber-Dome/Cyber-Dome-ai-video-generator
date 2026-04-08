# diagram_engine.py
import hashlib
import os
import re
import requests
from typing import Optional, List

# Cache version – increment this if you change diagram styling logic
CACHE_VERSION = "v1"

class DiagramEngine:
    def __init__(self, cache_dir: str = "diagram_cache", api_timeout: int = 10):
        self.cache_dir = cache_dir
        self.api_timeout = api_timeout
        self.kroki_base = "https://kroki.io"
        os.makedirs(self.cache_dir, exist_ok=True)

    def generate_diagram(self, scene_id: int, text: str, diagram_type: str = "auto") -> Optional[str]:
        mermaid_code = self._text_to_mermaid(text, diagram_type)
        if not mermaid_code:
            return None
        return self._render_mermaid(scene_id, mermaid_code)

    def _text_to_mermaid(self, text: str, diagram_type: str) -> Optional[str]:
        # Respect forced diagram_type
        if diagram_type == "sequence":
            return self._api_sequence(text)
        if diagram_type == "flowchart":
            return self._generic_process_flowchart(text)
        # Auto mode: infer from text
        text_lower = text.lower()
        if "api" in text_lower or ("request" in text_lower and "response" in text_lower):
            return self._api_sequence(text)
        if any(kw in text_lower for kw in ["auth", "login", "authentication", "oauth", "jwt"]):
            return self._auth_flowchart(text)
        if any(kw in text_lower for kw in ["database", "sql", "query", "db"]):
            return self._database_flowchart(text)
        if any(kw in text_lower for kw in ["dns", "network", "ip", "domain", "packet"]):
            return self._network_flowchart(text)
        return self._generic_process_flowchart(text)

    def _api_sequence(self, text: str) -> str:
        client = "Client"
        server = "API Server"
        if "browser" in text.lower():
            client = "Browser"
        if "backend" in text.lower():
            server = "Backend"
        elif "database" in text.lower():
            server = "Database API"
        return f"""sequenceDiagram
    participant {client}
    participant {server}
    {client}->>+{server}: HTTP Request
    {server}-->>-{client}: Response
    Note over {client},{server}: Headers, rate limiting, error handling"""

    def _auth_flowchart(self, text: str) -> str:
        return """flowchart TD
    A[User enters credentials] --> B{Validate}
    B -->|Valid| C[Generate JWT / Session]
    B -->|Invalid| D[Show error & retry]
    C --> E[Access protected resource]
    D --> A
    style A fill:#e1f5fe,stroke:#01579b
    style B fill:#fff9c4,stroke:#fbc02d
    style C fill:#c8e6c9,stroke:#2e7d32
    style E fill:#c8e6c9,stroke:#2e7d32
    style D fill:#ffcdd2,stroke:#c62828"""

    def _database_flowchart(self, text: str) -> str:
        return """flowchart LR
    App[Application] -->|SQL Query| DB[(Database)]
    DB -->|Result set| App
    App --> Transform[Transform data]
    Transform --> UI[Display to user]
    style DB fill:#f3e5f5,stroke:#6a1b9a,stroke-width:2px
    style App fill:#e3f2fd,stroke:#0d47a1
    style Transform fill:#fff3e0,stroke:#e65100
    style UI fill:#e8f5e9,stroke:#1b5e20"""

    def _network_flowchart(self, text: str) -> str:
        return """flowchart TD
    User[User types domain] --> Browser[Browser]
    Browser -->|DNS query| Resolver[Local DNS resolver]
    Resolver -->|Recursive lookup| Root[Root DNS]
    Root --> TLD[TLD DNS]
    TLD --> Authoritative[Authoritative DNS]
    Authoritative -->|IP address| Browser
    Browser --> Server[Web server]
    style User fill:#e0f7fa
    style Browser fill:#b2ebf2
    style Resolver fill:#ffe0b2
    style Authoritative fill:#c8e6c9"""

    def _generic_process_flowchart(self, text: str) -> str:
        steps = self._extract_steps(text)
        if not steps:
            steps = ["Start process", "Execute task", "Verify result", "End"]
        mermaid = "flowchart TD\n"
        for i, step in enumerate(steps):
            node_id = f"S{i+1}"
            clean_step = step[:40].strip()
            mermaid += f"    {node_id}[{clean_step}]\n"
            if i < len(steps) - 1:
                mermaid += f"    {node_id} --> S{i+2}\n"
        mermaid += "\n    style S1 fill:#e3f2fd,stroke:#0d47a1\n"
        mermaid += f"    style S{len(steps)} fill:#c8e6c9,stroke:#2e7d32\n"
        return mermaid

    def _extract_steps(self, text: str) -> list:
        text_lower = text.lower()
        first_match = re.search(r"first[:\s]+([^.,;]+)", text_lower)
        then_match = re.search(r"then[:\s]+([^.,;]+)", text_lower)
        finally_match = re.search(r"finally[:\s]+([^.,;]+)", text_lower)
        if first_match and then_match and finally_match:
            return [first_match.group(1), then_match.group(1), finally_match.group(1)]
        step_matches = re.findall(r"step\s+(\d+)[:\s]+([^.;]+)", text_lower)
        if step_matches:
            return [s[1].strip() for s in sorted(step_matches, key=lambda x: int(x[0]))]
        parts = re.split(r"\s+then\s+|\s+next\s+|\s+after that\s+", text_lower)
        if len(parts) >= 2:
            return [p.strip() for p in parts if p.strip()][:5]
        return []



    def _text_to_mermaid_with_highlight(
        self,
        text: str,
        diagram_type: str,
        highlight_step: int,
        steps: List[str],
    ) -> Optional[str]:
        """Generate Mermaid code with one step highlighted."""
        forced_type = "flowchart" if diagram_type == "auto" else diagram_type
        if forced_type == "sequence":
            base = self._api_sequence(text)
            # sequence highlighting is limited in Mermaid without complex styling;
            # keep the base sequence diagram for now.
            return base

        base = self._generic_process_flowchart(text)
        target_node = f"S{highlight_step + 1}"
        lines = base.split("\n")
        lines.append(f"    style {target_node} fill:#00ff88,stroke:#00cc66,stroke-width:4px")
        return "\n".join(lines)

    def _render_mermaid(self, scene_id: int, mermaid_code: str) -> Optional[str]:
        # Include cache version in hash
        versioned = f"{CACHE_VERSION}|{mermaid_code}"
        code_hash = hashlib.md5(versioned.encode("utf-8")).hexdigest()
        cache_path = os.path.join(self.cache_dir, f"{code_hash}.png")
        if os.path.exists(cache_path):
            return cache_path
        url = f"{self.kroki_base}/mermaid/png"
        headers = {"Content-Type": "text/plain"}
        try:
            resp = requests.post(url, data=mermaid_code.encode("utf-8"),
                                 headers=headers, timeout=self.api_timeout)
            if resp.status_code == 200:
                with open(cache_path, "wb") as f:
                    f.write(resp.content)
                return cache_path
            else:
                print(f"[DiagramEngine] API error {resp.status_code} for scene {scene_id}")
                return None
        except Exception as e:
            print(f"[DiagramEngine] Request failed for scene {scene_id}: {e}")
            return None