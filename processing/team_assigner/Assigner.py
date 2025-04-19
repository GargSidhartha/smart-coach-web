from sklearn.cluster import KMeans
import cv2
import numpy as np

class Assigner:
    def __init__(self) -> None:
         self.team_colors={}

    def get_clustering_model(self,image):
        # Ensure image is not empty
        if image.size == 0:
            print("Warning: Empty image passed to get_clustering_model")
            # Return a dummy model or handle error appropriately
            # Returning a model fitted on black might work in some cases
            dummy_kmeans = KMeans(n_clusters=2, n_init=1)
            # Provide a single sample with 3 features (HSV)
            dummy_kmeans.fit(np.array([[0,0,0]])) 
            return dummy_kmeans
            
        # Assuming input is BGR, convert to HSV
        image_hsv = cv2.cvtColor(image, cv2.COLOR_BGR2HSV) 
        # Handle potential empty dimensions after operations
        if image_hsv.shape[0] == 0 or image_hsv.shape[1] == 0:
            print("Warning: Image dimensions became zero after HSV conversion")
            dummy_kmeans = KMeans(n_clusters=2, n_init=1)
            dummy_kmeans.fit(np.array([[0,0,0]]))
            return dummy_kmeans
            
        image_2d = image_hsv.reshape(-1,3)
        # Perform K-means with 2 clusters
        kmeans = KMeans(n_clusters=2, n_init='auto', random_state=42) # Use fixed random_state for reproducibility
        kmeans.fit(image_2d)

        return kmeans

    def get_player_team(self, frame, player_bbox, kmeans):
            player_color_hsv = self.get_player_color(frame, player_bbox)
            # Ensure player_color is valid before predicting
            if player_color_hsv is None:
                 print("Warning: Could not determine player color, assigning default team 0")
                 return 0 # Default assignment
            # KMeans expects input shape (n_samples, n_features)
            team_id = kmeans.predict(player_color_hsv.reshape(1, -1))[0] 
            return team_id

    def get_player_color(self, frame, bbox):
        # Ensure bbox coordinates are integers and valid
        y1, x1, y2, x2 = map(int, [bbox[1], bbox[0], bbox[3], bbox[2]])
        if y1 >= y2 or x1 >= x2:
            print(f"Warning: Invalid player bbox for color extraction: {bbox}")
            return None # Indicate failure to get color
            
        image = frame[y1:y2, x1:x2]
        if image.size == 0:
            print(f"Warning: Empty ROI for player color extraction: {bbox}")
            return None

        # Process top half for team color (less likely to have grass)
        top_half_image = image[0:int(image.shape[0] / 2), :]
        if top_half_image.size == 0:
             print(f"Warning: Empty top half ROI for player color extraction: {bbox}")
             # Fallback to using the full image if top half is too small
             top_half_image = image 
             if top_half_image.size == 0:
                 return None

        kmeans = self.get_clustering_model(top_half_image)
        # Check if clustering produced valid centers
        if not hasattr(kmeans, 'cluster_centers_') or len(kmeans.cluster_centers_) < 2:
             print("Warning: Clustering failed to produce enough centers.")
             return None
             
        labels = kmeans.labels_
        if labels is None or len(labels) == 0:
            print("Warning: Clustering produced no labels.")
            return None

        # Handle potential clustering issues (e.g., only one cluster found)
        try:
            # Need to handle if top_half_image was 1D after slicing
            if len(top_half_image.shape) < 2 or top_half_image.shape[0] == 0 or top_half_image.shape[1] == 0:
                 print(f"Warning: Cannot reshape labels for bbox: {bbox}")
                 return None
            
            reshaped_labels = labels.reshape(top_half_image.shape[0], top_half_image.shape[1])
            # Ensure indices are within bounds
            h, w = reshaped_labels.shape
            if h == 0 or w == 0:
                print(f"Warning: Reshaped labels have zero dimension for bbox: {bbox}")
                return None
                
            corners = [
                reshaped_labels[0, 0],
                reshaped_labels[0, w-1],
                reshaped_labels[h-1, 0],
                reshaped_labels[h-1, w-1]
            ]
            non_player_cluster = max(set(corners), key=corners.count)
            player_cluster = 1 - non_player_cluster
            player_color_hsv = kmeans.cluster_centers_[player_cluster]
        except IndexError as e:
             print(f"Warning: Error accessing cluster labels/centers (IndexError: {e}). Bbox: {bbox}")
             # Fallback: Average color of the ROI (converted to HSV)
             try:
                 avg_color_bgr = np.mean(top_half_image.reshape(-1, 3), axis=0)
                 player_color_hsv = cv2.cvtColor(np.uint8([[avg_color_bgr]]), cv2.COLOR_BGR2HSV)[0][0]
             except Exception as avg_e:
                 print(f"Error calculating fallback average color: {avg_e}")
                 return None
        except Exception as e:
            print(f"Warning: Error during player color determination ({type(e).__name__}: {e}). Bbox: {bbox}")
            return None

        return player_color_hsv # This is in HSV space

    def assign_team_color(self, frame, players_detections):
            player_colors_hsv = []
            for _, bbox in enumerate(players_detections.xyxy):
                # Ensure bbox is valid list/tuple/array of 4 numbers
                if not isinstance(bbox, (list, tuple, np.ndarray)) or len(bbox) != 4:
                    print(f"Warning: Skipping invalid bbox format: {bbox}")
                    continue
                player_color = self.get_player_color(frame, bbox)
                if player_color is not None:
                    player_colors_hsv.append(player_color)
            
            if len(player_colors_hsv) < 2:
                 print("Warning: Not enough player colors detected (<2) to assign teams via clustering.")
                 # Assign default colors or handle error
                 self.team_colors[1] = np.array([100, 255, 255]) # Example Blue in HSV
                 self.team_colors[2] = np.array([0, 255, 255])   # Example Red in HSV
                 # Return a dummy kmeans fitted on these defaults
                 kmeans = KMeans(n_clusters=2, n_init=10)
                 # Ensure fit input is 2D array-like
                 fit_data = np.array(player_colors_hsv) if len(player_colors_hsv) > 0 else np.array([self.team_colors[1], self.team_colors[2]])
                 if len(fit_data.shape) == 1: # Handle single color case
                     fit_data = np.vstack([fit_data, fit_data]) # Duplicate if only one color found
                 if len(fit_data) < 2: # Still not enough? Use defaults
                     fit_data = np.array([self.team_colors[1], self.team_colors[2]])

                 try:
                      kmeans.fit(fit_data)
                 except Exception as fit_e:
                     print(f"Error fitting KMeans with default/limited data: {fit_e}")
                     # Cannot proceed without a model
                     return None
                 return kmeans
                 
            # Cluster the collected HSV colors
            kmeans = KMeans(n_clusters=2, init="k-means++", n_init=10, random_state=42)
            kmeans.fit(player_colors_hsv)
            
            # Store cluster centers (team average colors in HSV)
            self.team_colors[1] = kmeans.cluster_centers_[0]
            self.team_colors[2] = kmeans.cluster_centers_[1]
            # print(f"Assigned Team Colors (HSV): Team1={self.team_colors[1]}, Team2={self.team_colors[2]}")
            return kmeans 