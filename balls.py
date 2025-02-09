import pygame
import random
import math

# Pygame setup
pygame.init()
WIDTH, HEIGHT = 800, 800
CELL_SIZE = WIDTH // 20  # 20x20 grid
GRAVITY = 500  # Pixels per second squared
BALL_COUNT = 500
BALL_RADIUS = 15
ENLARGED_RADIUS = 100
SCATTER_FORCE = 500
SLEEP_VELOCITY_THRESHOLD = 1  # Prevent jitter
DAMPING = 0.995  # Slightly stronger damping to reduce jitter
FRICTION = 0.999999  # Extreme reduction in friction effects
CORRECTION_DAMPING = 0.75  # Softer position correction to stop jitter
HELD_REPULSION_FORCE = 5000  # Strong push force for held ball
VELOCITY_CAP = 300  # Prevents jittery high-speed movement
FPS = 60

screen = pygame.display.set_mode((WIDTH, HEIGHT))
clock = pygame.time.Clock()

# Ball class
class Ball:
    def __init__(self, x, y):
        self.x, self.y = x, y
        self.vx, self.vy = 0, 0
        self.radius = BALL_RADIUS
        self.held = False

    def update(self, dt):
        if self.held:
            return  # Held ball ignores physics

        self.vy += GRAVITY * dt  # Apply gravity
        self.vx *= DAMPING  # Apply damping
        self.vy *= DAMPING

        self.x += self.vx * dt
        self.y += self.vy * dt

        # Apply velocity cap to prevent extreme bouncing
        speed = math.hypot(self.vx, self.vy)
        if speed > VELOCITY_CAP:
            scale = VELOCITY_CAP / speed
            self.vx *= scale
            self.vy *= scale

        # HARD BOUNDARY ENFORCEMENT
        if self.x - self.radius < 0:
            self.x = self.radius
            self.vx = 0
        if self.x + self.radius > WIDTH:
            self.x = WIDTH - self.radius
            self.vx = 0
        if self.y + self.radius >= HEIGHT:
            self.y = HEIGHT - self.radius
            self.vy = 0

    def get_color(self):
        speed = math.hypot(self.vx, self.vy)
        speed_ratio = min(speed / GRAVITY, 1.0)  # Clamp between 0 and 1
        
        r = int(255 * speed_ratio)  # Scale red component
        g = int(255 * (1 - speed_ratio))  # Scale green component inversely
        return (r, g, 0)

    def draw(self, screen):
        pygame.draw.circle(screen, self.get_color(), (int(self.x), int(self.y)), self.radius)

# Grid system
class Grid:
    def __init__(self):
        self.cells = {}

    def clear(self):
        self.cells.clear()

    def add(self, ball):
        cell_x, cell_y = int(ball.x // CELL_SIZE), int(ball.y // CELL_SIZE)
        if (cell_x, cell_y) not in self.cells:
            self.cells[(cell_x, cell_y)] = []
        self.cells[(cell_x, cell_y)].append(ball)

    def get_neighbors(self, ball):
        neighbors = []
        cell_x, cell_y = int(ball.x // CELL_SIZE), int(ball.y // CELL_SIZE)
        for dx in [-1, 0, 1]:
            for dy in [-1, 0, 1]:
                if (cell_x + dx, cell_y + dy) in self.cells:
                    neighbors.extend(self.cells[(cell_x + dx, cell_y + dy)])
        return neighbors

# Ball simulation
balls = [Ball(random.uniform(10, WIDTH - 10), random.uniform(10, HEIGHT - 10)) for _ in range(BALL_COUNT)]
grid = Grid()
selected_ball = None
running = True

while running:
    dt = clock.tick(FPS) / 1000  # Time step in seconds

    # Event handling
    for event in pygame.event.get():
        if event.type == pygame.QUIT:
            running = False
        if event.type == pygame.KEYDOWN:
            if event.key in (pygame.K_ESCAPE, pygame.K_q):
                running = False
            if event.key == pygame.K_SPACE:
                for ball in balls:
                    angle = random.uniform(0, 2 * math.pi)
                    force = random.uniform(0.5, 1.5) * SCATTER_FORCE
                    ball.vx += math.cos(angle) * force
                    ball.vy += math.sin(angle) * force

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

    # Move selected ball with the mouse
    if selected_ball:
        mx, my = pygame.mouse.get_pos()
        selected_ball.x, selected_ball.y = mx, my
        selected_ball.vx = selected_ball.vy = 0  # Absolute positioning

    # Update physics
    grid.clear()
    for ball in balls:
        grid.add(ball)

    for ball in balls:
        ball.update(dt)

        # Collision detection with neighbors
        for other in grid.get_neighbors(ball):
            if other is not ball:
                dx, dy = other.x - ball.x, other.y - ball.y
                dist = math.hypot(dx, dy)
                overlap = (ball.radius + other.radius) - dist

                if overlap > 0:
                    angle = math.atan2(dy, dx)
                    correction = (overlap / 2) * CORRECTION_DAMPING  

                    # Special handling for held ball
                    if ball.held:
                        force = (overlap / (ball.radius + other.radius)) * HELD_REPULSION_FORCE
                        other.vx += math.cos(angle) * force
                        other.vy += math.sin(angle) * force
                    else:
                        ball.x -= math.cos(angle) * correction
                        ball.y -= math.sin(angle) * correction
                        other.x += math.cos(angle) * correction
                        other.y += math.sin(angle) * correction

                    # Ensure balls don't jitter by applying softer friction
                    ball.vx *= FRICTION
                    ball.vy *= FRICTION
                    other.vx *= FRICTION
                    other.vy *= FRICTION

    # Rendering
    screen.fill((0, 0, 0))
    for ball in balls:
        ball.draw(screen)
    pygame.display.flip()

pygame.quit()

