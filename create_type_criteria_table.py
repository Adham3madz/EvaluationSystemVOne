
import pyodbc
from config import CONNECTION_STRING

def migrate():
    try:
        conn = pyodbc.connect(CONNECTION_STRING)
        cursor = conn.cursor()
        
        # Check if table exists
        cursor.execute("SELECT COUNT(*) FROM INFORMATION_SCHEMA.TABLES WHERE TABLE_NAME = 'EvaluationTypeCriteria'")
        if cursor.fetchone()[0] == 0:
            print("Creating EvaluationTypeCriteria table...")
            cursor.execute("""
                CREATE TABLE [Optima].[dbo].[EvaluationTypeCriteria] (
                    LinkID INT IDENTITY(1,1) PRIMARY KEY,
                    EvaluationTypeID INT NOT NULL,
                    CriteriaID INT NOT NULL,
                    CONSTRAINT FK_TypeCriteria_Type FOREIGN KEY (EvaluationTypeID) REFERENCES [Optima].[dbo].[EvaluationTypes](EvaluationTypeID),
                    CONSTRAINT FK_TypeCriteria_Crit FOREIGN KEY (CriteriaID) REFERENCES [Optima].[dbo].[EvaluationCriteria](CriteriaID) ON DELETE CASCADE
                )
            """)
            conn.commit()
            print("Table created successfully.")
        else:
            print("Table already exists.")

        # --- SEEDING LOGIC (Link existing criteria to ALL types initially or specific?) ---
        # The user said "can we connect it". To avoid breaking the current system (where criteria appear for everyone),
        # we might want to link all existing criteria to *ALL* existing types, OR just leave them unlinked and fix logic.
        # BUT, if I change the logic to use this table, and the table is empty, NO criteria will show up!
        # SO, I MUST seed links for existing data.
        
        print("Seeding initial links...")
        
        # 1. Get all Criteria
        cursor.execute("SELECT CriteriaID, employee_class, CriteriaName FROM [Optima].[dbo].[EvaluationCriteria]")
        all_criteria = cursor.fetchall()
        
        # 2. Get all Types
        cursor.execute("SELECT EvaluationTypeID FROM [Optima].[dbo].[EvaluationTypes]")
        all_types = [r[0] for r in cursor.fetchall()]
        
        count = 0
        for crit in all_criteria:
            crit_id = crit.CriteriaID
            crit_name = crit.CriteriaName
            crit_class = crit.employee_class
            
            # Smart Seeding based on recent context?
            # The user uploaded an image for "15 Days" criteria.
            # But generally, safer to link to ALL types initially so nothing disappears, 
            # and let the user uncheck what they don't want.
            
            for type_id in all_types:
                # Check link
                cursor.execute("SELECT COUNT(*) FROM [Optima].[dbo].[EvaluationTypeCriteria] WHERE EvaluationTypeID=? AND CriteriaID=?", (type_id, crit_id))
                if cursor.fetchone()[0] == 0:
                    cursor.execute("INSERT INTO [Optima].[dbo].[EvaluationTypeCriteria] (EvaluationTypeID, CriteriaID) VALUES (?, ?)", (type_id, crit_id))
                    count += 1
        
        conn.commit()
        print(f"Seeded {count} links (Linked all existing criteria to all types to ensure visibility).")
            
    except Exception as e:
        print(f"Error: {e}")
    finally:
        if conn: conn.close()

if __name__ == "__main__":
    migrate()
