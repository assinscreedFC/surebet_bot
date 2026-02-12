#!/usr/bin/env python3
"""
Script pour vérifier l'état de la base de données
"""
import sqlite3

conn = sqlite3.connect('surebet.db')
cursor = conn.cursor()

# Lister les tables
cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
tables = cursor.fetchall()
print("=" * 50)
print("TABLES DANS LA DB:")
print("=" * 50)
for t in tables:
    cursor.execute(f"SELECT COUNT(*) FROM {t[0]}")
    count = cursor.fetchone()[0]
    print(f"  {t[0]}: {count} enregistrements")

# Vérifier les surebets
print("\n" + "=" * 50)
print("SUREBETS ENREGISTRÉS:")
print("=" * 50)
cursor.execute("SELECT * FROM surebets ORDER BY detected_at DESC LIMIT 5")
rows = cursor.fetchall()
if rows:
    for row in rows:
        print(row)
else:
    print("  Aucun surebet enregistré")

# Vérifier l'usage API
print("\n" + "=" * 50)
print("HISTORIQUE USAGE API:")
print("=" * 50)
cursor.execute("SELECT * FROM api_usage ORDER BY timestamp DESC LIMIT 10")
rows = cursor.fetchall()
if rows:
    for row in rows:
        print(f"  {row}")
else:
    print("  Aucun usage API enregistré")

# Vérifier les logs
print("\n" + "=" * 50)
print("DERNIERS LOGS:")
print("=" * 50)
cursor.execute("SELECT * FROM logs ORDER BY timestamp DESC LIMIT 10")
rows = cursor.fetchall()
if rows:
    for row in rows:
        print(f"  [{row[2]}] {row[3][:80]}...")
else:
    print("  Aucun log enregistré")

conn.close()
