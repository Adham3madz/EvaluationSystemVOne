
import pyodbc
from config import CONNECTION_STRING

def organize_15_days():
    conn = pyodbc.connect(CONNECTION_STRING)
    cursor = conn.cursor()

    # The list from Step 63
    criteria_15_days = [
        "جودة العمل (اتقان-دقة)",
        "الحماس للعمل وسرعة الإنجاز",
        "أطاعه الأوامر وتعليمات التشغيل",
        "القدرة على تحمل ضغوط العمل",
        "المرونة والتكيف مع بيئة العمل",
        "الالتزام بالسياسات العامة",
        "التعاون مع الزملاء",
        "احترام الزملاء والرؤساء",
        "المظهر العام"
    ]

    print("--- Isolating 15-Day Criteria ---")
    
    # Get ID for '15 يوم'
    cursor.execute("SELECT EvaluationTypeID FROM [AURAHR].[dbo].[EvaluationTypes] WHERE DisplayName LIKE '%15%'")
    row = cursor.fetchone()
    if not row:
        print("Error: Could not find '15 يوم' type.")
        return
    type_15_id = row.EvaluationTypeID
    print(f"Target Type ID: {type_15_id} (15 Days)")

    for name in criteria_15_days:
        # Find Criteria ID
        cursor.execute("SELECT CriteriaID FROM [AURAHR].[dbo].[EvaluationCriteria] WHERE CriteriaName = ?", (name,))
        c_row = cursor.fetchone()
        if c_row:
            cid = c_row.CriteriaID
            
            # Remove ALL current links
            cursor.execute("DELETE FROM [AURAHR].[dbo].[EvaluationTypeCriteria] WHERE CriteriaID = ?", (cid,))
            
            # Add ONLY 15-day link
            cursor.execute("INSERT INTO [AURAHR].[dbo].[EvaluationTypeCriteria] (EvaluationTypeID, CriteriaID) VALUES (?, ?)", (type_15_id, cid))
            print(f"Updated '{name}' -> Only 15 Days")
        else:
            print(f"Warning: '{name}' not found.")

    conn.commit()
    conn.close()
    print("Done.")

if __name__ == "__main__":
    organize_15_days()
