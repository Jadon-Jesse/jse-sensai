import sqlite3


def get_db_connection():
    conn = sqlite3.connect('database.db')
    conn.row_factory = sqlite3.Row
    return conn


conn = get_db_connection()

# Create a cursor object
cursor = conn.cursor()

posts = conn.execute('SELECT * FROM sens ORDER BY datetime(created) DESC LIMIT 10').fetchall()
# Get the last row id

for  post in posts:

    # set ai amd article stuff to blank so we can re processs on click
    blanks="-"

    cursor.execute("UPDATE sens SET gptreview = ? WHERE id = ?",
        (blanks, post['id'])
    )

    cursor.execute("UPDATE sens SET gpttitle = ? WHERE id = ?",
        ( blanks, post['id'])
    )

    conn.commit()

    # Print the last row id
    print("Last Row ID:", post["id"])

# Close the cursor and the database connection
cursor.close()
conn.close()