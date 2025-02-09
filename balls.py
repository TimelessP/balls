import pygame
import random
import math

# === Configuration Constants ===
pygame.init()
DEFAULT_WIDTH, DEFAULT_HEIGHT = 800, 800
FULLSCREEN_WIDTH, FULLSCREEN_HEIGHT = 1920, 1080
WIDTH, HEIGHT = DEFAULT_WIDTH, DEFAULT_HEIGHT
FPS = 60
clock = pygame.time.Clock()

# Simulation parameters:
BALL_COUNT = 500
BALL_RADIUS = 15             # Normal ball radius
ENLARGED_RADIUS = 100        # Held ball radius
GRAVITY = 500                # Gravity in px/s²
DAMPING = 0.98               # Global damping (applied during integration)
VELOCITY_CAP = 300         # Maximum allowed speed
MAX_SPEED_FOR_COLOR = 750  # Speed at which ball color is fully red
SCATTER_FORCE = 500        # Base velocity increment on Space press
VELOCITY_ZERO_THRESHOLD = 0.1  # Snap tiny speeds to zero

# Floor snapping parameters:
FLOOR_SNAP_TOLERANCE = 3     # Tolerance (pixels) near the floor for snapping
FLOOR_SNAP_VY_THRESHOLD = 10 # If vertical speed is below this, snap to floor

# Extra (neighbor-based) damping parameters (viscosity)
NEIGHBOR_DAMPING_BASE = 0.90  # Each touching neighbor multiplies velocity by 0.90
NEIGHBOR_DAMPING_MAX = 6      # Count up to 6 neighbors
# VISCOSITY parameter controls the extra damping effect:
# Set VISCOSITY = 0.0 for nearly zero extra damping (i.e. restore prior behavior)
VISCOSITY = 0.0

# Grid settings: fixed cell size of 80 pixels (same as non-fullscreen)
DEFAULT_CELL_SIZE = 80
CELL_SIZE = DEFAULT_CELL_SIZE  # Remains fixed regardless of resolution

# Fullscreen control:
fullscreen = False

# === Create Display Surface ===
screen = pygame.display.set_mode((WIDTH, HEIGHT))

# === Ball Class (PBD-style Integration) ===
class Ball:
    def __init__(self, x, y):
        self.x = x              # Current position
        self.y = y
        self.vx = 0.0           # Velocity
        self.vy = 0.0
        self.radius = BALL_RADIUS
        self.held = False       # True if controlled by the mouse
        self.px = x             # Predicted position (for constraint solving)
        self.py = y

    def apply_gravity(self, dt):
        if not self.held:
            self.vy += GRAVITY * dt

    def integrate(self, dt):
        if not self.held:
            self.px = self.x + self.vx * dt
            self.py = self.y + self.vy * dt

    def enforce_boundaries(self):
        if self.px - self.radius < 0:
            self.px = self.radius
        if self.px + self.radius > WIDTH:
            self.px = WIDTH - self.radius
        if self.py - self.radius < 0:
            self.py = self.radius
        if self.py + self.radius > HEIGHT:
            self.py = HEIGHT - self.radius

    def update_from_prediction(self, dt, grid):
        if not self.held:
            new_vx = (self.px - self.x) / dt
            new_vy = (self.py - self.y) / dt
            # Count touching neighbors using predicted positions.
            n = count_touching_neighbors(self, grid)
            # Extra damping factor: interpolate between no extra damping (1.0) and full extra damping.
            extra_damping = (1 - VISCOSITY) + VISCOSITY * (NEIGHBOR_DAMPING_BASE ** n)
            new_vx *= extra_damping
            new_vy *= extra_damping
            speed = math.hypot(new_vx, new_vy)
            if speed > VELOCITY_CAP:
                scale = VELOCITY_CAP / speed
                new_vx *= scale
                new_vy *= scale
            self.vx = new_vx
            self.vy = new_vy
            self.x = self.px
            self.y = self.py
            # Floor snap: if nearly resting on the floor, force a stable position.
            if self.y + self.radius >= HEIGHT - FLOOR_SNAP_TOLERANCE and abs(self.vy) < FLOOR_SNAP_VY_THRESHOLD:
                self.y = HEIGHT - self.radius
                self.vy = 0
                self.px = self.x
                self.py = self.y
        else:
            self.vx = 0
            self.vy = 0
            self.x = self.px
            self.y = self.py

    def draw(self, surf):
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

# === Grid for Spatial Partitioning (Fixed Cell Size) ===
class Grid:
    def __init__(self):
        self.cells = {}  # Mapping: (cell_x, cell_y) -> list of balls

    def clear(self):
        self.cells.clear()

    def add(self, ball):
        cell_x = int(ball.px // DEFAULT_CELL_SIZE)
        cell_y = int(ball.py // DEFAULT_CELL_SIZE)
        key = (cell_x, cell_y)
        if key not in self.cells:
            self.cells[key] = []
        self.cells[key].append(ball)

    def get_neighbors(self, ball):
        neighbors = []
        cell_x = int(ball.px // DEFAULT_CELL_SIZE)
        cell_y = int(ball.py // DEFAULT_CELL_SIZE)
        for dx in [-1, 0, 1]:
            for dy in [-1, 0, 1]:
                key = (cell_x + dx, cell_y + dy)
                if key in self.cells:
                    neighbors.extend(self.cells[key])
        return neighbors

# === Helper Function: Count Touching Neighbors ===
def count_touching_neighbors(ball, grid):
    count = 0
    for other in grid.get_neighbors(ball):
        if other is ball:
            continue
        dx = ball.px - other.px
        dy = ball.py - other.py
        if math.hypot(dx, dy) < (ball.radius + other.radius + 1):
            count += 1
    return min(count, NEIGHBOR_DAMPING_MAX)

# === Functions for Dynamic Ball Management ===
def add_balls_top(num):
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
    global balls
    if len(balls) <= num:
        balls = []
    else:
        to_remove = random.sample(balls, num)
        for b in to_remove:
            balls.remove(b)

def reposition_ball(ball, all_balls):
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
    global fullscreen, WIDTH, HEIGHT, screen, balls
    fullscreen = not fullscreen
    if fullscreen:
        WIDTH, HEIGHT = FULLSCREEN_WIDTH, FULLSCREEN_HEIGHT
        screen = pygame.display.set_mode((WIDTH, HEIGHT), pygame.FULLSCREEN)
    else:
        WIDTH, HEIGHT = DEFAULT_WIDTH, DEFAULT_HEIGHT
        screen = pygame.display.set_mode((WIDTH, HEIGHT))
    # CELL_SIZE remains fixed.
    for b in balls:
        if (b.x - b.radius < 0 or b.x + b.radius > WIDTH or
            b.y - b.radius < 0 or b.y + b.radius > HEIGHT or
            b.y > HEIGHT - 150):
            reposition_ball(b, balls)

def add_scatter(balls):
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
selected_ball = None

def solve_constraints(balls):
    for ball in balls:
        ball.enforce_boundaries()
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

running = True
while running:
    dt = clock.tick(FPS) / 1000
    for event in pygame.event.get():
        if event.type == pygame.QUIT:
            running = False
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
        if event.type == pygame.MOUSEBUTTONDOWN:
            if event.button == 1:
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

    if selected_ball:
        mx, my = pygame.mouse.get_pos()
        selected_ball.px = mx
        selected_ball.py = my
        selected_ball.x = mx
        selected_ball.y = my
        selected_ball.vx = 0
        selected_ball.vy = 0

    for ball in balls:
        if not ball.held:
            ball.apply_gravity(dt)
        ball.integrate(dt)

    grid.clear()
    for ball in balls:
        grid.add(ball)

    solve_constraints(balls)

    grid.clear()
    for ball in balls:
        grid.add(ball)

    for ball in balls:
        ball.update_from_prediction(dt, grid)

    for ball in balls:
        if not ball.held and (ball.y + ball.radius >= HEIGHT - FLOOR_SNAP_TOLERANCE) and (abs(ball.vy) < FLOOR_SNAP_VY_THRESHOLD):
            ball.y = HEIGHT - ball.radius
            ball.vy = 0
            ball.px = ball.x
            ball.py = ball.y

    screen.fill((0, 0, 0))
    for ball in balls:
        ball.draw(screen)
    pygame.display.flip()

pygame.quit()

