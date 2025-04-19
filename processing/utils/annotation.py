import supervision as sv
import cv2
import numpy as np
# Ensure relative import for graphics is correct
from .graphics import draw_team_ball_control 

# Enhanced color scheme with more professional colors
# Using sv.Color for consistency
colors = {
    "team1": sv.Color.from_hex('#1E90FF'),  # Blue
    "team2": sv.Color.from_hex('#DC143C'),  # Red
    "referee": sv.Color.from_hex('#FFD700'),  # Gold
    "goalkepper": sv.Color.from_hex('#32CD32'),  # Lime Green (more visible than #00FF00)
    "label_text": sv.Color.WHITE,
    "label_background": sv.Color.BLACK,
    "ball": sv.Color.from_hex('#FF8C00'),  # Orange
    "active_player": sv.Color.RED,  # Bright red
    "heatmap": sv.Color.RED # Red for heatmap
}

LABEL_TEXT_POSITION = sv.Position.BOTTOM_CENTER

# Enhanced annotators with better visibility
team1_ellipse_annotator = sv.EllipseAnnotator(color=colors["team1"], thickness=2)
team2_ellipse_annotator = sv.EllipseAnnotator(color=colors['team2'], thickness=2)
referee_ellipse_annotator = sv.EllipseAnnotator(color=colors['referee'], thickness=2)
goalkepper_ellipse_annotator = sv.EllipseAnnotator(color=colors['goalkepper'], thickness=2)

# Triangle for active player
active_player_annotator = sv.TriangleAnnotator(
    color=colors['active_player'],
    base=20, # Size of the triangle base
    height=20, # Size of the triangle height
    position=sv.Position.TOP_CENTER # Position relative to the bbox center
)

# Triangle for the ball
ball_triangle_annotator = sv.TriangleAnnotator(
    color=colors['ball'],
    base=15,
    height=15,
    position=sv.Position.BOTTOM_CENTER
)

# Enhanced label annotators with better readability
team1_label_annotator = sv.LabelAnnotator(
    color=colors['team1'],
    text_color=colors['label_text'],
    text_position=LABEL_TEXT_POSITION,
    text_scale=0.6,
    text_thickness=1,
    # Add background for better contrast if needed
    # background_color=colors['label_background'],
    # text_padding=2 
)
team2_label_annotator = sv.LabelAnnotator(
    color=colors['team2'],
    text_color=colors['label_text'],
    text_position=LABEL_TEXT_POSITION,
    text_scale=0.6,
    text_thickness=1
)
referee_label_annotator = sv.LabelAnnotator(
    color=colors['referee'],
    text_color=colors['label_text'],
    text_position=LABEL_TEXT_POSITION,
    text_scale=0.6,
    text_thickness=1
)
goalkepper_label_annotator = sv.LabelAnnotator(
    color=colors['goalkepper'],
    text_color=colors['label_text'],
    text_position=LABEL_TEXT_POSITION,
    text_scale=0.6,
    text_thickness=1
)

# Track positions for heatmap generation (optional)
team1_positions = []
team2_positions = []
max_positions = 200  # Keep the last N positions

# Function to add scoreboard overlay (adapted from original)
def add_scoreboard(frame, ball_possession_frames):
    # Use the draw_team_ball_control from graphics.py for consistency
    # This function might need adjustment based on draw_team_ball_control implementation
    # If draw_team_ball_control already does everything, just call that.
    # Assuming draw_team_ball_control handles the display:
    frame = draw_team_ball_control(frame, ball_possession_frames)
    return frame

# Generate heatmap from positions (optional feature)
def generate_heatmap(frame, positions):
    if not positions:
        return frame
        
    height, width = frame.shape[:2]
    heatmap = np.zeros((height, width), dtype=np.float32) # Use float32 for accumulation
    
    # Accumulate heatmap values
    for pos in positions:
        x, y = int(pos[0]), int(pos[1])
        if 0 <= x < width and 0 <= y < height:
             # Add gaussian intensity around the point
            size = 30 # Influence radius
            x_grid, y_grid = np.ogrid[-size:size+1, -size:size+1]
            gaussian = np.exp(-(x_grid*x_grid + y_grid*y_grid) / (2 * (size/2)**2)) # Gaussian kernel
            
            # Calculate bounds, ensuring they are within frame dimensions
            x_min, x_max = max(0, x - size), min(width, x + size + 1)
            y_min, y_max = max(0, y - size), min(height, y + size + 1)
            g_x_min, g_x_max = max(0, size - (x - x_min)), min(gaussian.shape[1], size + (x_max - x))
            g_y_min, g_y_max = max(0, size - (y - y_min)), min(gaussian.shape[0], size + (y_max - y))
            
            if g_x_min < g_x_max and g_y_min < g_y_max: # Ensure slice is valid
                try:
                    heatmap[y_min:y_max, x_min:x_max] += gaussian[g_y_min:g_y_max, g_x_min:g_x_max]
                except ValueError as e:
                     print(f"Heatmap shape mismatch error: {e}. Pos: {pos}, Bounds: ({y_min}:{y_max}, {x_min}:{x_max}), Kernel Slice: ({g_y_min}:{g_y_max}, {g_x_min}:{g_x_max})")

    # Normalize the heatmap
    if np.max(heatmap) > 0:
        heatmap = cv2.normalize(heatmap, None, 0, 255, cv2.NORM_MINMAX, dtype=cv2.CV_8U)
    else:
        heatmap = heatmap.astype(np.uint8)
    
    # Apply colormap
    colored_heatmap = cv2.applyColorMap(heatmap, cv2.COLORMAP_JET)
    
    # Blend with original frame
    alpha = 0.4
    result = cv2.addWeighted(frame, 1 - alpha, colored_heatmap, alpha, 0)
    
    return result

# Enhanced frame annotation with additional visualizations
def annotate_frames(frame, all_detection, labels, ball_possession_frames, show_heatmap=False):
    annotated_frame = frame.copy()
    
    # Optional heatmap generation 
    if show_heatmap:
         # Update positions (consider tracking centers of tracked detections for smoother heatmaps)
        if len(all_detection.get("team1", sv.Detections.empty()).xyxy) > 0:
            for box in all_detection["team1"].xyxy:
                center_x = (box[0] + box[2]) / 2
                center_y = (box[1] + box[3]) / 2
                team1_positions.append((center_x, center_y))
        
        if len(all_detection.get("team2", sv.Detections.empty()).xyxy) > 0:
            for box in all_detection["team2"].xyxy:
                center_x = (box[0] + box[2]) / 2
                center_y = (box[1] + box[3]) / 2
                team2_positions.append((center_x, center_y))
        
        # Limit the number of positions stored
        while len(team1_positions) > max_positions:
            team1_positions.pop(0)
        while len(team2_positions) > max_positions:
            team2_positions.pop(0)
        
        # Generate and overlay heatmaps
        annotated_frame = generate_heatmap(annotated_frame, team1_positions + team2_positions) # Combine positions or generate separate?

    # --- Standard Annotations --- 
    # Ellipses for players/ref/gk
    annotated_frame = team1_ellipse_annotator.annotate(scene=annotated_frame, detections=all_detection.get("team1", sv.Detections.empty()))
    annotated_frame = team2_ellipse_annotator.annotate(scene=annotated_frame, detections=all_detection.get("team2", sv.Detections.empty()))
    annotated_frame = referee_ellipse_annotator.annotate(scene=annotated_frame, detections=all_detection.get("referee", sv.Detections.empty()))
    annotated_frame = goalkepper_ellipse_annotator.annotate(scene=annotated_frame, detections=all_detection.get("goalkeepers", sv.Detections.empty()))
    
    # Triangle for ball
    annotated_frame = ball_triangle_annotator.annotate(scene=annotated_frame, detections=all_detection.get("ball", sv.Detections.empty()))
    
    # --- Labels --- 
    # Labels require both detections and the corresponding label strings
    if "labels_team1" in labels and len(labels["labels_team1"]) == len(all_detection.get("team1", sv.Detections.empty())):
        annotated_frame = team1_label_annotator.annotate(
            scene=annotated_frame, 
            detections=all_detection["team1"], 
            labels=labels["labels_team1"]
        )
    if "labels_team2" in labels and len(labels["labels_team2"]) == len(all_detection.get("team2", sv.Detections.empty())):
        annotated_frame = team2_label_annotator.annotate(
            scene=annotated_frame, 
            detections=all_detection["team2"], 
            labels=labels["labels_team2"]
        )
    if "labels_referee" in labels and len(labels["labels_referee"]) == len(all_detection.get("referee", sv.Detections.empty())):
        annotated_frame = referee_label_annotator.annotate(
            scene=annotated_frame,
            detections=all_detection["referee"],
            labels=labels["labels_referee"]
        )
    if "labels_gk" in labels and len(labels["labels_gk"]) == len(all_detection.get("goalkeepers", sv.Detections.empty())):
        annotated_frame = goalkepper_label_annotator.annotate(
            scene=annotated_frame,
            detections=all_detection["goalkeepers"],
            labels=labels["labels_gk"]
        )
    
    # --- Highlight active player --- 
    annotated_frame = active_player_annotator.annotate(
        scene=annotated_frame,
        detections=all_detection.get("active_player", sv.Detections.empty())
    )
    
    # --- Add the scoreboard/ball control display --- 
    # Pass the ball possession frame counts
    annotated_frame = add_scoreboard(annotated_frame, ball_possession_frames)
    
    return annotated_frame 