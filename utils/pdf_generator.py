import os
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import A4
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont

# Attempt to import Arabic reshaper tools. 
# If missing (offline server), we fallback to rendering text as-is.
try:
    import arabic_reshaper
    from bidi.algorithm import get_display
    HAS_ARABIC_SUPPORT = True
except ImportError:
    HAS_ARABIC_SUPPORT = False

# Register a font that supports Arabic (using a standard Windows font if available, or fallback)
FONT_PATH = "C:\\Windows\\Fonts\\arial.ttf" # Common on Windows
try:
    pdfmetrics.registerFont(TTFont('ArabicFont', FONT_PATH))
except:
    # Fallback if specific font not found
    pass

def reshaped_text(text):
    if not text:
        return ""
    if not HAS_ARABIC_SUPPORT:
        return text
    try:
        reshaped = arabic_reshaper.reshape(text)
        bidi_text = get_display(reshaped)
        return bidi_text
    except:
        return text

def draw_text(c, text, x, y, font_size=12, color=(0,0,0)):
    if not text:
        return
    try:
        c.setFont('ArabicFont', font_size)
        c.setFillColorRGB(*color)
        c.drawRightString(x, y, reshaped_text(text)) 
    except:
        pass

def generate_form_pdf(data):
    # Updated paths for EvaluationSystem
    output_dir = "D:/evaluationSystem/output"
    os.makedirs(output_dir, exist_ok=True)
    output_path = os.path.join(output_dir, "filled_form.pdf")
    
    c = canvas.Canvas(output_path, pagesize=A4)
    width, height = A4
    
    # --- PAGE 1 ---
    page1_img = "D:/evaluationSystem/static/assets/page1.png"
    if os.path.exists(page1_img):
        c.drawImage(page1_img, 0, 0, width=width, height=height)
    
    # Column X coordinates (Right to Left): 
    col_x = [550, 420, 310, 200, 80]
    
    # Helper to draw dynamic rows with a safety limit
    def draw_section(prefix, start_y, max_rows):
        row_h = 25
        y = start_y
        for i in range(1, 20): # Try up to 20, but stop if no data or max reached
            # Check if this row has data
            name_key = f'{prefix}_name_{i}'
            if name_key not in data and f'{prefix}_name_{i}' not in data:
                break # No more data for this prefix
            
            # Stop if we exceed visual space (optional, depending on strictness)
            if i > max_rows:
                 # You might want to handle overflow pages here in the future
                 break

            draw_text(c, data.get(f'{prefix}_name_{i}'), col_x[0], y)
            draw_text(c, data.get(f'{prefix}_dob_{i}'), col_x[1], y)
            draw_text(c, data.get(f'{prefix}_job_{i}'), col_x[2], y)
            draw_text(c, data.get(f'{prefix}_address_{i}'), col_x[3], y)
            draw_text(c, data.get(f'{prefix}_phone_{i}'), col_x[4], y)
            
            y -= row_h

    # 1. Personal Info Section (3 Rows)
    r1_y = 745
    draw_text(c, data.get('sub_department'), 550, r1_y)
    draw_text(c, data.get('join_date'), 350, r1_y)
    draw_text(c, data.get('birth_date'), 150, r1_y)

    r2_y = 720
    draw_text(c, data.get('national_id'), 550, r2_y)
    draw_text(c, data.get('phone'), 350, r2_y)
    draw_text(c, data.get('job_nature'), 150, r2_y)

    r3_y = 695
    draw_text(c, data.get('current_address'), 500, r3_y)
    draw_text(c, data.get('previous_address'), 200, r3_y)

    # 2. Spouse (1 Row - but dynamic allowed)
    draw_section('spouse', 650, 2)

    # 3. Parents (2 Rows)
    draw_section('parent', 610, 2)

    # 4. Siblings (4 Rows)
    draw_section('sibling', 540, 6) # Relaxed limit to 6

    # 5. Children (3 Rows)
    draw_section('child', 430, 6) # Relaxed limit to 6

    # 6. Paternal Uncles/Aunts (3 Rows)
    draw_section('p_uncle', 330, 5)

    # 7. Paternal Cousins (First 2 Rows on Page 1) - Special checking because split
    # Actually, simpler to just draw up to 2 here
    y_start = 230
    row_h = 25
    for i in range(1, 3):
        y = y_start - ((i-1)*row_h)
        if f'p_cousin_name_{i}' in data:
            draw_text(c, data.get(f'p_cousin_name_{i}'), col_x[0], y)
            draw_text(c, data.get(f'p_cousin_dob_{i}'), col_x[1], y)
            draw_text(c, data.get(f'p_cousin_job_{i}'), col_x[2], y)
            draw_text(c, data.get(f'p_cousin_address_{i}'), col_x[3], y)
            draw_text(c, data.get(f'p_cousin_phone_{i}'), col_x[4], y)

    c.showPage()
    
    # --- PAGE 2 ---
    page2_img = "D:/evaluationSystem/static/assets/page2.png"
    if os.path.exists(page2_img):
        c.drawImage(page2_img, 0, 0, width=width, height=height)

    # 7. Paternal Cousins (Continued - Rows 3+)
    y_start = 730
    bg_start_idx = 3
    for i in range(bg_start_idx, 20): # Try up to 20
        y = y_start - ((i - bg_start_idx)*row_h)
        if f'p_cousin_name_{i}' not in data:
            break
        # Page 2 limits?
        if y < 600: # Stop if we hit Maternal Uncles area (approx 580)
            break
            
        draw_text(c, data.get(f'p_cousin_name_{i}'), col_x[0], y)
        draw_text(c, data.get(f'p_cousin_dob_{i}'), col_x[1], y)
        draw_text(c, data.get(f'p_cousin_job_{i}'), col_x[2], y)
        draw_text(c, data.get(f'p_cousin_address_{i}'), col_x[3], y)
        draw_text(c, data.get(f'p_cousin_phone_{i}'), col_x[4], y)
        
    # 8. Maternal Uncles/Aunts (4 Rows)
    draw_section('m_uncle', 580, 6)

    # 9. Maternal Cousins (4 Rows)
    draw_section('m_cousin', 430, 10)

    c.save()
    return output_path
