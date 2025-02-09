import pygame
import random
import math

# === Configuration Constants ===
pygame.init()
WIDTH, HEIGHT = 800, 800
FPS = 60
clock = pygame.time.Clock()

BALL_COUNT = 500
BALL_RADIUS = 15             # Normal ball radius
ENLARGED_RADIUS = 100        # Radius when a ball is held
GRAVITY = 500                # Gravity in px/s²
# Use stronger damping (lower value) so energy dissipates faster (sand-like)
DAMPING = 0.98               
VELOCITY_CAP = 300         # Maximum allowed speed
MAX_SPEED_FOR_COLOR = 750  # Speed at which ball color is fully red
NUM_CONSTRAINT_ITERATIONS = 5  # (We use only one pass here for performance.)
SCATTER_FORCE = 500        # Base velocity increment on Space press
VELOCITY_ZERO_THRESHOLD = 0.1  # Snap very low speeds to zero

# Use a coarser grid: 10 cells across (each cell is 80x80)
CELL_COUNT = 10
CELL_SIZE = WIDTH // CELL_COUNT  # = 80

# === Create Display Surface ===
screen = pygame.display.set_mode((WIDTH, HEIGHT))

# === Ball Class (PBD-style) ===
class Ball:
    def __init__(self, x, y):
        # Current position:
        self.x = x
        self.y = y
        # Velocity:
        self.vx = 0.0
        self.vy = 0.0
        self.radius = BALL_RADIUS
        self.held = False  # When True, the ball is fixed to the mouse
        # Predicted position (for constraint solving):
        self.px = x
        self.py = y

    def apply_gravity(self, dt):
        if not self.held:
            self.vy += GRAVITY * dt

    def integrate(self, dt):
        if not self.held:
            # Predict new position from current velocity.
            self.px = self.x + self.vx * dt
            self.py = self.y + self.vy * dt
        # Held balls will be forced to follow the mouse externally.

    def enforce_boundaries(self):
        # Clamp predicted positions so that the ball stays completely inside.
        if self.px - self.radius < 0:
            self.px = self.radius
        if self.px + self.radius > WIDTH:
            self.px = WIDTH - self.radius
        if self.py - self.radius < 0:
            self.py = self.radius
        if self.py + self.radius > HEIGHT:
            self.py = HEIGHT - self.radius

    def update_from_prediction(self, dt):
        if not self.held:
            # Update velocity from the displacement.
            new_vx = (self.px - self.x) / dt
            new_vy = (self.py - self.y) / dt
            speed = math.hypot(new_vx, new_vy)
            if speed > VELOCITY_CAP:
                scale = VELOCITY_CAP / speed
                new_vx *= scale
                new_vy *= scale
            self.vx = new_vx
            self.vy = new_vy
            # Update current position.
            self.x = self.px
            self.y = self.py
        else:
            # Held ball: set velocity to zero.
            self.vx = 0
            self.vy = 0
            self.x = self.px
            self.y = self.py

    def draw(self, surf):
        # Color: held ball is yellow; near-zero speed → green; else interpolate from yellow (low) to red (high)
        if self.held:
            color = (255, 255, 0)
        else:
            speed = math.hypot(self.vx, self.vy)
            if speed < 1:
                color = (0, 255, 0)
            else:
                ratio = min(speed / MAX_SPEED_FOR_COLOR, 1.0)
                r = int(255 * ratio)
                g = int(255 * (1 - ratio))
                color = (r, g, 0)
        pygame.draw.circle(surf, color, (int(self.x), int(self.y)), self.radius)

# === Grid for Spatial Partitioning (10x10 cells) ===
class Grid:
    def __init__(self):
        self.cells = {}  # Mapping: (cell_x, cell_y) -> list of balls

    def clear(self):
        self.cells.clear()

    def add(self, ball):
        cell_x = int(ball.x // CELL_SIZE)
        cell_y = int(ball.y // CELL_SIZE)
        key = (cell_x, cell_y)
        if key not in self.cells:
            self.cells[key] = []
        self.cells[key].append(ball)

    def get_neighbors(self, ball):
        neighbors = []
        cell_x = int(ball.x // CELL_SIZE)
        cell_y = int(ball.y // CELL_SIZE)
        # Check the 3x3 area around this ball's cell.
        for dx in [-1, 0, 1]:
            for dy in [-1, 0, 1]:
                key = (cell_x + dx, cell_y + dy)
                if key in self.cells:
                    neighbors.extend(self.cells[key])
        return neighbors

# === Non-overlapping Ball Placement ===
balls = []
attempts = 0
while len(balls) < BALL_COUNT and attempts < 10000:
    x = random.uniform(BALL_RADIUS, WIDTH - BALL_RADIUS)
    y = random.uniform(BALL_RADIUS, HEIGHT - BALL_RADIUS)
    candidate = Ball(x, y)
    overlap = False
    for b in balls:
        if math.hypot(candidate.x - b.x, candidate.y - b.y) < candidate.radius + b.radius:
            overlap = True
            break
    if not overlap:
        balls.append(candidate)
    attempts += 1

grid = Grid()
selected_ball = None  # Ball currently held by the mouse

# === Constraint Solver ===
def solve_constraints(balls):
    # Enforce boundaries on predicted positions.
    for ball in balls:
        ball.enforce_boundaries()
    # For each pair of balls (using grid neighbors), if their predicted positions overlap, push them apart.
    # (If one is held, it remains fixed.)
    for ball in balls:
        neighbors = grid.get_neighbors(ball)
        for other in neighbors:
            if other is ball:
                continue
            dx = other.px - ball.px
            dy = other.py - ball.py
            dist = math.hypot(dx, dy)
            if dist == 0:
                continue
            min_dist = ball.radius + other.radius
            if dist < min_dist:
                overlap = min_dist - dist
                # Unit vector along the line between centers:
                ux = dx / dist
                uy = dy / dist
                if ball.held and not other.held:
                    # Held ball does not move.
                    other.px += ux * overlap
                    other.py += uy * overlap
                elif other.held and not ball.held:
                    ball.px -= ux * overlap
                    ball.py -= uy * overlap
                else:
                    # Both free: share the correction.
                    correction = overlap / 2
                    ball.px -= ux * correction
                    ball.py -= uy * correction
                    other.px += ux * correction
                    other.py += uy * correction

# === Scatter Function ===
def add_scatter(balls):
    # Each Space press adds a random velocity increment to every free ball.
    for ball in balls:
        if not ball.held:
            angle = random.uniform(0, 2 * math.pi)
            delta = random.uniform(0.5, 1.5) * SCATTER_FORCE
            ball.vx += math.cos(angle) * delta
            ball.vy += math.sin(angle) * delta

# === Main Loop ===
running = True
while running:
    dt = clock.tick(FPS) / 1000  # Delta time in seconds
    for event in pygame.event.get():
        if event.type == pygame.QUIT:
            running = False

        # --- Key Events ---
        if event.type == pygame.KEYDOWN:
            if event.key in (pygame.K_ESCAPE, pygame.K_q):
                running = False
            if event.key == pygame.K_SPACE:
                add_scatter(balls)

        # --- Mouse Events ---
        if event.type == pygame.MOUSEBUTTONDOWN:
            if event.button == 1:  # Left click
                mx, my = pygame.mouse.get_pos()
                for ball in balls:
                    if math.hypot(mx - ball.x, my - ball.y) < ball.radius:
                        selected_ball = ball
                        ball.held = True
                        ball.radius = ENLARGED_RADIUS
                        break
        if event.type == pygame.MOUSEBUTTONUP:
            if event.button == 1 and selected_ball:
                selected_ball.held = False
                selected_ball.radius = BALL_RADIUS
                selected_ball = None

    # --- Held Ball Tracking ---
    if selected_ball:
        mx, my = pygame.mouse.get_pos()
        # Force held ball's predicted position (and current) to the mouse.
        selected_ball.px = mx
        selected_ball.py = my
        selected_ball.x = mx
        selected_ball.y = my
        selected_ball.vx = 0
        selected_ball.vy = 0

    # --- Physics Integration ---
    for ball in balls:
        if not ball.held:
            ball.apply_gravity(dt)
        ball.integrate(dt)

    # --- Build the Grid ---
    grid.clear()
    for ball in balls:
        grid.add(ball)

    # --- Constraint Solving ---
    # (We run a fixed number of iterations per frame; here one pass is used.)
    solve_constraints(balls)

    # --- Update Velocities and Positions from Predicted Positions ---
    for ball in balls:
        ball.update_from_prediction(dt)

    # --- Rendering ---
    screen.fill((0, 0, 0))
    for ball in balls:
        ball.draw(screen)
    pygame.display.flip()

pygame.quit()

