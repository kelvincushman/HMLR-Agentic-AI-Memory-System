"""
Check if facts exist in fact_store for processed bridge blocks
"""
import sqlite3

conn = sqlite3.connect('hmlr/memory/cognitive_lattice_memory.db')
c = conn.cursor()

# Get the blocks we processed
blocks = [
    'bb_20251211_cf025c8d',  # Mountains in China
    'bb_20251211_827756fe',  # Basic Arithmetic
    'bb_20251211_8f000d46',  # Moon Facts
    'bb_20251210_4ecf1c9e'   # Mountains in China
]

print("\n" + "="*80)
print("FACT STORE CHECK FOR PROCESSED BLOCKS")
print("="*80 + "\n")

for block_id in blocks:
    c.execute("""
        SELECT COUNT(*) FROM fact_store 
        WHERE block_id = ?
    """, (block_id,))
    
    count = c.fetchone()[0]
    print(f"{block_id}: {count} facts")
    
    if count > 0:
        c.execute("""
            SELECT key, value FROM fact_store 
            WHERE block_id = ? 
            LIMIT 3
        """, (block_id,))
        
        facts = c.fetchall()
        for key, value in facts:
            print(f"  - {key}: {value[:60]}...")

print("\n" + "="*80)

# Check total facts
c.execute("SELECT COUNT(*) FROM fact_store")
total = c.fetchone()[0]
print(f"\nTotal facts in fact_store: {total}")

conn.close()
