from dataclasses import dataclass, field
from typing import List, Dict, Optional
import pandas as pd
import random

# import names


# 2 phase tournament structure
def get_rounds(num_players):
    if num_players < 4:
        raise ValueError("Tournament requires at least 4 players")

    # Tournament brackets with (max_players, total_rounds)
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
            # Get this opponent's opponents' win rates
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

    def __str__(self):  # need?
        return f"{self.name} ({self.wins}-{self.losses}, {self.win_percentage:.1%})"

    def add_players(self, names: List[str]) -> List[str]:
        player_ids = []
        for name in names:
            player_id = self.add_player(name, name)  # how does this function call work?
            player_ids.append(player_id)
        return player_ids

    def add_player(self, player_id: str, name: str):
        player = Player(player_id, name)
        player.tournament = self  # Set tournament reference
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

    def assign_bye(self, round_number: int) -> str:
        if round_number == 1:
            # Random player
            bye_player_id = random.choice(list(self.players.keys()))
        else:
            # Lowest-ranked player without a bye
            standings = self.get_standings_df()
            for _, row in standings.iterrows():
                if row["player_id"] not in self.bye_history:
                    bye_player_id = row["player_id"]
                    break  # why break statement i don't like them

        # Record the bye
        self.record_bye(bye_player_id, round_number)
        return bye_player_id

    def generate_pairings(
        self, round_number: int, phase1_rounds: int, minimum_match_points
    ):
        pairings = []
        unpaired = set(self.players.keys())

        # Phase-1 cut: remove players below threshold from active set
        if round_number > phase1_rounds and minimum_match_points is not None:
            eliminated = {
                p
                for p in unpaired
                if self.get_player_stats(p)["match_points"] < minimum_match_points
            }
            # if eliminated:
            #     print("Eliminated:", [self.players[p].name for p in eliminated])
            unpaired -= eliminated

        # --- Round 1: full random ---
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

        # --- Rounds 2+: buckets by wins, pair randomly within buckets, float down if odd ---
        # Build buckets only from active/unpaired players
        record_groups: Dict[int, List[str]] = {}
        for pid in list(unpaired):
            wins = self.players[pid].wins
            record_groups.setdefault(wins, []).append(pid)

        if not record_groups:
            return pairings  # nothing to pair

        # Shuffle each bucket
        for grp in record_groups.values():
            random.shuffle(grp)

        sorted_records = sorted(record_groups.keys(), reverse=True)

        # If total active is odd, assign a random bye from the lowest bracket
        total_active = sum(len(record_groups[r]) for r in sorted_records)
        if total_active % 2 == 1:
            lowest = sorted_records[-1]
            candidates = record_groups[lowest]
            bye_player = random.choice(candidates)
            self.record_bye(bye_player, round_number)
            candidates.remove(bye_player)
            unpaired.discard(bye_player)
            print(f"Player {bye_player} gets a bye")
            # if bracket empty after removal, it will be skipped below

        carry_down: Optional[str] = None

        for record in sorted_records:
            group = record_groups.get(record, [])
            if not group:
                continue

            # If there's a carry_down, try pairing it into this bucket
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
                # otherwise keep carry_down for the next (lower) bracket

            # Pair inside the group greedily:
            # Pop the first player, find the first legal partner in the group, pop them and pair.
            while len(group) >= 2:
                p1 = group.pop(0)
                # find partner that hasn't played p1
                partner_idx = None
                for j, cand in enumerate(group):
                    if self.can_pair(p1, cand):
                        partner_idx = j
                        break
                if partner_idx is not None:
                    p2 = group.pop(partner_idx)
                else:
                    # no legal partner found in this bucket: fallback to the first element (may be a rematch)
                    p2 = group.pop(0)
                pairings.append((p1, p2))
                unpaired.discard(p1)
                unpaired.discard(p2)

            # If one leftover in the group, it becomes carry_down (unless we already have one)
            if len(group) == 1:
                last = group.pop()
                if carry_down is None:
                    carry_down = last
                else:
                    # Try to pair them if possible; otherwise pair anyway to avoid deadlock.
                    if self.can_pair(carry_down, last):
                        pairings.append((carry_down, last))
                        unpaired.discard(carry_down)
                        unpaired.discard(last)
                        carry_down = None
                    else:
                        # fallback: pair them even if it's a rematch
                        pairings.append((carry_down, last))
                        unpaired.discard(carry_down)
                        unpaired.discard(last)
                        carry_down = None

        # Final safety: if a carry_down somehow remains, try to pair with any leftover unpaired
        if carry_down:
            remaining = [pid for pid in unpaired if pid != carry_down]
            if remaining:
                opp = remaining[0]
                pairings.append((carry_down, opp))
                unpaired.discard(carry_down)
                unpaired.discard(opp)
            else:
                # no one remains, grant bye
                self.record_bye(carry_down, round_number)
                unpaired.discard(carry_down)
                print(f"Player {carry_down} gets a bye")

        # Sanity check: no player should appear in >1 pairing this round
        participants = []
        for a, b in pairings:
            participants.extend([a, b])
        dupes = {x for x in participants if participants.count(x) > 1}
        if dupes:
            print("Warning: duplicate participants in this round's pairings:", dupes)
            # In debug mode you might raise an exception here.

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
        return not self.players[player1_id].has_played(player2_id)

    def print_standings(self, top_cut, long_line=51, short_line=49):
        standings = self.get_standings_df()

        def line_for(points):
            return "-" * (short_line if points < 10 else long_line)

        # Print header line
        print(line_for(standings.loc[0, "match_points"]))

        more_spaces = False
        for i, row in standings.iterrows():
            if i == top_cut:
                print(line_for(row["match_points"]))

            # Once a player with < 10 points is found, all subsequent rows use extra spacing
            if row["match_points"] < 10:
                more_spaces = True

            # Choose spacing based on the flag
            spacing = "   " if more_spaces else "  "

            print(
                f"|{row['name']}\t"
                f"|  {row['wins']}/{row['losses']}/0 ({row['match_points']}){spacing}"
                f"|  {row['match_points']}{spacing}"
                f"|  {row['opp_win_percentage']:.2%}  "
                f"|  {row['opp_opp_win_percentage']:.2%}|"
            )

        # Print footer line
        print(line_for(standings.loc[0, "match_points"]))


# if __name__ == "__main__":
# Create tournament and add players
tournament = Tournament()

# players = ["Alice", "Bob", "Charlie", "Diana", "Eve", "Frank"]
players = ["Heath"]
names = pd.read_csv("swiss_names.csv")
names = names["first_name"].iloc[0:124].to_list()
players = players + names

for i, name in enumerate(players):
    tournament.add_player(
        f"P{i+1}", name if len(name) < 6 else name[:6]
    )  # why not use add players?

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

    # Print standings after each round
tournament.print_standings(top_cut)
# if round_number == 8:
results = tournament.get_standings_df()
results.to_csv("~/Downloads/swiss.csv")

stats = tournament.get_player_stats("P1")
print(stats)
