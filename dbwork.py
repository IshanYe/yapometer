import sqlite3 

connection = sqlite3.connect('dbwork.db')

cursor = connection.cursor()

cursor.execute("""
    CREATE TABLE IF NOT EXISTS test (
        column_a INTEGER,
        column_b TEXT,
        column_c INTEGER,

        PRIMARY KEY (column_a, column_b)
    )
""")

# for i in range(1, 5):
#     for j in range(1):
#         cursor.execute("""
#             INSERT INTO test 
#             (column_a, column_b, column_c)

#             VALUES (?, ?, ?)
#         """, (
#             i,
#             "aura",
#             j
#         ))

#         connection.commit()

# for i in range(1, 5):
#     for j in range (1, 6): 
#         cursor.execute ("""
#             INSERT INTO test
#             (column_a, column_b, column_c)

#             VALUES (?, ?, ?)

#             ON CONFLICT (column_a, column_b)

#             DO UPDATE SET
#             column_c = column_c + 10
#         """, 
#         (i, "aura", j)
#         ) 

#         connection.commit()

cursor.execute("""
    SELECT column_c 

    FROM test

    WHERE column_a = ?
""",
(1,))

print (cursor.fetchone()[0])