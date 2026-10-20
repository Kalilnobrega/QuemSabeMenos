"""Exporta os modelos de app/events.py como JSON Schema para o front gerar tipos TS."""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from pydantic.json_schema import models_json_schema  # noqa: E402

from app.events import EVENT_MODELS  # noqa: E402

OUTPUT = Path(__file__).resolve().parents[2] / "frontend" / "src" / "types" / "events.schema.json"

_, schema = models_json_schema([(model, "serialization") for model in EVENT_MODELS])
schema["title"] = "Events"

# Títulos de propriedades viram aliases inúteis no TS (ex.: `type ServerTime = number`).
for definition in schema.get("$defs", {}).values():
    for prop in definition.get("properties", {}).values():
        prop.pop("title", None)
OUTPUT.parent.mkdir(parents=True, exist_ok=True)
OUTPUT.write_text(json.dumps(schema, indent=2, ensure_ascii=False) + "\n")
print(f"Schema exportado para {OUTPUT}")
