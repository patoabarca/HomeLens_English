"""A2: CLI reproducible. Simulación por defecto; API sólo con dos flags explícitos.

Ejecutar desde la raíz: python -m scripts.evaluacion.ejecutar_experimento --help
"""
from __future__ import annotations

import argparse
import hashlib
import json
import time
from datetime import datetime, timezone
from importlib.metadata import version
from pathlib import Path
from types import SimpleNamespace
from uuid import UUID, uuid4

from homelens.analisis import _cargar_prompt_exploracion, analizar_exploracion
from homelens.config import cargar_configuracion
from homelens.esquemas_ia import RespuestaExploracionIA
from homelens.imagenes import preparar_imagen
from homelens.integraciones.gemini import AdaptadorGemini
from homelens.modelos import ContextoUsuario

from .dataset_experimento import (PROYECTO, cargar_dataset, dentro, fotografia,
                                  guardar_json, identificador, preparar_manifest)
from .evaluacion_common import sha256_file, write_csv
from .metricas import SINONIMOS, VERSION_CRITERIOS

RESULTADOS = PROYECTO / "data/evaluacion/resultados"
FIXTURE = Path(__file__).parent / "fixtures/respuesta_simulada.json"


def ahora() -> str:
    return datetime.now(timezone.utc).isoformat()


def huella(value: object) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=False, allow_nan=False).encode()).hexdigest()


def configuracion(simulada: bool) -> tuple[dict, object]:
    result = cargar_configuracion(cargar_archivo_env=not simulada, incluir_secretos=not simulada)
    if not result.ok:
        raise ValueError("Configuración de HomeLens inválida")
    cfg = result.valor
    adapter = AdaptadorGemini(modelo=cfg.gemini_model, timeout_segundos=cfg.gemini_timeout_seconds,
                             max_reintentos=cfg.gemini_max_retries)
    sources = ["homelens/analisis.py", "homelens/imagenes.py", "homelens/integraciones/gemini.py",
               "homelens/esquemas_ia.py", "homelens/modelos.py", "homelens/config.py",
               "scripts/evaluacion/evaluacion_common.py"]
    sources += [str(p.relative_to(PROYECTO)).replace("\\", "/") for p in Path(__file__).parent.glob("*_experimento.py")]
    sources += ["scripts/evaluacion/metricas.py", "scripts/evaluacion/informe_metricas.py"]
    generacion = {
        "response_mime_type": "application/json",
        "temperatura_enviada": adapter.modelo != "gemini-3.6-flash",
        "otros_parametros": "No fijados por HomeLens; defaults del proveedor/SDK",
    }
    if adapter.modelo == "gemini-3.6-flash":
        generacion["razonamiento"] = {
            "nivel_predeterminado_documentado": "medium",
            "origen": "predeterminado_proveedor",
            "configuracion_enviada": False,
        }
    else:
        generacion["temperature"] = 0.2
    snapshot = {
        "modo": "simulado" if simulada else "real", "modelo": adapter.modelo,
        "prompt_sha256": hashlib.sha256(_cargar_prompt_exploracion().encode()).hexdigest(),
        "schema_version": 1, "schema_sha256": huella(RespuestaExploracionIA.model_json_schema()),
        "generacion": generacion,
        "timeout_segundos": adapter.timeout_segundos, "max_reintentos": adapter.max_reintentos,
        "preparacion": {"max_bytes": cfg.max_image_size_bytes, "max_dimension_px": 1280},
        "criterios": VERSION_CRITERIOS, "iou_umbral": 0.5, "sinonimos": SINONIMOS,
        "fuentes_sha256": {p: sha256_file(PROYECTO / p) for p in sorted(set(sources))},
        "versiones": {name: version(name) for name in ("google-genai", "pydantic", "Pillow")},
        "fixture_sha256": sha256_file(FIXTURE) if simulada else None,
    }
    return snapshot, cfg


class ClienteRegistrado:
    """Observa el transporte del adaptador original; no construye otro prompt."""

    def __init__(self, base: AdaptadorGemini, simulado: bool):
        self.base, self.simulado = base, simulado
        self.models = self
        self.llamadas = []
        self.cliente = None

    def generate_content(self, **kwargs):
        config = kwargs["config"]
        observed = config.model_dump(mode="python", exclude_none=True, exclude={"system_instruction", "response_schema"})
        # Convertir únicamente configuración de generación sin credenciales ni bytes.
        observed = json.loads(json.dumps(observed, default=str))
        attempt = {"inicio_utc": ahora(), "configuracion_enviada": observed,
                   "estado": "iniciada", "tokens": None, "respuesta_texto": None}
        self.llamadas.append(attempt)
        started = time.perf_counter()
        try:
            if self.simulado:
                response = SimpleNamespace(text=FIXTURE.read_text(encoding="utf-8"), usage_metadata=None, model_version=None)
            else:
                if self.cliente is None:
                    self.cliente = self.base._obtener_cliente()
                response = self.cliente.models.generate_content(**kwargs)
            text = getattr(response, "text", None)
            if text and self.base.api_key:
                text = text.replace(self.base.api_key, "[CREDENCIAL_ELIMINADA]")
            attempt["respuesta_texto"] = text
            usage = getattr(response, "usage_metadata", None)
            if usage is not None:
                attempt["tokens"] = {k: getattr(usage, k, None) for k in (
                    "prompt_token_count", "candidates_token_count", "total_token_count", "thoughts_token_count", "cached_content_token_count")}
            attempt["modelo_version_reportada"] = getattr(response, "model_version", None)
            attempt["estado"] = "recibida"
            return response
        except Exception:
            # No persistir str(exc): podría incluir URL, cabeceras o credenciales.
            attempt["estado"] = "error_transporte"
            raise
        finally:
            attempt["duracion_segundos"] = time.perf_counter() - started

    def close(self):
        if self.cliente is not None and hasattr(self.cliente, "close"):
            self.cliente.close()


def validar_separacion(manifest: dict, piloto: dict) -> None:
    if manifest["conjunto"] != "evaluacion_final" or piloto["conjunto"] != "piloto":
        raise ValueError("Se requiere manifiesto final y manifiesto piloto")
    for key in ("image_id", "sha256"):
        if {r[key] for r in manifest["imagenes"]} & {r[key] for r in piloto["imagenes"]}:
            raise ValueError("Hay imágenes compartidas entre piloto y final")


def congelar(manifest_path: Path, piloto_path: Path, output: Path) -> None:
    manifest, _ = cargar_dataset(manifest_path)
    piloto, _ = cargar_dataset(piloto_path)
    validar_separacion(manifest, piloto)
    cfg, _ = configuracion(False)
    protocol = {"fecha_utc": ahora(), "configuracion": cfg, "config_sha256": huella(cfg),
                "manifest_sha256": sha256_file(manifest_path), "piloto": piloto,
                "nota": "Configuración fijada antes de consultar las fotografías finales; no implica resultados medidos."}
    output = dentro(output, RESULTADOS)
    if output.exists():
        raise ValueError("El protocolo ya existe; conservar la versión anterior")
    guardar_json(output, protocol)


def ejecutar(manifest_path: Path, run_id: str, *, real: bool = False, autorizar_api: bool = False,
             limit: int | None = None, image_id: str | None = None, reintentar_fallidas: bool = False,
             protocolo: Path | None = None) -> Path:
    identificador(run_id)
    if real and not autorizar_api:
        raise ValueError("Una llamada real requiere --real --autorizar-api")
    if autorizar_api and not real:
        raise ValueError("--autorizar-api sólo corresponde al modo --real")
    if limit is not None and limit < 1:
        raise ValueError("El límite debe ser positivo")
    manifest, annotations = cargar_dataset(manifest_path)
    config, app_cfg = configuracion(not real)
    if manifest["conjunto"] == "evaluacion_final":
        if real:
            if not protocolo:
                raise ValueError("La ejecución real final requiere un protocolo congelado")
            protocol = json.loads(protocolo.read_text(encoding="utf-8"))
            if protocol["configuracion"] != config or protocol["config_sha256"] != huella(config) or protocol["manifest_sha256"] != sha256_file(manifest_path):
                raise ValueError("El protocolo no coincide con datos/configuración actuales")
            validar_separacion(manifest, protocol["piloto"])
            if len(manifest["imagenes"]) != 30:
                raise ValueError("El conjunto final debe contener las 30 fotografías previstas")
        elif protocolo:
            raise ValueError("La simulación final no utiliza un protocolo de ejecución real")
    images = [x for x in manifest["imagenes"] if image_id is None or x["image_id"] == image_id]
    if not images:
        raise ValueError("No se encontró la imagen solicitada")
    if limit:
        images = images[:limit]
    if real and (not app_cfg.gemini_api_key or any(x["origen"] == "pendiente" or x["permisos"] != "confirmados" for x in images)):
        raise ValueError("La ejecución real requiere GEMINI_API_KEY y procedencia/permisos confirmados para las imágenes seleccionadas")
    if real and manifest["conjunto"] == "evaluacion_final" and any(
        image.get("revision_humana") != "aprobada" for image in images
    ):
        raise ValueError("La ejecución real final requiere revisión humana aprobada para cada imagen seleccionada")
    run = dentro(RESULTADOS / run_id, RESULTADOS)
    identity = {"run_id": run_id, "configuracion": config, "config_sha256": huella(config),
                "manifest_sha256": sha256_file(manifest_path), "dataset": manifest, "anotaciones": annotations}
    if (run / "ejecucion.json").exists():
        previous = json.loads((run / "ejecucion.json").read_text(encoding="utf-8"))
        if any(previous.get(k) != v for k, v in identity.items()):
            raise ValueError("No se puede reanudar con datos o configuración distintos; usar otro run-id")
    else:
        run.mkdir(parents=True, exist_ok=False)
        guardar_json(run / "ejecucion.json", {**identity, "creada_utc": ahora()})
    user = ContextoUsuario(UUID(int=0), "evaluacion-local")
    for image in images:
        folder = dentro(run / image["image_id"], run)
        folder.mkdir(exist_ok=True)
        attempts = sorted(folder.glob("intento_*.json"))
        old = json.loads(attempts[-1].read_text(encoding="utf-8")) if attempts else None
        if old and (old["estado"] == "valida" or not reintentar_fallidas):
            if old["estado"] == "valida" and sha256_file(fotografia(manifest, image)) != image["sha256"]:
                raise ValueError("La fotografía completada cambió; no se puede reutilizar su respuesta")
            continue
        number = len(attempts) + 1
        target = folder / f"intento_{number:04d}.json"
        record = {"run_id": run_id, "image_id": image["image_id"], "sha256": image["sha256"],
                  "origen": image["origen"], "modo": config["modo"], "conjunto": manifest["conjunto"],
                  "config_sha256": huella(config), "modelo": config["modelo"], "prompt_sha256": config["prompt_sha256"],
                  "schema_version": 1, "schema_sha256": config["schema_sha256"], "intento": number,
                  "inicio_utc": ahora(), "estado": "en_curso", "duracion_segundos": None,
                  "respuesta": None, "error_codigo": None, "llamadas": []}
        # Reserva durable antes de consultar API: un corte no provoca una repetición silenciosa.
        with target.open("x", encoding="utf-8") as handle:
            json.dump(record, handle, ensure_ascii=False)
        capture = None
        start = None
        try:
            photo = fotografia(manifest, image)
            if photo.stat().st_size > app_cfg.max_image_size_bytes:
                raise ValueError("LIMITE_ARCHIVO")
            if sha256_file(photo) != image["sha256"]:
                raise ValueError("HASH_IMAGEN_DISTINTO")
            prepared = preparar_imagen(photo.read_bytes(), max_bytes=app_cfg.max_image_size_bytes, max_dimension_px=1280)
            if not prepared.ok:
                raise ValueError("IMAGEN_INVALIDA")
            # CVAT refiere a la orientación original. No transformar cajas ante EXIF rotado.
            from PIL import Image
            with Image.open(photo) as source:
                if source.getexif().get(274, 1) != 1:
                    raise ValueError("ORIENTACION_EXIF_REQUIERE_REVISION")
                metadata_path = PROYECTO / manifest["root"] / "imagenes_normalizadas.json"
                metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
                candidate = next(r for r in metadata if r["image_id"] == image["image_id"])
                expected = (int(candidate["width"]), int(candidate["height"]))
                if source.size != expected:
                    transform = candidate.get("transformacion_validada") or {}
                    if not (transform.get("method") == "uniform_resize_same_aspect_ratio"
                            and transform.get("visual_review_accepted") is True
                            and (transform.get("coco_width"), transform.get("coco_height")) == expected
                            and (transform.get("actual_width"), transform.get("actual_height")) == source.size
                            and abs(source.width / source.height - expected[0] / expected[1]) <= 0.001):
                        raise ValueError("DIMENSIONES_REQUIEREN_REVISION")
            record["imagen_preparada_sha256"] = hashlib.sha256(prepared.valor.contenido).hexdigest()
            base = AdaptadorGemini(api_key=app_cfg.gemini_api_key if real else None,
                                   modelo=config["modelo"], timeout_segundos=config["timeout_segundos"],
                                   max_reintentos=config["max_reintentos"])
            capture = ClienteRegistrado(base, not real)
            adapter = AdaptadorGemini(modelo=base.modelo, timeout_segundos=base.timeout_segundos,
                                     max_reintentos=base.max_reintentos, cliente=capture)
            start = time.perf_counter()
            result = analizar_exploracion(user, prepared.valor, uuid4(), adaptador=adapter)
            record["duracion_segundos"] = time.perf_counter() - start
            raw = capture.llamadas[-1]["respuesta_texto"] if capture.llamadas else None
            if raw:
                try:
                    record["respuesta"] = json.loads(raw)
                except ValueError:
                    pass
            if result.ok and raw:
                # Igual coerción del esquema que usa el adaptador. El texto original
                # sigue conservado en llamadas, incluso si Pydantic normaliza tipos.
                record["respuesta"] = RespuestaExploracionIA.model_validate_json(raw).model_dump(mode="json")
            record["estado"] = "valida" if result.ok else "respuesta_invalida" if result.error.codigo == "RESPUESTA_INVALIDA" else "fallida_api"
            record["error_codigo"] = None if result.ok else result.error.codigo
        except Exception as exc:
            record["estado"] = "fallida_local" if start is None else "fallida_api"
            record["error_codigo"] = str(exc) if isinstance(exc, ValueError) and str(exc) in {"LIMITE_ARCHIVO", "HASH_IMAGEN_DISTINTO", "IMAGEN_INVALIDA", "ORIENTACION_EXIF_REQUIERE_REVISION", "DIMENSIONES_REQUIEREN_REVISION"} else "ERROR_LOCAL_CONTROLADO"
            if start is not None:
                record["duracion_segundos"] = time.perf_counter() - start
        finally:
            if capture:
                record["llamadas"] = capture.llamadas
                try:
                    capture.close()
                except Exception:
                    pass
            record["fin_utc"] = ahora()
            guardar_json(target, record)
            exportar_indice(run)
    return run


def registros(run: Path, todos: bool = False) -> list[dict]:
    records = []
    for folder in sorted(run.iterdir()):
        if folder.is_dir():
            files = sorted(folder.glob("intento_*.json"))
            records.extend(json.loads(f.read_text(encoding="utf-8")) for f in (files if todos else files[-1:]))
    return records


def exportar_indice(run: Path) -> None:
    fields = ["run_id", "image_id", "modo", "conjunto", "origen", "sha256", "modelo", "prompt_sha256",
              "schema_version", "schema_sha256", "config_sha256", "inicio_utc", "fin_utc", "estado",
              "intento", "duracion_segundos", "error_codigo", "respuesta_json", "tokens_json"]
    rows = []
    for record in registros(run, todos=True):
        rows.append({**record, "respuesta_json": f"{record['image_id']}/intento_{record['intento']:04d}.json",
                     "tokens_json": json.dumps([x.get("tokens") for x in record["llamadas"]])})
    write_csv(run / "respuestas.csv", fields, rows)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="accion", required=True)
    prepare = sub.add_parser("preparar", help="Crear manifiesto lateral; no modificar A1")
    prepare.add_argument("--root", type=Path, required=True)
    prepare.add_argument("--fotos-root", type=Path, required=True)
    prepare.add_argument("--conjunto", choices=["piloto", "evaluacion_final"], required=True)
    prepare.add_argument("--origen", choices=["real", "sintetica", "pendiente"], default="pendiente")
    prepare.add_argument("--manifest", type=Path, required=True)
    freeze = sub.add_parser("congelar")
    freeze.add_argument("--manifest", type=Path, required=True)
    freeze.add_argument("--piloto-manifest", type=Path, required=True)
    freeze.add_argument("--protocolo", type=Path, required=True)
    run = sub.add_parser("ejecutar")
    run.add_argument("--manifest", type=Path, required=True)
    run.add_argument("--run-id", required=True)
    run.add_argument("--real", action="store_true")
    run.add_argument("--autorizar-api", action="store_true")
    run.add_argument("--limite", type=int)
    run.add_argument("--image-id")
    run.add_argument("--reintentar-fallidas", action="store_true")
    run.add_argument("--protocolo", type=Path)
    args = parser.parse_args()
    try:
        if args.accion == "preparar":
            output = dentro(args.manifest, RESULTADOS)
            if output.exists():
                raise ValueError("El manifiesto ya existe; editar sólo sus metadatos humanos o usar otro nombre")
            guardar_json(output, preparar_manifest(args.root, args.fotos_root, args.conjunto, args.origen))
        elif args.accion == "congelar":
            congelar(args.manifest, args.piloto_manifest, args.protocolo)
        else:
            output = ejecutar(args.manifest, args.run_id, real=args.real, autorizar_api=args.autorizar_api,
                              limit=args.limite, image_id=args.image_id, reintentar_fallidas=args.reintentar_fallidas,
                              protocolo=args.protocolo)
            print(output.relative_to(PROYECTO))
        return 0
    except (ValueError, OSError, KeyError) as exc:
        # Errores de preparación no incluyen mensajes del proveedor ni credenciales.
        print(f"No se inició/completó la operación: {type(exc).__name__}. Revisar datos, rutas y protocolo.")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
