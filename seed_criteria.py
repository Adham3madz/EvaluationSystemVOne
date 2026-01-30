
import pyodbc
from config import CONNECTION_STRING

def seed_criteria():
    conn = pyodbc.connect(CONNECTION_STRING)
    cursor = conn.cursor()
    
    # Target Classes (Internal Names)
    # A, B, C, اداري (for B), اداري C, فني (for C), فني A
    target_classes = ['A', 'B', 'C', 'اداري', 'اداري C', 'فني', 'فني A']
    class_string = ",".join(target_classes)
    
    # Criteria Data from Image
    criteria_list = [
        {"name": "جودة العمل (اتقان-دقة)", "weight": 0.20, "max": 10},
        {"name": "الحماس للعمل وسرعة الإنجاز", "weight": 0.20, "max": 10},
        {"name": "أطاعه الأوامر وتعليمات التشغيل", "weight": 0.15, "max": 10},
        {"name": "القدرة على تحمل ضغوط العمل", "weight": 0.10, "max": 10},
        {"name": "المرونة والتكيف مع بيئة العمل", "weight": 0.10, "max": 10},
        {"name": "الالتزام بالسياسات العامة", "weight": 0.05, "max": 5},
        {"name": "التعاون مع الزملاء", "weight": 0.05, "max": 5},
        {"name": "احترام الزملاء والرؤساء", "weight": 0.05, "max": 5},
        {"name": "المظهر العام", "weight": 0.10, "max": 5}
    ]

    print(f"Targeting Classes: {class_string}")
    
    for c in criteria_list:
        try:
            # Check if exists (by name) - we might want to update or skip
            # For this task, we skip if exact name exists to avoid duplicates
            cursor.execute("SELECT COUNT(*) FROM [Optima].[dbo].[EvaluationCriteria] WHERE CriteriaName = ?", (c['name'],))
            exists = cursor.fetchone()[0] > 0
            
            if exists:
                print(f"Skipping (Already Exists): {c['name']}")
                # Optional: Update the class string if you want to ensure these classes are included
                # cursor.execute("UPDATE [Optima].[dbo].[EvaluationCriteria] SET employee_class = ? WHERE CriteriaName = ?", (class_string, c['name']))
            else:
                cursor.execute("""
                    INSERT INTO [Optima].[dbo].[EvaluationCriteria] 
                    (CriteriaName, CriteriaWeight, MaxScore, AppliesToDeptID, employee_class) 
                    VALUES (?, ?, ?, NULL, ?)
                """, (c['name'], c['weight'], c['max'], class_string))
                print(f"Added: {c['name']}")
                
        except Exception as e:
            print(f"Error adding {c['name']}: {e}")

    conn.commit()
    conn.close()
    print("Done.")

if __name__ == "__main__":
    seed_criteria()
