"""El bot de descuentos: busca promos en las fuentes, las entiende, las verifica y las publica o deja para revisión."""
import json
import logging
from datetime import datetime

from .extract import extract, extract_claude_image, extract_rules, claude_available
from .fetch import FetchError, fetch_source
from .verify import expire_old, register_feedback, upsert_promo  # noqa: F401

log = logging.getLogger(__name__)


def retire_missing(con, source_id, seen):
    """Las promos que la página ya no muestra se dan de baja solas.

    Por seguridad, solo si esta vez se leyó al menos la mitad de lo que había: si la página cambió de diseño
    o cargó a medias, no se borra todo de golpe (queda el error a la vista en el panel).
    """
    active = [r["id"] for r in con.execute("SELECT id FROM promos WHERE source_id=? AND status IN ('publicada','revision')", (source_id,))]
    missing = [i for i in active if i not in seen]
    if not missing or len(seen) < len(active) / 2:
        return 0
    con.executemany("UPDATE promos SET status='vencida' WHERE id=?", [(i,) for i in missing])
    return len(missing)


def run_bot(con, only_source=None):
    """Corre todas las fuentes activas. Devuelve el resumen de la corrida."""
    started = datetime.now().isoformat(timespec="seconds")
    stats = {"found": 0, "new": 0, "published": 0, "queued": 0, "errors": [], "extractor": "claude" if claude_available() else "reglas"}
    q = "SELECT * FROM sources WHERE enabled=1" + (" AND id=?" if only_source else "")
    for src in con.execute(q, (only_source,) if only_source else ()).fetchall():
        try:
            text = fetch_source(src)
            promos, how = extract(text, src["name"], src["method_id"] if "method_id" in src.keys() else None)
            stats["extractor"] = how
            seen = set()
            for p in promos:
                stats["found"] += 1
                pid, is_new, status = upsert_promo(con, p, "bot", source_id=src["id"], trust=src["trust"], source_url=src["url"],
                                                   is_example=src["kind"] == "fixture")
                if pid:
                    seen.add(pid)
                if is_new:
                    stats["new"] += 1
                    stats["published" if status == "publicada" else "queued"] += 1
            stats["retired"] = stats.get("retired", 0) + retire_missing(con, src["id"], seen)
            con.execute("UPDATE sources SET last_run=?, last_status=? WHERE id=?",
                        (started, f"OK: {len(promos)} promos ({how})", src["id"]))
        except FetchError as e:
            stats["errors"].append(f"{src['name']}: {e}")
            con.execute("UPDATE sources SET last_run=?, last_status=? WHERE id=?", (started, f"Error: {e}", src["id"]))
        except Exception as e:  # noqa: BLE001 - una fuente rota no frena a las demás
            log.exception("Fuente %s", src["name"])
            stats["errors"].append(f"{src['name']}: {e}")
    stats["expired"] = expire_old(con)
    con.execute("INSERT INTO bot_runs(started, finished, found, new, published, queued, errors, extractor) VALUES(?,?,?,?,?,?,?,?)",
                (started, datetime.now().isoformat(timespec="seconds"), stats["found"], stats["new"], stats["published"],
                 stats["queued"], json.dumps(stats["errors"], ensure_ascii=False), stats["extractor"]))
    return stats


def read_user_submission(con, uid, text=None, image_path=None, link=None):
    """Una promo que sube un usuario (texto, link o foto). Siempre queda para revisión, salvo confianza muy alta."""
    promos, how = [], "reglas"
    if image_path and claude_available():
        promos, how = (extract_claude_image(image_path) or []), "claude"
    body = " ".join(x for x in [text, link] if x)
    if not promos and body:
        promos, how = extract(body, "usuario")
    results = []
    for p in promos:
        pid, is_new, status = upsert_promo(con, p, "usuario", trust=0.5, source_url=link, created_by=uid,
                                           force_status="revision")
        results.append({**p, "id": pid, "new": is_new, "status": status})
    return {"promos": results, "extractor": how, "image_needs_review": bool(image_path) and not promos}


__all__ = ["run_bot", "read_user_submission", "register_feedback", "extract_rules", "claude_available"]
