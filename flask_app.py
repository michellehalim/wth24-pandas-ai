import os
import time
import random
import requests
from flask import Flask, request, jsonify
import vertexai
from vertexai.preview.generative_models import GenerativeModel, Image

# Vertex AI configuration
PROJECT_ID = "wth24-445408"
REGION = "asia-east1"

# Initialize Vertex AI
vertexai.init(project=PROJECT_ID, location=REGION)

app = Flask(__name__)

def download_image(image_url, local_path="temp_image.jpg"):
    """Download an image from a Firebase Storage URL and save it locally."""
    response = requests.get(image_url, stream=True)
    if response.status_code == 200:
        with open(local_path, "wb") as file:
            for chunk in response.iter_content(1024):
                file.write(chunk)
        print(f"Image downloaded successfully: {image_url}")
    else:
        raise Exception(f"Failed to download image from URL: {response.status_code}")

def analyze_image(image_file_path):
    """Analyze an image using Vertex AI."""
    # Load the image
    image = Image.load_from_file(image_file_path)

    # Initialize the generative multimodal model
    generative_multimodal_model = GenerativeModel("gemini-1.5-pro-001")

    def generate_content_with_backoff(prompt, image, retries=5):
        """Handle exponential backoff for Vertex AI requests."""
        for i in range(retries):
            try:
                response = generative_multimodal_model.generate_content([prompt, image])
                return response
            except Exception as e:
                if "429" in str(e):
                    wait_time = (2 ** i) + random.uniform(0, 1)
                    print(f"Rate limit exceeded. Retrying in {wait_time:.2f} seconds...")
                    time.sleep(wait_time)
                else:
                    raise e
        raise Exception("Maximum retries exceeded")

    # Create the prompt
    prompt = (
        "Classify the image into one of the following categories: 'Clothes', 'Toys', 'Books', 'Electronics', 'Stationery' or 'Others'. "
        "Provide a detailed and specific name for the item, including relevant details such as brand, model, or type. "
        "Give a short description (min 30 words and max 50 words), describing the main features and appearance of the item. "
        "Additionally, assess the quality of the item based on visual appearance. "
        "Categorize the quality of the item into one of the following categories: 'excellent', 'good', 'fair', or 'poor'. "
        "Return the results in the following format:\n"
        "Category: <Category>\n"
        "Item: <Item Name>\n"
        "Description: <Item Description>\n"
        "Quality: <Quality Category>"
    )

    # Generate content
    response = generate_content_with_backoff(prompt, image)

    # Parse the response
    category, item, description, quality = None, None, None, None
    if response and response.text:
        lines = response.text.splitlines()
        for line in lines:
            if line.lower().startswith("category:"):
                category = line[len("Category:"):].strip()
            elif line.lower().startswith("item:"):
                item = line[len("Item:"):].strip()
            elif line.lower().startswith("description:"):
                description = line[len("Description:"):].strip()
            elif line.lower().startswith("quality:"):
                quality = line[len("Quality:"):].strip()

    return category, item, description, quality

@app.route('/analyze-image', methods=['POST'])
def analyze_image_api():
    """API endpoint to analyze an image from a Firebase URL."""
    try:
        data = request.json
        image_url = data.get("image_url")  # Get the image URL from the request

        if not image_url:
            return jsonify({"error": "image_url is required"}), 400

        # Download the image from the URL
        local_path = "temp_image.jpg"
        download_image(image_url, local_path)

        # Analyze the image
        category, item, description, quality = analyze_image(local_path)

        # Clean up the temporary file
        if os.path.exists(local_path):
            os.remove(local_path)

        # Return the analysis results
        return jsonify({
            "category": category,
            "item": item,
            "description": description,
            "quality": quality
        })

    except Exception as e:
        return jsonify({"error": str(e)}), 500

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8080)