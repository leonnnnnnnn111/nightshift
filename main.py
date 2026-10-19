import math
import random
import sys
from collections import deque

import pygame

# NIGHT SHIFT — небольшой атмосферный 2D-хоррор на Python + Pygame.
# Управление: WASD/стрелки — ходьба, Shift — бег, E — взаимодействие,
# F — фонарик, Esc — пауза.

pygame.init()
pygame.display.set_caption("NIGHT SHIFT")
WIDTH, HEIGHT = 1000, 700
FPS = 60
screen = pygame.display.set_mode((WIDTH, HEIGHT))
clock = pygame.time.Clock()

# Палитра
BLACK = (5, 7, 12)
DARK = (12, 17, 25)
WALL = (29, 38, 48)
WALL_EDGE = (61, 75, 83)
FLOOR = (22, 29, 35)
FLOOR_ALT = (25, 32, 38)
WHITE = (225, 233, 235)
MUTED = (142, 157, 165)
RED = (215, 55, 65)
GREEN = (93, 220, 150)
YELLOW = (238, 196, 95)
CYAN = (104, 209, 220)

TILE = 50
MAP_W, MAP_H = 20, 14
WORLD_W, WORLD_H = MAP_W * TILE, MAP_H * TILE
WORLD_X = (WIDTH - WORLD_W) // 2
WORLD_Y = (HEIGHT - WORLD_H) // 2 + 8

# 0 — пол, 1 — стена. Карта специально сделана вручную, чтобы уровень был проходимым.
MAP_TEMPLATE = [
    "11111111111111111111",
    "10000000000000000001",
    "10111001110111011001",
    "10001000000100001001",
    "11101011110101101011",
    "10000010000100000001",
    "10111010111101111001",
    "10000010000001000001",
    "10111011101111011001",
    "10001000001000001001",
    "11001011101011101011",
    "10000000100000000001",
    "10000000000000000001",
    "11111111111111111111",
]
GRID = [[int(c) for c in row] for row in MAP_TEMPLATE]

def clamp(value, low, high):
    return max(low, min(high, value))

def distance(a, b):
    return math.hypot(a[0] - b[0], a[1] - b[1])

def tile_center(tx, ty):
    return (WORLD_X + tx * TILE + TILE // 2, WORLD_Y + ty * TILE + TILE // 2)

def world_to_tile(pos):
    tx = int((pos[0] - WORLD_X) // TILE)
    ty = int((pos[1] - WORLD_Y) // TILE)
    return tx, ty

def is_wall(tx, ty):
    if tx < 0 or ty < 0 or tx >= MAP_W or ty >= MAP_H:
        return True
    return GRID[ty][tx] == 1

def circle_hits_wall(x, y, radius):
    # Проверяем несколько точек вокруг игрока — так он не проходит сквозь углы.
    for ox, oy in ((-radius, 0), (radius, 0), (0, -radius), (0, radius),
                   (-radius * .7, -radius * .7), (radius * .7, -radius * .7),
                   (-radius * .7, radius * .7), (radius * .7, radius * .7)):
        tx, ty = world_to_tile((x + ox, y + oy))
        if is_wall(tx, ty):
            return True
    return False

def move_with_collision(pos, dx, dy, radius=13):
    x, y = pos
    if not circle_hits_wall(x + dx, y, radius):
        x += dx
    if not circle_hits_wall(x, y + dy, radius):
        y += dy
    return [x, y]

def find_path(start, goal):
    """Поиск пути BFS по клеткам карты: используется для преследования монстра."""
    if start == goal:
        return [start]
    queue = deque([start])
    previous = {start: None}
    while queue:
        current = queue.popleft()
        if current == goal:
            break
        x, y = current
        for nxt in ((x + 1, y), (x - 1, y), (x, y + 1), (x, y - 1)):
            if not is_wall(*nxt) and nxt not in previous:
                previous[nxt] = current
                queue.append(nxt)
    if goal not in previous:
        return []
    path = []
    node = goal
    while node is not None:
        path.append(node)
        node = previous[node]
    return path[::-1]

def draw_text(surface, text, font, color, center, shadow=True):
    if shadow:
        shadow_img = font.render(text, True, (0, 0, 0))
        surface.blit(shadow_img, (center[0] - shadow_img.get_width() // 2 + 2,
                                  center[1] - shadow_img.get_height() // 2 + 3))
    img = font.render(text, True, color)
    surface.blit(img, (center[0] - img.get_width() // 2,
                       center[1] - img.get_height() // 2))

FONT = pygame.font.SysFont("consolas", 20)
SMALL = pygame.font.SysFont("consolas", 15)
MED = pygame.font.SysFont("consolas", 30, bold=True)
BIG = pygame.font.SysFont("consolas", 64, bold=True)
TITLE = pygame.font.SysFont("consolas", 76, bold=True)

class Game:
    def __init__(self):
        self.state = "menu"
        self.reset()

    def reset(self):
        self.player = [tile_center(1, 1)[0], tile_center(1, 1)[1]]
        self.player_speed = 170
        self.player_radius = 12
        self.facing = (1, 0)
        self.stamina = 100.0
        self.flashlight = True
        self.battery = 100.0
        self.elapsed = 0.0
        self.message = "найди 3 предохранителя и запусти генератор"
        self.message_timer = 4.0
        self.keys_found = 0
        self.generator_on = False
        self.exit_open = False
        self.interact_cooldown = 0.0
        self.heartbeat = 0.0
        self.jumpscare_flash = 0.0
        self.particles = []
        self.noise_timer = 0.0
        self.monster = [tile_center(18, 12)[0], tile_center(18, 12)[1]]
        self.monster_speed = 76.0
        self.monster_path = []
        self.path_timer = 0.0
        self.monster_mode = "patrol"
        self.monster_target = tile_center(17, 1)
        self.patrol_points = [tile_center(17, 1), tile_center(2, 11),
                              tile_center(17, 11), tile_center(2, 5)]
        self.patrol_index = 0
        self.keys = [
            {"pos": tile_center(5, 3), "found": False, "name": "предохранитель"},
            {"pos": tile_center(14, 5), "found": False, "name": "предохранитель"},
            {"pos": tile_center(8, 11), "found": False, "name": "предохранитель"},
        ]
        self.generator_pos = tile_center(17, 7)
        self.exit_pos = tile_center(10, 1)
        self.decor = []
        random.seed(8)
        for ty in range(1, MAP_H - 1):
            for tx in range(1, MAP_W - 1):
                if not is_wall(tx, ty) and random.random() < .10:
                    self.decor.append((tile_center(tx, ty), random.choice(["stain", "paper", "crack"])))

    def say(self, text, duration=3.0):
        self.message = text
        self.message_timer = duration

    def add_particles(self, pos, count=8, color=RED):
        for _ in range(count):
            angle = random.random() * math.tau
            speed = random.uniform(15, 75)
            self.particles.append({
                "x": pos[0], "y": pos[1],
                "vx": math.cos(angle) * speed, "vy": math.sin(angle) * speed,
                "life": random.uniform(.25, .65), "max": .65,
                "color": color, "r": random.randint(1, 3)
            })

    def nearest_interactable(self):
        candidates = []
        for key in self.keys:
            if not key["found"]:
                candidates.append((distance(self.player, key["pos"]), "key", key))
        if not self.generator_on:
            candidates.append((distance(self.player, self.generator_pos), "generator", None))
        if self.generator_on and not self.exit_open:
            candidates.append((distance(self.player, self.exit_pos), "exit", None))
        if not candidates:
            return None
        d, kind, obj = min(candidates, key=lambda item: item[0])
        return (kind, obj) if d < 48 else None

    def interact(self):
        target = self.nearest_interactable()
        if target is None:
            self.say("здесь нечего трогать", 1.3)
            return
        kind, obj = target
        if kind == "key":
            obj["found"] = True
            self.keys_found += 1
            self.add_particles(obj["pos"], 12, YELLOW)
            self.say(f"предохранитель найден: {self.keys_found}/3", 2.2)
        elif kind == "generator":
            if self.keys_found < 3:
                self.say(f"не хватает предохранителей: {self.keys_found}/3", 2.2)
            else:
                self.generator_on = True
                self.monster_speed = 100
                self.add_particles(self.generator_pos, 24, CYAN)
                self.say("генератор запущен. теперь к выходу!", 3.0)
        elif kind == "exit":
            self.exit_open = True
            self.state = "win"

    def update_monster(self, dt):
        # Монстр замечает игрока, если тот близко. Бег повышает дистанцию обнаружения.
        d = distance(self.monster, self.player)
        detect_range = 245 if self.flashlight else 185
        if self.stamina < 25:
            detect_range += 25
        if d < detect_range:
            self.monster_mode = "chase"
            self.monster_target = tuple(self.player)
        elif self.monster_mode == "chase" and d > 340:
            self.monster_mode = "patrol"

        self.path_timer -= dt
        if self.path_timer <= 0:
            self.path_timer = .34 if self.monster_mode == "chase" else .75
            start = world_to_tile(self.monster)
            goal = world_to_tile(self.player if self.monster_mode == "chase" else self.monster_target)
            self.monster_path = find_path(start, goal)

        if self.monster_mode == "patrol" and distance(self.monster, self.monster_target) < 22:
            self.patrol_index = (self.patrol_index + 1) % len(self.patrol_points)
            self.monster_target = self.patrol_points[self.patrol_index]

        target_pos = None
        if len(self.monster_path) > 1:
            target_pos = tile_center(*self.monster_path[1])
        else:
            target_pos = self.monster_target if self.monster_mode == "patrol" else tuple(self.player)

        dx = target_pos[0] - self.monster[0]
        dy = target_pos[1] - self.monster[1]
        length = math.hypot(dx, dy)
        if length > 2:
            speed = self.monster_speed * (1.22 if self.monster_mode == "chase" else 1.0)
            step = min(length, speed * dt)
            self.monster[0] += dx / length * step
            self.monster[1] += dy / length * step

        if distance(self.monster, self.player) < 25:
            self.state = "dead"
            self.jumpscare_flash = .4

    def update(self, dt):
        if self.state != "playing":
            return
        self.elapsed += dt
        self.interact_cooldown = max(0, self.interact_cooldown - dt)
        self.message_timer = max(0, self.message_timer - dt)
        self.heartbeat += dt
        self.noise_timer += dt
        self.jumpscare_flash = max(0, self.jumpscare_flash - dt)

        keys = pygame.key.get_pressed()
        dx = (keys[pygame.K_d] or keys[pygame.K_RIGHT]) - (keys[pygame.K_a] or keys[pygame.K_LEFT])
        dy = (keys[pygame.K_s] or keys[pygame.K_DOWN]) - (keys[pygame.K_w] or keys[pygame.K_UP])
        moving = dx != 0 or dy != 0
        if moving:
            length = math.hypot(dx, dy)
            dx, dy = dx / length, dy / length
            self.facing = (dx, dy)

        running = (keys[pygame.K_LSHIFT] or keys[pygame.K_RSHIFT]) and moving and self.stamina > 1
        speed = self.player_speed * (1.55 if running else 1.0)
        if running:
            self.stamina = max(0, self.stamina - 32 * dt)
        else:
            self.stamina = min(100, self.stamina + 20 * dt)

        self.player = move_with_collision(self.player, dx * speed * dt, dy * speed * dt, self.player_radius)
        if self.flashlight:
            self.battery = max(0, self.battery - 1.45 * dt)
            if self.battery <= 0:
                self.flashlight = False
                self.say("фонарик сел. ищи выход в темноте...", 3)
        else:
            self.battery = min(100, self.battery + .5 * dt)

        self.update_monster(dt)
        for p in self.particles[:]:
            p["x"] += p["vx"] * dt
            p["y"] += p["vy"] * dt
            p["life"] -= dt
            if p["life"] <= 0:
                self.particles.remove(p)

    def draw_world(self, surface):
        surface.fill(BLACK)
        # Пол и стены
        for ty in range(MAP_H):
            for tx in range(MAP_W):
                x, y = WORLD_X + tx * TILE, WORLD_Y + ty * TILE
                rect = pygame.Rect(x, y, TILE, TILE)
                if GRID[ty][tx]:
                    pygame.draw.rect(surface, WALL, rect)
                    pygame.draw.rect(surface, WALL_EDGE, rect, 2)
                    pygame.draw.line(surface, (39, 49, 59), (x + 5, y + 8), (x + TILE - 5, y + 8), 1)
                else:
                    shade = FLOOR if (tx + ty) % 2 else FLOOR_ALT
                    pygame.draw.rect(surface, shade, rect)
                    # тонкие швы пола
                    pygame.draw.rect(surface, (31, 40, 47), rect, 1)

        for pos, kind in self.decor:
            x, y = int(pos[0]), int(pos[1])
            if kind == "stain":
                pygame.draw.ellipse(surface, (35, 29, 34), (x - 10, y - 5, 20, 10))
            elif kind == "paper":
                pygame.draw.rect(surface, (95, 91, 77), (x - 5, y - 7, 10, 14), border_radius=2)
            else:
                pygame.draw.line(surface, (42, 48, 50), (x - 8, y - 4), (x + 7, y + 6), 2)

        # Объекты задания
        for i, key in enumerate(self.keys):
            if not key["found"]:
                x, y = map(int, key["pos"])
                pulse = 2 * math.sin(self.elapsed * 4 + i) if self.state == "playing" else 0
                pygame.draw.circle(surface, (115, 87, 35), (x, y), int(10 + pulse))
                pygame.draw.rect(surface, YELLOW, (x - 6, y - 5, 12, 10), border_radius=2)
                pygame.draw.circle(surface, (255, 240, 160), (x + 2, y), 2)

        gx, gy = map(int, self.generator_pos)
        pygame.draw.rect(surface, (42, 62, 67), (gx - 17, gy - 20, 34, 40), border_radius=4)
        pygame.draw.rect(surface, CYAN if self.generator_on else (72, 84, 86),
                         (gx - 11, gy - 13, 22, 26), 2, border_radius=3)
        pygame.draw.circle(surface, GREEN if self.generator_on else RED, (gx, gy + 8), 4)
        if self.generator_on:
            for i in range(3):
                pygame.draw.line(surface, (58, 112, 115), (gx - 10, gy - 8 + i * 6), (gx + 10, gy - 8 + i * 6), 1)

        ex, ey = map(int, self.exit_pos)
        pygame.draw.rect(surface, (57, 65, 70), (ex - 18, ey - 23, 36, 46), border_radius=3)
        pygame.draw.rect(surface, GREEN if self.generator_on else (105, 52, 56),
                         (ex - 13, ey - 18, 26, 36), 2)
        pygame.draw.circle(surface, YELLOW, (ex + 7, ey), 2)

        # Монстр: силуэт, длинные руки и светящиеся глаза
        mx, my = map(int, self.monster)
        if self.monster_mode == "chase":
            aura = 28 + 3 * math.sin(self.elapsed * 12)
            pygame.draw.circle(surface, (64, 20, 29), (mx, my), int(aura))
        pygame.draw.ellipse(surface, (4, 4, 7), (mx - 14, my - 18, 28, 39))
        pygame.draw.line(surface, (4, 4, 7), (mx - 7, my - 2), (mx - 22, my + 12), 7)
        pygame.draw.line(surface, (4, 4, 7), (mx + 7, my - 2), (mx + 22, my + 12), 7)
        pygame.draw.circle(surface, RED, (mx - 5, my - 8), 2)
        pygame.draw.circle(surface, RED, (mx + 5, my - 8), 2)

        # Игрок
        px, py = map(int, self.player)
        pygame.draw.ellipse(surface, (0, 0, 0), (px - 14, py + 7, 28, 9))
        pygame.draw.circle(surface, (78, 142, 160), (px, py), self.player_radius)
        pygame.draw.circle(surface, (177, 224, 224), (px - 3, py - 4), 4)
        fx, fy = self.facing
        pygame.draw.line(surface, (215, 230, 224), (px, py), (px + int(fx * 15), py + int(fy * 15)), 3)

        # Частицы
        for p in self.particles:
            alpha_factor = clamp(p["life"] / p["max"], 0, 1)
            color = tuple(int(c * alpha_factor) for c in p["color"])
            pygame.draw.circle(surface, color, (int(p["x"]), int(p["y"])), p["r"])

        # Атмосферное затемнение с круглым световым пятном фонарика
        darkness = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
        darkness.fill((0, 0, 0, 220 if self.flashlight and self.battery > 0 else 244))
        px, py = map(int, self.player)
        # Мягкое свечение несколькими кругами
        if self.flashlight and self.battery > 0:
            for radius, alpha in ((175, 0), (155, 18), (130, 48), (100, 82), (65, 118)):
                pygame.draw.circle(darkness, (0, 0, 0, alpha), (px, py), radius)
            # вырезаем центральную область фонарика
            pygame.draw.circle(darkness, (0, 0, 0, 0), (px, py), 88)
            fx, fy = self.facing
            cone_center = (int(px + fx * 78), int(py + fy * 78))
            pygame.draw.circle(darkness, (0, 0, 0, 45), cone_center, 115)
            pygame.draw.circle(darkness, (0, 0, 0, 0), cone_center, 75)
        else:
            pygame.draw.circle(darkness, (0, 0, 0, 0), (px, py), 48)
        surface.blit(darkness, (0, 0))

        # Лёгкая виньетка и HUD
        vignette = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
        pygame.draw.rect(vignette, (0, 0, 0, 80), (0, 0, WIDTH, 18))
        pygame.draw.rect(vignette, (0, 0, 0, 80), (0, HEIGHT - 18, WIDTH, 18))
        surface.blit(vignette, (0, 0))
        self.draw_hud(surface)

    def draw_bar(self, surface, x, y, w, h, value, color, label):
        pygame.draw.rect(surface, (17, 22, 27), (x, y, w, h), border_radius=4)
        pygame.draw.rect(surface, color, (x, y, int(w * clamp(value / 100, 0, 1)), h), border_radius=4)
        pygame.draw.rect(surface, (88, 100, 106), (x, y, w, h), 1, border_radius=4)
        surface.blit(SMALL.render(label, True, WHITE), (x, y - 19))

    def draw_hud(self, surface):
        # Верхняя панель
        pygame.draw.rect(surface, (8, 12, 17), (0, 0, WIDTH, 64))
        surface.blit(MED.render("NIGHT SHIFT", True, (210, 220, 220)), (24, 12))
        objective = "ЗАДАЧА: " + (f"предохранители {self.keys_found}/3" if not self.generator_on else
                                   ("доберись до выхода" if not self.exit_open else "выход открыт"))
        surface.blit(SMALL.render(objective, True, CYAN if self.generator_on else MUTED), (390, 14))
        elapsed = int(self.elapsed)
        surface.blit(SMALL.render(f"{elapsed // 60:02d}:{elapsed % 60:02d}", True, WHITE), (900, 14))
        self.draw_bar(surface, 390, 39, 150, 9, self.stamina, GREEN, "выносливость")
        self.draw_bar(surface, 560, 39, 150, 9, self.battery, YELLOW, "батарея фонаря")
        status = "ON" if self.flashlight and self.battery > 0 else "OFF"
        surface.blit(SMALL.render(f"фонарь: {status}", True, YELLOW if status == "ON" else RED), (730, 36))

        # Подсказка взаимодействия
        target = self.nearest_interactable()
        if target:
            kind, _ = target
            hint = {"key": "[E] взять предохранитель", "generator": "[E] запустить генератор",
                    "exit": "[E] открыть выход"}[kind]
            draw_text(surface, hint, FONT, YELLOW, (WIDTH // 2, HEIGHT - 62))

        if self.message_timer > 0:
            draw_text(surface, self.message, SMALL, WHITE, (WIDTH // 2, HEIGHT - 31))

        surface.blit(SMALL.render("WASD — ходьба  |  SHIFT — бег  |  E — действие  |  F — фонарь  |  ESC — пауза",
                                  True, (126, 140, 148)), (WIDTH // 2 - 335, HEIGHT - 12))

    def draw_menu(self, surface):
        surface.fill((5, 8, 13))
        # Геометрический фон и мерцающие линии
        for i in range(12):
            y = 100 + i * 48
            pygame.draw.line(surface, (14, 24, 31), (0, y), (WIDTH, y), 1)
        for i in range(8):
            x = i * 145 + int(math.sin(pygame.time.get_ticks() / 900 + i) * 18)
            pygame.draw.line(surface, (15, 26, 33), (x, 0), (x - 90, HEIGHT), 1)
        # стилизованный силуэт двери
        pygame.draw.rect(surface, (18, 29, 36), (690, 145, 190, 380), border_radius=5)
        pygame.draw.rect(surface, (54, 72, 78), (708, 163, 154, 344), 3, border_radius=4)
        pygame.draw.circle(surface, RED, (835, 340), 5)
        for r, a in ((110, 14), (80, 24), (50, 35)):
            glow = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
            pygame.draw.circle(glow, (130, 10, 25, a), (790, 300), r)
            surface.blit(glow, (0, 0))
        draw_text(surface, "NIGHT", TITLE, WHITE, (340, 205))
        draw_text(surface, "SHIFT", TITLE, RED, (340, 280))
        draw_text(surface, "ты здесь не один.", MED, (142, 160, 167), (340, 350))
        draw_text(surface, "найди предохранители. запусти генератор. выберись.", SMALL,
                  MUTED, (340, 393))
        draw_text(surface, "[ ENTER ]  начать смену", FONT, YELLOW, (340, 480))
        draw_text(surface, "[ ESC ]  выйти", SMALL, MUTED, (340, 520))
        draw_text(surface, "2D SURVIVAL HORROR  •  PYTHON / PYGAME", SMALL,
                  (67, 87, 96), (WIDTH // 2, 650))

    def draw_overlay(self, surface, title, subtitle, options):
        shade = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
        shade.fill((0, 0, 0, 205))
        surface.blit(shade, (0, 0))
        draw_text(surface, title, BIG, WHITE, (WIDTH // 2, 250))
        draw_text(surface, subtitle, FONT, MUTED, (WIDTH // 2, 315))
        for i, line in enumerate(options):
            draw_text(surface, line, FONT, YELLOW if i == 0 else WHITE,
                      (WIDTH // 2, 390 + i * 42))

game = Game()
running = True

while running:
    dt = min(clock.tick(FPS) / 1000.0, .04)

    for event in pygame.event.get():
        if event.type == pygame.QUIT:
            running = False
        elif event.type == pygame.KEYDOWN:
            if game.state == "menu":
                if event.key == pygame.K_RETURN:
                    game.reset()
                    game.state = "playing"
                elif event.key == pygame.K_ESCAPE:
                    running = False
            elif game.state == "playing":
                if event.key == pygame.K_ESCAPE:
                    game.state = "paused"
                elif event.key == pygame.K_e:
                    game.interact()
                elif event.key == pygame.K_f:
                    if game.battery > 1:
                        game.flashlight = not game.flashlight
                    else:
                        game.say("батарея разряжена", 1.5)
            elif game.state == "paused":
                if event.key == pygame.K_ESCAPE:
                    game.state = "playing"
                elif event.key == pygame.K_RETURN:
                    game.state = "playing"
                elif event.key == pygame.K_m:
                    game.state = "menu"
            elif game.state in ("dead", "win"):
                if event.key == pygame.K_RETURN:
                    game.reset()
                    game.state = "playing"
                elif event.key == pygame.K_ESCAPE:
                    game.state = "menu"

    game.update(dt)

    if game.state == "menu":
        game.draw_menu(screen)
    else:
        game.draw_world(screen)
        if game.state == "paused":
            game.draw_overlay(screen, "ПАУЗА", "смена поставлена на паузу",
                              ["[ ENTER / ESC ] продолжить", "[ M ] главное меню"])
        elif game.state == "dead":
            game.draw_overlay(screen, "ТЕБЯ НАШЛИ", "ночная смена закончилась",
                              ["[ ENTER ] попробовать снова", "[ ESC ] главное меню"])
            if game.jumpscare_flash > 0:
                flash = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
                flash.fill((180, 0, 15, int(100 * game.jumpscare_flash / .4)))
                screen.blit(flash, (0, 0))
        elif game.state == "win":
            game.draw_overlay(screen, "ТЫ ВЫБРАЛСЯ", f"время смены: {int(game.elapsed)//60:02d}:{int(game.elapsed)%60:02d}",
                              ["[ ENTER ] сыграть ещё раз", "[ ESC ] главное меню"])

    pygame.display.flip()

pygame.quit()
sys.exit()
