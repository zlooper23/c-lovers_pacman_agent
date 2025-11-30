from capture_agents import CaptureAgent
import random, util
from game import Directions
import game

def create_team(first_index, second_index, is_red,
                first='ReflexAgent', second='ReflexAgent'):
    return [ReflexAgent(first_index, isFirst=True, teammateIndex=second_index),
            ReflexAgent(second_index, isFirst=False, teammateIndex=first_index)]

class ReflexAgent(CaptureAgent):
    
    def __init__(self, index, isFirst=False, teammateIndex=None):
        super().__init__(index)
        self.isFirst = isFirst
        self.teammateIndex = teammateIndex 
        self.last_positions = util.Queue()

    #Initialize the agent's starting position and role
    def register_initial_state(self, game_state):
        self.start = game_state.get_agent_position(self.index)
        CaptureAgent.register_initial_state(self, game_state)
        self.current_role = "Defense" if self.isFirst else "Offense"

        #Initialize last positions queue to avoid loops
        while not self.last_positions.is_empty():
            self.last_positions.pop()
        for _ in range(5):
            self.last_positions.push(self.start)

    #Choose action based on current role and evaluation
    def choose_action(self, game_state):
        self.current_role = self.decide_role(game_state)
        
        actions = game_state.get_legal_actions(self.index)
        values = [self.evaluate(game_state, a) for a in actions]

        max_value = max(values)
        best_actions = [a for a, v in zip(actions, values) if v == max_value]

        chosen_action = random.choice(best_actions)
        
        next_state = self.get_successor(game_state, chosen_action)
        new_pos = next_state.get_agent_position(self.index)
        
        #Update last positions queue when moving
        self.last_positions.pop()
        self.last_positions.push(new_pos)
        
        return chosen_action

    def get_successor(self, game_state, action):
        successor = game_state.generate_successor(self.index, action)
        pos = successor.get_agent_state(self.index).get_position()
        if pos != util.nearest_point(pos):
            return successor.generate_successor(self.index, action)
        return successor

    #To get score of a state after taking an action, multiply the features by the weights
    def evaluate(self, game_state, action):
        features = self.get_features(game_state, action)
        weights = self.get_weights(game_state, action)
        return features * weights

    #Function to decide the role of the agent
    def decide_role(self, game_state):
        score = game_state.get_score()
        opponents = self.get_opponents(game_state)
        
        enemies = [game_state.get_agent_state(i) for i in opponents]
        invaders = [a for a in enemies if a.is_pacman and a.get_position() is not None]
                
        #If winning significantly, play defense
        if score > 4:
            return "Defense"
        
        #If losing significantly, play offense
        if score < -4:
            return "Offense"

        #If there is an invader, the closest agent plays defense (chases the invader)
        if len(invaders) > 0:
            my_pos = game_state.get_agent_position(self.index)
            
            invader_positions = [a.get_position() for a in invaders]

            min_dist = float('inf')
            closest_invader_pos = None
            
            for pos in invader_positions:
                dist = self.get_maze_distance(my_pos, pos)
                if dist < min_dist:
                    min_dist = dist
                    closest_invader_pos = pos
            
            my_dist_to_invader = min_dist
            
            teammate_pos = game_state.get_agent_position(self.teammateIndex)
            if teammate_pos is not None:
                teammate_dist_to_invader = self.get_maze_distance(teammate_pos, closest_invader_pos)
            else:
                teammate_dist_to_invader = float('inf')

            if my_dist_to_invader <= teammate_dist_to_invader:
                return "Defense"
            else:
                return "Offense"

        #Default role based on initial assignment
        return "Defense" if self.isFirst else "Offense"

    #Get features to caulcuate the score of an action
    def get_features(self, game_state, action):
        features = util.Counter()
        successor = self.get_successor(game_state, action)
        my_state = successor.get_agent_state(self.index)
        my_pos = my_state.get_position()

        food_list = self.get_food(successor).as_list()
        features['successor_score'] = -len(food_list)

        #Get distance to the closest food
        if len(food_list) > 0:
            min_distance = min([self.get_maze_distance(my_pos, food) for food in food_list])
            features['distance_to_food'] = min_distance

        enemies = [successor.get_agent_state(i) for i in self.get_opponents(successor)]

        #Get positions of defenders
        defenders = [a for a in enemies if not a.is_pacman and a.get_position() is not None]
        
        if len(defenders) > 0:
            dists = [self.get_maze_distance(my_pos, a.get_position()) for a in defenders]
            min_dist = min(dists)
            
            features['ghost_danger'] = 0 
            #Increase exponentially the danger when the ghost is closer
            if min_dist <= 5: 
                ghost_danger = 10000.0 / ((min_dist + 0.5) ** 2) 
                features['ghost_danger'] = ghost_danger
        
        carrying = my_state.num_carrying
        if carrying > 0:
            #Calculate distance to base (other side of the map)
            width = game_state.data.layout.width
            mid_x = width // 2
            home_x = mid_x - 1 if self.red else mid_x
            
            home_boundary = [ (home_x, y) for y in range(game_state.data.layout.height)
                              if not game_state.data.layout.is_wall((home_x, y)) ]
            
            min_dist_home = min([self.get_maze_distance(my_pos, h) for h in home_boundary])
            features['distance_to_home'] = min_dist_home

            #When carrying more food, prioritize going home
            features['distance_to_home'] *= carrying

            #If only 1 food left, go home
            if len(food_list) < 2: 
                features['distance_to_home'] = 10000

        #If is ghost stay in defense 
        features['on_defense'] = 1
        if my_state.is_pacman: features['on_defense'] = 0

        #Count how many invaders
        invaders = [a for a in enemies if a.is_pacman and a.get_position() is not None]
        features['num_invaders'] = len(invaders)

        #If there are invaders, get the distance to the closest one
        if len(invaders) > 0:
            dists = [self.get_maze_distance(my_pos, a.get_position()) for a in invaders]
            features['invader_distance'] = min(dists)
        else:
        #Patrol the center of the map
            width = game_state.data.layout.width
            mid_x = width // 2
            if self.red: mid_x -= 1
            mid_y = game_state.data.layout.height // 2
            features['patrol_distance'] = self.get_maze_distance(my_pos, (mid_x, mid_y))

        ·
        #Code to don't get stuck in loops
        features['loop_penalty'] = 0
        successor = self.get_successor(game_state, action)
        new_pos = successor.get_agent_state(self.index).get_position()
        
        history_list = self.last_positions.list
        
        #Count how many times visited the new_pos in the last positions
        if new_pos in history_list:
            features['loop_penalty'] = history_list.count(new_pos) * 10 

        return features

    def get_weights(self, game_state, action):
        
        if self.current_role == "Offense":
            return {
                'successor_score': 150,
                'distance_to_food': -2,
                'ghost_danger': -250,
                'distance_to_home': -10,
                'loop_penalty': -50, 

                # Don't take into account defensive features
                'num_invaders': 0, 
                'on_defense': 0, 
                'invader_distance': 0, 
                'patrol_distance': 0
            }
        
        elif self.current_role == "Defense":
            return {
                'num_invaders': -1000,
                'on_defense': 100,
                'invader_distance': -500, 
                'patrol_distance': -1,
                
                #Don't take into account offensive features
                'loop_penalty': 0, 
                'successor_score': 0, 
                'distance_to_food': 0, 
                'ghost_danger': 0, 
                'distance_to_home': 0

            }
