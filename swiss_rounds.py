from dataclasses import dataclass, field
from typing import List, Dict, Optional
import pandas as pd
import random
import math

# --- ASCII Bracket Configuration Constants ---
NAME_W = 6  # Maximum number of characters displayed for a name (updated to 6 for swiss_rounds)
COL_GAP = 8  # Number of spaces/line characters between columns
ROUND_W = NAME_W + COL_GAP  # Total width allocated for one full round (14)
LINE_W = ROUND_W - 1  # Width of the horizontal lines drawn under names (13)


def make_grid(height, width):
    """
    Initializes a blank 2D grid (canvas) filled with space characters.

    Args:
        height (int): The number of rows in the grid.
        width (int): The number of columns in the grid.

    Returns:
        list of list of str: A 2D array representing the blank canvas.
    """
    return [[" "] * width for _ in range(height)]


def write(grid, row, col, text):
    """
    Writes a string onto the grid at the specified coordinates.
    Safely ignores characters that fall outside the grid's boundaries.

    Args:
        grid (list of list of str): The canvas to write on.
        row (int): The starting row index (Y-coordinate).
        col (int): The starting column index (X-coordinate).
        text (str): The string to write onto the grid.
    """
    for i, ch in enumerate(text):
        if 0 <= row < len(grid) and col + i < len(grid[row]):
            grid[row][col + i] = ch


def center_pad(name, w):
    """
    Truncates a name to the maximum allowed length, then centers it
    within a specified width using space padding.

    Args:
        name (str): The string to format.
        w (int): The total width to center the string within.

    Returns:
        str: The formatted, centered string.
    """
    return name[:NAME_W].center(w)


def render(grid):
    """
    Converts the 2D grid into a single, printable multi-line string.

    Args:
        grid (list of list of str): The canvas to render.

    Returns:
        str: The final ASCII art representation, with trailing whitespace removed.
    """
    return "\n".join("".join(row).rstrip() for row in grid)


def draw_match(
    grid, row_top, row_bot, col_in, col_out, top_name, bot_name, winner_name
):
    """
    Draws a single tournament matchup on the grid, including the competitors'
    names, connecting lines, and the winner's name advancing to the next round.
    """
    # Calculate the exact middle row for the junction and winner's line
    row_mid = (row_top + row_bot) // 2

    # 1. Write competitor names centered directly ABOVE their respective lines (row - 1)
    write(grid, row_top - 1, col_in, center_pad(top_name, LINE_W))
    write(grid, row_bot - 1, col_in, center_pad(bot_name, LINE_W))

    # 2. Draw horizontal lines for both competitors
    for c in range(col_in, col_out - 1):
        grid[row_top][c] = "-"
        grid[row_bot][c] = "-"

    # 3. Draw the vertical connector connecting the top and bottom lines
    for r in range(row_top, row_bot + 1):
        grid[r][col_out - 1] = "|"

    # Place junction markers (+) at the corners and the middle intersection
    grid[row_top][col_out - 1] = "+"
    grid[row_bot][col_out - 1] = "+"
    grid[row_mid][col_out - 1] = "+"

    # 4. Draw the horizontal line for the winner branching off the middle junction
    for c in range(col_out, col_out + LINE_W):
        if c < len(grid[0]):
            grid[row_mid][c] = "-"

    # 5. Write the winner's name centered directly ABOVE their new line
    write(grid, row_mid - 1, col_out, center_pad(winner_name, LINE_W))


def get_visual_match_numbers(round_num, total_rounds):
    """
    Helper function to calculate the visual vertical order of matches
    for a standard bracket (e.g. 1v8, 4v5, 3v6, 2v7).
    Uses parity to ensure highest seeds are positioned on the outer edges.
    """
    order = [1]
    for r in range(total_rounds, round_num, -1):
        next_order = []
        L = 2 ** (total_rounds - r + 1)
        for x in order:
            # Odd seeds stay on top, even seeds go to the bottom of their sub-bracket
            if x % 2 == 1:
                next_order.extend([x, L - x + 1])
            else:
                next_order.extend([L - x + 1, x])
        order = next_order
    return order


# ==========================================
# Original Swiss Rounds Logic
# ==========================================


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
        if num_players < max_players + 1:
            return rounds, phase1, point_thresh, top_cut

    return ValueError("Too many players!!")


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

    def add_match(
        self, opponent_id: str, won: bool, round_number: int, is_bye: bool = False
    ):
        self.matches.append(Match(opponent_id, won, round_number, is_bye))

    def add_bye(self, round_number: int):
        self.matches.append(Match("BYE", True, round_number, is_bye=True))

    @property
    def wins(self) -> int:
        return sum(1 for match in self.matches if match.won)

    @property
    def losses(self) -> int:
        return sum(1 for match in self.matches if not match.won and not match.is_bye)

    @property
    def win_percentage(self) -> float:
        total_matches = len(self.matches)
        if total_matches == 0:
            return 0.0
        return self.wins / total_matches

    @property
    def match_points(self) -> int:
        return self.wins * 3

    @property
    def opp_percentage(self) -> float:
        if not self.matches or not self.tournament:
            return 0.0

        opp_win_rates = []
        for opp_id in self.get_opponents():
            opp_win_rate = self.tournament.players[opp_id].win_percentage
            opp_win_rates.append(max(0.25, opp_win_rate))

        return sum(opp_win_rates) / len(opp_win_rates) if opp_win_rates else 0.0

    @property
    def opp_opp_percentage(self) -> float:
        if not self.matches or not self.tournament:
            return 0.0

        all_opp_opp_rates = []
        for opp_id in self.get_opponents():
            opponent = self.tournament.players[opp_id]
            for opp_opp_id in opponent.get_opponents():
                opp_opp_win_rate = self.tournament.players[opp_opp_id].win_percentage
                all_opp_opp_rates.append(max(0.25, opp_opp_win_rate))

        return (
            sum(all_opp_opp_rates) / len(all_opp_opp_rates)
            if all_opp_opp_rates
            else 0.0
        )

    def has_played(self, opponent_id: str) -> bool:
        return any(match.opponent_id == opponent_id for match in self.matches)

    def get_opponents(self) -> List[str]:
        return [match.opponent_id for match in self.matches if not match.is_bye]

    def get_non_bye_matches(self) -> List[Match]:
        return [match for match in self.matches if not match.is_bye]


class Tournament:
    def __init__(self):
        self.players: Dict[str, Player] = {}
        self.current_round = 0
        self.bye_history = set()

    def add_players(self, names: List[str]) -> List[str]:
        player_ids = []
        for name in names:
            player_id = self.add_player(name, name)
            player_ids.append(player_id)
        return player_ids

    def add_player(self, player_id: str, name: str):
        player = Player(player_id, name)
        player.tournament = self
        self.players[player_id] = player

    def start_new_round(self) -> int:
        self.current_round += 1
        return self.current_round

    def record_match(
        self, player1_id: str, player2_id: str, player1_won: bool, round_number: int
    ):
        self.players[player1_id].add_match(player2_id, player1_won, round_number)
        self.players[player2_id].add_match(player1_id, not player1_won, round_number)

    def record_bye(self, player_id: str, round_number: int):
        player = self.players[player_id]
        player.add_bye(round_number)
        self.bye_history.add(player_id)

    def drop_player(self, player_id: str):
        if player_id not in self.players:
            raise ValueError(f"Player {player_id} not found in tournament")
        self.players[player_id].dropped = True
        print(f"Player {self.players[player_id].name} has dropped from the tournament")

    def assign_bye(self, round_number: int) -> str:
        if round_number == 1:
            bye_player_id = random.choice(list(self.players.keys()))
        else:
            standings = self.get_standings_df()
            for _, row in standings.iterrows():
                if row["player_id"] not in self.bye_history:
                    bye_player_id = row["player_id"]
                    break

        self.record_bye(bye_player_id, round_number)
        return bye_player_id

    def generate_pairings(
        self, round_number: int, phase1_rounds: int, minimum_match_points
    ):
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
                print(f"Player {bye_player} gets a bye")

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
            print(f"Player {bye_player} gets a bye")

        carry_down: Optional[str] = None

        for record in sorted_records:
            group = record_groups.get(record, [])
            if not group:
                continue

            if carry_down:
                found_idx = None
                for i, opp in enumerate(group):
                    if self.can_pair(carry_down, opp):
                        found_idx = i
                        break
                if found_idx is not None:
                    opp = group.pop(found_idx)
                    pairings.append((carry_down, opp))
                    unpaired.discard(carry_down)
                    unpaired.discard(opp)
                    carry_down = None

            while len(group) >= 2:
                p1 = group.pop(0)
                partner_idx = None
                for j, cand in enumerate(group):
                    if self.can_pair(p1, cand):
                        partner_idx = j
                        break
                if partner_idx is not None:
                    p2 = group.pop(partner_idx)
                else:
                    p2 = group.pop(0)
                pairings.append((p1, p2))
                unpaired.discard(p1)
                unpaired.discard(p2)

            if len(group) == 1:
                last = group.pop()
                if carry_down is None:
                    carry_down = last
                else:
                    if self.can_pair(carry_down, last):
                        pairings.append((carry_down, last))
                        unpaired.discard(carry_down)
                        unpaired.discard(last)
                        carry_down = None
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
                print(f"Player {carry_down} gets a bye")

        participants = []
        for a, b in pairings:
            participants.extend([a, b])
        dupes = {x for x in participants if participants.count(x) > 1}
        if dupes:
            print("Warning: duplicate participants in this round's pairings:", dupes)

        return pairings

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
        for player_id, player in self.players.items():
            if player.dropped:
                continue
            data.append(
                {
                    "player_id": player_id,
                    "name": player.name,
                    "wins": player.wins,
                    "losses": player.losses,
                    "match_points": player.match_points,
                    "opp_win_percentage": player.opp_percentage,
                    "opp_opp_win_percentage": player.opp_opp_percentage,
                    "win_percentage": player.win_percentage,
                    "matches_played": len(player.matches),
                }
            )

        df = pd.DataFrame(data)
        return df.sort_values(
            ["match_points", "opp_win_percentage", "opp_opp_win_percentage"],
            ascending=[False, False, False],
        ).reset_index(drop=True)

    def can_pair(self, player1_id: str, player2_id: str) -> bool:
        """
        Determines if two players can be paired together.
        In standard Swiss, players cannot be paired if they have already played each other.
        """
        if player1_id == player2_id:
            return False

        player1 = self.players[player1_id]
        return not player1.has_played(player2_id)

    def print_standings(self, top_cut, long_line=51, short_line=49):
        standings = self.get_standings_df()

        def line_for(points):
            return "-" * (short_line if points < 10 else long_line)

        print(line_for(standings.loc[0, "match_points"]))

        more_spaces = False
        for i, row in standings.iterrows():
            if i == top_cut:
                print(line_for(row["match_points"]))

            if row["match_points"] < 10:
                more_spaces = True

            spacing = "   " if more_spaces else "  "

            print(
                f"|{row['name']}\t"
                f"|  {row['wins']}/{row['losses']}/0 ({row['match_points']}){spacing}"
                f"|  {row['match_points']}{spacing}"
                f"|  {row['opp_win_percentage']:.2%}  "
                f"|  {row['opp_opp_win_percentage']:.2%}|"
            )

        print(line_for(standings.loc[0, "match_points"]))


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
    def __init__(self, seeded_player_ids: List[str], tournament: "Tournament"):
        self.tournament = tournament
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
                round_number=1,
                match_number=match_num,
                player1_id=self.seeds[seed],
                player2_id=None,
                winner_id=self.seeds[seed],
                is_bye=True,
            )
            first_round_matches.append(m)
            match_num += 1

        playing_seeds = list(range(self.num_byes + 1, self.size + 1))
        lo, hi = 0, len(playing_seeds) - 1
        while lo < hi:
            top_seed = playing_seeds[lo]
            bot_seed = playing_seeds[hi]
            m = BracketMatch(
                round_number=1,
                match_number=match_num,
                player1_id=self.seeds[top_seed],
                player2_id=self.seeds[bot_seed],
            )
            first_round_matches.append(m)
            match_num += 1
            lo += 1
            hi -= 1

        self.rounds[1] = first_round_matches
        self._try_advance_round()

    def _all_round_complete(self, round_number: int) -> bool:
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
                m = BracketMatch(
                    round_number=next_round,
                    match_number=match_num,
                    player1_id=winners[lo],
                    player2_id=winners[hi],
                )
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

    def record_result(self, round_number: int, match_number: int, winner_id: str):
        matches = self.rounds.get(round_number)
        if matches is None:
            raise ValueError(f"Round {round_number} does not exist in this bracket.")

        target = next((m for m in matches if m.match_number == match_number), None)
        if target is None:
            raise ValueError(f"Match {match_number} not found in round {round_number}.")
        if winner_id not in (target.player1_id, target.player2_id):
            raise ValueError(
                f"{winner_id} is not a participant in this match "
                f"({target.player1_id} vs {target.player2_id})."
            )

        target.winner_id = winner_id
        self._try_advance_round()

    def get_champion(self) -> Optional[str]:
        final_round = self.rounds.get(self.num_rounds)
        if final_round and len(final_round) == 1 and final_round[0].winner_id:
            return final_round[0].winner_id
        return None

    def print_bracket(self):
        """Pretty-print every round of the bracket using ASCII art."""
        print(f"\n{'='*55}")
        print(f"  Single Elimination Bracket  ({self.size} players)")
        print(f"  Bracket size: {self.bracket_size}  |  Byes: {self.num_byes}")
        print(f"{'='*55}\n")

        if self.num_rounds == 0:
            print("No matches to display.")
            return

        # Calculate dimensions
        HEIGHT = 2 * self.bracket_size + 5
        WIDTH = ROUND_W * (self.num_rounds + 1) + 5
        grid = make_grid(HEIGHT, WIDTH)

        # Generate intelligent headers
        for i in range(self.num_rounds + 1):
            if i == self.num_rounds:
                header = "Champion"
            elif i == self.num_rounds - 1:
                header = "Finals"
            elif i == self.num_rounds - 2:
                header = "Semifinals"
            elif i == self.num_rounds - 3:
                header = "Quarterfinals"
            else:
                header = f"Round {i + 1}"
            write(grid, 0, i * ROUND_W, center_pad(header, LINE_W))

        # The Algorithm: Loop through rounds and draw matches
        for r in range(self.num_rounds):
            col_in = r * ROUND_W
            col_out = (r + 1) * ROUND_W

            # Calculate geometric spacing for the current round
            start_row = 3 + (2**r) - 1
            diff = 2 ** (r + 1)
            step = 2 ** (r + 2)

            # Use 1-indexed round for tracking within the model
            swiss_round_num = r + 1
            visual_match_nums = get_visual_match_numbers(
                swiss_round_num, self.num_rounds
            )

            for m_visual_idx, match_num in enumerate(visual_match_nums):
                # Fetch the match object corresponding to its visual position
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

                p1_name = ""
                p2_name = ""
                winner_name = ""

                if match:
                    if swiss_round_num == 1:
                        # First round maps directly to the match structure
                        p1_name = (
                            self.tournament.players[match.player1_id].name
                            if match.player1_id
                            else ""
                        )
                        if match.is_bye:
                            p2_name = "(BYE)"
                            # If a match is a bye, player 1 automatically advances
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
                        # For R2+, dynamically fetch the correct geometric players to prevent visual line crossing!
                        prev_round_num = swiss_round_num - 1
                        prev_visual_match_nums = get_visual_match_numbers(
                            prev_round_num, self.num_rounds
                        )

                        # Find exactly which matches feed into our top and bottom lines
                        prev_top_match_num = prev_visual_match_nums[m_visual_idx * 2]
                        prev_bot_match_num = prev_visual_match_nums[
                            m_visual_idx * 2 + 1
                        ]

                        top_match = next(
                            (
                                m
                                for m in self.rounds.get(prev_round_num, [])
                                if m.match_number == prev_top_match_num
                            ),
                            None,
                        )
                        bot_match = next(
                            (
                                m
                                for m in self.rounds.get(prev_round_num, [])
                                if m.match_number == prev_bot_match_num
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
        # Print the final generated bracket
        print(render(grid))

        champion = self.get_champion()
        if champion:
            champ_name = self.tournament.players[champion].name
            print(f"\n  🏆 Champion: {champ_name}")
        print(f"{'='*55}\n")


# ==========================================
# Main Test Execution
# ==========================================

if __name__ == "__main__":
    tournament = Tournament()

    players = ["Heath"]
    try:
        names = pd.read_csv("swiss_names.csv")
        names = names["first_name"].iloc[0:63].to_list()
        players = players + names
    except Exception:
        # Fallback if csv goes missing
        players += ["Alice", "Bob", "Charlie", "Diana", "Eve", "Frank"]

    for i, name in enumerate(players):
        tournament.add_player(f"P{i+1}", name.strip() if len(name) < 6 else name[:6])

    total_rounds, phase1, point_threshold, top_cut = get_rounds(len(players))
    print(f"Total rounds: {total_rounds}")
    print(f"Phase 1 rounds: {phase1}")
    print(f"Minimum points needed to advance to phase 2: {point_threshold}")
    print(f"Players in top cut: {top_cut}")

    for _ in range(total_rounds):
        round_number = tournament.start_new_round()
        print(f"\nRound {round_number}")

        pairings = tournament.generate_pairings(round_number, phase1, point_threshold)

        for p1, p2 in pairings:
            winner = random.choice([p1, p2])
            tournament.record_match(
                p1, p2, player1_won=(winner == p1), round_number=round_number
            )
            if p1 == "P1" or p2 == "P1":
                print(
                    f"Match: {tournament.players[p1].name} vs {tournament.players[p2].name} -> Winner: {tournament.players[winner].name}"
                )

    tournament.print_standings(top_cut)

    standings = tournament.get_standings_df()
    top_cut_ids = standings["player_id"].iloc[:top_cut].tolist()

    bracket = SingleEliminationBracket(top_cut_ids, tournament)
    bracket.print_bracket()

    for round_number in range(1, bracket.num_rounds + 1):
        for match in bracket.get_current_matches():
            winner = random.choice([match.player1_id, match.player2_id])
            bracket.record_result(round_number, match.match_number, winner)
        bracket.print_bracket()

    champ_id = bracket.get_champion()
    if champ_id:
        print(f"Champion: {tournament.players[champ_id].name}")

    stats = tournament.get_player_stats("P1")
    print(stats)
