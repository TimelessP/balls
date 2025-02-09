import pygame
import random
import math

# === Configuration Constants ===
pygame.init()
DEFAULT_WIDTH, DEFAULT_HEIGHT = 800, 800
# Fullscreen resolution as specified:
FULLSCREEN_WIDTH, FULLSCREEN_HEIGHT = 1920, 1080
WIDTH, HEIGHT = DEFAULT_WIDTH, DEFAULT_HEIGHT
FPS = 60
clock = pygame.time.Clock()

# Simulation parameters:
BALL_COUNT = 500
BALL_RADIUS = 15             # Normal ball radius
ENLARGED_RADIUS = 100        # Radius when a ball is held
GRAVITY = 500                # Gravity (px/s²)
DAMPING = 0.98               # Damping factor (lower value dissipates energy faster)
VELOCITY_CAP = 300         # Maximum allowed speed
MAX_SPEED_FOR_COLOR = 750  # Speed at which ball color is fully red
SCATTER_FORCE = 500        # Base velocity increment on Space press
VELOCITY_ZERO_THRESHOLD = 0.1  # Snap tiny speeds to zero

# For floor stabilization: if after update a free ball is at the bottom and its vertical speed is low, snap it.
FLOOR_SNAP_VY_THRESHOLD = 5   # px/s
FLOOR_SNAP_TOLERANCE = 1      # pixel

# Grid settings: use a fixed cell size of 80 pixels (non-fullscreen cell size)
DEFAULT_CELL_SIZE = 80
CELL_SIZE = DEFAULT_CELL_SIZE  # remains fixed even in fullscreen

# Fullscreen control:
fullscreen = False

# === Create Display Surface ===
screen = pygame.display.set_mode((WIDTH, HEIGHT))

# === Ball Class (PBD-style Integration) ===
class Ball:
    def __init__(self, x, y):
        # Current position:
        self.x = x
        self.y = y
        # Velocity:
        self.vx = 0.0
        self.vy = 0.0
        self.radius = BALL_RADIUS
        self.held = False  # When True, the ball is fixed to the mouse.
        # Predicted position (for constraint solving):
        self.px = x
        self.py = y

    def apply_gravity(self, dt):
        if not self.held:
            self.vy += GRAVITY * dt

    def integrate(self, dt):
        if not self.held:
            self.px = self.x + self.vx * dt
            self.py = self.y + self.vy * dt

    def enforce_boundaries(self):
        # Clamp predicted positions so that the ball remains fully inside the client area.
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
            new_vx = (self.px - self.x) / dt
            new_vy = (self.py - self.y) / dt
            speed = math.hypot(new_vx, new_vy)
            if speed > VELOCITY_CAP:
                scale = VELOCITY_CAP / speed
                new_vx *= scale
                new_vy *= scale
            self.vx = new_vx
            self.vy = new_vy
            self.x = self.px
            self.y = self.py
            # If the ball is nearly resting on the floor, snap it.
            if self.y + self.radius >= HEIGHT - FLOOR_SNAP_TOLERANCE and abs(self.vy) < FLOOR_SNAP_VY_THRESHOLD:
                self.y = HEIGHT - self.radius
                self.vy = 0
                self.py = self.y
        else:
            self.vx = 0
            self.vy = 0
            self.x = self.px
            self.y = self.py

    def draw(self, surf):
        if self.held:
            color = (255, 255, 0)  # Held ball is yellow.
        else:
            speed = math.hypot(self.vx, self.vy)
            if speed < 1:
                color = (0, 255, 0)  # Nearly static: green.
            else:
                ratio = min(speed / MAX_SPEED_FOR_COLOR, 1.0)
                r = int(255 * ratio)
                g = int(255 * (1 - ratio))
                color = (r, g, 0)
        pygame.draw.circle(surf, color, (int(self.x), int(self.y)), self.radius)

# === Grid for Spatial Partitioning (Fixed Cell Size) ===
class Grid:
    def __init__(self):
        self.cells = {}  # Mapping: (cell_x, cell_y) -> list of balls

    def clear(self):
        self.cells.clear()

    def add(self, ball):
        # Use fixed DEFAULT_CELL_SIZE.
        cell_x = int(ball.x // DEFAULT_CELL_SIZE)
        cell_y = int(ball.y // DEFAULT_CELL_SIZE)
        key = (cell_x, cell_y)
        if key not in self.cells:
            self.cells[key] = []
        self.cells[key].append(ball)

    def get_neighbors(self, ball):
        neighbors = []
        cell_x = int(ball.x // DEFAULT_CELL_SIZE)
        cell_y = int(ball.y // DEFAULT_CELL_SIZE)
        for dx in [-1, 0, 1]:
            for dy in [-1, 0, 1]:
                key = (cell_x + dx, cell_y + dy)
                if key in self.cells:
                    neighbors.extend(self.cells[key])
        return neighbors

# === Functions for Dynamic Ball Management ===

def add_balls_top(num):
    """Add 'num' new non-overlapping balls randomly in the top 100 pixels of the client area."""
    global balls, WIDTH, HEIGHT
    count = 0
    attempts = 0
    while count < num and attempts < 1000:
        x = random.uniform(BALL_RADIUS, WIDTH - BALL_RADIUS)
        y = random.uniform(BALL_RADIUS, BALL_RADIUS + 100)
        candidate = Ball(x, y)
        overlap = False
        for b in balls:
            if math.hypot(candidate.x - b.x, candidate.y - b.y) < candidate.radius + b.radius:
                overlap = True
                break
        if not overlap:
            balls.append(candidate)
            count += 1
        attempts += 1

def remove_random_balls(num):
    """Remove 'num' random balls from the scene."""
    global balls
    if len(balls) <= num:
        balls = []
    else:
        to_remove = random.sample(balls, num)
        for b in to_remove:
            balls.remove(b)

def reposition_ball(ball, all_balls):
    """Reposition a ball randomly in the top region (y between BALL_RADIUS and BALL_RADIUS+100)
       ensuring no overlap with any other ball."""
    attempts = 0
    while attempts < 100:
        candidate_x = random.uniform(BALL_RADIUS, WIDTH - BALL_RADIUS)
        candidate_y = random.uniform(BALL_RADIUS, BALL_RADIUS + 100)
        overlap = False
        for other in all_balls:
            if other is ball:
                continue
            if math.hypot(candidate_x - other.x, candidate_y - other.y) < ball.radius + other.radius:
                overlap = True
                break
        if not overlap:
            ball.x = candidate_x
            ball.y = candidate_y
            ball.px = candidate_x
            ball.py = candidate_y
            return
        attempts += 1
    ball.x = max(ball.radius, min(ball.x, WIDTH - ball.radius))
    ball.y = max(ball.radius, min(ball.y, HEIGHT - ball.radius))
    ball.px = ball.x
    ball.py = ball.y

def toggle_fullscreen():
    """Toggle fullscreen mode to 1920x1080. On toggling, reposition any ball that is out-of-bound
       or too near the bottom by adding it randomly at the top."""
    global fullscreen, WIDTH, HEIGHT, screen, balls
    fullscreen = not fullscreen
    if fullscreen:
        WIDTH, HEIGHT = FULLSCREEN_WIDTH, FULLSCREEN_HEIGHT
        screen = pygame.display.set_mode((WIDTH, HEIGHT), pygame.FULLSCREEN)
    else:
        WIDTH, HEIGHT = DEFAULT_WIDTH, DEFAULT_HEIGHT
        screen = pygame.display.set_mode((WIDTH, HEIGHT))
    # CELL_SIZE remains fixed at DEFAULT_CELL_SIZE.
    for b in balls:
        if (b.x - b.radius < 0 or b.x + b.radius > WIDTH or
            b.y - b.radius < 0 or b.y + b.radius > HEIGHT or
            b.y > HEIGHT - 150):  # if too near the bottom
            reposition_ball(b, balls)

def add_scatter(balls):
    """Each Space press adds a random velocity increment to every free ball."""
    for ball in balls:
        if not ball.held:
            angle = random.uniform(0, 2 * math.pi)
            delta = random.uniform(0.5, 1.5) * SCATTER_FORCE
            ball.vx += math.cos(angle) * delta
            ball.vy += math.sin(angle) * delta

# === Initial Non-Overlapping Placement of Balls ===
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
selected_ball = None  # Currently held ball (if any)

# === Constraint Solver (Single-Pass) ===
def solve_constraints(balls):
    # Enforce boundaries on predicted positions.
    for ball in balls:
        ball.enforce_boundaries()
    # For each ball, check its neighbors and resolve overlaps.
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
                ux = dx / dist
                uy = dy / dist
                if ball.held and not other.held:
                    other.px += ux * overlap
                    other.py += uy * overlap
                elif other.held and not ball.held:
                    ball.px -= ux * overlap
                    ball.py -= uy * overlap
                else:
                    correction = overlap / 2
                    ball.px -= ux * correction
                    ball.py -= uy * correction
                    other.px += ux * correction
                    other.py += uy * correction

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
            if event.key == pygame.K_1:
                add_balls_top(20)
            if event.key == pygame.K_2:
                remove_random_balls(20)
            if event.key == pygame.K_F11:
                toggle_fullscreen()

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
    solve_constraints(balls)

    # --- Update Velocities and Positions from Predictions ---
    for ball in balls:
        ball.update_from_prediction(dt)

    # --- Rendering ---
    screen.fill((0, 0, 0))
    for ball in balls:
        ball.draw(screen)
    pygame.display.flip()

pygame.quit()

