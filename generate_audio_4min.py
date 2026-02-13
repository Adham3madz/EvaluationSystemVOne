import re
from gtts import gTTS
import os
import sys

def clean_markdown(text):
    # Remove markdown bold/italics
    text = re.sub(r'\*\*(.*?)\*\*', r'\1', text)
    text = re.sub(r'\*(.*?)\*', r'\1', text)
    # Remove any stray newlines or weird chars
    text = text.replace('\n', ' ').strip()
    return text

def extract_voiceover_text(file_path):
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            lines = f.readlines()

        voice_over_text = []
        capture = False
        current_block = ""
        
        for line in lines:
            line = line.strip()
            
            # Start capturing when we see the Voice Over header
            if "**[التعليق الصوتي / Voice Over]:**" in line:
                capture = True
                continue
            
            # Stop capturing when we hit a separator or a new section header
            if capture and (line.startswith("---") or line.startswith("###") or line.startswith("**[")):
                capture = False
                if current_block:
                    voice_over_text.append(current_block)
                    current_block = ""
                continue
            
            if capture and line:
                # Accumulate text, removing quotes if present at start/end
                clean_line = line.strip('"')
                if clean_line:
                    current_block += clean_line + " "
        
        # Determine if last block needs adding
        if capture and current_block:
             voice_over_text.append(current_block)

        # Join all blocks
        full_text = " ".join(voice_over_text)
        
        # Clean markdown
        full_text = clean_markdown(full_text)
        
        return full_text

    except Exception as e:
        print(f"Error reading file {file_path}: {e}")
        return None

def generate_audio(text, output_file):
    if not text:
        print("No text found to convert.")
        return

    print(f"Generating audio from {len(text)} characters...")
    try:
        tts = gTTS(text=text, lang='ar')
        tts.save(output_file)
        print(f"SUCCESS: Audio saved to: {output_file}")
    except Exception as e:
        print(f"ERROR: {e}")

if __name__ == "__main__":
    script_path = r"d:\evaluationSystem\AURA_HR_DETAILED_SCRIPT_4MIN.md"
    output_path = r"d:\evaluationSystem\AURA_HR_DETAILED_voiceover.mp3"
    
    if not os.path.exists(script_path):
        print(f"File not found: {script_path}")
        sys.exit(1)

    print(f"Reading script from: {script_path}")
    voiceover_text = extract_voiceover_text(script_path)
    
    if voiceover_text:
        # print(f"Preview: {voiceover_text[:200]}...")
        generate_audio(voiceover_text, output_path)
    else:
        print("Could not extract any voice over text from the file.")
