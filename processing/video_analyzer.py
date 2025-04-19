import time
import json
import os
import cv2
import numpy as np
import supervision as sv
from ultralytics import YOLO
from tqdm import tqdm
import torch

# Use relative imports for local modules within the 'processing' package
from .utils import get_number_of_frames, get_frames, annotate_frames, assign_ball_to_player, get_player_color
from .team_assigner import Assigner
from .config import MODEL_CLASSES # Assuming MODEL_CLASSES is defined here

# Define the main analysis function
def analyze_video(input_path: str, output_video_path: str, output_stats_path: str, model_path: str, task=None):
    """
    Processes the input video using YOLO, ByteTrack, team assignment, and generates
    an annotated video and a statistics JSON file.

    Args:
        input_path (str): Path to the input video file.
        output_video_path (str): Path where the processed video should be saved.
        output_stats_path (str): Path where the statistics JSON should be saved.
        model_path (str): Path to the YOLO model file (.pt).
        task (celery.Task, optional): The Celery task instance for progress updates. Defaults to None.

    Returns:
        dict: A dictionary containing relative paths to the results.
              Example: {'video_path': 'results/unique_id_processed.mp4',
                        'stats_path': 'results/unique_id_stats.json'}

    Raises:
        FileNotFoundError: If the input video or model file does not exist.
        Exception: For errors during video processing or writing.
    """
    start_time = time.time()
    print(f"--- Starting Video Analysis --- ")
    print(f"Input video: {input_path}")
    print(f"Output video: {output_video_path}")
    print(f"Output stats: {output_stats_path}")
    print(f"Using model: {model_path}")
    
    # Check for GPU availability
    device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')
    if device.type == 'cuda':
        gpu_name = torch.cuda.get_device_name(0)
        print(f"GPU detected: {gpu_name}")
        print(f"Using GPU acceleration for video processing")
    else:
        print("No GPU detected. Using CPU for processing (this will be slower)")
    
    # --- Input Validation ---
    if not os.path.exists(input_path):
        raise FileNotFoundError(f"Input video not found: {input_path}")
    if not os.path.exists(model_path):
        raise FileNotFoundError(f"Model file not found: {model_path}")
    
    # --- Initialization ---
    print("Loading YOLO model...")
    # Initialize model with GPU support if available, force device selection
    model = YOLO(model_path).to(device)
    
    print("Getting video info...")
    total_frames, fps = get_number_of_frames(input_path)
    if total_frames <= 0 or fps <= 0:
        raise ValueError(f"Could not read video properties (frames/fps) from {input_path}")
    print(f"Total frames: {total_frames}, FPS: {fps:.2f}")

    frame_generator = get_frames(input_path)
    
    # Determine video dimensions from the first frame
    try:
        first_frame = next(frame_generator)
        # Reset generator to start from the beginning again for processing loop
        frame_generator = get_frames(input_path) 
    except StopIteration:
        raise ValueError(f"Cannot read first frame from video: {input_path}")
        
    original_height, original_width, _ = first_frame.shape
    print(f"Video dimensions: {original_width}x{original_height}")

    # --- Create output directory ---
    output_dir = os.path.dirname(output_video_path)
    os.makedirs(output_dir, exist_ok=True) # Ensure output directory exists
    
    # --- Initialize video writer with Windows-friendly codecs ---
    out = None
    codec_attempts = [
        ('H264', 'mp4'),  # H.264 codec with MP4 container
        ('avc1', 'mp4'),  # Alternative name for H.264
        ('mp4v', 'mp4'),  # MPEG-4 codec
        ('DIVX', 'avi'),  # DIVX codec with AVI container
        ('XVID', 'avi')   # XVID codec with AVI container
    ]
    
    # Try each codec in order until one works
    for codec, extension in codec_attempts:
        try:
            print(f"Trying codec: {codec}")
            codec_path = output_video_path
            if not codec_path.lower().endswith(f".{extension}"):
                codec_path = f"{os.path.splitext(output_video_path)[0]}.{extension}"
            
            fourcc = cv2.VideoWriter_fourcc(*codec)
            test_out = cv2.VideoWriter(codec_path, fourcc, fps, (original_width, original_height))
            
            if test_out.isOpened():
                out = test_out
                output_video_path = codec_path
                print(f"Successfully initialized VideoWriter with {codec} codec")
                break
            else:
                test_out.release()
        except Exception as e:
            print(f"Failed to initialize with {codec} codec: {e}")
    
    if out is None or not out.isOpened():
        # Last resort - try Microsoft Video 1 codec which is very widely supported
        try:
            print("Trying Microsoft Video 1 codec as last resort")
            codec_path = f"{os.path.splitext(output_video_path)[0]}.avi"
            fourcc = cv2.VideoWriter_fourcc('M', 'S', 'V', 'C')
            out = cv2.VideoWriter(codec_path, fourcc, fps, (original_width, original_height))
            output_video_path = codec_path
        except Exception as e:
            print(f"Failed to initialize MSVC codec: {e}")
            raise IOError(f"Failed to initialize any video writer. OpenCV may not have codec support on this system.")
    
    if not out.isOpened():
        raise IOError(f"Failed to open video writer for path: {output_video_path}")

    # Initialize tracker and team assigner
    tracker_team1 = sv.ByteTrack()
    tracker_team2 = sv.ByteTrack() # Separate tracker for each team
    team_assigner = Assigner()

    # --- State Variables ---
    is_first_frame = True
    kmeans_teams = None # KMeans model for team assignment
    team_colors = {} # Store average team colors (used by Assigner)
    ball_possession_frames = {MODEL_CLASSES["team1"]: 0, MODEL_CLASSES["team2"]: 0} # Frame counts
    last_player_with_ball_team = None
    total_frames_processed = 0
    # Define progress update frequency (update roughly every second of video)
    update_interval_frames = max(1, int(fps)) if fps > 0 else 1

    # --- Processing Loop ---
    print("Starting frame processing loop...")
    try:
        # Create tqdm progress bar and capture it to extract ETA info later
        progress_bar = tqdm(frame_generator, total=total_frames, desc="Analyzing video")
        
        for frame in progress_bar:
            total_frames_processed += 1
            
            # 1. Object Detection - use GPU acceleration with device parameter
            result = model.predict(frame, conf=0.3, verbose=False, device=device)[0]
            detections = sv.Detections.from_ultralytics(result)
            
            # Separate detections by initial class (Player, Ball, Referee, Goalkeeper)
            # Use .get() with default 0 to handle cases where a class might not be in MODEL_CLASSES
            ball_detections = detections[detections.class_id == MODEL_CLASSES.get("ball", -1)]
            players_detections = detections[detections.class_id == MODEL_CLASSES.get("player", -1)]
            referee_detections = detections[detections.class_id == MODEL_CLASSES.get("referee", -1)]
            # Initial goalkeeper detections (if model distinguishes them)
            goalkeepers_detections = detections[detections.class_id == MODEL_CLASSES.get("goalkepper", -1)] # Watch for typo

            # Apply NMS specifically to players to avoid overlapping boxes
            players_detections = players_detections.with_nms(threshold=0.5)

            # 2. Team Assignment (on first frame or if needed)
            if is_first_frame and len(players_detections) > 0:
                print("Assigning team colors...")
                kmeans_teams = team_assigner.assign_team_color(frame, players_detections)
                if kmeans_teams is None:
                     print("Warning: Failed to assign team colors, proceeding with defaults.")
                     # Handle case where assigner failed (e.g., assign fixed default teams)
                else:
                    team_colors = team_assigner.team_colors # Assigner stores colors internally
                    print(f"Team colors assigned (HSV): {team_colors}")
                is_first_frame = False
            elif is_first_frame and len(players_detections) == 0:
                print("Warning: No players detected in the first frame to assign teams.")
                is_first_frame = False # Avoid infinite loop if first frame has no players

            # 3. Assign Team ID to each player detection
            team1_indices = []
            team2_indices = []
            gk_indices = [] # Indices of players re-classified as goalkeepers

            if kmeans_teams is not None and len(players_detections) > 0:
                for i, bbox in enumerate(players_detections.xyxy):
                    team_id = team_assigner.get_player_team(frame, bbox, kmeans_teams)
                    
                    if team_id == 0:
                        team1_indices.append(i)
                    elif team_id == 1:
                        team2_indices.append(i)
            
            # Create Detections objects for each team
            team1_detections = players_detections[team1_indices]
            team2_detections = players_detections[team2_indices]
            # Combine explicitly detected GKs with re-classified players
            gk_players = players_detections[gk_indices]
            all_goalkeepers = sv.Detections.merge([goalkeepers_detections, gk_players])
            
            # 4. Update Trackers
            team1_detections_tracked = tracker_team1.update_with_detections(detections=team1_detections)
            team2_detections_tracked = tracker_team2.update_with_detections(detections=team2_detections)
            
            # 5. Ball Possession
            active_player_detection = sv.Detections.empty()
            
            # --- Safely merge tracked detections --- 
            detections_to_merge = []
            if len(team1_detections_tracked) > 0:
                detections_to_merge.append(team1_detections_tracked)
            if len(team2_detections_tracked) > 0:
                detections_to_merge.append(team2_detections_tracked)

            if not detections_to_merge: # If both were empty
                all_tracked_players = sv.Detections.empty()
            elif len(detections_to_merge) == 1: # If only one had detections
                all_tracked_players = detections_to_merge[0]
            else: # If both had detections, merge them
                try:
                    all_tracked_players = sv.Detections.merge(detections_to_merge)
                except ValueError as merge_error:
                    print(f"Warning: Error merging detections: {merge_error}. Skipping ball assignment for this frame.")
                    all_tracked_players = sv.Detections.empty() # Fallback to empty
            # --- End of safe merge --- 
                    
            # Use combined tracked teams for ball assignment check
            player_idx_with_ball = assign_ball_to_player(all_tracked_players, ball_detections.xyxy)
            
            current_player_team = None
            if player_idx_with_ball != -1 and len(all_tracked_players) > player_idx_with_ball:
                # Determine the team of the player with the ball based on tracker ID
                player_tracker_id = all_tracked_players.tracker_id[player_idx_with_ball]
                # Check which original tracked list contained this ID
                if player_tracker_id in team1_detections_tracked.tracker_id:
                    current_player_team = MODEL_CLASSES["team1"]
                elif player_tracker_id in team2_detections_tracked.tracker_id:
                    current_player_team = MODEL_CLASSES["team2"]
                
                if current_player_team is not None:
                    ball_possession_frames[current_player_team] += 1
                    last_player_with_ball_team = current_player_team
                    # Create detection for annotating the active player
                    active_player_detection = all_tracked_players[player_idx_with_ball]
                    # Pad the box for better visibility
                    active_player_detection.xyxy = sv.pad_boxes(xyxy=active_player_detection.xyxy, px=10)
            elif last_player_with_ball_team is not None:
                # If ball is not near anyone, assign possession to last team known to have it
                ball_possession_frames[last_player_with_ball_team] += 1

            # Pad ball box
            if len(ball_detections.xyxy) > 0:
                 ball_detections.xyxy = sv.pad_boxes(xyxy=ball_detections.xyxy, px=10)

            # 6. Annotation
            labels = {
                "labels_team1": [f"{tracker_id}" for tracker_id in team1_detections_tracked.tracker_id],
                "labels_team2": [f"{tracker_id}" for tracker_id in team2_detections_tracked.tracker_id],
                "labels_referee": ["ref"] * len(referee_detections),
                "labels_gk": ["GK"] * len(all_goalkeepers)
            }
            
            all_detections_for_annotation = {
                "goalkeepers": all_goalkeepers,
                "ball": ball_detections,
                # Pass tracked teams for consistent ID labeling
                "team1": team1_detections_tracked, 
                "team2": team2_detections_tracked, 
                "referee": referee_detections,
                "active_player": active_player_detection
            }

            annotated_frame = annotate_frames(
                frame, 
                all_detections_for_annotation, 
                labels, 
                ball_possession_frames, # Pass frame counts
                show_heatmap=False # Heatmap disabled by default
            )
            
            # 7. Write Frame
            out.write(annotated_frame)

            # 8. Update Celery Task Progress with tqdm's ETA info
            if task is not None and total_frames_processed % update_interval_frames == 0:
                progress_percent = int((total_frames_processed / total_frames) * 100)
                
                # Extract ETA from tqdm format string
                remaining_time = ""
                if hasattr(progress_bar, "format_dict"):
                    # Get remaining time in seconds from tqdm
                    remaining_seconds = progress_bar.format_dict.get("remaining", 0)
                    
                    # Format remaining time in the same format as tqdm displays
                    if remaining_seconds >= 3600:
                        hours = int(remaining_seconds // 3600)
                        minutes = int((remaining_seconds % 3600) // 60)
                        remaining_time = f"{hours:d}:{minutes:02d}:{int(remaining_seconds % 60):02d}"
                    elif remaining_seconds >= 60:
                        minutes = int(remaining_seconds // 60)
                        remaining_time = f"{minutes:d}:{int(remaining_seconds % 60):02d}"
                    else:
                        remaining_time = f"{remaining_seconds:.2f}s"
                        
                    # Calculate frames/second rate from tqdm
                    rate = progress_bar.format_dict.get("rate", 0)
                
                task.update_state(
                    state='PROGRESS',
                    meta={
                        'current': total_frames_processed,
                        'total': total_frames,
                        'status': f'Analyzing video: {progress_percent}%',
                        'eta': remaining_time,
                        'rate': f"{rate:.2f}it/s" if rate else ""
                    }
                )

        # --- End of Loop --- 
        print("Finished processing frames.")

    except Exception as e:
        print(f"Error during frame processing loop: {e}")
        # Clean up resources
        out.release()
        raise # Re-raise the exception to signal failure
    finally:
        # Ensure video writer is always released
        if out.isOpened():
            out.release()
            print("Video writer released.")

    # --- Final Statistics Calculation ---
    print("Calculating final statistics...")
    total_possession = sum(ball_possession_frames.values())
    stats = {
        "source_video": os.path.basename(input_path),
        "model_used": os.path.basename(model_path),
        "total_frames": total_frames,
        "frames_processed": total_frames_processed,
        "duration_seconds": total_frames / fps if fps > 0 else 0,
        "processing_time_seconds": time.time() - start_time,
        "ball_possession_frames": ball_possession_frames,
        "ball_possession_percent": {
            "team1": round((ball_possession_frames[MODEL_CLASSES["team1"]] / max(total_possession, 1)) * 100, 2),
            "team2": round((ball_possession_frames[MODEL_CLASSES["team2"]] / max(total_possession, 1)) * 100, 2)
        },
        # Add other stats like offsides if calculated
        "offsides_calculated": False, # Placeholder
        "total_offsides": 0 # Placeholder
    }

    # --- Save Statistics ---
    print(f"Saving statistics to: {output_stats_path}")
    try:
        with open(output_stats_path, 'w') as f:
            json.dump(stats, f, indent=4)
    except IOError as e:
        print(f"Error saving statistics file: {e}")
        # Decide if this is a critical error - maybe just log it?

    print(f"--- Video Analysis Complete --- ")
    
    # Return relative paths for the Flask app
    # Get the file name part only from the output paths
    result_folder_name = os.path.basename(os.path.dirname(output_video_path))
    relative_video_path = os.path.join(result_folder_name, os.path.basename(output_video_path))
    relative_stats_path = os.path.join(result_folder_name, os.path.basename(output_stats_path))
    
    return {"video_path": relative_video_path, "stats_path": relative_stats_path}