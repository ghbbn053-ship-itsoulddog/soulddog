#!/usr/bin/env python3
"""
查询Milvus向量化数据的脚本
"""

from pymilvus import connections, Collection, utility
import json

def check_vector_data():
    """检查向量化数据"""
    try:
        # 连接Milvus
        connections.connect(
            alias="default",
            host="milvus",
            port="19530"
        )
        print("✅ Milvus连接成功")
        
        # 检查集合是否存在
        collection_name = "campus_knowledge"
        if utility.has_collection(collection_name):
            print(f"✅ 集合 '{collection_name}' 存在")
            
            # 加载集合
            collection = Collection(collection_name)
            collection.load()
            
            # 获取统计信息
            stats = collection.get_stats()
            print(f"📊 集合统计信息: {json.dumps(stats, indent=2, ensure_ascii=False)}")
            
            # 查询总记录数
            count_result = collection.query(expr="id > 0", output_fields=["count(*)"])
            total_count = len(count_result) if count_result else 0
            print(f"📈 总记录数: {total_count}")
            
            # 查询用户1的数据
            user1_results = collection.query(
                expr="user_id == 1",
                output_fields=["id", "user_id", "text", "source", "metadata"]
            )
            print(f"👤 用户1的数据条数: {len(user1_results)}")
            
            if user1_results:
                print("\n📋 用户1的数据详情:")
                for i, item in enumerate(user1_results[:5]):  # 只显示前5条
                    print(f"\n--- 第{i+1}条 ---")
                    print(f"ID: {item.get('id')}")
                    print(f"来源: {item.get('source')}")
                    print(f"文本: {item.get('text')[:100]}...")
                    print(f"元数据: {item.get('metadata')}")
                
                if len(user1_results) > 5:
                    print(f"\n... 还有 {len(user1_results) - 5} 条数据")
            
            # 按来源统计
            sources = {}
            all_results = collection.query(
                expr="user_id == 1",
                output_fields=["source"]
            )
            for item in all_results:
                source = item.get('source', '未知')
                sources[source] = sources.get(source, 0) + 1
            
            print(f"\n📊 数据来源统计:")
            for source, count in sources.items():
                print(f"  {source}: {count}条")
                
        else:
            print(f"❌ 集合 '{collection_name}' 不存在")
            
    except Exception as e:
        print(f"❌ 查询失败: {str(e)}")
    finally:
        try:
            connections.disconnect("default")
            print("\n✅ Milvus连接已关闭")
        except:
            pass

if __name__ == "__main__":
    check_vector_data()