"""
Pygame presentation layer for Minesweeper.

This module owns:
- Renderer: all drawing of cells, header, and result overlays
- InputController: translate mouse input to board actions and UI feedback
- Game: orchestration of loop, timing, state transitions, and composition

The logic lives in components.Board; this module should not implement rules.
"""

import sys
import pygame

import config
from components import Board
from pygame.locals import Rect


class Renderer:
    """Draws the Minesweeper UI.

    Knows how to draw individual cells with flags/numbers, header info,
    and end-of-game overlays with a semi-transparent background.
    """

    def __init__(self, screen: pygame.Surface, board: Board):
        self.screen = screen
        self.board = board
        self.font = pygame.font.Font(config.font_name, config.font_size)
        self.header_font = pygame.font.Font(config.font_name, config.header_font_size)
        self.result_font = pygame.font.Font(config.font_name, config.result_font_size)

    def cell_rect(self, col: int, row: int) -> Rect:
        """Return the rectangle in pixels for the given grid cell."""
        x = config.margin_left + col * config.cell_size
        y = config.margin_top + row * config.cell_size
        return Rect(x, y, config.cell_size, config.cell_size)

    def draw_cell(self, col: int, row: int, highlighted: bool) -> None:
        """Draw a single cell, respecting revealed/flagged state and highlight."""
        cell = self.board.cells[self.board.index(col, row)]
        rect = self.cell_rect(col, row)
        if cell.state.is_revealed:
            pygame.draw.rect(self.screen, config.color_cell_revealed, rect)
            if cell.state.is_mine:
                pygame.draw.circle(self.screen, config.color_cell_mine, rect.center, rect.width // 4)
            elif cell.state.adjacent > 0:
                color = config.number_colors.get(cell.state.adjacent, config.color_text)
                label = self.font.render(str(cell.state.adjacent), True, color)
                label_rect = label.get_rect(center=rect.center)
                self.screen.blit(label, label_rect)
        else:
            base_color = config.color_highlight if highlighted else config.color_cell_hidden
            pygame.draw.rect(self.screen, base_color, rect)
            if cell.state.is_flagged:
                flag_w = max(6, rect.width // 3)
                flag_h = max(8, rect.height // 2)
                pole_x = rect.left + rect.width // 3
                pole_y = rect.top + 4
                pygame.draw.line(self.screen, config.color_flag, (pole_x, pole_y), (pole_x, pole_y + flag_h), 2)
                pygame.draw.polygon(
                    self.screen,
                    config.color_flag,
                    [
                        (pole_x + 2, pole_y),
                        (pole_x + 2 + flag_w, pole_y + flag_h // 3),
                        (pole_x + 2, pole_y + flag_h // 2),
                    ],
                )
        pygame.draw.rect(self.screen, config.color_grid, rect, 1)

    def draw_header(self, remaining_mines: int, time_text: str) -> None:
        """Draw the header bar containing remaining mines and elapsed time."""
        pygame.draw.rect(
            self.screen,
            config.color_header,
            Rect(0, 0, config.width, config.margin_top - 4),
        )
        left_text = f"Mines: {remaining_mines}"
        right_text = f"Time: {time_text}"
        left_label = self.header_font.render(left_text, True, config.color_header_text)
        right_label = self.header_font.render(right_text, True, config.color_header_text)
        self.screen.blit(left_label, (10, 12))
        self.screen.blit(right_label, (config.width - right_label.get_width() - 10, 12))

    def draw_result_overlay(self, text: str | None) -> None:
        """Draw a semi-transparent overlay with centered result text, if any."""
        if not text:
            return
        overlay = pygame.Surface((config.width, config.height), pygame.SRCALPHA)
        overlay.fill((0, 0, 0, config.result_overlay_alpha))
        self.screen.blit(overlay, (0, 0))
        label = self.result_font.render(text, True, config.color_result)
        rect = label.get_rect(center=(config.width // 2, config.height // 2))
        self.screen.blit(label, rect)


class InputController:
    """Translates input events into game and board actions."""

    def __init__(self, game: "Game"):
        self.game = game

    def pos_to_grid(self, x: int, y: int):
        """Convert pixel coordinates to (col,row) grid indices or (-1,-1) if out of bounds."""
        if not (config.margin_left <= x < config.width - config.margin_right):
            return -1, -1
        if not (config.margin_top <= y < config.height - config.margin_bottom):
            return -1, -1
        col = (x - config.margin_left) // config.cell_size
        row = (y - config.margin_top) // config.cell_size
        if 0 <= col < self.game.board.cols and 0 <= row < self.game.board.rows:
            return int(col), int(row)
        return -1, -1

    def handle_mouse(self, pos, button) -> None:
        # TODO: Handle mouse button events: left=reveal, right=flag, middle=neighbor highlight  in here
        col, row = self.pos_to_grid(pos[0], pos[1])
        if col == -1:
            return
        
        game = self.game
        
        if button == config.mouse_left:
            game.highlight_targets.clear()
        
            if not game.started:
                game.started = True
                game.start_ticks_ms = pygame.time.get_ticks()

            game.board.reveal(col, row)
    
        elif button == config.mouse_right:
            game.highlight_targets.clear()
            game.board.toggle_flag(col, row)

        elif button == config.mouse_middle:
                neighbors = game.board.neighbors(col, row)

                game.highlight_targets = {
                    (nc, nr)
                    for (nc, nr) in neighbors
                    if not game.board.cells[game.board.index(nc, nr)].state.is_revealed
                }
        
                game.highlight_until_ms = pygame.time.get_ticks() + config.highlight_duration_ms
        
class Game:
    """Main application object orchestrating loop and high-level state."""

    def __init__(self):
        pygame.init()
        pygame.display.set_caption(config.title)
        self.screen = pygame.display.set_mode(config.display_dimension)
        self.clock = pygame.time.Clock()
        self.board = Board(config.cols, config.rows, config.num_mines)
        self.renderer = Renderer(self.screen, self.board)
        self.input = InputController(self)
        self.highlight_targets = set()
        self.highlight_until_ms = 0
        self.started = False
        self.start_ticks_ms = 0
        self.end_ticks_ms = 0

    def reset(self):
        """Reset the game state and start a new board."""
        self.board = Board(config.cols, config.rows, config.num_mines)
        self.renderer.board = self.board
        self.highlight_targets.clear()
        self.highlight_until_ms = 0
        self.started = False
        self.start_ticks_ms = 0
        self.end_ticks_ms = 0
        
        # 이슈3 구현(1/2)
    def set_difficulty(self, cols, rows, mines):
        config.cols = cols
        config.rows = rows
        config.num_mines = mines
        
        # 창 크기 재계산 (config.py에 있는 공식 사용)
        config.width = config.margin_left + config.cols * config.cell_size + config.margin_right
        config.height = config.margin_top + config.rows * config.cell_size + config.margin_bottom
        config.display_dimension = (config.width, config.height)
        
        # 화면 다시 만들기
        self.screen = pygame.display.set_mode(config.display_dimension)
        
        # 게임 리셋
        self.reset()

    def _elapsed_ms(self) -> int:
        """Return elapsed time in milliseconds (stops when game ends)."""
        if not self.started:
            return 0
        if self.end_ticks_ms:
            return self.end_ticks_ms - self.start_ticks_ms
        return pygame.time.get_ticks() - self.start_ticks_ms

    def _format_time(self, ms: int) -> str:
        """Format milliseconds as mm:ss string."""
        total_seconds = ms // 1000
        minutes = total_seconds // 60
        seconds = total_seconds % 60
        return f"{minutes:02d}:{seconds:02d}"

    def _result_text(self) -> str | None:
        """Return result label to display, or None if game continues."""
        if self.board.game_over:
            return "GAME OVER"
        if self.board.win:
            return "GAME CLEAR"
        return None

    def draw(self):
        """Render one frame: header, grid, result overlay."""
        if pygame.time.get_ticks() > self.highlight_until_ms and self.highlight_targets:
            self.highlight_targets.clear()
        self.screen.fill(config.color_bg)
        remaining = max(0, config.num_mines - self.board.flagged_count())
        time_text = self._format_time(self._elapsed_ms())
        self.renderer.draw_header(remaining, time_text)
        now = pygame.time.get_ticks()
        for r in range(self.board.rows):
            for c in range(self.board.cols):
                highlighted = (now <= self.highlight_until_ms) and ((c, r) in self.highlight_targets)
                self.renderer.draw_cell(c, r, highlighted)
        self.renderer.draw_result_overlay(self._result_text())
        pygame.display.flip()

    def run_step(self) -> bool:
        """Process inputs, update time, draw, and tick the clock once."""
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                return False
            if event.type == pygame.KEYDOWN:
                if event.key == pygame.K_r:
                    self.reset()
                    # 이슈3구현(2/2)
                elif event.key == pygame.K_1: # 1번 누르면 쉬움
                    self.set_difficulty(9, 9, 10)
                elif event.key == pygame.K_2: # 2번 누르면 보통
                    self.set_difficulty(16, 16, 40)
                elif event.key == pygame.K_3: # 3번 누르면 어려움
                    self.set_difficulty(24, 24, 99)
            if event.type == pygame.MOUSEBUTTONDOWN:
                self.input.handle_mouse(event.pos, event.button)
        if (self.board.game_over or self.board.win) and self.started and not self.end_ticks_ms:
            self.end_ticks_ms = pygame.time.get_ticks()
        self.draw()
        self.clock.tick(config.fps)
        return True


def main() -> int:
    """Application entrypoint: run the main loop until quit."""
    game = Game()
    running = True
    while running:
        running = game.run_step()
    pygame.quit()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
