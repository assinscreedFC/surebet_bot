#!/usr/bin/env python3
"""Script pour vérifier les sports disponibles sur The Odds API."""

import asyncio
import sys
sys.path.insert(0, '.')

from core.odds_client import OddsClient

async def check_sports():
    client = OddsClient('1972bdce61e6fd1e7dbbbea1e937cfbc')
    resp = await client.get_sports()
    
    if not resp.success:
        print(f"Erreur: {resp.error}")
        return
    
    print("=== SPORTS FOOTBALL DISPONIBLES ===")
    football = [s for s in resp.data if 'soccer' in s['key'] and s.get('active')]
    for s in sorted(football, key=lambda x: x['title']):
        print(f"  '{s['key']}': \"{s['title']}\",")
    
    print("\n=== SPORTS US DISPONIBLES ===")
    us = [s for s in resp.data if s['key'].startswith(('basketball', 'americanfootball', 'tennis')) and s.get('active')]
    for s in sorted(us, key=lambda x: x['title']):
        print(f"  '{s['key']}': \"{s['title']}\",")
    
    await client.close()
    print(f"\nRequêtes restantes: {resp.requests_remaining}")

if __name__ == "__main__":
    asyncio.run(check_sports())
