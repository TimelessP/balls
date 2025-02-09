import pygame
import random
import math

# === Configuration Constants ===
pygame.init()
WIDTH, HEIGHT = 800, 800
FPS = 60
clock = pygame.time.Clock()

BALL_COUNT = 500
BALL_RADIUS = 15              # Normal ball radius
ENLARGED_RADIUS = 100         # Radius when a ball is held
GRAVITY = 500                 # Gravity (px/s²)
DAMPING = 0.995               # Damping factor for velocity
VELOCITY_CAP = 300            # Maximum allowed speed
MAX_SPEED_FOR_COLOR = 750     # Speed at which ball color is fully red
NUM_CONSTRAINT_ITERATIONS = 5 # Number of constraint iterations per frame
SCATTER_FORCE = 500           # Base velocity increment when Space is pressed

# **** Create the display surface ****
screen = pygame.display.set_mode((WIDTH, HEIGHT))

# === Ball Class (using PBD) ===
class Ball:
    def __init__(self, x, y):
        # Current position:
        self.x = x
        self.y = y
        # Velocity:
        self.vx = 0.0
        self.vy = 0.0
        self.radius = BALL_RADIUS
        self.held = False  # When held, the ball follows the mouse and is not updated by physics.
        # Predicted position (used in constraint solving):
        self.px = x
        self.py = y

    def apply_gravity(self, dt):
        if not self.held:
            self.vy += GRAVITY * dt

    def integrate(self, dt):
        if not self.held:
            # Predict new position using current velocity.
            self.px = self.x + self.vx * dt
            self.py = self.y + self.vy * dt
        # For held balls, we force their predicted position to follow the mouse.

    def enforce_boundaries(self):
        # Clamp predicted positions so that the ball stays entirely within the screen.
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
            # Update velocity from the difference between predicted and current positions.
            new_vx = (self.px - self.x) / dt
            new_vy = (self.py - self.y) / dt
            speed = math.hypot(new_vx, new_vy)
            if speed > VELOCITY_CAP:
                scale = VELOCITY_CAP / speed
                new_vx *= scale
                new_vy *= scale
            self.vx = new_vx
            self.vy = new_vy
            # Update current position:
            self.x = self.px
            self.y = self.py
        else:
            self.vx = 0
            self.vy = 0
            self.x = self.px
            self.y = self.py

    def draw(self, surf):
        if self.held:
            color = (255, 255, 0)  # Held ball always yellow.
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

# === Constraint Solver ===
def solve_constraints(balls):
    # First, enforce boundaries on predicted positions.
    for ball in balls:
        ball.enforce_boundaries()
    # Then, for each pair of balls, if their predicted positions overlap, push them apart.
    n = len(balls)
    for i in range(n):
        for j in range(i + 1, n):
            b1 = balls[i]
            b2 = balls[j]
            dx = b2.px - b1.px
            dy = b2.py - b1.py
            dist = math.hypot(dx, dy)
            min_dist = b1.radius + b2.radius
            if dist < min_dist and dist > 0:
                overlap = min_dist - dist
                ux = dx / dist
                uy = dy / dist
                if b1.held and not b2.held:
                    # Held ball remains fixed; move b2 fully.
                    b2.px += ux * overlap
                    b2.py += uy * overlap
                elif b2.held and not b1.held:
                    b1.px -= ux * overlap
                    b1.py -= uy * overlap
                else:
                    correction = overlap / 2
                    b1.px -= ux * correction
                    b1.py -= uy * correction
                    b2.px += ux * correction
                    b2.py += uy * correction

# === Scatter Function ===
def add_scatter(balls):
    # Each Space press adds a random velocity increment (accumulating over presses) to every free ball.
    for ball in balls:
        if not ball.held:
            angle = random.uniform(0, 2 * math.pi)
            delta = random.uniform(0.5, 1.5) * SCATTER_FORCE
            ball.vx += math.cos(angle) * delta
            ball.vy += math.sin(angle) * delta

# === Create Balls ===
balls = []
for _ in range(BALL_COUNT):
    x = random.uniform(BALL_RADIUS, WIDTH - BALL_RADIUS)
    y = random.uniform(BALL_RADIUS, HEIGHT - BALL_RADIUS)
    balls.append(Ball(x, y))
selected_ball = None  # Ball currently held by the mouse

# === Main Loop ===
running = True
while running:
    dt = clock.tick(FPS) / 1000  # Delta time (seconds per frame)
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
        # Force the held ball’s predicted and current position to exactly follow the mouse.
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

    # --- Constraint Solving ---
    # Run a fixed number of constraint iterations.
    for _ in range(NUM_CONSTRAINT_ITERATIONS):
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

