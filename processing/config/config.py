# This file defines constants used by the processing logic, 
# primarily the mapping of class names to model output indices.
# Paths for input/output/model are handled by the main Flask app config 
# and passed dynamically to the processing functions.

MODEL_CLASSES = {
     "ball":0,
     "goalkepper":1, # Note: potential typo "goalkeeper"
     "player":2,
     "referee":3,
     "team1":4, # Represents the class ID for team 1 detections initially
     "team2":5, # Represents the class ID for team 2 detections initially
     "active_player":6 # Used temporarily to highlight player with ball
}

# You can add other non-path related configuration constants here if needed. 