from dataclasses import dataclass, field
from typing import List, Dict, Optional
import pandas as pd
import random
import math
import wcwidth


# ─────────────────────────────────────────────────────────────
#  ANSI color palette  (gracefully degrades in plain terminals)
# ─────────────────────────────────────────────────────────────
class C:
    RESET = "\033[0m"
    BOLD = "\033[1m"
    DIM = "\033[2m"

    # Elo tier colours
    GOLD = "\033[38;5;220m"
    SILVER = "\033[38;5;250m"
    BRONZE = "\033[38;5;172m"
    BLUE = "\033[38;5;75m"
    GREEN = "\033[38;5;120m"
    RED = "\033[38;5;203m"
    CYAN = "\033[38;5;87m"
    PURPLE = "\033[38;5;183m"
    GREY = "\033[38;5;240m"
    WHITE = "\033[38;5;255m"
    YELLOW = "\033[38;5;228m"


def elo_color(elo: float) -> str:
    """Map an Elo rating to a colour tier."""
    if elo >= 1800:
        return C.GOLD
    if elo >= 1650:
        return C.SILVER
    if elo >= 1550:
        return C.CYAN
    if elo >= 1450:
        return C.GREEN
    if elo >= 1350:
        return C.YELLOW
    if elo >= 1200:
        return C.BRONZE
    return C.RED


def elo_bar(elo: float, width: int = 20) -> str:
    """Render a compact ASCII progress-bar for an Elo rating (range 800–2200)."""
    lo, hi = 800, 2200
    fraction = max(0.0, min(1.0, (elo - lo) / (hi - lo)))
    filled = round(fraction * width)
    bar = "█" * filled + "░" * (width - filled)
    col = elo_color(elo)
    return f"{col}{bar}{C.RESET}"


def delta_str(delta: float, width: int = 7) -> str:
    """
    Format an Elo delta with exactly one sign character and a colour.
    The numeric portion is padded to `width` characters BEFORE the ANSI
    colour codes are added, so the string always occupies the same number
    of visible terminal columns regardless of the sign or magnitude.
    `width` = 7 covers the widest case: '-999.9' (6 chars) + 1 spare.
    """
    sign = "+" if delta >= 0 else "-"
    num = f"{abs(delta):.1f}"  # e.g. '12.3' or '123.4'
    raw = f"{sign}{num}"  # e.g. '+12.3' or '-123.4'
    padded = raw.rjust(width)  # fixed visual width, no ANSI yet
    col = C.GREEN if delta >= 0 else C.RED
    return f"{col}{padded}{C.RESET}"


# ─────────────────────────────────────────────────────────────
#  ASCII Bracket Configuration
# ─────────────────────────────────────────────────────────────
NAME_W = 6
COL_GAP = 8
ROUND_W = NAME_W + COL_GAP  # 14
LINE_W = ROUND_W - 1  # 13


def trim_visual_width(name: str, max_width: int = 6) -> str:
    current_width, result = 0, []
    for char in name:
        char_width = max(0, wcwidth.wcwidth(char))
        if current_width + char_width > max_width:
            break
        result.append(char)
        current_width += char_width
    return "".join(result)


def visual_width(text: str) -> int:
    """Return the true terminal column-width of a string (handles CJK wide chars)."""
    return sum(max(0, wcwidth.wcwidth(ch)) for ch in text)


def visual_ljust(text: str, width: int) -> str:
    """
    Left-justify `text` within `width` terminal columns.
    Pads with spaces based on the visual width of each character,
    so CJK double-width chars align correctly with ASCII.
    """
    used = visual_width(text)
    pad = max(0, width - used)
    return text + " " * pad


def make_grid(height, width):
    return [[" "] * width for _ in range(height)]


def write(grid, row, col, text):
    for i, ch in enumerate(text):
        if 0 <= row < len(grid) and col + i < len(grid[row]):
            grid[row][col + i] = ch


def center_pad(name, w):
    """
    Trim `name` to NAME_W terminal columns, then centre it within `w` columns.
    Uses visual_width so CJK double-wide characters are counted correctly.
    """
    trimmed = trim_visual_width(name, NAME_W)
    used = visual_width(trimmed)
    total_pad = max(0, w - used)
    left_pad = total_pad // 2
    right_pad = total_pad - left_pad
    return " " * left_pad + trimmed + " " * right_pad


def render(grid):
    return "\n".join("".join(row).rstrip() for row in grid)


def draw_match(
    grid, row_top, row_bot, col_in, col_out, top_name, bot_name, winner_name
):
    row_mid = (row_top + row_bot) // 2
    write(grid, row_top - 1, col_in, center_pad(top_name, LINE_W))
    write(grid, row_bot - 1, col_in, center_pad(bot_name, LINE_W))
    for c in range(col_in, col_out - 1):
        grid[row_top][c] = "-"
        grid[row_bot][c] = "-"
    for r in range(row_top, row_bot + 1):
        grid[r][col_out - 1] = "|"
    grid[row_top][col_out - 1] = "+"
    grid[row_bot][col_out - 1] = "+"
    grid[row_mid][col_out - 1] = "+"
    for c in range(col_out, col_out + LINE_W):
        if c < len(grid[0]):
            grid[row_mid][c] = "-"
    write(grid, row_mid - 1, col_out, center_pad(winner_name, LINE_W))


def get_visual_match_numbers(round_num, total_rounds):
    order = [1]
    for r in range(total_rounds, round_num, -1):
        next_order = []
        L = 2 ** (total_rounds - r + 1)
        for x in order:
            if x % 2 == 1:
                next_order.extend([x, L - x + 1])
            else:
                next_order.extend([L - x + 1, x])
        order = next_order
    return order


# ─────────────────────────────────────────────────────────────
#  Elo Engine
# ─────────────────────────────────────────────────────────────
def expected_score(rating_a: float, rating_b: float) -> float:
    """Classic Elo expected score for player A against player B."""
    return 1.0 / (1.0 + 10 ** ((rating_b - rating_a) / 400.0))


def dynamic_k(total_matches: int) -> float:
    """
    K-factor that decays as a player accumulates experience.
    High early on (ratings should move fast with little data),
    stabilising once a player has a meaningful sample.
    """
    if total_matches < 30:
        return 40.0  # provisional — learning fast
    if total_matches < 100:
        return 24.0  # established
    return 16.0  # veteran — stable


# ─────────────────────────────────────────────────────────────
#  Player Registry  (persists across tournaments)
# ─────────────────────────────────────────────────────────────
@dataclass
class RegistryEntry:
    """Everything we know about a player across their entire career."""

    player_id: str
    name: str
    elo: float = 1500.0
    total_matches: int = 0  # career match count (drives K-factor)
    career_wins: int = 0
    career_losses: int = 0
    tournaments: int = 0  # number of tournaments entered
    peak_elo: float = 1500.0
    elo_history: List[float] = field(default_factory=lambda: [1500.0])

    # ── Elo update ──────────────────────────────────────────
    def update_elo(self, opponent_elo: float, won: bool) -> float:
        """
        Apply one Elo update.  Returns the signed rating delta so the
        caller can display it.
        """
        exp = expected_score(self.elo, opponent_elo)
        k = dynamic_k(self.total_matches)
        score = 1.0 if won else 0.0
        delta = k * (score - exp)
        self.elo += delta
        self.total_matches += 1
        if won:
            self.career_wins += 1
        else:
            self.career_losses += 1
        if self.elo > self.peak_elo:
            self.peak_elo = self.elo
        self.elo_history.append(round(self.elo, 1))
        return delta

    @property
    def win_rate(self) -> float:
        total = self.career_wins + self.career_losses
        return self.career_wins / total if total else 0.0

    @property
    def career_record(self) -> str:
        return f"{self.career_wins}W – {self.career_losses}L"


class PlayerRegistry:
    """
    Long-lived store of player Elo ratings.
    Pass this between tournament instances to accumulate history.
    """

    def __init__(self):
        self._entries: Dict[str, RegistryEntry] = {}

    def register(self, player_id: str, name: str) -> RegistryEntry:
        if player_id not in self._entries:
            self._entries[player_id] = RegistryEntry(player_id=player_id, name=name)
        entry = self._entries[player_id]
        entry.tournaments += 1
        return entry

    def get(self, player_id: str) -> Optional[RegistryEntry]:
        return self._entries.get(player_id)

    def play_match(self, id_a: str, id_b: str, a_won: bool):
        """
        Record a real or simulated match result, updating both players' Elo.
        Returns (delta_a, delta_b) for display purposes.
        """
        a = self._entries[id_a]
        b = self._entries[id_b]
        delta_a = a.update_elo(b.elo, won=a_won)
        delta_b = b.update_elo(a.elo, won=not a_won)
        return delta_a, delta_b

    def simulate_match(self, id_a: str, id_b: str):
        """
        Simulate a match outcome whose probability is derived from Elo ratings.
        Higher-rated players win more often — but upsets absolutely happen.
        Returns the winner's id.
        """
        a = self._entries[id_a]
        b = self._entries[id_b]
        exp = expected_score(a.elo, b.elo)
        a_won = random.random() < exp
        self.play_match(id_a, id_b, a_won)
        return id_a if a_won else id_b

    def leaderboard(self, top_n: int = 20) -> List[RegistryEntry]:
        entries = sorted(self._entries.values(), key=lambda e: e.elo, reverse=True)
        return entries[:top_n]

    def print_leaderboard(self, top_n: int = 20, title: str = "GLOBAL LEADERBOARD"):
        entries = self.leaderboard(top_n)
        width = 72

        print()
        print(f"{C.BOLD}{C.WHITE}{'─'*width}{C.RESET}")
        print(f"{C.BOLD}{C.GOLD}  {'⬡ ' + title:^{width-2}}{C.RESET}")
        print(f"{C.BOLD}{C.WHITE}{'─'*width}{C.RESET}")
        header = (
            f"  {'#':>3}  {'Name':<18}  {'Elo':>6}  "
            f"{'Rating bar':<22}  {'Record':<14}  {'WR':>5}"
        )
        print(f"{C.DIM}{header}{C.RESET}")
        print(f"{C.GREY}  {'─'*67}{C.RESET}")

        for rank, e in enumerate(entries, 1):
            col = elo_color(e.elo)
            bar = elo_bar(e.elo, width=20)
            name = visual_ljust(e.name[:18], 18)
            record = f"{e.career_wins}W/{e.career_losses}L"
            wr = f"{e.win_rate:.0%}"
            print(
                f"  {rank:>3}  {col}{name}{C.RESET}  "
                f"{col}{e.elo:>6.1f}{C.RESET}  "
                f"{bar}  "
                f"{C.DIM}{record:<14}{C.RESET}  "
                f"{C.DIM}{wr:>5}{C.RESET}"
            )

        print(f"{C.GREY}{'─'*width}{C.RESET}")
        print()


# ─────────────────────────────────────────────────────────────
#  Swiss rounds core logic
# ─────────────────────────────────────────────────────────────
def get_rounds(num_players):
    if num_players < 4:
        raise ValueError("Tournament requires at least 4 players")
    brackets = [
        (8, 3, 3, None, None),
        (16, 4, 4, None, 2),
        (32, 6, 6, None, 4),
        (64, 7, 7, None, 6),
        (128, 9, 7, 13, 8),
        (256, 10, 8, 16, 8),
        (512, 11, 8, 16, 8),
        (1024, 12, 8, 16, 8),
        (2048, 13, 8, 16, 8),
        (4096, 14, 8, 16, 8),
        (8192, 15, 9, 19, 8),
    ]
    for max_players, rounds, phase1, point_thresh, top_cut in brackets:
        if num_players <= max_players:
            return rounds, phase1, point_thresh, top_cut
    return ValueError("Too many players!")


@dataclass
class Match:
    opponent_id: str
    won: bool
    round_number: int
    is_bye: bool = False

    def __str__(self):
        if self.is_bye:
            return f"R{self.round_number}: BYE"
        result = "W" if self.won else "L"
        return f"R{self.round_number} vs {self.opponent_id}: {result}"


@dataclass
class Player:
    player_id: str
    name: str
    matches: List[Match] = field(default_factory=list)
    tournament: Optional["Tournament"] = field(default=None, repr=False)
    dropped: bool = False

    def add_match(self, opponent_id, won, round_number, is_bye=False):
        self.matches.append(Match(opponent_id, won, round_number, is_bye))

    def add_bye(self, round_number):
        self.matches.append(Match("BYE", True, round_number, is_bye=True))

    @property
    def wins(self):
        return sum(1 for m in self.matches if m.won)

    @property
    def losses(self):
        return sum(1 for m in self.matches if not m.won and not m.is_bye)

    @property
    def win_percentage(self):
        total = len(self.matches)
        return self.wins / total if total else 0.0

    @property
    def match_points(self):
        return self.wins * 3

    @property
    def opp_percentage(self):
        if not self.matches or not self.tournament:
            return 0.0
        rates = []
        for oid in self.get_opponents():
            wr = self.tournament.players[oid].win_percentage
            rates.append(max(0.25, wr))
        return sum(rates) / len(rates) if rates else 0.0

    @property
    def opp_opp_percentage(self):
        if not self.matches or not self.tournament:
            return 0.0
        rates = []
        for oid in self.get_opponents():
            opp = self.tournament.players[oid]
            for ooid in opp.get_opponents():
                wr = self.tournament.players[ooid].win_percentage
                rates.append(max(0.25, wr))
        return sum(rates) / len(rates) if rates else 0.0

    def has_played(self, opponent_id):
        return any(m.opponent_id == opponent_id for m in self.matches)

    def get_opponents(self):
        return [m.opponent_id for m in self.matches if not m.is_bye]

    def get_non_bye_matches(self):
        return [m for m in self.matches if not m.is_bye]


class Tournament:
    def __init__(self, registry: PlayerRegistry, name: str = "Tournament"):
        self.players: Dict[str, Player] = {}
        self.current_round = 0
        self.bye_history: set = set()
        self.registry = registry
        self.name = name
        # track Elo snapshots for each match, keyed by round
        self.round_deltas: Dict[int, List[dict]] = {}

    # ── Player management ───────────────────────────────────
    def add_player(self, player_id: str, name: str):
        player = Player(player_id, name)
        player.tournament = self
        self.players[player_id] = player
        self.registry.register(player_id, name)

    def add_players(self, names: List[str]) -> List[str]:
        ids = []
        for name in names:
            pid = name
            self.add_player(pid, name)
            ids.append(pid)
        return ids

    # ── Round management ────────────────────────────────────
    def start_new_round(self) -> int:
        self.current_round += 1
        self.round_deltas[self.current_round] = []
        return self.current_round

    def record_match(self, p1_id, p2_id, p1_won, round_number):
        """Record match result in Swiss system AND update Elo registry."""
        self.players[p1_id].add_match(p2_id, p1_won, round_number)
        self.players[p2_id].add_match(p1_id, not p1_won, round_number)

        p1_elo_before = self.registry.get(p1_id).elo
        p2_elo_before = self.registry.get(p2_id).elo
        delta_a, delta_b = self.registry.play_match(p1_id, p2_id, p1_won)

        self.round_deltas[round_number].append(
            {
                "p1": p1_id,
                "p2": p2_id,
                "p1_won": p1_won,
                "p1_before": p1_elo_before,
                "p2_before": p2_elo_before,
                "delta_a": delta_a,
                "delta_b": delta_b,
            }
        )

    def simulate_round_match(self, p1_id, p2_id, round_number):
        """
        Simulate a match result using Elo win probability, then record it.
        Returns the winner's id.
        """
        a_entry = self.registry.get(p1_id)
        b_entry = self.registry.get(p2_id)
        exp = expected_score(a_entry.elo, b_entry.elo)
        p1_won = random.random() < exp
        self.record_match(p1_id, p2_id, p1_won, round_number)
        return p1_id if p1_won else p2_id

    def record_bye(self, player_id, round_number):
        self.players[player_id].add_bye(round_number)
        self.bye_history.add(player_id)

    # ── Pairings ────────────────────────────────────────────
    def generate_pairings(self, round_number, phase1_rounds, minimum_match_points):
        pairings = []
        unpaired = {pid for pid in self.players if not self.players[pid].dropped}

        if round_number > phase1_rounds and minimum_match_points is not None:
            eliminated = {
                p
                for p in unpaired
                if self.get_player_stats(p)["match_points"] < minimum_match_points
            }
            unpaired -= eliminated

        if round_number == 1:
            pool = list(unpaired)
            random.shuffle(pool)
            if len(pool) % 2 == 1:
                bye_player = random.choice(pool)
                self.record_bye(bye_player, round_number)
                pool.remove(bye_player)
                unpaired.discard(bye_player)
            for i in range(0, len(pool), 2):
                p1, p2 = pool[i], pool[i + 1]
                pairings.append((p1, p2))
                unpaired.discard(p1)
                unpaired.discard(p2)
            return pairings

        record_groups: Dict[int, List[str]] = {}
        for pid in list(unpaired):
            wins = self.players[pid].wins
            record_groups.setdefault(wins, []).append(pid)

        if not record_groups:
            return pairings

        for grp in record_groups.values():
            random.shuffle(grp)

        sorted_records = sorted(record_groups.keys(), reverse=True)
        total_active = sum(len(record_groups[r]) for r in sorted_records)

        if total_active % 2 == 1:
            lowest = sorted_records[-1]
            candidates = record_groups[lowest]
            bye_player = random.choice(candidates)
            self.record_bye(bye_player, round_number)
            candidates.remove(bye_player)
            unpaired.discard(bye_player)

        carry_down: Optional[str] = None

        for record in sorted_records:
            group = record_groups.get(record, [])
            if not group:
                continue

            if carry_down:
                found_idx = next(
                    (
                        i
                        for i, opp in enumerate(group)
                        if self.can_pair(carry_down, opp)
                    ),
                    None,
                )
                if found_idx is not None:
                    opp = group.pop(found_idx)
                    pairings.append((carry_down, opp))
                    unpaired.discard(carry_down)
                    unpaired.discard(opp)
                    carry_down = None

            while len(group) >= 2:
                p1 = group.pop(0)
                partner_idx = next(
                    (j for j, cand in enumerate(group) if self.can_pair(p1, cand)), None
                )
                p2 = group.pop(partner_idx if partner_idx is not None else 0)
                pairings.append((p1, p2))
                unpaired.discard(p1)
                unpaired.discard(p2)

            if len(group) == 1:
                last = group.pop()
                if carry_down is None:
                    carry_down = last
                else:
                    pairings.append((carry_down, last))
                    unpaired.discard(carry_down)
                    unpaired.discard(last)
                    carry_down = None

        if carry_down:
            remaining = [pid for pid in unpaired if pid != carry_down]
            if remaining:
                opp = remaining[0]
                pairings.append((carry_down, opp))
                unpaired.discard(carry_down)
                unpaired.discard(opp)
            else:
                self.record_bye(carry_down, round_number)
                unpaired.discard(carry_down)

        return pairings

    def can_pair(self, p1_id, p2_id) -> bool:
        if p1_id == p2_id:
            return False
        return not self.players[p1_id].has_played(p2_id)

    # ── Stats / Standings ───────────────────────────────────
    def get_player_stats(self, player_id: str) -> Dict:
        player = self.players[player_id]
        return {
            "name": player.name,
            "wins": player.wins,
            "losses": player.losses,
            "win_percentage": player.win_percentage,
            "match_points": player.match_points,
            "opponents": player.get_opponents(),
            "matches_played": len(player.matches),
        }

    def get_standings_df(self) -> pd.DataFrame:
        data = []
        for pid, player in self.players.items():
            if player.dropped:
                continue
            entry = self.registry.get(pid)
            data.append(
                {
                    "player_id": pid,
                    "name": player.name,
                    "wins": player.wins,
                    "losses": player.losses,
                    "match_points": player.match_points,
                    "opp_win_percentage": player.opp_percentage,
                    "opp_opp_win_percentage": player.opp_opp_percentage,
                    "win_percentage": player.win_percentage,
                    "matches_played": len(player.matches),
                    "elo": entry.elo if entry else 1500.0,
                }
            )
        df = pd.DataFrame(data)
        return df.sort_values(
            ["match_points", "opp_win_percentage", "opp_opp_win_percentage"],
            ascending=[False, False, False],
        ).reset_index(drop=True)

    # ── Pretty printing ──────────────────────────────────────
    def print_round_header(self, round_number: int, total_rounds: int):
        width = 72
        print()
        print(f"{C.BOLD}{C.WHITE}{'━'*width}{C.RESET}")
        phase = "PHASE I" if round_number <= 7 else "PHASE II"
        print(
            f"{C.BOLD}{C.CYAN}  ROUND {round_number} / {total_rounds}"
            f"  {C.DIM}│{C.RESET}{C.CYAN}  {phase}{C.RESET}"
        )
        print(f"{C.BOLD}{C.WHITE}{'━'*width}{C.RESET}")

    def print_round_results(self, round_number: int):
        deltas = self.round_deltas.get(round_number, [])
        if not deltas:
            return
        print(f"\n{C.DIM}  {'MATCH RESULTS':^50}{'ELO SHIFT':>18}{C.RESET}")
        print(f"{C.GREY}  {'─'*67}{C.RESET}")
        for d in deltas:
            p1n = self.players[d["p1"]].name
            p2n = self.players[d["p2"]].name
            win = p1n if d["p1_won"] else p2n
            lose = p2n if d["p1_won"] else p1n
            d1 = d["delta_a"] if d["p1_won"] else d["delta_b"]
            d2 = d["delta_b"] if d["p1_won"] else d["delta_a"]
            e1 = self.registry.get(d["p1"]).elo
            e2 = self.registry.get(d["p2"]).elo
            win_col = visual_ljust(win, 14)
            lose_col = visual_ljust(lose, 14)
            print(
                f"  {C.GREEN}{win_col}{C.RESET}"
                f"{C.DIM}def.{C.RESET}"
                f"  {C.RED}{lose_col}{C.RESET}"
                f"  {delta_str(d1)}  {C.DIM}{e1:>6.0f}{C.RESET}"
                f"  {delta_str(d2)}  {C.DIM}{e2:>6.0f}{C.RESET}"
            )

    def print_standings(self, top_cut, long_line=72, short_line=70):
        standings = self.get_standings_df()
        width = 72

        print()
        print(f"{C.BOLD}{C.WHITE}{'─'*width}{C.RESET}")
        print(f"{C.BOLD}{C.PURPLE}  {'STANDINGS':^{width-2}}{C.RESET}")
        print(f"{C.BOLD}{C.WHITE}{'─'*width}{C.RESET}")
        header = (
            f"  {'#':>3}  {'Name':<16}  {'Record':^7}  "
            f"{'Pts':>3}  {'Elo':>6}  {'Rating bar':<22}  OWP"
        )
        print(f"{C.DIM}{header}{C.RESET}")
        print(f"{C.GREY}  {'─'*67}{C.RESET}")

        for i, row in standings.iterrows():
            if i == top_cut:
                print(f"{C.GREY}  {'╌'*67}  ← top-cut line{C.RESET}")

            pid = row["player_id"]
            entry = self.registry.get(pid)
            elo = entry.elo if entry else 1500.0
            col = elo_color(elo)
            record = f"{int(row['wins'])}–{int(row['losses'])}"
            bar = elo_bar(elo, 18)
            rank = i + 1
            name = visual_ljust(row["name"][:16], 16)

            print(
                f"  {rank:>3}  {col}{name}{C.RESET}"
                f"  {C.DIM}{record:^7}{C.RESET}"
                f"  {C.BOLD}{int(row['match_points']):>3}{C.RESET}"
                f"  {col}{elo:>6.1f}{C.RESET}"
                f"  {bar}"
                f"  {C.DIM}{row['opp_win_percentage']:.0%}{C.RESET}"
            )

        print(f"{C.GREY}{'─'*width}{C.RESET}")
        print()


# ─────────────────────────────────────────────────────────────
#  Single-Elimination Bracket
# ─────────────────────────────────────────────────────────────
@dataclass
class BracketMatch:
    round_number: int
    match_number: int
    player1_id: Optional[str]
    player2_id: Optional[str]
    winner_id: Optional[str] = None
    is_bye: bool = False

    def __str__(self):
        p1 = self.player1_id or "TBD"
        p2 = self.player2_id or "TBD"
        if self.is_bye:
            return f"R{self.round_number} M{self.match_number}: {p1} (BYE)"
        result = f" → {self.winner_id}" if self.winner_id else ""
        return f"R{self.round_number} M{self.match_number}: {p1} vs {p2}{result}"


class SingleEliminationBracket:
    def __init__(
        self,
        seeded_player_ids: List[str],
        tournament: Tournament,
        registry: PlayerRegistry,
    ):
        self.tournament = tournament
        self.registry = registry
        self.size = len(seeded_player_ids)
        if self.size < 2:
            raise ValueError("Need at least 2 players for a bracket.")

        self.seeds: Dict[int, str] = {
            i + 1: pid for i, pid in enumerate(seeded_player_ids)
        }
        self.bracket_size = 2 ** math.ceil(math.log2(self.size))
        self.num_byes = self.bracket_size - self.size
        self.rounds: Dict[int, List[BracketMatch]] = {}
        self.num_rounds = int(math.log2(self.bracket_size))
        self.current_round = 1
        self._build_first_round()

    def _build_first_round(self):
        first_round_matches: List[BracketMatch] = []
        match_num = 1
        for seed in range(1, self.num_byes + 1):
            m = BracketMatch(
                1, match_num, self.seeds[seed], None, self.seeds[seed], is_bye=True
            )
            first_round_matches.append(m)
            match_num += 1
        playing_seeds = list(range(self.num_byes + 1, self.size + 1))
        lo, hi = 0, len(playing_seeds) - 1
        while lo < hi:
            m = BracketMatch(
                1,
                match_num,
                self.seeds[playing_seeds[lo]],
                self.seeds[playing_seeds[hi]],
            )
            first_round_matches.append(m)
            match_num += 1
            lo += 1
            hi -= 1
        self.rounds[1] = first_round_matches
        self._try_advance_round()

    def _all_round_complete(self, round_number):
        return all(m.winner_id is not None for m in self.rounds.get(round_number, []))

    def _try_advance_round(self):
        while self._all_round_complete(self.current_round):
            next_round = self.current_round + 1
            if next_round > self.num_rounds:
                break
            winners = [m.winner_id for m in self.rounds[self.current_round]]
            next_matches: List[BracketMatch] = []
            lo, hi = 0, len(winners) - 1
            match_num = 1
            while lo < hi:
                m = BracketMatch(next_round, match_num, winners[lo], winners[hi])
                next_matches.append(m)
                match_num += 1
                lo += 1
                hi -= 1
            self.rounds[next_round] = next_matches
            self.current_round = next_round

    def get_current_matches(self) -> List[BracketMatch]:
        return [
            m
            for m in self.rounds.get(self.current_round, [])
            if not m.is_bye and m.winner_id is None
        ]

    def record_result(self, round_number, match_number, winner_id):
        matches = self.rounds.get(round_number)
        if matches is None:
            raise ValueError(f"Round {round_number} does not exist.")
        target = next((m for m in matches if m.match_number == match_number), None)
        if target is None:
            raise ValueError(f"Match {match_number} not found in round {round_number}.")
        if winner_id not in (target.player1_id, target.player2_id):
            raise ValueError(f"{winner_id} is not a participant in this match.")
        # Elo update for the bracket match
        loser_id = (
            target.player2_id if winner_id == target.player1_id else target.player1_id
        )
        self.registry.play_match(winner_id, loser_id, a_won=True)
        target.winner_id = winner_id
        self._try_advance_round()

    def simulate_match(self, round_number, match_number):
        """Simulate a bracket match using Elo win probability."""
        matches = self.rounds.get(round_number)
        target = next((m for m in matches if m.match_number == match_number), None)
        p1, p2 = target.player1_id, target.player2_id
        winner = self.registry.simulate_match(p1, p2)
        target.winner_id = winner
        self._try_advance_round()
        return winner

    def get_champion(self) -> Optional[str]:
        final = self.rounds.get(self.num_rounds)
        if final and len(final) == 1 and final[0].winner_id:
            return final[0].winner_id
        return None

    def print_bracket(self):
        print(f"\n{C.BOLD}{C.WHITE}{'='*55}{C.RESET}")
        print(
            f"{C.BOLD}{C.GOLD}  Single Elimination Bracket  ({self.size} players){C.RESET}"
        )
        print(
            f"{C.DIM}  Bracket size: {self.bracket_size}  |  Byes: {self.num_byes}{C.RESET}"
        )
        print(f"{C.BOLD}{C.WHITE}{'='*55}{C.RESET}\n")

        if self.num_rounds == 0:
            print("No matches to display.")
            return

        HEIGHT = 2 * self.bracket_size + 5
        WIDTH = ROUND_W * (self.num_rounds + 1) + 5
        grid = make_grid(HEIGHT, WIDTH)

        for i in range(self.num_rounds + 1):
            if i == self.num_rounds:
                header = "Champion"
            elif i == self.num_rounds - 1:
                header = "Finals"
            elif i == self.num_rounds - 2:
                header = "Semifinals"
            elif i == self.num_rounds - 3:
                header = "Quarters"
            else:
                header = f"Round {i+1}"
            write(grid, 0, i * ROUND_W, center_pad(header, LINE_W))

        for r in range(self.num_rounds):
            col_in = r * ROUND_W
            col_out = (r + 1) * ROUND_W
            start_row = 3 + (2**r) - 1
            diff = 2 ** (r + 1)
            step = 2 ** (r + 2)
            swiss_round_num = r + 1
            visual_match_nums = get_visual_match_numbers(
                swiss_round_num, self.num_rounds
            )

            for m_visual_idx, match_num in enumerate(visual_match_nums):
                match = next(
                    (
                        m
                        for m in self.rounds.get(swiss_round_num, [])
                        if m.match_number == match_num
                    ),
                    None,
                )
                row_top = start_row + m_visual_idx * step
                row_bot = row_top + diff
                p1_name = p2_name = winner_name = ""

                if match:
                    if swiss_round_num == 1:
                        p1_name = (
                            self.tournament.players[match.player1_id].name
                            if match.player1_id
                            else ""
                        )
                        if match.is_bye:
                            p2_name = "(BYE)"
                            winner_name = p1_name
                        else:
                            p2_name = (
                                self.tournament.players[match.player2_id].name
                                if match.player2_id
                                else ""
                            )
                            winner_name = (
                                self.tournament.players[match.winner_id].name
                                if match.winner_id
                                else ""
                            )
                    else:
                        prev_rn = swiss_round_num - 1
                        prev_visuals = get_visual_match_numbers(
                            prev_rn, self.num_rounds
                        )
                        top_match = next(
                            (
                                m
                                for m in self.rounds.get(prev_rn, [])
                                if m.match_number == prev_visuals[m_visual_idx * 2]
                            ),
                            None,
                        )
                        bot_match = next(
                            (
                                m
                                for m in self.rounds.get(prev_rn, [])
                                if m.match_number == prev_visuals[m_visual_idx * 2 + 1]
                            ),
                            None,
                        )
                        top_id = top_match.winner_id if top_match else None
                        bot_id = bot_match.winner_id if bot_match else None
                        p1_name = self.tournament.players[top_id].name if top_id else ""
                        p2_name = self.tournament.players[bot_id].name if bot_id else ""
                        winner_name = (
                            self.tournament.players[match.winner_id].name
                            if match.winner_id
                            else ""
                        )

                draw_match(
                    grid,
                    row_top,
                    row_bot,
                    col_in,
                    col_out,
                    p1_name,
                    p2_name,
                    winner_name,
                )

        print(render(grid))
        champion = self.get_champion()
        if champion:
            champ_name = self.tournament.players[champion].name
            champ_elo = self.registry.get(champion).elo
            col = elo_color(champ_elo)
            print(
                f"\n  {C.GOLD}CHAMPION:{C.RESET} "
                f"{C.BOLD}{col}{champ_name}{C.RESET}  "
                f"{C.DIM}(Elo {champ_elo:.0f}){C.RESET}"
            )
        print(f"{C.BOLD}{C.WHITE}{'='*55}{C.RESET}\n")


# ─────────────────────────────────────────────────────────────
#  Elo insight printer  (the Veritasium moment)
# ─────────────────────────────────────────────────────────────
def print_elo_insights(registry: PlayerRegistry, tournament: Tournament):
    """
    Print a concise, beautiful summary of what the Elo system
    learned from this tournament.
    """
    width = 72
    entries = sorted(registry._entries.values(), key=lambda e: e.elo, reverse=True)

    print()
    print(f"{C.BOLD}{C.WHITE}{'━'*width}{C.RESET}")
    print(
        f"{C.BOLD}{C.CYAN}  ELO INSIGHTS  {C.DIM}— what the ratings learned this tournament{C.RESET}"
    )
    print(f"{C.BOLD}{C.WHITE}{'━'*width}{C.RESET}")

    # Biggest movers
    standings = tournament.get_standings_df()
    movers = []
    for _, row in standings.iterrows():
        pid = row["player_id"]
        entry = registry.get(pid)
        if entry and len(entry.elo_history) >= 2:
            delta = entry.elo - entry.elo_history[0]
            movers.append((entry, delta))

    movers.sort(key=lambda x: abs(x[1]), reverse=True)

    print(f"\n{C.DIM}  BIGGEST MOVERS{C.RESET}")
    print(f"{C.GREY}  {'─'*50}{C.RESET}")
    for entry, delta in movers[:5]:
        bar = elo_bar(entry.elo, 14)
        name = visual_ljust(entry.name[:18], 18)
        print(
            f"  {elo_color(entry.elo)}{name}{C.RESET}"
            f"  {entry.elo_history[0]:>6.0f} → {entry.elo:>6.0f}"
            f"  {delta_str(delta)}  {bar}"
        )

    # Biggest upset of the tournament
    biggest_upset = None
    biggest_gap = 0.0
    for rn, deltas in tournament.round_deltas.items():
        for d in deltas:
            gap = abs(d["p1_before"] - d["p2_before"])
            loser_was_fav = (d["p1_before"] > d["p2_before"] and not d["p1_won"]) or (
                d["p2_before"] > d["p1_before"] and d["p1_won"]
            )
            if loser_was_fav and gap > biggest_gap:
                biggest_gap = gap
                biggest_upset = d

    if biggest_upset:
        p1n = tournament.players[biggest_upset["p1"]].name
        p2n = tournament.players[biggest_upset["p2"]].name
        winner_name = p1n if biggest_upset["p1_won"] else p2n
        loser_name = p2n if biggest_upset["p1_won"] else p1n
        w_elo = (
            biggest_upset["p1_before"]
            if biggest_upset["p1_won"]
            else biggest_upset["p2_before"]
        )
        l_elo = (
            biggest_upset["p2_before"]
            if biggest_upset["p1_won"]
            else biggest_upset["p1_before"]
        )
        exp = expected_score(w_elo, l_elo)
        print(f"\n{C.DIM}  BIGGEST UPSET{C.RESET}")
        print(f"{C.GREY}  {'─'*50}{C.RESET}")
        print(
            f"  {C.GREEN}{winner_name}{C.RESET} ({w_elo:.0f})"
            f"  def.  "
            f"{C.RED}{loser_name}{C.RESET} ({l_elo:.0f})"
        )
        print(
            f"  {C.DIM}Expected win probability for {winner_name}: "
            f"{C.RESET}{C.YELLOW}{exp:.1%}{C.RESET}"
        )
        print(f"  {C.DIM}Elo gap: {C.RESET}{C.YELLOW}{biggest_gap:.0f} points{C.RESET}")

    # Distribution
    bins = {
        "≥1800": 0,
        "1650–1799": 0,
        "1500–1649": 0,
        "1350–1499": 0,
        "1200–1349": 0,
        "<1200": 0,
    }
    for e in entries:
        if e.elo >= 1800:
            bins["≥1800"] += 1
        elif e.elo >= 1650:
            bins["1650–1799"] += 1
        elif e.elo >= 1500:
            bins["1500–1649"] += 1
        elif e.elo >= 1350:
            bins["1350–1499"] += 1
        elif e.elo >= 1200:
            bins["1200–1349"] += 1
        else:
            bins["<1200"] += 1

    total = len(entries)
    print(f"\n{C.DIM}  RATING DISTRIBUTION{C.RESET}")
    print(f"{C.GREY}  {'─'*50}{C.RESET}")
    tier_colors = [C.GOLD, C.SILVER, C.CYAN, C.GREEN, C.BRONZE, C.RED]
    for (label, count), col in zip(bins.items(), tier_colors):
        bar_len = round((count / total) * 30) if total else 0
        bar = "█" * bar_len
        print(f"  {col}{label:>12}{C.RESET}  {col}{bar:<30}{C.RESET}  {count:>3}")

    print(f"\n{C.GREY}{'━'*width}{C.RESET}\n")


# ─────────────────────────────────────────────────────────────
#  Main
# ─────────────────────────────────────────────────────────────
if __name__ == "__main__":
    # ── Load player names ───────────────────────────────────
    players = ["Heath"]
    try:
        names_df = pd.read_csv("swiss_names.csv")
        csv_names = names_df["first_name"].iloc[0:63].tolist()
        players = players + csv_names
    except Exception:
        players += ["Alice", "Bob", "Charlie", "Diana", "Eve", "Frank"]

    # ── Initialise registry and tournament ──────────────────
    registry = PlayerRegistry()
    tournament = Tournament(registry, name="Swiss Championship")

    for i, raw_name in enumerate(players):
        clean = raw_name.strip()
        trimmed = trim_visual_width(clean, max_width=6)
        tournament.add_player(f"P{i+1}", trimmed)

    total_rounds, phase1, point_threshold, top_cut = get_rounds(len(players))

    # ── Tournament banner ───────────────────────────────────
    width = 72
    print()
    print(f"{C.BOLD}{C.GOLD}{'█'*width}{C.RESET}")
    print(
        f"{C.BOLD}{C.WHITE}{'█':^1}{'SWISS CHAMPIONSHIP — ELO EDITION':^{width-2}}{'█':^1}{C.RESET}"
    )
    print(f"{C.BOLD}{C.GOLD}{'█'*width}{C.RESET}")
    print(
        f"{C.DIM}  {len(players)} players  │  {total_rounds} rounds  │"
        f"  Top {top_cut} to elimination bracket{C.RESET}"
    )
    print(
        f"{C.DIM}  Elo start: 1500  │  K-factor: 40 → 24 → 16 (by experience){C.RESET}"
    )
    print()

    # ── Swiss rounds ────────────────────────────────────────
    for _ in range(total_rounds):
        round_number = tournament.start_new_round()
        tournament.print_round_header(round_number, total_rounds)

        pairings = tournament.generate_pairings(round_number, phase1, point_threshold)

        for p1, p2 in pairings:
            tournament.simulate_round_match(p1, p2, round_number)

        tournament.print_round_results(round_number)

    # ── Final standings ─────────────────────────────────────
    tournament.print_standings(top_cut)

    # ── Elo insights ─────────────────────────────────────────
    print_elo_insights(registry, tournament)

    # ── Single-elim bracket ──────────────────────────────────
    standings = tournament.get_standings_df()
    top_cut_ids = standings["player_id"].iloc[:top_cut].tolist()
    bracket = SingleEliminationBracket(top_cut_ids, tournament, registry)
    bracket.print_bracket()

    for round_number in range(1, bracket.num_rounds + 1):
        for match in bracket.get_current_matches():
            bracket.simulate_match(round_number, match.match_number)
        bracket.print_bracket()

    # ── Global leaderboard ───────────────────────────────────
    registry.print_leaderboard(top_n=20, title="FINAL ELO LEADERBOARD")

    champ_id = bracket.get_champion()
    if champ_id:
        champ = registry.get(champ_id)
        champ_col = elo_color(champ.elo)
        print(
            f"{C.BOLD}{C.GOLD}  CHAMPION: "
            f"{champ_col}{champ.name}{C.RESET}"
            f"{C.GOLD}  (Elo {champ.elo:.0f}  |  "
            f"peak {champ.peak_elo:.0f}){C.RESET}\n"
        )
