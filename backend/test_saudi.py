import asyncio
from app.services.data_scraper import scrape_espn_results, scrape_upcoming_fixtures

async def test_saudi():
    print("Testing ESPN values...")
    r = await scrape_espn_results('Saudi Pro League')
    f = await scrape_upcoming_fixtures('Saudi Pro League')
    print('Results:', len(r), 'Fixtures:', len(f))

if __name__ == "__main__":
    asyncio.run(test_saudi())
