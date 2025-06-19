import sqlite3
import os

def migrate_industry_per():
    """Add industry_per column to financial_info table."""
    db_path = os.path.join(os.path.dirname(__file__), '../db/stock_master.db')
    
    try:
        with sqlite3.connect(db_path) as conn:
            cursor = conn.cursor()
            
            # Check if column exists
            cursor.execute("PRAGMA table_info(financial_info)")
            columns = [col[1] for col in cursor.fetchall()]
            
            if 'industry_per' not in columns:
                print("Adding industry_per column to financial_info table...")
                cursor.execute("""
                    ALTER TABLE financial_info
                    ADD COLUMN industry_per FLOAT
                """)
                conn.commit()
                print("Successfully added industry_per column")
            else:
                print("industry_per column already exists")
                
    except Exception as e:
        print(f"Error during migration: {str(e)}")
        return False
        
    return True

if __name__ == "__main__":
    migrate_industry_per() 