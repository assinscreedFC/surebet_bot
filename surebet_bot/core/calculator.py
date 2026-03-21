# Calculateur d'arbitrage (Surebet)

from dataclasses import dataclass
from typing import Optional


@dataclass
class ValueBet:
    """Un value bet détecté sur un outcome précis."""
    outcome_name: str
    bookmaker: str
    odds: float
    consensus_prob: float   # Probabilité consensuelle (moyenne fair)
    value_pct: float        # (odds × consensus_prob - 1) × 100
    bookmakers_count: int   # Nb bookmakers ayant participé au consensus


@dataclass
class SurebetResult:
    """Résultat d'un calcul d'arbitrage."""
    is_surebet: bool
    profit_pct: float  # Pourcentage de profit
    profit_base_100: float  # Gain si mise 100€ sur chaque outcome
    stakes: list[float]  # Mises optimales pour 100€ de gain garanti
    implied_probability: float  # Somme des probabilités implicites


def calculate_implied_probability(odds: list[float]) -> float:
    """
    Calcule la somme des probabilités implicites.
    
    Formule: L = Σ(1/cote_n)
    
    Si L < 1 → Surebet détecté!
    """
    if not odds or any(o <= 0 for o in odds):
        return float('inf')
    
    return sum(1/o for o in odds)


def calculate_arbitrage(odds: list[float], total_stake: float = 100.0) -> SurebetResult:
    """
    Calcule si un arbitrage est possible et le profit associé.
    
    Args:
        odds: Liste des cotes (ex: [1.85, 2.20] pour 2-way)
        total_stake: Mise totale (défaut: 100€)
    
    Returns:
        SurebetResult avec détails du calcul
    
    Raises:
        ValueError: Si les données d'entrée sont invalides
    """
    # Validation des entrées
    if not odds:
        raise ValueError("La liste des cotes ne peut pas être vide")
    
    if len(odds) < 2:
        raise ValueError("Au moins 2 cotes sont nécessaires pour un arbitrage")
    
    if any(o <= 1.0 for o in odds):
        invalid_odds = [o for o in odds if o <= 1.0]
        raise ValueError(
            f"Cotes invalides détectées: {invalid_odds}. "
            f"Les cotes doivent être > 1.0"
        )
    
    if total_stake <= 0:
        raise ValueError(
            f"La mise totale doit être positive, reçu: {total_stake}"
        )
    
    L = calculate_implied_probability(odds)
    
    is_surebet = L < 1.0
    
    if is_surebet:
        # Profit en pourcentage
        profit_pct = (1 - L) * 100
        
        # Mises optimales pour garantir le même gain sur chaque issue
        # stake_i = total_stake * (1/cote_i) / L
        stakes = [(total_stake * (1/o) / L) for o in odds]
        
        # Gain garanti
        # Gain = stake_i * cote_i - total_stake
        guaranteed_return = stakes[0] * odds[0]
        profit_base_100 = guaranteed_return - total_stake
        
    else:
        profit_pct = (1 - L) * 100  # Sera négatif
        stakes = [total_stake / len(odds)] * len(odds)  # Mises égales
        profit_base_100 = 0.0
    
    return SurebetResult(
        is_surebet=is_surebet,
        profit_pct=round(profit_pct, 2),
        profit_base_100=round(profit_base_100, 2),
        stakes=[round(s, 2) for s in stakes],
        implied_probability=round(L, 4)
    )


def calculate_two_way_arbitrage(odds1: float, odds2: float) -> SurebetResult:
    """
    Raccourci pour calculer un arbitrage 2-way.
    
    Ex: Over/Under, Home/Away
    """
    return calculate_arbitrage([odds1, odds2])


def calculate_three_way_arbitrage(odds1: float, odds2: float, odds3: float) -> SurebetResult:
    """
    Raccourci pour calculer un arbitrage 3-way.
    
    Ex: 1X2 (Home/Draw/Away)
    """
    return calculate_arbitrage([odds1, odds2, odds3])


def format_surebet_message(
    sport: str,
    league: str,
    match: str,
    market: str,
    outcomes: list[dict],  # [{"bookmaker": "...", "name": "...", "odds": ...}]
    result: SurebetResult
) -> str:
    """
    Formate un message d'alerte Surebet.
    
    Format VDO Group avec profit en % et base 100.
    """
    lines = [
        "🚀 OPPORTUNITÉ SUREBET DETECTÉE 🚀",
        "----------------------------------",
        f"🏆 Sport : {sport} - {league}",
        f"⚽ Match : {match}",
        f"📊 Marché : {market}",
        "",
    ]
    
    for i, outcome in enumerate(outcomes):
        stake = result.stakes[i] if i < len(result.stakes) else 0
        lines.append(
            f"✅ {outcome['bookmaker']} | {outcome['name']} | "
            f"Cote: {outcome['odds']:.2f} | Mise: {stake:.2f}€"
        )
    
    lines.extend([
        "",
        f"📈 Profit estimé : {result.profit_pct:.2f}%",
        f"💰 Gain base 100€ : {result.profit_base_100:.2f}€",
        f"🎯 Retour garanti : {100 + result.profit_base_100:.2f}€",
        "----------------------------------",
        "VDO Group"
    ])
    
    return "\n".join(lines)


def calculate_value_bets(
    outcome_name: str,
    bookmaker_odds: list[tuple[str, float]],
    all_outcomes_by_bookmaker: dict[str, list[float]],
    min_bookmakers: int = 4,
    min_threshold: float = 0.03
) -> list[ValueBet]:
    """
    Détecte les value bets pour un outcome donné.

    Algorithme :
    1. Pour chaque bookmaker (qui a coté TOUS les outcomes du marché),
       calculer fair_prob = (1/cote_outcome) / sum(1/cote_i for all outcomes)
    2. consensus_prob = moyenne des fair_probs
    3. value = (cote × consensus_prob) - 1
    4. Retourner si value > min_threshold

    Args:
        outcome_name: Ex "PSG", "Over 2.5"
        bookmaker_odds: [(bookmaker, cote)] pour CET outcome
        all_outcomes_by_bookmaker: {bookmaker: [cote_outcome1, cote_outcome2, ...]}
        min_bookmakers: Nb min pour consensus valide
        min_threshold: Value minimum (0.03 = 3%)
    """
    if not bookmaker_odds:
        raise ValueError("bookmaker_odds ne peut pas être vide")

    fair_probs = []
    for bookmaker, all_odds in all_outcomes_by_bookmaker.items():
        if not all_odds or any(o <= 1.0 for o in all_odds):
            continue
        total_implied = sum(1 / o for o in all_odds)
        if total_implied <= 0:
            continue
        bk_odds_for_outcome = next(
            (o for bk, o in bookmaker_odds if bk == bookmaker), None
        )
        if bk_odds_for_outcome is None:
            continue
        fair_probs.append((1 / bk_odds_for_outcome) / total_implied)

    if len(fair_probs) < min_bookmakers:
        return []

    consensus_prob = sum(fair_probs) / len(fair_probs)
    bookmakers_count = len(fair_probs)

    results = []
    for bookmaker, odds in bookmaker_odds:
        raw_value = (odds * consensus_prob) - 1
        if raw_value >= min_threshold:
            results.append(ValueBet(
                outcome_name=outcome_name,
                bookmaker=bookmaker,
                odds=round(odds, 2),
                consensus_prob=round(consensus_prob, 4),
                value_pct=round(raw_value * 100, 2),
                bookmakers_count=bookmakers_count
            ))

    return sorted(results, key=lambda x: x.value_pct, reverse=True)


# === TESTS ===
if __name__ == "__main__":
    # Test surebet
    result = calculate_two_way_arbitrage(1.85, 2.20)
    print(f"Odds: 1.85 / 2.20")
    print(f"Surebet: {result.is_surebet}")
    print(f"Profit: {result.profit_pct}%")
    print(f"Gain base 100€: {result.profit_base_100}€")
    print(f"Mises optimales: {result.stakes}")
    print()
    
    # Test non-surebet
    result2 = calculate_two_way_arbitrage(1.50, 2.20)
    print(f"Odds: 1.50 / 2.20")
    print(f"Surebet: {result2.is_surebet}")
    print(f"Profit: {result2.profit_pct}%")
