import asyncio
from app.core.database import AsyncSessionLocal
from app.models.task import SubdomainRecord
from sqlalchemy import select

async def check_subdomains():
    try:
        async with AsyncSessionLocal() as db:
            stmt = select(SubdomainRecord).where(SubdomainRecord.task_id == '7ba9a117-90e7-459e-8285-be15047ab548')
            result = await db.execute(stmt)
            subdomains = result.scalars().all()
            print(f'Found {len(subdomains)} subdomain records in database')
            for i, subdomain in enumerate(subdomains[:10]):  # 显示前10个
                print(f'{i+1}. {subdomain.subdomain} - {subdomain.ip_address} - {"accessible" if subdomain.is_accessible else "not accessible"}')
            if len(subdomains) > 10:
                print(f'... and {len(subdomains) - 10} more')
    except Exception as e:
        print(f'Error: {e}')

if __name__ == "__main__":
    asyncio.run(check_subdomains())