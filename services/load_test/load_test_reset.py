import asyncio
from datetime import datetime, timezone, timedelta

import httpx

CARPAYIN_URL     = "http://hd-public-alb-204074971.ap-northeast-2.elb.amazonaws.com"
PMS_URL          = "http://mockpms-public-alb-810192222.ap-northeast-2.elb.amazonaws.com"
PG_URL           = "http://mockpg-public-alb-581820362.ap-northeast-2.elb.amazonaws.com"
CARD_URL         = "http://192.168.200.200:40002/"
LOT_ID           = "LOT_GANGNAM_01"
CONCURRENT_USERS = 5
ENTRY_TIME       = (datetime.now(timezone.utc) - timedelta(hours=2)).strftime("%Y-%m-%dT%H:%M:%S")

# 테스트 후 초기화
async def main():
    # 비동기 클라이언트 생성
    async with httpx.AsyncClient() as client:
        print("=== 초기화 ===")
        # 이제 함수 내부이므로 await를 안전하게 사용할 수 있습니다.
        await client.post(f"{CARPAYIN_URL}/dev/reset")
        await client.post(f"{PMS_URL}/dev/reset")
        await client.post(f"{PG_URL}/dev/reset")
        await client.post(f"{CARD_URL}/dev/reset")
        print("초기화 완료")

# 프로그램 진입점
if __name__ == "__main__":
    asyncio.run(main())