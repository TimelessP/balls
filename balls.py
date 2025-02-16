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
ENLARGED_RADIUS = 100        # Held-ball (enlarged) radius
GRAVITY = 500                # Gravity (px/s²)
DAMPING = 0.98               # Global damping (applied during integration)
VELOCITY_CAP = 300           # Normal maximum allowed speed
THROWN_VELOCITY_CAP = VELOCITY_CAP * 2  # Thrown balls can exceed normal speed
MAX_SPEED_FOR_COLOR = 750    # Speed at which ball color is fully red
SCATTER_FORCE = 500          # Base velocity for scatter
VELOCITY_ZERO_THRESHOLD = 0.1  # Threshold to snap tiny speeds to zero

# Floor snapping parameters:
FLOOR_SNAP_TOLERANCE = 3     
FLOOR_SNAP_VY_THRESHOLD = 10 

# Extra damping parameters:
NEIGHBOR_DAMPING_BASE = 0.90  
NEIGHBOR_DAMPING_MAX = 6      
VISCOSITY = 0.0               

# Grid settings:
DEFAULT_CELL_SIZE = 80
CELL_SIZE = DEFAULT_CELL_SIZE  

# Container parameters:
CONTAINER_RADIUS = 150  # Radius of the container circle

# Fullscreen control:
fullscreen = False

# Size transition parameters:
PICKUP_TRANSITION_TIME = 1.0   # Seconds for a ball to grow when picked up
RELEASE_TRANSITION_TIME = 3.0  # Seconds for a ball to shrink after release

# Throw multiplier:
THROW_MULTIPLIER = 8.0  # Multiplier for throw velocity

# Mouse velocity calculation settings:
MOUSE_VELOCITY_TIME_WINDOW = 0.5  # Seconds over which to compute average mouse velocity

# Jitter and spring settings for contained balls:
CONTAINER_JITTER_SPEED = 50.0     # Maximum jitter speed (pixels per second)
OFFSET_SPRING_THRESHOLD = 0.7      # Fraction of max offset beyond which spring is applied
OFFSET_SPRING_FACTOR = 0.9         # Factor to pull offset inward if exceeded

# === Global Variables ===
mouse_history = []  # List of (timestamp, (x, y))
current_mouse_velocity = (0, 0)

# Create the display surface and assign it to the global variable 'screen'
screen = pygame.display.set_mode((WIDTH, HEIGHT), pygame.RESIZABLE)

# === Helper Function: Count Touching Neighbors ===
def count_touching_neighbors(ball, grid):
    count = 0
    for other in grid.get_neighbors(ball):
        if other is ball:
            continue
        if isinstance(other, Container):
            continue
        dx = ball.px - other.px
        dy = ball.py - other.py
        if math.hypot(dx, dy) < (ball.radius + other.radius + 1):
            count += 1
    return min(count, NEIGHBOR_DAMPING_MAX)

# === Class Definitions ===

class Ball:
    def __init__(self, x, y):
        self.x = x              # Current position
        self.y = y
        self.vx = 0.0           # Velocity components
        self.vy = 0.0
        self.radius = BALL_RADIUS
        self.held = False       # Held by left-click
        self.contained = False  # Captured by container mode
        self.offset = (0, 0)    # Relative offset if contained
        self.pickup_timer = 0.0
        self.release_timer = 0.0
        self.release_start_radius = BALL_RADIUS  # Size at moment of release
        self.px = x             # Predicted position (for collisions)
        self.py = y

    def update_size(self, dt):
        if self.held:
            if self.pickup_timer > 0:
                self.pickup_timer -= dt
                if self.pickup_timer < 0:
                    self.pickup_timer = 0
                fraction = 1 - (self.pickup_timer / PICKUP_TRANSITION_TIME)
                self.radius = BALL_RADIUS + (ENLARGED_RADIUS - BALL_RADIUS) * fraction
            else:
                self.radius = ENLARGED_RADIUS
        elif not self.held and self.release_timer > 0:
            self.release_timer -= dt
            if self.release_timer < 0:
                self.release_timer = 0
            fraction = self.release_timer / RELEASE_TRANSITION_TIME
            self.radius = BALL_RADIUS + (self.release_start_radius - BALL_RADIUS) * fraction
        else:
            self.radius = BALL_RADIUS

    def apply_gravity(self, dt):
        if not self.held and not self.contained:
            self.vy += GRAVITY * dt

    def integrate(self, dt):
        if not self.held and not self.contained:
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
        if not self.held and not self.contained:
            new_vx = (self.px - self.x) / dt
            new_vy = (self.py - self.y) / dt
            n = count_touching_neighbors(self, grid)
            extra_damping = (1 - VISCOSITY) + VISCOSITY * (NEIGHBOR_DAMPING_BASE ** n)
            new_vx *= extra_damping
            new_vy *= extra_damping
            speed = math.hypot(new_vx, new_vy)
            cap = THROWN_VELOCITY_CAP if self.release_timer > 0 else VELOCITY_CAP
            if speed > cap:
                scale = cap / speed
                new_vx *= scale
                new_vy *= scale
            self.vx = new_vx
            self.vy = new_vy
            self.x = self.px
            self.y = self.py
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
        elif self.contained:
            color = (0, 255, 255)  # Cyan for contained balls
        else:
            speed = math.hypot(self.vx, self.vy)
            if speed < 1:
                color = (0, 255, 0)
            else:
                ratio = min(speed / MAX_SPEED_FOR_COLOR, 1.0)
                r = int(255 * ratio)
                g = int(255 * (1 - ratio))
                color = (r, g, 0)
        pygame.draw.circle(surf, color, (int(self.x), int(self.y)), int(self.radius))


class Container:
    def __init__(self, x, y, radius):
        self.x = x              # Current position
        self.y = y
        self.radius = radius
        self.held = True        # Container is immovable
        self.px = x             # Predicted position (for collisions)
        self.py = y
    def update(self, new_x, new_y):
        self.x = new_x
        self.y = new_y
        self.px = new_x
        self.py = new_y
    def enforce_boundaries(self):
        if self.x - self.radius < 0:
            self.x = self.radius
        if self.x + self.radius > WIDTH:
            self.x = WIDTH - self.radius
        if self.y - self.radius < 0:
            self.y = self.radius
        if self.y + self.radius > HEIGHT:
            self.y = HEIGHT - self.radius
        self.px = self.x
        self.py = self.y
    def draw(self, surf):
        pygame.draw.circle(surf, (255, 255, 255), (int(self.x), int(self.y)), self.radius, 2)


class Grid:
    def __init__(self):
        self.cells = {}  # Mapping: (cell_x, cell_y) -> list of objects

    def clear(self):
        self.cells.clear()

    def add(self, obj):
        if isinstance(obj, Container):
            pos_x = obj.x
            pos_y = obj.y
        else:
            pos_x = obj.px
            pos_y = obj.py
        cell_x = int(pos_x // DEFAULT_CELL_SIZE)
        cell_y = int(pos_y // DEFAULT_CELL_SIZE)
        key = (cell_x, cell_y)
        if key not in self.cells:
            self.cells[key] = []
        self.cells[key].append(obj)

    def get_neighbors(self, obj):
        neighbors = []
        if isinstance(obj, Container):
            pos_x = obj.x
            pos_y = obj.y
        else:
            pos_x = obj.px
            pos_y = obj.py
        cell_x = int(pos_x // DEFAULT_CELL_SIZE)
        cell_y = int(pos_y // DEFAULT_CELL_SIZE)
        for dx in [-1, 0, 1]:
            for dy in [-1, 0, 1]:
                key = (cell_x + dx, cell_y + dy)
                if key in self.cells:
                    neighbors.extend(self.cells[key])
        return neighbors

# === Collision Solver Functions ===

def solve_free_constraints(objects):
    for obj in objects:
        obj.enforce_boundaries()
    for obj in objects:
        neighbors = grid.get_neighbors(obj)
        for other in neighbors:
            if other is obj:
                continue
            dx = other.px - obj.px
            dy = other.py - obj.py
            dist = math.hypot(dx, dy)
            if dist == 0:
                continue
            min_dist = obj.radius + other.radius
            if dist < min_dist:
                overlap = min_dist - dist
                ux = dx / dist
                uy = dy / dist
                if (hasattr(obj, 'held') and obj.held) or (hasattr(obj, 'contained') and obj.contained):
                    other.px += ux * overlap
                    other.py += uy * overlap
                elif (hasattr(other, 'held') and other.held) or (hasattr(other, 'contained') and other.contained):
                    obj.px -= ux * overlap
                    obj.py -= uy * overlap
                else:
                    correction = overlap / 2
                    obj.px -= ux * correction
                    obj.py -= uy * correction
                    other.px += ux * correction
                    other.py += uy * correction

def solve_contained_collisions(contained_objects, container):
    # Solve collisions among contained balls:
    for i in range(len(contained_objects)):
        for j in range(i + 1, len(contained_objects)):
            ball1 = contained_objects[i]
            ball2 = contained_objects[j]
            dx = ball2.x - ball1.x
            dy = ball2.y - ball1.y
            dist = math.hypot(dx, dy)
            min_dist = ball1.radius + ball2.radius
            if dist < min_dist and dist > 0:
                overlap = min_dist - dist
                shift_x = (dx / dist) * (overlap / 2)
                shift_y = (dy / dist) * (overlap / 2)
                ball1.x -= shift_x
                ball1.y -= shift_y
                ball2.x += shift_x
                ball2.y += shift_y
                ball1.px = ball1.x
                ball1.py = ball1.y
                ball2.px = ball2.x
                ball2.py = ball2.y
    # Force each contained ball to remain inside the container:
    for ball in contained_objects:
        dx = ball.x - container.x
        dy = ball.y - container.y
        dist = math.hypot(dx, dy)
        max_offset = container.radius - ball.radius
        if dist > max_offset and dist > 0:
            overlap = dist - max_offset
            ball.x -= (dx / dist) * overlap
            ball.y -= (dy / dist) * overlap
            ball.px = ball.x
            ball.py = ball.y

# === Dynamic Ball Management Functions ===
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
    global fullscreen, WIDTH, HEIGHT, screen, balls, container
    fullscreen = not fullscreen
    if fullscreen:
        WIDTH, HEIGHT = FULLSCREEN_WIDTH, FULLSCREEN_HEIGHT
        screen = pygame.display.set_mode((WIDTH, HEIGHT), pygame.FULLSCREEN)
    else:
        WIDTH, HEIGHT = DEFAULT_WIDTH, DEFAULT_HEIGHT
        screen = pygame.display.set_mode((WIDTH, HEIGHT))
    for b in balls:
        if (b.x - b.radius < 0 or b.x + b.radius > WIDTH or
            b.y - b.radius < 0 or b.y + b.radius > HEIGHT or
            b.y > HEIGHT - 150):
            reposition_ball(b, balls)
    if container is not None:
        if (container.x - container.radius < 0 or container.x + container.radius > WIDTH or
            container.y - container.radius < 0 or container.y + container.radius > HEIGHT or
            container.y > HEIGHT - 150):
            container.x = WIDTH / 2
            container.y = BALL_RADIUS + 50
            container.px = container.x
            container.py = container.y

def add_scatter(balls):
    for ball in balls:
        if not ball.held and not ball.contained:
            angle = random.uniform(0, 2 * math.pi)
            delta = random.uniform(0.5, 1.5) * SCATTER_FORCE
            ball.vx += math.cos(angle) * delta
            ball.vy += math.sin(angle) * delta

# === Global Variables for Balls, Container, and Mouse Tracking ===
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

container = None  # Global container, initially None.
grid = Grid()
selected_ball = None  # For held-ball mode (left-click)

mouse_history = []  # List of (timestamp, (x, y))
current_mouse_velocity = (0, 0)

# === Main Loop ===
running = True
while running:
    dt = clock.tick(FPS) / 1000
    current_time = pygame.time.get_ticks() / 1000.0
    for event in pygame.event.get():
        if event.type == pygame.QUIT:
            running = False
        if event.type == pygame.VIDEORESIZE:  # Detect window resizing
            WIDTH, HEIGHT = event.w, event.h
            # we can't do this whilst resizing because it destroys the window:
            # screen = pygame.display.set_mode((WIDTH, HEIGHT), pygame.RESIZABLE)
            for ball in balls:
                if (ball.x - ball.radius < 0 or ball.x + ball.radius > WIDTH or
                    ball.y - ball.radius < 0 or ball.y + ball.radius > HEIGHT or
                    ball.y > HEIGHT - 150):
                    reposition_ball(ball, balls)
            if container is not None:
                if (container.x - container.radius < 0 or container.x + container.radius > WIDTH or
                    container.y - container.radius < 0 or container.y + container.radius > HEIGHT or
                    container.y > HEIGHT - 150):
                    container.x = WIDTH / 2
                    container.y = BALL_RADIUS + 50
                    container.px = container.x
                    container.py = container.y

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
        if event.type == pygame.MOUSEMOTION:
            mouse_history.append((current_time, event.pos))
            while mouse_history and current_time - mouse_history[0][0] > MOUSE_VELOCITY_TIME_WINDOW:
                mouse_history.pop(0)
            if len(mouse_history) >= 2:
                old_time, old_pos = mouse_history[0]
                dt_mouse = current_time - old_time
                if dt_mouse > 0:
                    dx = event.pos[0] - old_pos[0]
                    dy = event.pos[1] - old_pos[1]
                    current_mouse_velocity = (dx / dt_mouse, dy / dt_mouse)
                else:
                    current_mouse_velocity = (0, 0)
            else:
                current_mouse_velocity = (0, 0)
        if event.type == pygame.MOUSEBUTTONDOWN:
            mouse_history.clear()
            current_mouse_velocity = (0, 0)
            if event.button == 3:
                mx, my = pygame.mouse.get_pos()
                if container is None:
                    container = Container(mx, my, CONTAINER_RADIUS)
                    for ball in balls:
                        if math.hypot(ball.x - container.x, ball.y - container.y) < container.radius:
                            ball.contained = True
                            max_offset = container.radius - ball.radius
                            r = math.sqrt(random.random()) * max_offset
                            theta = random.uniform(0, 2*math.pi)
                            ball.offset = (r * math.cos(theta), r * math.sin(theta))
                            ball.x = container.x + ball.offset[0]
                            ball.y = container.y + ball.offset[1]
                            ball.px = ball.x
                            ball.py = ball.y
            elif event.button == 1:
                mx, my = pygame.mouse.get_pos()
                for ball in balls:
                    if math.hypot(mx - ball.x, my - ball.y) < ball.radius:
                        selected_ball = ball
                        ball.held = True
                        ball.pickup_timer = PICKUP_TRANSITION_TIME
                        break
        if event.type == pygame.MOUSEBUTTONUP:
            if event.button == 3 and container is not None:
                for ball in balls:
                    if ball.contained:
                        ball.vx = current_mouse_velocity[0] * THROW_MULTIPLIER
                        ball.vy = current_mouse_velocity[1] * THROW_MULTIPLIER
                        if ball.radius > BALL_RADIUS:
                            ball.release_timer = RELEASE_TRANSITION_TIME
                        ball.contained = False
                        ball.offset = (0, 0)
                container = None
            if event.button == 1 and selected_ball is not None:
                selected_ball.vx = current_mouse_velocity[0] * THROW_MULTIPLIER
                selected_ball.vy = current_mouse_velocity[1] * THROW_MULTIPLIER
                selected_ball.held = False
                selected_ball.release_timer = RELEASE_TRANSITION_TIME
                selected_ball.release_start_radius = selected_ball.radius
                selected_ball = None

    if container is not None and not pygame.mouse.get_pressed()[2]:
        container = None
        for ball in balls:
            ball.contained = False
            ball.offset = (0, 0)

    if container is not None:
        mx, my = pygame.mouse.get_pos()
        container.update(mx, my)
        # Update contained balls with jitter and ensure they stay inside the container.
        contained_balls = [ball for ball in balls if ball.contained]
        for ball in contained_balls:
            jitter_dx = random.uniform(-CONTAINER_JITTER_SPEED, CONTAINER_JITTER_SPEED) * dt
            jitter_dy = random.uniform(-CONTAINER_JITTER_SPEED, CONTAINER_JITTER_SPEED) * dt
            new_offset_x = ball.offset[0] + jitter_dx
            new_offset_y = ball.offset[1] + jitter_dy
            max_offset = container.radius - ball.radius
            current_offset = math.hypot(new_offset_x, new_offset_y)
            if current_offset > OFFSET_SPRING_THRESHOLD * max_offset:
                new_offset_x *= OFFSET_SPRING_FACTOR
                new_offset_y *= OFFSET_SPRING_FACTOR
            ball.offset = (new_offset_x, new_offset_y)
            ball.x = container.x + ball.offset[0]
            ball.y = container.y + ball.offset[1]
            ball.px = ball.x
            ball.py = ball.y

    if selected_ball is not None:
        mx, my = pygame.mouse.get_pos()
        selected_ball.px = mx
        selected_ball.py = my
        selected_ball.x = mx
        selected_ball.y = my
        selected_ball.vx = 0
        selected_ball.vy = 0

    for ball in balls:
        ball.update_size(dt)
    for ball in balls:
        if not ball.held and not ball.contained:
            ball.apply_gravity(dt)
        ball.integrate(dt)

    # --- Solve collisions for free balls ---
    free_balls = [b for b in balls if not b.contained]
    free_objects = free_balls.copy()
    if container is not None:
        free_objects.append(container)
    solve_free_constraints(free_objects)

    # --- Solve collisions among contained balls and enforce container boundaries ---
    contained_balls = [b for b in balls if b.contained]
    if container is not None and contained_balls:
        solve_contained_collisions(contained_balls, container)

    grid.clear()
    for ball in free_balls:
        grid.add(ball)
    if container is not None:
        cell_x = int(container.x // DEFAULT_CELL_SIZE)
        cell_y = int(container.y // DEFAULT_CELL_SIZE)
        key = (cell_x, cell_y)
        if key not in grid.cells:
            grid.cells[key] = []
        grid.cells[key].append(container)
    for ball in free_balls:
        ball.update_from_prediction(dt, grid)

    for ball in balls:
        if not ball.held and not ball.contained and (ball.y + ball.radius >= HEIGHT - FLOOR_SNAP_TOLERANCE) and (abs(ball.vy) < FLOOR_SNAP_VY_THRESHOLD):
            ball.y = HEIGHT - ball.radius
            ball.vy = 0
            ball.px = ball.x
            ball.py = ball.y

    # --- Global Special-Object Check ---
    special_object = None
    if container is not None:
        special_object = container
    elif selected_ball is not None:
        special_object = selected_ball
    if special_object is not None:
        for ball in free_balls:
            if ball is special_object:
                continue
            dx = ball.x - special_object.x
            dy = ball.y - special_object.y
            dist = math.hypot(dx, dy)
            min_dist = ball.radius + special_object.radius
            if dist < min_dist and dist > 0:
                overlap = min_dist - dist
                ball.x += (dx / dist) * overlap
                ball.y += (dy / dist) * overlap
                ball.px = ball.x
                ball.py = ball.y

    screen.fill((0, 0, 0))
    for ball in balls:
        ball.draw(screen)
    if container is not None:
        container.draw(screen)
    pygame.display.flip()

pygame.quit()

