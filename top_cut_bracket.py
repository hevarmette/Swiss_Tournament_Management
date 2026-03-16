import math

# --- Configuration Constants ---
NAME_W = 5  # Maximum number of characters displayed for a name
COL_GAP = 8  # Number of spaces/line characters between columns
ROUND_W = NAME_W + COL_GAP  # Total width allocated for one full round (13)
LINE_W = ROUND_W - 1  # Width of the horizontal lines drawn under names (12)


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
    # Slice the name to enforce the max length, then center it
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

    Args:
        grid (list of list of str): The canvas to draw on.
        row_top (int): The row index for the top competitor's horizontal line.
        row_bot (int): The row index for the bottom competitor's horizontal line.
        col_in (int): The starting column index for this round.
        col_out (int): The ending column index (where the vertical connector goes).
        top_name (str): Name of the top competitor.
        bot_name (str): Name of the bottom competitor.
        winner_name (str): Name of the winner advancing to the next round.
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


# ==========================================
# Main Execution: Building the Bracket
# ==========================================

# 1. Define your players (Length MUST be a power of 2: 2, 4, 8, 16, 32...)
players = [
    "Alice",
    "Hank",
    "Diana",
    "Eve",
    "Charl",
    "Frank",
    "Bob",
    "Grace",
    "Ivy",
    "Jack",
    "Kevin",
    "Liam",
    "Mia",
    "Noah",
    "Olivia",
    "Pete",
]

# Calculate total rounds (e.g., 16 players = 4 rounds)
total_rounds = int(math.log2(len(players)))

# 2. Dynamically calculate required canvas dimensions
# Height needs enough room for all players to have 2 rows of space each
HEIGHT = 2 * len(players) + 5
WIDTH = ROUND_W * (total_rounds + 1) + 5
grid = make_grid(HEIGHT, WIDTH)

# 3. Generate intelligent headers
for i in range(total_rounds + 1):
    if i == total_rounds:
        header = "Winner"
    elif i == total_rounds - 1:
        header = "Finals"
    elif i == total_rounds - 2:
        header = "Semifinals"
    elif i == total_rounds - 3:
        header = "Quarterfinals"
    else:
        header = f"Round {i + 1}"

    write(grid, 0, i * ROUND_W, center_pad(header, LINE_W))

# 4. The Algorithm: Loop through rounds and draw matches
current_players = players.copy()

for r in range(total_rounds):
    next_players = []

    # Calculate geometric spacing for the current round
    start_row = 3 + (2**r) - 1  # The very first row drops further down each round
    diff = 2 ** (r + 1)  # Gap between top and bottom player doubles
    step = 2 ** (r + 2)  # Gap between distinct matches doubles

    col_in = r * ROUND_W
    col_out = (r + 1) * ROUND_W

    # Process each matchup in the current round
    for m in range(len(current_players) // 2):
        p1 = current_players[2 * m]
        p2 = current_players[2 * m + 1]

        # For visualization, we are automatically advancing player 1 as the winner
        winner = p1

        row_top = start_row + m * step
        row_bot = row_top + diff

        draw_match(grid, row_top, row_bot, col_in, col_out, p1, p2, winner)

        next_players.append(winner)

    # Promote the winners to the next round
    current_players = next_players

# Print the final generated bracket
print(render(grid))
