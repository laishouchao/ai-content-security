import asyncio
from app.core.database import AsyncSessionLocal
from app.models.task import ThirdPartyDomain
from sqlalchemy import select

async def check_domains():
    try:
        async with AsyncSessionLocal() as db:
            stmt = select(ThirdPartyDomain).where(ThirdPartyDomain.task_id == '7ba9a117-90e7-459e-8285-be15047ab548')
            result = await db.execute(stmt)
            domains = result.scalars().all()
            print(f'Found {len(domains)} third party domains in database')
            for i, domain in enumerate(domains[:5]):  # 显示前5个
                print(f'{i+1}. {domain.domain} - {domain.domain_type} - {domain.risk_level}')
            if len(domains) > 5:
                print(f'... and {len(domains) - 5} more')
    except Exception as e:
        print(f'Error: {e}')

if __name__ == "__main__":
    asyncio.run(check_domains())