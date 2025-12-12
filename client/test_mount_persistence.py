#!/usr/bin/env python3
"""
简单的 mount 持久化测试脚本

测试流程：
1. 创建 sandbox
2. 挂载 bucket
3. 写入测试文件
4. 销毁 sandbox
5. 重新创建 sandbox
6. 重新挂载 bucket
7. 检查文件是否还在（验证持久化）

使用方法：
    python test_mount_persistence.py
"""

import os
import sys
import time

# 添加路径以导入 client
current_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(current_dir)
project_root = os.path.dirname(parent_dir)
sys.path.insert(0, project_root)

# 加载 .env 文件
try:
    from dotenv import load_dotenv
    env_path = os.path.join(current_dir, ".env")
    if os.path.exists(env_path):
        load_dotenv(env_path)
    else:
        env_path = os.path.join(parent_dir, ".env")
        if os.path.exists(env_path):
            load_dotenv(env_path)
except ImportError:
    pass

from artifact_sandbox.client.client import SandboxManager, SandboxError


def main():
    print("=" * 60)
    print("Mount 持久化测试")
    print("=" * 60)
    
    # 获取配置
    bucket_name = os.environ.get("BUCKET_NAME", "")
    bucket_endpoint = os.environ.get("BUCKET_ENDPOINT", "")
    access_key = os.environ.get("AWS_ACCESS_KEY_ID", "")
    secret_key = os.environ.get("AWS_SECRET_ACCESS_KEY", "")
    
    if not bucket_name or not bucket_endpoint:
        print("\n❌ 错误: 需要设置环境变量:")
        print("  BUCKET_NAME=your-bucket-name")
        print("  BUCKET_ENDPOINT=https://your-endpoint.com")
        print("\n或者创建 .env 文件:")
        print("  BUCKET_NAME=your-bucket-name")
        print("  BUCKET_ENDPOINT=https://your-endpoint.com")
        sys.exit(1)
    
    # 创建 manager
    manager = SandboxManager()
    
    mount_path = "/mnt/bucket"
    test_file = f"{mount_path}/persistence_test_{int(time.time())}.txt"
    test_content = f"持久化测试文件\n创建时间: {time.strftime('%Y-%m-%d %H:%M:%S')}\n"
    
    # 构建 bucket 选项
    bucket_options = {
        "endpoint": bucket_endpoint,
        "provider": "r2" if "r2.cloudflarestorage.com" in bucket_endpoint else "s3",
        "readOnly": False
    }
    
    if access_key and secret_key:
        bucket_options["credentials"] = {
            "accessKeyId": access_key,
            "secretAccessKey": secret_key
        }
    
    try:
        # ========== 第一步：创建 sandbox 并挂载 ==========
        print("\n[步骤 1/4] 创建 sandbox...")
        # 使用时间戳生成唯一 ID，便于区分
        sandbox_id = f"persistence-{int(time.time())}"
        sandbox = manager.create_or_get_sandbox(sandbox_id)
        print(f"✓ Sandbox 创建成功: {sandbox.sandbox_id}")
        
        print("\n[步骤 2/4] 挂载 bucket...")
        sandbox.mount_bucket(bucket_name, mount_path, bucket_options)
        print(f"✓ Bucket '{bucket_name}' 已挂载到 {mount_path}")
        
        # ========== 第二步：写入测试文件 ==========
        print("\n[步骤 3/4] 写入测试文件...")
        sandbox.write(test_file, test_content)
        print(f"✓ 文件已写入: {test_file}")
        
        # 验证文件存在
        if sandbox.exists(test_file):
            print(f"✓ 文件存在确认: {test_file}")
        else:
            print(f"⚠ 警告: 文件写入后未找到: {test_file}")
        
        # 读取验证
        read_content = sandbox.read(test_file)
        print(f"✓ 文件内容验证: {len(read_content)} 字节")
        
        # ========== 第三步：销毁 sandbox ==========
        print("\n[步骤 4/4] 销毁 sandbox...")
        manager.destroy_sandbox(sandbox.sandbox_id)
        print("✓ Sandbox 已销毁")
        
        # 等待一下确保清理完成
        time.sleep(1)
        
        # ========== 第四步：重新创建 sandbox 并检查持久化 ==========
        print("\n" + "=" * 60)
        print("持久化验证阶段")
        print("=" * 60)
        
        print("\n[验证 1/3] 重新创建 sandbox...")
        new_sandbox_id = f"{sandbox_id}-verify"
        new_sandbox = manager.create_or_get_sandbox(new_sandbox_id)
        print(f"✓ 新 Sandbox 创建成功: {new_sandbox.sandbox_id}")
        print("  注意: 这是新的 sandbox (ID 不同)")
        
        print("\n[验证 2/3] 重新挂载 bucket...")
        new_sandbox.mount_bucket(bucket_name, mount_path, bucket_options)
        print(f"✓ Bucket '{bucket_name}' 已重新挂载到 {mount_path}")
        
        # ========== 第五步：检查文件是否还在 ==========
        print("\n[验证 3/3] 检查文件是否持久化...")
        if new_sandbox.exists(test_file):
            print(f"✓✓✓ 持久化成功！文件仍在: {test_file}")
            
            # 读取内容验证
            persisted_content = new_sandbox.read(test_file)
            if persisted_content == test_content:
                print("✓✓✓ 文件内容完全一致！")
                print("\n" + "=" * 60)
                print("✅ 测试通过: Bucket 持久化正常")
                print("=" * 60)
            else:
                print("⚠ 警告: 文件存在但内容不一致")
                print(f"  原始长度: {len(test_content)} 字节")
                print(f"  当前长度: {len(persisted_content)} 字节")
                # 打印内容差异，使用 repr 方便看出换行/空格
                print("\n  原始内容:")
                print(f"  {repr(test_content)}")
                print("\n  当前内容:")
                print(f"  {repr(persisted_content)}")
        else:
            print(f"❌ 持久化失败！文件不存在: {test_file}")
            print("\n" + "=" * 60)
            print("❌ 测试失败: Bucket 持久化异常")
            print("=" * 60)
            
            # 列出目录看看有什么
            try:
                result = new_sandbox.run(f"ls -la {mount_path}")
                print(f"\n目录内容:\n{result.get('output', '')}")
            except:
                pass
        
        # 清理
        print("\n清理中...")
        manager.destroy_sandbox(new_sandbox.sandbox_id)
        print("✓ 清理完成")
        
    except SandboxError as e:
        print(f"\n❌ 错误: {e}")
        if e.status_code:
            print(f"   状态码: {e.status_code}")
        if e.response_text:
            print(f"   响应: {e.response_text[:200]}")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ 未预期的错误: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()

