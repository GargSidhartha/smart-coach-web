from rembg import remove
from PIL import Image
import numpy as np
from sklearn.cluster import KMeans



def get_player_color(frame,bbox):
    # Ensure bbox coordinates are integers and valid
    y1, x1, y2, x2 = map(int, [bbox[1], bbox[0], bbox[3], bbox[2]])
    
    # Check for valid bbox dimensions
    if y1 >= y2 or x1 >= x2:
        # Return a default color or raise an error if the bbox is invalid
        print(f"Warning: Invalid bounding box detected: {bbox}")
        return np.array([0, 0, 0]) # Default to black
        
    image_roi = frame[y1:y2, x1:x2]
    
    # Check if ROI is empty
    if image_roi.size == 0:
        print(f"Warning: Empty ROI from bounding box: {bbox}")
        return np.array([0, 0, 0]) # Default to black

    # Use rembg to remove background
    # Note: rembg might require specific input format (PIL Image)
    try:
        pil_image = Image.fromarray(cv2.cvtColor(image_roi, cv2.COLOR_BGR2RGB))
        output_image = remove(pil_image)
        output_array = np.array(output_image)
    except Exception as e:
        print(f"Error during background removal with rembg: {e}")
        # Fallback: Use original ROI if rembg fails
        output_array = cv2.cvtColor(image_roi, cv2.COLOR_BGR2RGBA) # Need RGBA

    # Check if output array is valid
    if output_array.shape[0] == 0 or output_array.shape[1] == 0:
         print(f"Warning: Empty image after background removal for bbox: {bbox}")
         return np.array([0, 0, 0]) # Default to black

    pixels = output_array.reshape(-1, 4) 
    # Keep only non-transparent pixels
    pixels = pixels[pixels[:, 3] > 10] # Use a threshold for transparency

    # Check if any foreground pixels remain
    if len(pixels) == 0:
        print(f"Warning: No foreground pixels found after background removal for bbox: {bbox}. Analyzing original ROI.")
        # Fallback: Analyze the original ROI without transparency check
        output_array = cv2.cvtColor(image_roi, cv2.COLOR_BGR2RGB)
        pixels = output_array.reshape(-1, 3)
        if len(pixels) == 0:
             print(f"Error: Original ROI is also empty for bbox: {bbox}")
             return np.array([0, 0, 0]) # Default to black

    # Use KMeans for color clustering
    n_clusters = 3  
    # Handle case with fewer pixels than clusters
    actual_clusters = min(n_clusters, len(pixels))
    if actual_clusters < 1:
        print(f"Error: No pixels to cluster for bbox: {bbox}")
        return np.array([0, 0, 0]) # Default to black

    kmeans = KMeans(n_clusters=actual_clusters, n_init=10) # Use n_init explicitly
    try:
        kmeans.fit(pixels[:, :3])  # Use RGB channels
    except Exception as e:
        print(f"Error during KMeans fitting: {e}")
        return np.array([0, 0, 0]) # Default to black

    cluster_centers = kmeans.cluster_centers_
    _, counts = np.unique(kmeans.labels_, return_counts=True)

    # Get the dominant color (most frequent cluster)
    sorted_indices = np.argsort(counts)[::-1]
    dominant_color = cluster_centers[sorted_indices[0]]

    # Return dominant color as BGR (OpenCV standard)
    return dominant_color[::-1] # Convert RGB to BGR

# Need cv2 for color conversion if rembg fails or for PIL conversion
import cv2 