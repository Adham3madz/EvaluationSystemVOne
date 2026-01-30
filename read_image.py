
import pytesseract
from PIL import Image
import sys

# Path from prompt
image_path = r"C:/Users/zizo/.gemini/antigravity/brain/9ccda004-f15a-4dcb-a96a-aa4c4d877f2c/uploaded_image_1769098552297.png"

try:
    # Set tesseract cmd path if needed (Start with default)
    # pytesseract.pytesseract.tesseract_cmd = r'C:\Program Files\Tesseract-OCR\tesseract.exe'
    
    text = pytesseract.image_to_string(Image.open(image_path), lang='ara+eng')
    print("--- OCR RESULT START ---")
    print(text)
    print("--- OCR RESULT END ---")
except Exception as e:
    print(f"OCR Error: {e}")
    # Fallback: List suggested criteria if OCR fails?
    print("Could not read image. Please confirm if tesseract is installed.")
