import sys
import pygame
import numpy as np
import time
import tracemalloc

PADDLE_SPEED = 10
WINDOW_HEIGHT = 480
WINDOW_LENGTH = 480


class State:
    def __init__(self, p1, p2, ball, game_window):
        self.p1 = p1
        self.p2 = p2
        self.ball = ball
        self.isEnd = False
        # Game observation
        self.gameObs = {self.p1.name: self.p1.pos[0], self.p2.name: self.p2.pos[0], 'ball': self.ball.pos}  # Game observation
        self.gameHash = None
        self.game_window = game_window

    def getHash(self):
        return str(self.gameObs)

    def updateState(self, p1_move, p2_move, ball_move):
        self.gameObs[self.p1.name] += p1_move
        self.gameObs[self.p2.name] += p2_move
        self.gameObs['ball'] = (self.ball.pos[0] + ball_move[0], self.ball.pos[1] + ball_move[1],
                                self.ball.velocity.x, self.ball.velocity.y)
        self.ball.pos = (self.ball.pos[0] + ball_move[0], self.ball.pos[1] + ball_move[1])

    def giveReward(self, player1, player2):
        self.p1.feedReward(player1)
        self.p2.feedReward(player2)

    def play(self, rounds=100):
        tracemalloc.start()
        round = 1
        for i in range(rounds):
            print('Round: ' + repr(round))
            round += 1
            # Paddle and Ball reset
            self.p1.pos = (WINDOW_LENGTH/2 - 16, 10)
            self.p2.pos = (WINDOW_LENGTH/2 - 16, WINDOW_HEIGHT - 10)
            self.ball.pos = (WINDOW_LENGTH/2, WINDOW_HEIGHT/2)
            self.gameObs = {self.p1.name: self.p1.pos[0], self.p2.name: self.p2.pos[0], 'ball': self.ball.pos}

            p1_reward = 0
            p2_reward = 0
            # Should set a time limit
            while not self.isEnd:
                start_time = time.time()
                for event in pygame.event.get():
                    if event.type == pygame.QUIT:
                        sys.exit()

                # Wall bounce
                if self.ball.pos[0] <= 0 or self.ball.pos[0] >= WINDOW_LENGTH:
                    new_vel = pygame.math.Vector2(-self.ball.velocity[0], self.ball.velocity[1])
                    self.ball.velocity = new_vel
                # Paddle bounce if I had any
                # Might be getting double bounce and scoring for the other player
                if self.ball.rect.collidepoint(p1.pos):
                    p1_reward += 0.5
                    new_vel = pygame.math.Vector2(self.ball.velocity[0], -self.ball.velocity[1])
                    self.ball.velocity = new_vel
                elif self.ball.rect.collidepoint(p2.pos):
                    p2_reward += 0.5
                    new_vel = pygame.math.Vector2(self.ball.velocity[0], -self.ball.velocity[1])
                    self.ball.velocity = new_vel

                # Choose action and add state to each player
                p1_action = self.p1.chooseAction(self.gameObs) * self.p1.speed
                p2_action = self.p2.chooseAction(self.gameObs) * self.p2.speed
                ball_action = self.ball.velocity
                self.updateState(p1_action, p2_action, ball_action)
                obs_hash = self.getHash()
                self.p1.addState(obs_hash)
                self.p2.addState(obs_hash)

                # Update display
                self.p1.rect = self.p1.pos
                self.p2.rect = self.p2.pos
                self.ball.rect[0], self.ball.rect[1] = self.ball.pos
                self.game_window.fill((0, 0, 0))
                self.game_window.blit(self.p1.image, self.p1.rect)
                self.game_window.blit(self.p2.image, self.p2.rect)
                self.game_window.blit(self.ball.image, self.ball.rect)

                pygame.display.flip()

                # FPS Counter
                # print('FPS: ' + repr(1.0 / (time.time() - start_time)))

                # Win conditions
                if self.ball.pos[1] <= 0:
                    p2_reward += 1
                    self.giveReward(p1_reward, p2_reward)
                    self.p1.reset()
                    self.p2.reset()
                    print('p1 +' + repr(p1_reward))
                    print('p2 +' + repr(p2_reward))
                    break

                if self.ball.pos[1] >= WINDOW_HEIGHT:
                    p1_reward += 1
                    self.giveReward(p1_reward, p2_reward)
                    self.p1.reset()
                    self.p2.reset()
                    print('p1 +' + repr(p1_reward))
                    print('p2 +' + repr(p2_reward))
                    break

        snapshot = tracemalloc.take_snapshot()
        top_stats = snapshot.statistics('lineno')

        print("[ Top 10 ]")
        for stat in top_stats[:10]:
            print(stat)
        # print('p1 size: ' + repr(sys.getsizeof(self.p1.stateValue)))
        # print('p2 size: ' + repr(sys.getsizeof(self.p2.stateValue)))
        # print(repr(self.p1.stateValue))
        # print(repr(self.p2.stateValue))


class Player(pygame.sprite.Sprite):
    def __init__(self, name, speed=PADDLE_SPEED, exp_rate=0.3):
        self.pos = (0, 0)
        self.name = name
        self.speed = speed
        self.expRate = exp_rate
        self.lr = 0.6
        self.gamma = 0.96
        self.states = []
        self.stateValue = {}  # State -> Value
        self.moves = [1, -1, 0]

        self.image = pygame.image.load("Paddle.png").convert()
        self.rect = self.image.get_rect()

    def getHash(self, game_obs):
        return str(game_obs)

    def chooseAction(self, game_obs):
        x = self.pos[0]
        if x < self.rect[0] / 2:
            self.pos = (self.rect[0] / 2, self.pos[1])
        elif x > WINDOW_LENGTH - (self.rect[0] / 2):
            self.pos = (WINDOW_LENGTH - (self.rect[0] / 2), self.pos[1])

        if np.random.uniform(0, 1) <= self.expRate:
            # Make a random move
            action = np.random.choice(self.moves)
        else:
            value_max = -999
            # For every move calculate value
            for a in range(len(self.moves)):
                next_obs = game_obs.copy()
                next_obs[self.name] += self.moves[a]
                next_obs_hash = self.getHash(next_obs)
                value = 0 if self.stateValue.get(next_obs_hash) is None else self.stateValue.get(next_obs_hash)
                if value >= value_max:
                    value_max = value
                    action = self.moves[a]
        self.pos = (self.pos[0] + action, self.pos[1])
        return action

    def addState(self, state):
        self.states.append(state)

    def feedReward(self, reward):
        for st in reversed(self.states):
            if self.stateValue.get(st) is None:
                self.stateValue[st] = 0
            self.stateValue[st] += self.lr * (self.gamma * reward - self.stateValue[st])
            reward = self.stateValue[st]

    # Clear current rounds states
    def reset(self):
        self.states = []


class Ball(pygame.sprite.Sprite):
    def __init__(self, position=(0, 0), speed=10):
        self.pos = position
        self.speed = speed
        self.image = pygame.image.load('Ball.png').convert()
        self.rect = self.image.get_rect()
        self.velocity = pygame.math.Vector2.normalize(pygame.Vector2(4, -2)) * self.speed
        self.velocity.x = int(self.velocity.x)
        self.velocity.y = int(self.velocity.y)


if __name__ == '__main__':
    pygame.init()
    gw = pygame.display.set_mode([WINDOW_HEIGHT, WINDOW_LENGTH])
    # Player 1 is on top of screen
    p1 = Player('P1')
    p2 = Player('P2')
    ball = Ball()

    st = State(p1, p2, ball, gw)
    st.play(100)
