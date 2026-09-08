"""Rutas base del motor Gla-2 (IA y orquestador, sin IDE)."""

from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
MEMORIA_PATH = ROOT / "datos" / "memoria.md"
IDENTIDAD_PATH = ROOT / "datos" / "identidad.md"
HALLAZGOS_PATH = ROOT / "datos" / "hallazgos.jsonl"
APRENDIZAJES_PATH = ROOT / "datos" / "aprendizajes.jsonl"
FORMATO_PATH = ROOT / "datos" / "formato.jsonl"
PESOS_DIR = ROOT / "datos" / "pesos"
BALANCES_PATH = PESOS_DIR / "balances.json"
EXPERIMENTOS_PATH = PESOS_DIR / "experimentos.jsonl"
SANDBOX_DIR = ROOT / "sandbox" / "runs"
# R1 no se entrena. Gla-2 es otro modelo.
MODELO_CONGELADO = "deepseek-r1:8b"
MODELO_GLA2 = "gla-2"
BASE_GLA2 = "qwen2.5-coder:1.5b"
SKILLS_DIR = ROOT / "skills"
MODELFILE_PATH = ROOT / "Modelfile"
SPECS_DIR = ROOT / "specs"
ENV_PATH = ROOT / ".env"
