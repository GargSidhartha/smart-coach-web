import cv2
import supervision as sv
# Use relative import for config
from ..config import MODEL_CLASSES

def draw_team_ball_control(frame,ball_control):
    # Draw a semi-transparent rectangle 
    overlay = frame.copy()
    # Adjust coordinates if needed for different frame sizes/layouts
    # These seem hardcoded for a specific resolution (like 1920 width)
    x1, y1, x2, y2 = 1210, 70, 1838, 145 
    cv2.rectangle(overlay, (x1, y1), (x2, y2), (255,255,255), -1 )
    alpha = 0.4 # Adjusted transparency 
    cv2.addWeighted(overlay, alpha, frame, 1 - alpha, 0, frame)

    total_possession = ball_control.get(MODEL_CLASSES["team1"], 0) + ball_control.get(MODEL_CLASSES["team2"], 0)
    if total_possession > 0:
        team_1 = ball_control.get(MODEL_CLASSES["team1"], 0) / total_possession
        team_2 = ball_control.get(MODEL_CLASSES["team2"], 0) / total_possession
    else:
        team_1 = 0
        team_2 = 0

    # Use coordinates relative to the rectangle
    text_x = x1 + 10
    text_y_header = y1 + 30 # Adjust for text placement inside the box
    text_y_values = y1 + 60
    
    cv2.putText(frame,"Ball Control : ",(text_x, text_y_header), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0,0,0), 2)
    # Adjust positions for team percentages
    cv2.putText(frame, f"{team_1*100:.1f}%",(text_x + 250, text_y_values), cv2.FONT_HERSHEY_SIMPLEX, 1, sv.Color.as_bgr(sv.Color.from_hex('#1E90FF')), 3)
    cv2.putText(frame, f"{team_2*100:.1f}%",(text_x + 450, text_y_values), cv2.FONT_HERSHEY_SIMPLEX, 1, sv.Color.as_bgr(sv.Color.from_hex('#DC143C')), 3)

    return frame 