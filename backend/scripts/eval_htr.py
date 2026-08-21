#!/usr/bin/env python
"""Avalia a leitura de manuscrito contra um conjunto de referência.

Item 3 do docs/HTR_PLANO_EXECUCAO.md. Enquanto este script não tiver dados
reais para rodar, toda melhoria de leitura no projeto é hipótese: não há como
dizer se uma mudança ajudou, e mudanças que ajudam o caso comum costumam piorar
casos não previstos.

Como montar o conjunto
----------------------
Um diretório com os recortes (PNG) e um `labels.jsonl`, uma linha por recorte:

    {"crop": "p001_q01.png", "reference": "actina e miosina deslizam",
     "strata": ["cursiva_ligada", "caneta_azul", "scanner"]}

`reference` é a transcrição feita **à mão**, exatamente como o aluno escreveu:
sem corrigir português, sem completar palavra, preservando abreviação. Caixa em
branco entra com `"reference": ""` — esses casos são os que medem alucinação, e
são os mais importantes do conjunto.

Estratifique. As falhas de HTR se concentram em bolsões (lápis fraco, cursiva
ligada, foto de celular) e a média global esconde qual. Sugestão de eixos:
`cursiva_ligada` · `bastao` · `mista` · `lapis` · `caneta_azul` · `caneta_preta`
· `scanner` · `celular`.

Uso
---
    # linha de base, sem chamar modelo nenhum (usa transcrições já gravadas)
    python scripts/eval_htr.py --labels eval/labels.jsonl --predictions eval/baseline.jsonl

    # roda o pipeline de verdade sobre os recortes (gasta chamadas de LLM)
    python scripts/eval_htr.py --labels eval/labels.jsonl --run-model

    # compara duas execuções
    python scripts/eval_htr.py --labels eval/labels.jsonl \
        --predictions eval/antes.jsonl --compare eval/depois.jsonl
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.services.vision.htr_metrics import Report, Sample, evaluate  # noqa: E402


def read_jsonl(path: Path) -> list[dict]:
    records = []
    for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        try:
            records.append(json.loads(line))
        except json.JSONDecodeError as exc:
            raise SystemExit(f"{path}:{line_number}: JSON inválido — {exc}") from exc
    return records


def load_samples(labels_path: Path, predictions_path: Path | None) -> list[Sample]:
    labels = read_jsonl(labels_path)
    if not labels:
        raise SystemExit(f"{labels_path} está vazio.")

    predictions: dict[str, dict] = {}
    if predictions_path:
        predictions = {str(item.get("crop") or ""): item for item in read_jsonl(predictions_path)}

    samples = []
    missing = 0
    for label in labels:
        crop = str(label.get("crop") or "")
        prediction = predictions.get(crop, {})
        if predictions_path and crop not in predictions:
            missing += 1
        samples.append(
            Sample(
                reference=str(label.get("reference") or ""),
                hypothesis=str(prediction.get("hypothesis") or ""),
                confidence=prediction.get("confidence"),
                strata=tuple(label.get("strata") or ()),
                crop_id=crop,
            )
        )

    if missing:
        # Não é erro: recorte sem predição conta como resposta não lida, que é
        # exatamente o que aconteceria em produção se o pipeline falhasse ali.
        print(f"aviso: {missing} recorte(s) sem predição; contados como não lidos.", file=sys.stderr)
    return samples


def run_model(labels_path: Path, crops_dir: Path, output_path: Path) -> Path:
    """Roda a transcrição real sobre cada recorte e grava as predições."""
    from app.services.openrouter_vision_client import transcribe_answer_crop
    from app.services.vision.ink import detect_ink
    from PIL import Image

    labels = read_jsonl(labels_path)
    results = []
    for index, label in enumerate(labels, start=1):
        crop_name = str(label.get("crop") or "")
        crop_path = crops_dir / crop_name
        if not crop_path.is_file():
            print(f"  [{index}/{len(labels)}] {crop_name}: arquivo não encontrado", file=sys.stderr)
            continue

        # O detector de tinta resolve caixa vazia antes de gastar chamada — a
        # avaliação tem de exercitar o mesmo caminho da produção, senão mede
        # outra coisa.
        with Image.open(crop_path) as image:
            ink = detect_ink(image)

        if not ink.has_ink:
            results.append({"crop": crop_name, "hypothesis": "", "confidence": "alta", "source": "ink_detector"})
            print(f"  [{index}/{len(labels)}] {crop_name}: caixa vazia (tinta {ink.ink_ratio:.4f})")
            continue

        try:
            read = transcribe_answer_crop(str(crop_path), question_number=label.get("question"))
        except Exception as exc:  # noqa: BLE001 — um recorte ruim não derruba a avaliação
            print(f"  [{index}/{len(labels)}] {crop_name}: FALHOU — {exc}", file=sys.stderr)
            results.append({"crop": crop_name, "hypothesis": "", "confidence": "baixa", "error": str(exc)})
            continue

        results.append(
            {
                "crop": crop_name,
                "hypothesis": read.get("answer_transcription") or "",
                "confidence": read.get("reading_confidence"),
                "model": read.get("model_used"),
            }
        )
        print(f"  [{index}/{len(labels)}] {crop_name}: {results[-1]['hypothesis'][:60]!r}")

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        "\n".join(json.dumps(item, ensure_ascii=False) for item in results) + "\n",
        encoding="utf-8",
    )
    return output_path


def print_report(report: Report, title: str) -> None:
    print(f"\n{title}")
    print("=" * len(title))
    print(f"  recortes avaliados      {report.samples}")
    print(f"  CER                     {report.cer:.4f}   <- a metrica que importa")
    print(f"  CER sem acentos         {report.cer_no_accents:.4f}")
    print(f"  WER                     {report.wer:.4f}")
    print(f"  leituras perfeitas      {report.perfect_reads}")
    print(f"  respostas nao lidas     {report.missed_answers}")
    print(f"  caixas vazias           {report.empty_boxes}")
    print(
        f"  alucinacao em vazia     {report.hallucinated_empty} "
        f"({report.hallucination_rate:.1%})   <- o erro mais grave"
    )

    correlation = report.confidence_cer_correlation
    if correlation is None:
        print("  confianca x CER         sem variacao suficiente para medir")
    else:
        veredito = (
            "confianca informativa"
            if correlation < -0.4
            else "CONFIANCA NAO CALIBRADA: o gate de revisao nao significa nada"
        )
        print(f"  confianca x CER         {correlation:+.3f}   <- {veredito}")

    if report.by_stratum:
        print("\n  por estrato (a media global esconde os bolsoes):")
        width = max(len(name) for name in report.by_stratum)
        for name, stratum in sorted(report.by_stratum.items(), key=lambda kv: -kv[1].cer):
            print(
                f"    {name:<{width}}  n={stratum.samples:<4} CER={stratum.cer:.4f} "
                f"alucinacao={stratum.hallucination_rate:.1%}"
            )


def print_comparison(before: Report, after: Report) -> None:
    print("\ncomparacao")
    print("==========")
    rows = [
        ("CER", before.cer, after.cer, "menor melhor"),
        ("WER", before.wer, after.wer, "menor melhor"),
        ("alucinacao em vazia", before.hallucination_rate, after.hallucination_rate, "menor melhor"),
    ]
    for name, old, new, direction in rows:
        delta = new - old
        arrow = "melhorou" if delta < 0 else ("piorou" if delta > 0 else "igual")
        print(f"  {name:<22} {old:.4f} -> {new:.4f}  ({delta:+.4f}, {arrow}; {direction})")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--labels", type=Path, required=True, help="labels.jsonl com as transcricoes de referencia")
    parser.add_argument("--predictions", type=Path, help="predictions.jsonl a avaliar")
    parser.add_argument("--compare", type=Path, help="segundo predictions.jsonl, para comparar com o primeiro")
    parser.add_argument("--crops", type=Path, help="diretorio dos recortes (default: ao lado de --labels)")
    parser.add_argument("--run-model", action="store_true", help="roda a transcricao real (gasta chamadas de LLM)")
    parser.add_argument("--json", type=Path, help="grava o relatorio em JSON")
    args = parser.parse_args()

    if not args.labels.is_file():
        raise SystemExit(f"Arquivo de referencia nao encontrado: {args.labels}")

    predictions_path = args.predictions
    if args.run_model:
        crops_dir = args.crops or args.labels.parent
        output = args.predictions or args.labels.with_name("predictions.jsonl")
        print(f"Transcrevendo recortes de {crops_dir} ...")
        predictions_path = run_model(args.labels, crops_dir, output)
        print(f"\nPredicoes gravadas em {predictions_path}")

    if not predictions_path:
        raise SystemExit("Informe --predictions ou use --run-model.")

    report = evaluate(load_samples(args.labels, predictions_path))
    print_report(report, f"HTR — {predictions_path.name}")

    if args.compare:
        other = evaluate(load_samples(args.labels, args.compare))
        print_report(other, f"HTR — {args.compare.name}")
        print_comparison(report, other)

    if args.json:
        args.json.parent.mkdir(parents=True, exist_ok=True)
        args.json.write_text(json.dumps(report.as_dict(), ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"\nRelatorio JSON: {args.json}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
