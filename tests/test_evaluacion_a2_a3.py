"""Experimentos y métricas con datos controlados: nunca se consulta Gemini."""
from __future__ import annotations

import json
import hashlib
from pathlib import Path
from types import SimpleNamespace
from zipfile import ZipFile

import pytest
from PIL import Image
from homelens.integraciones import gemini

from scripts.evaluacion import ejecutar_experimento as runner
from scripts.evaluacion import informe_metricas as report
from scripts.evaluacion.dataset_experimento import cargar_dataset, dentro, guardar_json, preparar_manifest
from scripts.evaluacion.evaluacion_common import read_csv, write_csv
from scripts.evaluacion.importar_cvat import import_cvat
from scripts.evaluacion.metricas import emparejar, iou, resumir, tiempos


@pytest.fixture(autouse=True)
def sin_red(monkeypatch):
    def prohibido(*args, **kwargs):
        raise AssertionError("Acceso real a Gemini prohibido en tests")
    monkeypatch.setattr(gemini.genai, "Client", prohibido)
    monkeypatch.setenv("GEMINI_MODEL", "gemini-2.5-flash")
    monkeypatch.setenv("GEMINI_MAX_RETRIES", "0")
    monkeypatch.setenv("GEMINI_API_KEY", "credencial-simulada-no-real")


@pytest.fixture
def dataset(tmp_path, monkeypatch):
    photos = tmp_path / "fotos"
    photos.mkdir()
    for i, color in enumerate(("white", "blue"), 1):
        Image.new("RGB", (100, 80), color).save(photos / f"{i}.jpg")
    export = tmp_path / "cvat.zip"
    with ZipFile(export, "w") as archive:
        archive.writestr("annotations/instances_default.json", json.dumps({
            "images": [{"id": i, "width": 100, "height": 80, "file_name": f"{i}.jpg"} for i in (1, 2)],
            "categories": [{"id": 1, "name": "Chair"}],
            "annotations": [{"id": i, "image_id": i, "category_id": 1, "bbox": [15, 8, 70, 56]} for i in (1, 2)]}))
    root = tmp_path / "a1"
    import_cvat(export, root, "test", "piloto", photos)
    rows = read_csv(root / "candidatos.csv")
    for row in rows:
        row["aceptada"] = "si"
    write_csv(root / "candidatos.csv", list(rows[0]), rows)
    results = tmp_path / "resultados"
    monkeypatch.setattr(runner, "RESULTADOS", results)
    monkeypatch.setattr(report, "RESULTADOS", results)
    manifest = preparar_manifest(root, photos, "piloto", "sintetica")
    path = results / "manifest.json"
    guardar_json(path, manifest)
    return path, root, photos


@pytest.fixture
def cliente_gemini_controlado(monkeypatch):
    """Cliente sin red para verificar ejecuciones reales sólo contra un fixture."""
    calls = []
    response = SimpleNamespace(text=runner.FIXTURE.read_text(encoding="utf-8"), usage_metadata=None)
    client = SimpleNamespace(models=SimpleNamespace(generate_content=lambda **kwargs: calls.append(kwargs) or response))
    monkeypatch.setattr(gemini.genai, "Client", lambda **kwargs: client)
    return calls


@pytest.fixture
def dataset_final(dataset, tmp_path, request):
    """Conjunto final completamente controlado, separado del piloto y sin API."""
    cantidad = getattr(request, "param", 30)
    photos = tmp_path / "fotos_finales"
    photos.mkdir()
    for i in range(1, cantidad + 1):
        Image.new("RGB", (100, 80), (i, 0, 0)).save(photos / f"{i}.png")
    export = tmp_path / "final.zip"
    with ZipFile(export, "w") as archive:
        archive.writestr("annotations/instances_default.json", json.dumps({
            "images": [{"id": i, "width": 100, "height": 80, "file_name": f"{i}.png"} for i in range(1, cantidad + 1)],
            "categories": [{"id": 1, "name": "Chair"}],
            "annotations": [{"id": i, "image_id": i, "category_id": 1, "bbox": [15, 8, 70, 56]} for i in range(1, cantidad + 1)],
        }))
    root = tmp_path / "a1_final"
    import_cvat(export, root, "final_controlado", "evaluacion_final", photos)
    rows = read_csv(root / "candidatos.csv")
    for row in rows:
        row["aceptada"] = "si"
    write_csv(root / "candidatos.csv", list(rows[0]), rows)
    manifest = preparar_manifest(root, photos, "evaluacion_final", "sintetica")
    # Sólo los datos temporales del test reciben esta autorización ficticia.
    for image in manifest["imagenes"]:
        image["permisos"] = "confirmados"
    path = runner.RESULTADOS / "manifest_final_controlado.json"
    guardar_json(path, manifest)
    return path, dataset[0], runner.RESULTADOS / "protocolo_final_controlado.json"


def pred(name="chair", box=None, id="obj_1"):
    return {"id_local": id, "nombre_en": name, "box": box or [100, 100, 500, 500]}


def ref(name="Chair", box=None, id="1"):
    return {"id": id, "categoria": name, "box": box or [100, 100, 500, 500]}


@pytest.mark.parametrize("a,b,expected", [
    ([0, 0, 100, 200], [0, 0, 100, 200], 1),
    ([0, 0, 100, 200], [0, 100, 100, 300], 1 / 3),
    ([0, 0, 100, 200], [100, 0, 200, 200], 0),
    ([100, 200, 500, 600], [200, 200, 400, 600], 0.5),
])
def test_iou_orden_yxyx(a, b, expected):
    assert iou(a, b) == pytest.approx(expected)


@pytest.mark.parametrize("box", [[0, 0, 0, 100], [-1, 0, 10, 10], [0, 0, 1001, 100], [True, 0, 10, 10], [0, 0, float("nan"), 10], [0, 0, 1], [0, 10, 10, 1]])
def test_coordenadas_invalidas(box):
    with pytest.raises(ValueError):
        iou(box, [0, 0, 100, 100])


def test_sinonimos_sin_confundir_categorias():
    assert emparejar([pred("couch")], [ref("Sofa")], {}, False)[0]["identificacion"] == "correcta"
    assert emparejar([pred("coffee table")], [ref("Table")], {}, False)[0]["identificacion"] == "pendiente"


def test_repetidos_asignacion_optima_uno_a_uno():
    a, b = [0, 0, 400, 400], [500, 500, 900, 900]
    pairs = emparejar([pred(box=b), pred(box=a, id="obj_2")], [ref(box=a), ref(box=b, id="2")], {}, False)
    assert [p["referencia_id"] for p in pairs] == ["2", "1"]
    assert [p["iou"] for p in pairs] == [1, 1]


def test_asignacion_no_es_greedy():
    # La primera detección admite dos refs; la segunda sólo la primera categoría/instancia.
    refs = [ref(box=[0, 0, 400, 400]), ref(box=[0, 500, 400, 900], id="2")]
    pairs = emparejar([pred(box=[0, 0, 400, 900]), pred(box=[0, 0, 400, 300], id="obj_2")], refs, {}, False)
    # Primer objeto equidistante queda pendiente por ambigüedad, nunca se inventa una instancia.
    assert pairs[0]["identificacion"] == "pendiente"
    assert pairs[1]["referencia_id"] == "1"


def test_repetidos_sin_superposicion_o_empate_pendientes():
    refs = [ref(box=[0, 0, 100, 100]), ref(box=[0, 200, 100, 300], id="2")]
    assert emparejar([pred(box=[500, 500, 900, 900])], refs, {}, True)[0]["identificacion"] == "pendiente"
    pairs = emparejar([pred(), pred(id="obj_2")], [ref()], {}, False)
    assert all(p["identificacion"] == "pendiente" for p in pairs)


def test_no_anotado_no_es_error_automatico():
    assert emparejar([pred("book")], [ref()], {}, False)[0]["identificacion"] == "pendiente"
    assert emparejar([pred("book")], [ref()], {}, True)[0]["identificacion"] == "incorrecta"


def test_revision_humana_presencia_sin_cvat_y_matching_manual():
    manual = {"obj_1": {"identificacion": "correcta", "referencia_id": ""}}
    pair = emparejar([pred("book")], [ref()], manual, False)[0]
    assert pair["identificacion"] == "correcta" and pair["iou"] is None
    manual["obj_1"]["referencia_id"] = "1"
    assert emparejar([pred("seat")], [ref()], manual, False)[0]["iou"] == 1
    with pytest.raises(ValueError):
        emparejar([pred(), pred(id="obj_2")], [ref()], {"obj_1": manual["obj_1"], "obj_2": manual["obj_1"]}, False)


def test_precision_cobertura_iou_y_denominadores():
    rows = [{"identificacion": "correcta", "iou": 0.5, "traduccion": "correcta", "gramatica_en": "incorrecta"},
            {"identificacion": "incorrecta", "iou": None, "traduccion": "incorrecta"},
            {"identificacion": "pendiente", "iou": None}]
    result = resumir(rows, 6)
    assert result["precision_revisadas"] == {"numerador": 1, "denominador": 2, "valor": 0.5}
    assert result["fraccion_confirmada_total"]["valor"] == pytest.approx(1 / 3)
    assert result["cobertura_referencias"]["valor"] == pytest.approx(1 / 6)
    assert result["iou"]["al_menos_050"] == 1 and result["sin_emparejar"] == 2
    assert result["traduccion"]["valor"] == 0.5 and result["traduccion"]["pendientes"] == 1
    assert result["gramatica_es"]["valor"] is None
    assert resumir([], 0)["precision_revisadas"]["valor"] is None


def test_tiempos_exitos_fallos_y_sin_api():
    result = tiempos([{"estado": "valida", "duracion_segundos": n} for n in (1, 2, 6)] +
                     [{"estado": "fallida_api", "duracion_segundos": 8}, {"estado": "fallida_local", "duracion_segundos": None}])
    assert result["exitosas"] == {"cantidad": 3, "promedio": 3, "mediana": 2, "minimo": 1, "maximo": 6}
    assert result["fallidas"]["promedio"] == 8


@pytest.mark.parametrize("modelo", ["gemini-2.5-flash", "gemini-3.6-flash"])
def test_cvat_lectura_simulacion_reanudacion_e_informe(dataset, monkeypatch, modelo):
    monkeypatch.setenv("GEMINI_MODEL", modelo)
    path, root, _ = dataset
    original = (root / "anotaciones.csv").read_bytes()
    run = runner.ejecutar(path, "simulacion")
    records = runner.registros(run)
    assert len(records) == 2 and all(r["estado"] == "valida" for r in records)
    assert all(r["modo"] == "simulado" and r["duracion_segundos"] >= 0 for r in records)
    assert all(r["llamadas"][0]["tokens"] is None for r in records)
    assert records[0]["respuesta"]["actividades"][0]["opcion_correcta_id"] == "A"
    config = records[0]["llamadas"][0]["configuracion_enviada"]
    assert "system_instruction" not in config
    if modelo == "gemini-3.6-flash":
        assert "temperature" not in config
    else:
        assert config["temperature"] == 0.2
    runner.ejecutar(path, "simulacion")
    assert len(runner.registros(run, todos=True)) == 2
    output = report.informar(run)
    summary = json.loads((output / "resumen.json").read_text(encoding="utf-8"))
    assert summary["respuestas_validas"] == 2 and summary["modo"] == "simulado"
    assert summary["metricas"]["traduccion"]["denominador"] == 0
    assert summary["metricas"]["iou"]["promedio"] == 1
    assert len(read_csv(output / "referencias.csv")) == 2
    assert (root / "anotaciones.csv").read_bytes() == original
    assert "credencial-simulada-no-real" not in (run / "ejecucion.json").read_text()


@pytest.mark.parametrize("modelo", ["gemini-2.5-flash", "gemini-3.6-flash"])
def test_configuracion_registrada_y_solicitud_compartida(dataset, monkeypatch, modelo):
    from uuid import UUID, uuid4
    from homelens.modelos import ContextoUsuario
    from homelens.esquemas_ia import RespuestaExploracionIA

    monkeypatch.setenv("GEMINI_MODEL", modelo)
    snapshot, app_cfg = runner.configuracion(False)
    image = runner.preparar_imagen((dataset[2] / "1.jpg").read_bytes(), max_dimension_px=1280).valor
    calls = []
    response = SimpleNamespace(text=runner.FIXTURE.read_text(encoding="utf-8"), usage_metadata=None)
    client = SimpleNamespace(models=SimpleNamespace(generate_content=lambda **kwargs: calls.append(kwargs) or response))
    primary = runner.AdaptadorGemini(modelo=app_cfg.gemini_model, cliente=client, max_reintentos=0)
    capture = runner.ClienteRegistrado(primary, False)
    evaluation = runner.AdaptadorGemini(modelo=app_cfg.gemini_model, cliente=capture, max_reintentos=0)
    user = ContextoUsuario(UUID(int=0), "comparacion-offline")
    for adapter in (primary, evaluation):
        assert runner.analizar_exploracion(user, image, uuid4(), adaptador=adapter).ok
    assert calls[0] == calls[1]
    assert calls[0]["model"] == snapshot["modelo"] == modelo
    config = calls[0]["config"]
    assert config.system_instruction == runner._cargar_prompt_exploracion()
    assert config.response_schema is RespuestaExploracionIA
    assert config.response_mime_type == snapshot["generacion"]["response_mime_type"]
    sent = capture.llamadas[0]["configuracion_enviada"]
    if modelo == "gemini-3.6-flash":
        incompatible = {"temperature", "top_p", "top_k", "candidate_count", "presence_penalty", "frequency_penalty", "thinking_config"}
        assert incompatible.isdisjoint(sent)
        assert "temperature" not in snapshot["generacion"]
        assert snapshot["generacion"]["temperatura_enviada"] is False
        assert snapshot["generacion"]["razonamiento"] == {
            "nivel_predeterminado_documentado": "medium", "origen": "predeterminado_proveedor",
            "configuracion_enviada": False,
        }
    else:
        assert sent["temperature"] == snapshot["generacion"]["temperature"] == 0.2
        assert snapshot["generacion"]["temperatura_enviada"] is True
        assert "razonamiento" not in snapshot["generacion"]


def test_revision_exportada_aplicada_sin_sobrescribir(dataset):
    run = runner.ejecutar(dataset[0], "revision")
    report.informar(run)
    path = run / "revision_humana.csv"
    rows = read_csv(path)
    rows[0]["traduccion"] = "correcta"
    rows[0]["gramatica_en"] = "incorrecta"
    write_csv(path, report.REVISION_CAMPOS, rows)
    content = path.read_bytes()
    output = report.informar(run)
    metrics = json.loads((output / "resumen.json").read_text())["metricas"]
    assert metrics["traduccion"]["valor"] == 1 and metrics["traduccion"]["pendientes"] == 1
    assert metrics["gramatica_en"]["valor"] == 0
    assert path.read_bytes() == content


def test_api_requiere_autorizacion_y_permisos(dataset):
    with pytest.raises(ValueError, match="autorizar-api"):
        runner.ejecutar(dataset[0], "real", real=True)
    with pytest.raises(ValueError, match="permisos"):
        runner.ejecutar(dataset[0], "real", real=True, autorizar_api=True)


@pytest.mark.parametrize("selector,autorizada", [
    ({"image_id": "cvat_test_2"}, "cvat_test_2"),
    ({"image_id": "cvat_test_2", "limit": 1}, "cvat_test_2"),
    ({"limit": 1}, "cvat_test_1"),
])
def test_permisos_solo_de_imagenes_seleccionadas(dataset, monkeypatch, cliente_gemini_controlado, selector, autorizada):
    monkeypatch.setenv("GEMINI_MODEL", "gemini-3.6-flash")
    path = dataset[0]
    manifest = json.loads(path.read_text(encoding="utf-8"))
    next(x for x in manifest["imagenes"] if x["image_id"] == autorizada)["permisos"] = "confirmados"
    guardar_json(path, manifest)
    original = path.read_bytes()
    run = runner.ejecutar(path, "seleccion_autorizada", real=True, autorizar_api=True, **selector)
    records = runner.registros(run)
    assert len(records) == 1 and records[0]["image_id"] == autorizada and records[0]["estado"] == "valida"
    assert len(cliente_gemini_controlado) == 1 and cliente_gemini_controlado[0]["model"] == "gemini-3.6-flash"
    assert path.read_bytes() == original
    assert next(x for x in manifest["imagenes"] if x["image_id"] != autorizada)["permisos"] == "pendiente"


@pytest.mark.parametrize("selector,pendiente", [
    ({"image_id": "cvat_test_2"}, "cvat_test_2"),
    ({"image_id": "cvat_test_2", "limit": 1}, "cvat_test_2"),
    ({"limit": 1}, "cvat_test_1"),
    ({"limit": 2}, "cvat_test_2"),
    ({}, "cvat_test_2"),
])
def test_seleccion_con_permiso_pendiente_rechazada(dataset, cliente_gemini_controlado, selector, pendiente):
    manifest = json.loads(dataset[0].read_text(encoding="utf-8"))
    for image in manifest["imagenes"]:
        image["permisos"] = "pendiente" if image["image_id"] == pendiente else "confirmados"
    guardar_json(dataset[0], manifest)
    with pytest.raises(ValueError, match="permisos.*seleccionadas"):
        runner.ejecutar(dataset[0], "seleccion_rechazada", real=True, autorizar_api=True, **selector)
    assert not cliente_gemini_controlado
    assert not (runner.RESULTADOS / "seleccion_rechazada").exists()


def test_final_completo_valida_las_30_y_ejecuta_con_fixture(dataset_final, cliente_gemini_controlado):
    path, piloto, protocolo = dataset_final
    runner.congelar(path, piloto, protocolo)
    run = runner.ejecutar(path, "final_controlado", real=True, autorizar_api=True, protocolo=protocolo)
    assert len(runner.registros(run)) == len(cliente_gemini_controlado) == 30
    assert all(r["estado"] == "valida" for r in runner.registros(run))


def test_final_completo_rechaza_una_de_las_30_sin_permiso(dataset_final, cliente_gemini_controlado):
    path, piloto, protocolo = dataset_final
    manifest = json.loads(path.read_text(encoding="utf-8"))
    manifest["imagenes"][-1]["permisos"] = "pendiente"
    guardar_json(path, manifest)
    runner.congelar(path, piloto, protocolo)
    with pytest.raises(ValueError, match="permisos"):
        runner.ejecutar(path, "final_rechazado", real=True, autorizar_api=True, protocolo=protocolo)
    assert not cliente_gemini_controlado
    assert not (runner.RESULTADOS / "final_rechazado").exists()


@pytest.mark.parametrize("dataset_final", [29], indirect=True)
def test_seleccion_no_elude_cantidad_final_de_30(dataset_final, cliente_gemini_controlado):
    path, piloto, protocolo = dataset_final
    runner.congelar(path, piloto, protocolo)
    with pytest.raises(ValueError, match="30 fotografías"):
        runner.ejecutar(path, "final_incompleto", real=True, autorizar_api=True, limit=1,
                       image_id="cvat_final_controlado_1", protocolo=protocolo)
    assert not cliente_gemini_controlado
    assert not (runner.RESULTADOS / "final_incompleto").exists()


def test_fallo_individual_continua_y_reintento_conserva_historial(dataset):
    path, _, photos = dataset
    (photos / "1.jpg").write_bytes(b"alterado")
    run = runner.ejecutar(path, "fallos")
    records = runner.registros(run)
    assert [r["estado"] for r in records] == ["fallida_local", "valida"]
    assert records[0]["error_codigo"] == "HASH_IMAGEN_DISTINTO"
    runner.ejecutar(path, "fallos")
    assert len(runner.registros(run, todos=True)) == 2
    runner.ejecutar(path, "fallos", reintentar_fallidas=True)
    assert len(runner.registros(run, todos=True)) == 3


@pytest.mark.parametrize("raw", ["{invalid", '{"estado":"UTILIZABLE","objetos":[],"actividades":[]}',
                                   runner.FIXTURE.read_text(encoding="utf-8").replace('"ymin": 100', '"ymin": 900')])
def test_respuesta_invalida_no_se_evalua(dataset, monkeypatch, tmp_path, raw):
    fixture = tmp_path / "fixture.json"
    fixture.write_text(raw, encoding="utf-8")
    monkeypatch.setattr(runner, "FIXTURE", fixture)
    run = runner.ejecutar(dataset[0], "invalidas", limit=1)
    assert runner.registros(run)[0]["estado"] == "respuesta_invalida"
    output = report.informar(run)
    summary = json.loads((output / "resumen.json").read_text())
    assert summary["fallidas"] == 1 and summary["no_ejecutadas"] == 1


def test_timeout_sanitizado_y_continuidad(dataset, monkeypatch):
    def timeout(self, **kwargs):
        raise TimeoutError("credencial-simulada-no-real")
    monkeypatch.setattr(runner.ClienteRegistrado, "generate_content", timeout)
    run = runner.ejecutar(dataset[0], "timeout")
    records = runner.registros(run)
    assert len(records) == 2 and all(r["error_codigo"] == "TIEMPO_AGOTADO" for r in records)
    assert all(r["duracion_segundos"] is not None for r in records)
    assert "credencial-simulada-no-real" not in next(run.glob("*/intento_*.json")).read_text()


def test_limite_una_imagen_y_proteccion_rutas(dataset):
    run = runner.ejecutar(dataset[0], "una", limit=1)
    assert len(runner.registros(run)) == 1
    with pytest.raises(ValueError):
        runner.ejecutar(dataset[0], "../fuera")
    with pytest.raises(ValueError):
        dentro(Path("C:/Windows"), Path.cwd())


def test_datos_y_config_distintos_no_reanudan(dataset, monkeypatch):
    runner.ejecutar(dataset[0], "original")
    monkeypatch.setenv("GEMINI_MODEL", "modelo-distinto")
    with pytest.raises(ValueError, match="configuración"):
        runner.ejecutar(dataset[0], "original")
    rows = read_csv(dataset[1] / "anotaciones.csv")
    rows[0]["categoria"] = "Table"
    write_csv(dataset[1] / "anotaciones.csv", list(rows[0]), rows)
    with pytest.raises(ValueError, match="A1 cambió"):
        cargar_dataset(dataset[0])


def test_separacion_final_y_piloto():
    piloto = {"conjunto": "piloto", "imagenes": [{"image_id": "a", "sha256": "x"}]}
    final = {"conjunto": "evaluacion_final", "imagenes": [{"image_id": "b", "sha256": "x"}]}
    with pytest.raises(ValueError, match="compartidas"):
        runner.validar_separacion(final, piloto)
    final["imagenes"][0]["sha256"] = "y"
    runner.validar_separacion(final, piloto)


def test_final_reservado_y_congelacion(dataset):
    path, root, photos = dataset
    piloto_path = path.parent / "piloto.json"
    piloto_path.write_bytes(path.read_bytes())
    rows = read_csv(root / "candidatos.csv")
    for row in rows:
        row["destino"] = "evaluacion_final"
    write_csv(root / "candidatos.csv", list(rows[0]), rows)
    final = preparar_manifest(root, photos, "evaluacion_final", "sintetica")
    guardar_json(path, final)
    with pytest.raises(ValueError, match="reservado"):
        runner.ejecutar(path, "final")
    assert not (runner.RESULTADOS / "final").exists()
    with pytest.raises(ValueError):
        runner.congelar(path, piloto_path, path.parent / "protocolo.json")


def test_cliente_registra_tokens_y_config_sin_anotaciones(monkeypatch):
    usage = SimpleNamespace(prompt_token_count=10, candidates_token_count=20, total_token_count=30)
    response = SimpleNamespace(text=runner.FIXTURE.read_text(encoding="utf-8"), usage_metadata=usage, model_version="version-controlada")
    calls = []
    class Fake:
        models = SimpleNamespace(generate_content=lambda **kwargs: calls.append(kwargs) or response)
        def close(self):
            pass
    monkeypatch.setattr(gemini.genai, "Client", lambda **kwargs: Fake())
    base = runner.AdaptadorGemini(api_key="falsa", max_reintentos=0)
    capture = runner.ClienteRegistrado(base, False)
    adapter = runner.AdaptadorGemini(cliente=capture, max_reintentos=0)
    result = adapter.analizar_imagen_exploracion(b"image", "image/jpeg", "prompt controlado")
    assert result.ok
    assert capture.llamadas[0]["tokens"]["total_token_count"] == 30
    assert set(calls[0]) == {"model", "contents", "config"}
    assert len(calls[0]["contents"]) == 2  # Imagen + instrucción original de HomeLens.
    capture.close()


def test_protocolo_final_30_metadatos_sin_abrir_fotos(dataset, tmp_path, monkeypatch):
    piloto_path, _, _ = dataset
    root, photos = tmp_path / "final_a1", tmp_path / "final_fotos"
    root.mkdir()
    photos.mkdir()  # Intencionalmente sin imágenes: preparar/congelar no las abre.
    candidates, annotations = [], []
    for i in range(30):
        candidates.append({"image_id": f"final_{i}", "sha256": hashlib.sha256(f"final_{i}".encode()).hexdigest(),
                           "ruta_relativa": f"../final_fotos/{i}.jpg", "fuente": "CVAT", "destino": "evaluacion_final",
                           "aceptada": "si", "cantidad_objetos": "1"})
        annotations.append({"image_id": f"final_{i}", "cvat_annotation_id": str(i), "categoria": "Chair", "bbox_homelens_yxyx": "[0,0,100,100]"})
    write_csv(root / "candidatos.csv", list(candidates[0]), candidates)
    write_csv(root / "anotaciones.csv", list(annotations[0]), annotations)
    final = preparar_manifest(root, photos, "evaluacion_final", "real")
    for image in final["imagenes"]:
        image["permisos"] = "confirmados"
    final_path = piloto_path.parent / "final.json"
    guardar_json(final_path, final)
    protocol = piloto_path.parent / "protocolo.json"
    runner.congelar(final_path, piloto_path, protocol)
    assert protocol.exists()
    with pytest.raises(ValueError, match="ya existe"):
        runner.congelar(final_path, piloto_path, protocol)
    monkeypatch.setenv("GEMINI_MODEL", "modelo-cambiado-tras-congelar")
    with pytest.raises(ValueError, match="protocolo"):
        runner.ejecutar(final_path, "final_bloqueado", real=True, autorizar_api=True, protocolo=protocol)
    assert not (runner.RESULTADOS / "final_bloqueado").exists()


def test_referencia_faltante_y_respuesta_sin_objetos(dataset, monkeypatch, tmp_path):
    fixture = tmp_path / "sin_objetos.json"
    fixture.write_text('{"estado":"SIN_OBJETOS_CLAROS","objetos":[],"actividades":[]}', encoding="utf-8")
    monkeypatch.setattr(runner, "FIXTURE", fixture)
    run = runner.ejecutar(dataset[0], "sin_objetos")
    output = report.informar(run)
    summary = json.loads((output / "resumen.json").read_text())
    assert summary["respuestas_validas"] == 2
    assert summary["metricas"]["cobertura_referencias"] == {"numerador": 0, "denominador": 2, "valor": 0}
    assert summary["metricas"]["precision_revisadas"]["valor"] is None


def test_reanudacion_interrumpida_no_repite_por_defecto(dataset):
    run = runner.ejecutar(dataset[0], "interrumpida", limit=1)
    path = next(run.glob("*/intento_0001.json"))
    record = json.loads(path.read_text())
    record["estado"] = "en_curso"
    guardar_json(path, record)
    runner.ejecutar(dataset[0], "interrumpida", limit=1)
    assert len(runner.registros(run, todos=True)) == 1
    runner.ejecutar(dataset[0], "interrumpida", limit=1, reintentar_fallidas=True)
    assert len(runner.registros(run, todos=True)) == 2


def test_asignacion_global_maximiza_cantidad_antes_de_iou():
    # La primera prefiere ref1 pero admite ref2; la segunda sólo superpone ref1.
    refs = [ref(box=[0, 0, 400, 400]), ref(box=[0, 500, 400, 900], id="2")]
    pairs = emparejar([pred(box=[0, 0, 400, 700]), pred(box=[0, 0, 400, 300], id="obj_2")], refs, {}, False)
    assert [p["referencia_id"] for p in pairs] == ["2", "1"]
