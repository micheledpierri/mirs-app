"""
MIRS — Evidence Strength Score Calculator
analysis/evidence_scorer.py

Implementa la formula pesata definita nel documento di progetto (Sezione 4.1):
  - Numero e qualità dei RCT:               peso 30%
  - Presenza di meta-analisi concordanti:   peso 25%
  - Aggiornamento linee guida (< 5 anni):   peso 20%
  - Concordanza tra fonti diverse:          peso 15%
  - Volume complessivo pubblicazioni:       peso 10%

Ogni componente produce un sub-score 0–100, poi viene applicata la media pesata.
Il risultato finale è un intero 0–100.

Autore: Michele De Pierri — Phase 3
"""

import math
from datetime import datetime
from typing import Optional


# ── Costanti di calibrazione ────────────────────────────────────────── #

# Thresholds per il sub-score RCT (componente 30%)
RCT_SCORE_TABLE = [
    (0,   0),   # 0 RCT → sub-score 0
    (1,  20),
    (3,  40),
    (5,  55),
    (10, 70),
    (20, 85),
    (30, 95),
    (50, 100),
]

# Thresholds per il sub-score Meta-analisi (componente 25%)
META_SCORE_TABLE = [
    (0,   0),
    (1,  40),
    (2,  60),
    (3,  75),
    (5,  90),
    (8, 100),
]

# Thresholds per il volume totale pubblicazioni (componente 10%)
VOLUME_SCORE_TABLE = [
    (0,    0),
    (10,  15),
    (50,  35),
    (100, 55),
    (200, 70),
    (500, 85),
    (1000,100),
]

# Pesi della formula pesata (devono sommare a 1.0)
WEIGHTS = {
    "rct":         0.30,
    "meta":        0.25,
    "guidelines":  0.20,
    "concordance": 0.15,
    "volume":      0.10,
}


# ── Funzioni di supporto ────────────────────────────────────────────── #

def _interpolate_score(value: int, table: list[tuple[int, int]]) -> float:
    """
    Interpolazione lineare tra i punti della tabella soglia.
    Restituisce float 0–100.
    """
    if value <= table[0][0]:
        return float(table[0][1])
    if value >= table[-1][0]:
        return float(table[-1][1])
    for i in range(len(table) - 1):
        x0, y0 = table[i]
        x1, y1 = table[i + 1]
        if x0 <= value <= x1:
            t = (value - x0) / (x1 - x0)
            return y0 + t * (y1 - y0)
    return 0.0


def _count_article_type(articles: list[dict], keywords: list[str]) -> int:
    """
    Conta gli articoli il cui article_type contiene almeno una delle keywords.
    Accetta sia dict con chiave 'article_types' (stringa o lista) che oggetti SQLAlchemy Article.
    """
    count = 0
    for art in articles:
        # Supporta sia dict che ORM object
        if isinstance(art, dict):
            at_raw = art.get("article_types") or ""
        else:
            at_raw = getattr(art, "article_types", "") or ""

        # Normalizza: lista → stringa unica separata da spazi
        if isinstance(at_raw, list):
            at = " ".join(str(t) for t in at_raw).lower()
        else:
            at = str(at_raw).lower()

        if any(kw.lower() in at for kw in keywords):
            count += 1
    return count


def _year_from_pub_date(pub_date) -> Optional[int]:
    """Estrae l'anno da pub_date (stringa o int)."""
    if pub_date is None:
        return None
    try:
        return int(str(pub_date)[:4])
    except (ValueError, TypeError):
        return None


# ── Sub-score individuali ───────────────────────────────────────────── #

def score_rct(articles: list[dict]) -> float:
    """
    Componente 30%: numero e qualità degli RCT.
    Conta articoli classificati come RCT o Clinical Trial.
    """
    n = _count_article_type(
        articles,
        keywords=["randomized controlled trial", "rct", "clinical trial", "randomised"]
    )
    return _interpolate_score(n, RCT_SCORE_TABLE)


def score_meta_analysis(articles: list[dict]) -> float:
    """
    Componente 25%: presenza di meta-analisi concordanti.
    Conta meta-analisi e systematic review.
    """
    n = _count_article_type(
        articles,
        keywords=["meta-analysis", "meta analysis", "systematic review", "cochrane"]
    )
    return _interpolate_score(n, META_SCORE_TABLE)


def score_guidelines(articles: list[dict], current_year: Optional[int] = None) -> float:
    """
    Componente 20%: aggiornamento linee guida (< 5 anni).
    
    Formula:
      - Cerca articoli classificati come 'guideline' o 'practice guideline'
      - Conta solo quelli pubblicati negli ultimi 5 anni
      - Score = (guideline_recenti / max(total_guidelines, 1)) * 100
        moltiplicato per un fattore presenza (almeno 1 guideline = bonus base 40)
    """
    if current_year is None:
        current_year = datetime.now().year
    cutoff_year = current_year - 5

    guideline_articles = [
        art for art in articles
        if _count_article_type([art], keywords=["guideline", "practice guideline", "consensus"]) > 0
    ]
    total = len(guideline_articles)
    if total == 0:
        return 0.0

    recent = sum(
        1 for art in guideline_articles
        if (_year_from_pub_date(
            art.get("pub_date") if isinstance(art, dict) else getattr(art, "pub_date", None)
        ) or 0) >= cutoff_year
    )

    # Bonus base: avere almeno una guideline vale 40 punti
    base = 40.0
    # Recency ratio: sale fino a 60 punti aggiuntivi se tutte le linee guida sono recenti
    recency_ratio = recent / total
    return min(100.0, base + recency_ratio * 60.0)


def score_concordance(articles: list[dict]) -> float:
    """
    Componente 15%: concordanza tra fonti diverse.
    
    Proxy clinicamente valido:
      - Presenza di review narrative → base 30
      - Presenza di meta-analisi → +30
      - Presenza di linee guida → +25
      - Presenza di RCT → +15
    
    Il razionale è che quando esistono più tipologie di evidenza (RCT + 
    meta-analisi + linee guida + review) su uno stesso topic, la concordanza
    tra fonti è presupponibile. In assenza di fonti eterogenee, il sistema
    non può misurare la vera concordanza senza analisi del testo (Phase 5 LLM).
    """
    sub = 0.0
    has_review = _count_article_type(articles, ["review", "systematic review"]) > 0
    has_meta = _count_article_type(articles, ["meta-analysis", "meta analysis"]) > 0
    has_guideline = _count_article_type(articles, ["guideline", "consensus"]) > 0
    has_rct = _count_article_type(articles, ["randomized controlled trial", "rct", "clinical trial"]) > 0

    if has_review:   sub += 30.0
    if has_meta:     sub += 30.0
    if has_guideline: sub += 25.0
    if has_rct:      sub += 15.0

    return min(100.0, sub)


def score_volume(articles: list[dict]) -> float:
    """
    Componente 10%: volume complessivo pubblicazioni.
    """
    n = len(articles)
    return _interpolate_score(n, VOLUME_SCORE_TABLE)


# ── Score composito ─────────────────────────────────────────────────── #

class EvidenceScoreResult:
    """
    Contenitore per il risultato completo dell'analisi.
    Espone il punteggio finale e i sub-score per trasparenza e debug.
    """

    def __init__(
        self,
        total_score: int,
        sub_scores: dict[str, float],
        article_counts: dict[str, int],
        n_articles: int
    ):
        self.total_score = total_score          # Score finale 0–100
        self.sub_scores = sub_scores            # {'rct': 55.0, 'meta': 40.0, ...}
        self.article_counts = article_counts    # {'rct': 23, 'meta': 8, 'guidelines': 4}
        self.n_articles = n_articles

    def to_dict(self) -> dict:
        return {
            "evidence_strength_score": self.total_score,
            "sub_scores": {k: round(v, 1) for k, v in self.sub_scores.items()},
            "article_counts": self.article_counts,
            "n_articles_analyzed": self.n_articles,
        }

    def summary_text(self) -> str:
        """Testo breve per la stat card dell'Overview."""
        level = (
            "Molto forte" if self.total_score >= 80 else
            "Forte"       if self.total_score >= 60 else
            "Moderata"    if self.total_score >= 40 else
            "Limitata"    if self.total_score >= 20 else
            "Insufficiente"
        )
        return f"{self.total_score}/100 — {level}"

    def __repr__(self):
        return (
            f"EvidenceScoreResult(total={self.total_score}, "
            f"rct={self.sub_scores['rct']:.0f}, "
            f"meta={self.sub_scores['meta']:.0f}, "
            f"guidelines={self.sub_scores['guidelines']:.0f})"
        )


def calculate_evidence_score(articles: list, current_year: Optional[int] = None) -> EvidenceScoreResult:
    """
    Calcola l'Evidence Strength Score composito (0–100).

    Args:
        articles: Lista di articoli — supporta sia dict che oggetti SQLAlchemy Article.
                  Ogni articolo deve avere i campi: article_types, pub_date.
        current_year: Anno corrente (default: datetime.now().year).
                      Parametro utile per test con anni fissi.

    Returns:
        EvidenceScoreResult con score finale, sub-score e conteggi.

    Raises:
        ValueError: Se articles è None.
    """
    if articles is None:
        raise ValueError("articles non può essere None")

    if len(articles) == 0:
        return EvidenceScoreResult(
            total_score=0,
            sub_scores={k: 0.0 for k in WEIGHTS},
            article_counts={"rct": 0, "meta": 0, "guidelines": 0},
            n_articles=0
        )

    # Calcola sub-score
    sub_rct        = score_rct(articles)
    sub_meta       = score_meta_analysis(articles)
    sub_guidelines = score_guidelines(articles, current_year)
    sub_concordance = score_concordance(articles)
    sub_volume     = score_volume(articles)

    sub_scores = {
        "rct":         sub_rct,
        "meta":        sub_meta,
        "guidelines":  sub_guidelines,
        "concordance": sub_concordance,
        "volume":      sub_volume,
    }

    # Media pesata
    weighted_sum = sum(WEIGHTS[k] * v for k, v in sub_scores.items())
    total_score = max(0, min(100, round(weighted_sum)))

    # Conteggi per il report
    article_counts = {
        "rct": _count_article_type(
            articles, ["randomized controlled trial", "rct", "clinical trial", "randomised"]
        ),
        "meta": _count_article_type(
            articles, ["meta-analysis", "meta analysis", "systematic review", "cochrane"]
        ),
        "guidelines": _count_article_type(
            articles, ["guideline", "practice guideline", "consensus"]
        ),
    }

    return EvidenceScoreResult(
        total_score=total_score,
        sub_scores=sub_scores,
        article_counts=article_counts,
        n_articles=len(articles)
    )


# ── Funzione di integrazione con il database ────────────────────────── #

def calculate_and_save_score(session, query_id: int) -> Optional[EvidenceScoreResult]:
    """
    Calcola l'Evidence Score per una query salvata nel DB e aggiorna la tabella scores.

    Args:
        session: SQLAlchemy session
        query_id: ID della query in database

    Returns:
        EvidenceScoreResult o None se la query non esiste.

    Usage in main_window.py:
        from analysis.evidence_scorer import calculate_and_save_score
        result = calculate_and_save_score(session, query_id)
        if result:
            center_panel.update_evidence_score(result.total_score)
    """
    try:
        from data.models import Query, Score

        query = session.query(Query).filter_by(id=query_id).first()
        if not query:
            return None

        # Carica solo gli articoli inclusi (non esclusi dall'utente)
        included_articles = [
            art for art in query.articles
            if getattr(art, "included", True) is not False
        ]

        result = calculate_evidence_score(included_articles)

        # Aggiorna o crea il record Score
        score_record = session.query(Score).filter_by(query_id=query_id).first()
        if score_record is None:
            score_record = Score(query_id=query_id)
            session.add(score_record)

        score_record.evidence_score = result.total_score
        session.commit()

        return result

    except Exception as e:
        import logging
        logging.getLogger("mirs.evidence_scorer").error(
            f"Errore nel calcolo score per query {query_id}: {e}"
        )
        return None


# ── Test standalone ─────────────────────────────────────────────────── #

if __name__ == "__main__":
    # Dataset di test minimale — simula articoli da PubMed
    test_articles = [
        {"article_types": "Randomized Controlled Trial", "pub_date": "2023"},
        {"article_types": "Randomized Controlled Trial", "pub_date": "2022"},
        {"article_types": "Randomized Controlled Trial", "pub_date": "2021"},
        {"article_types": "Meta-Analysis", "pub_date": "2023"},
        {"article_types": "Meta-Analysis", "pub_date": "2020"},
        {"article_types": "Systematic Review", "pub_date": "2022"},
        {"article_types": "Practice Guideline", "pub_date": "2022"},
        {"article_types": "Practice Guideline", "pub_date": "2019"},
        {"article_types": "Review", "pub_date": "2023"},
        {"article_types": "Journal Article", "pub_date": "2021"},
        {"article_types": "Journal Article", "pub_date": "2020"},
        {"article_types": "Journal Article", "pub_date": "2019"},
        {"article_types": "Case Reports", "pub_date": "2022"},
        {"article_types": "Journal Article", "pub_date": "2018"},
        {"article_types": "Clinical Trial", "pub_date": "2021"},
    ]

    result = calculate_evidence_score(test_articles, current_year=2025)

    print("=" * 50)
    print("EVIDENCE STRENGTH SCORE — Test Standalone")
    print("=" * 50)
    print(f"\nArticoli analizzati: {result.n_articles}")
    print(f"\nConteggi per tipo:")
    for k, v in result.article_counts.items():
        print(f"  {k:12s}: {v}")
    print(f"\nSub-score:")
    for k, v in result.sub_scores.items():
        weight = WEIGHTS[k]
        contribution = weight * v
        print(f"  {k:12s}: {v:5.1f}  (peso {weight:.0%} → contributo {contribution:.1f})")
    print(f"\n{'='*50}")
    print(f"EVIDENCE STRENGTH SCORE: {result.total_score}/100")
    print(f"Interpretazione: {result.summary_text()}")
    print("=" * 50)
