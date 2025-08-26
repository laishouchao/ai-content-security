import asyncio
import redis
import json

async def check_redis_data():
    try:
        # 连接Redis (使用远程Redis服务器)
        r = redis.Redis(host='115.190.95.157', port=6379, password='yourredispassword', db=0, decode_responses=True)
        
        task_id = '7ba9a117-90e7-459e-8285-be15047ab548'
        
        # 检查任务相关的所有key
        keys = r.keys(f"*{task_id}*")
        print(f"Found {len(keys)} keys for task {task_id}:")
        
        for key in keys:
            data_type = r.type(key)
            print(f"\nKey: {key} (type: {data_type})")
            
            if data_type == 'string':
                value = r.get(key)
                try:
                    # 尝试解析为JSON
                    parsed_value = json.loads(value)
                    if isinstance(parsed_value, list):
                        print(f"  Contains {len(parsed_value)} items")
                        if len(parsed_value) > 0:
                            print(f"  First item: {parsed_value[0]}")
                    elif isinstance(parsed_value, dict):
                        print(f"  Dict with keys: {list(parsed_value.keys())}")
                    else:
                        print(f"  Value: {parsed_value}")
                except json.JSONDecodeError:
                    print(f"  Value: {value}")
            elif data_type == 'list':
                length = r.llen(key)
                print(f"  List length: {length}")
                if length > 0:
                    first_item = r.lindex(key, 0)
                    print(f"  First item: {first_item}")
            elif data_type == 'set':
                length = r.scard(key)
                print(f"  Set size: {length}")
                if length > 0:
                    sample = r.srandmember(key)
                    print(f"  Sample item: {sample}")
            elif data_type == 'hash':
                fields = r.hgetall(key)
                print(f"  Hash with {len(fields)} fields: {list(fields.keys())}")
                
        # 检查常见的模式
        patterns = [
            f"task:{task_id}:subdomains",
            f"task:{task_id}:links", 
            f"task:{task_id}:third_party_domains",
            f"task:{task_id}:progress",
            f"task:{task_id}:status",
            f"scan_result:{task_id}",
            f"subdomains:{task_id}",
            f"links:{task_id}",
            f"third_party:{task_id}"
        ]
        
        print(f"\nChecking common patterns:")
        for pattern in patterns:
            if r.exists(pattern):
                data_type = r.type(pattern)
                print(f"  {pattern} exists (type: {data_type})")
                
                if data_type == 'string':
                    value = r.get(pattern)
                    try:
                        parsed_value = json.loads(value)
                        if isinstance(parsed_value, list):
                            print(f"    Contains {len(parsed_value)} items")
                        else:
                            print(f"    Value: {parsed_value}")
                    except:
                        print(f"    Value: {value}")
                elif data_type == 'list':
                    length = r.llen(pattern)
                    print(f"    List length: {length}")
                elif data_type == 'set':
                    length = r.scard(pattern)
                    print(f"    Set size: {length}")
                elif data_type == 'hash':
                    fields = r.hgetall(pattern)
                    print(f"    Hash fields: {list(fields.keys())}")
            else:
                print(f"  {pattern} does not exist")
                
    except Exception as e:
        print(f'Error: {e}')

if __name__ == "__main__":
    asyncio.run(check_redis_data())