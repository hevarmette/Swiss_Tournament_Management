NAME_W = 8
COL_GAP = 5
ROUND_W = NAME_W + COL_GAP


def make_grid(height, width):
    return [[" "] * width for _ in range(height)]


def write(grid, row, col, text):
    for i, ch in enumerate(text):
        if 0 <= row < len(grid) and col + i < len(grid[row]):
            grid[row][col + i] = ch


def pad(name, w):
    return name[:w].ljust(w)


def render(grid):
    return "\n".join("".join(row) for row in grid)


def draw_match(
    grid, row_top, row_bot, col_in, col_out, top_name, bot_name, winner_name
):
    row_mid = (row_top + row_bot) // 2

    write(grid, row_top, col_in, pad(top_name, NAME_W))
    write(grid, row_bot, col_in, pad(bot_name, NAME_W))

    for c in range(col_in + NAME_W, col_out):
        grid[row_top][c] = "-"
        grid[row_bot][c] = "-"

    for r in range(row_top, row_bot + 1):
        grid[r][col_out - 1] = "|"
    grid[row_top][col_out - 1] = "+"
    grid[row_bot][col_out - 1] = "+"
    grid[row_mid][col_out - 1] = "+"

    for c in range(col_out - 1, col_out + NAME_W - 1):
        if grid[row_mid][c] in (" ", "-"):
            grid[row_mid][c] = "-"
    write(grid, row_mid, col_out + NAME_W - 1, " " + pad(winner_name, NAME_W))


HEIGHT = 15
WIDTH = ROUND_W * 3 + NAME_W + 10
grid = make_grid(HEIGHT, WIDTH)

c1, c2, c3, c4 = 0, ROUND_W, ROUND_W * 2, ROUND_W * 3

draw_match(grid, 0, 2, c1, c2, "Alice", "Hank", "Alice")
draw_match(grid, 4, 6, c1, c2, "Diana", "Eve", "Diana")
draw_match(grid, 8, 10, c1, c2, "Charl", "Frank", "Charl")
draw_match(grid, 12, 14, c1, c2, "Bob", "Grace", "Bob")

draw_match(grid, 1, 5, c2, c3, "Alice", "Diana", "Alice")
draw_match(grid, 9, 13, c2, c3, "Charl", "Bob", "Charl")

draw_match(grid, 3, 11, c3, c4, "Alice", "Charl", "Alice")

print(render(grid))
