from dataclasses import dataclass
from statistics import mean, median


@dataclass(frozen=True)
class MultilingualCaseMeasurement:
    case_id: str
    top_1_correct: bool
    top_k_relevant: bool
    answer_language_correct: bool
    citation_provenance_correct: bool
    latency_ms: float


def summarize_measurements(
    measurements: list[MultilingualCaseMeasurement],
) -> dict[str, float | int]:
    if not measurements:
        raise ValueError("At least one multilingual measurement is required")
    total = len(measurements)

    def percentage(attribute: str) -> float:
        correct = sum(bool(getattr(item, attribute)) for item in measurements)
        return round(correct * 100.0 / total, 2)

    latencies = [item.latency_ms for item in measurements]
    return {
        "case_count": total,
        "retrieval_top_1_accuracy_percent": percentage("top_1_correct"),
        "retrieval_top_k_recall_percent": percentage("top_k_relevant"),
        "answer_language_accuracy_percent": percentage("answer_language_correct"),
        "citation_provenance_accuracy_percent": percentage(
            "citation_provenance_correct"
        ),
        "mean_rag_latency_ms": round(mean(latencies), 2),
        "median_rag_latency_ms": round(median(latencies), 2),
    }
