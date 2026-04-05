import os
import sys
import oss2
from dotenv import load_dotenv

# 加载环境变量
load_dotenv()

def deploy_to_oss():
    # 从环境变量获取配置
    access_key_id = os.getenv('ALIYUN_ACCESS_KEY_ID')
    access_key_secret = os.getenv('ALIYUN_ACCESS_KEY_SECRET')
    bucket_name = os.getenv('ALIYUN_OSS_BUCKET')
    endpoint = os.getenv('ALIYUN_OSS_ENDPOINT')

    print(f"准备部署到 Bucket: {bucket_name}")
    print(f"Endpoint: {endpoint}")

    if not access_key_id or not access_key_secret or not bucket_name or not endpoint:
        print("错误: 环境变量未正确配置")
        sys.exit(1)

    if not endpoint.startswith(('http://', 'https://')):
        endpoint = f'https://{endpoint}'

    # 创建Bucket对象
    auth = oss2.Auth(access_key_id, access_key_secret)
    bucket = oss2.Bucket(auth, endpoint, bucket_name)

    # 检查Bucket是否存在
    try:
        bucket.get_bucket_info()
        print(f"Bucket '{bucket_name}' 连接成功")
    except oss2.exceptions.NoSuchBucket:
        print(f"错误: Bucket '{bucket_name}' 不存在")
        print("请先在阿里云控制台手动创建该 Bucket，并设置读写权限为'公共读'")
        sys.exit(1)
    except Exception as e:
        print(f"连接 Bucket 失败: {e}")
        sys.exit(1)

    # 获取当前目录
    current_dir = os.path.dirname(os.path.abspath(__file__))
    
    # 需要上传的文件类型
    content_types = {
        '.html': 'text/html',
        '.css': 'text/css',
        '.js': 'application/javascript',
        '.json': 'application/json',
        '.png': 'image/png',
        '.jpeg': 'image/jpeg',
        '.jpg': 'image/jpeg',
        '.webp': 'image/webp',
        '.svg': 'image/svg+xml',
        '.ico': 'image/x-icon',
        '.xml': 'application/xml',
        '.txt': 'text/plain'
    }
    allowed_extensions = set(content_types.keys())

    # 遍历并上传文件
    success_count = 0
    fail_count = 0

    for root, dirs, files in os.walk(current_dir):
        # 排除不需要上传的文件和目录
        if '__pycache__' in root or '.git' in root or '.env' in root or 'node_modules' in root or 'tools-src' in root:
            continue
        dirs[:] = [directory for directory in dirs if directory not in {'__pycache__', '.git', 'deploy', '.trae', '.claude', 'node_modules', 'tools-src'}]
            
        for file in files:
            # 排除脚本本身和配置文件
            if file.endswith('.py') or file.startswith('.env') or file.startswith('.'):
                continue
            ext = os.path.splitext(file)[1].lower()
            if ext not in allowed_extensions:
                continue
                
            file_path = os.path.join(root, file)
            # 计算在OSS中的路径（相对路径）
            rel_path = os.path.relpath(file_path, current_dir)
            # 统一使用正斜杠
            oss_path = rel_path.replace('\\', '/')
            
            # 获取Content-Type
            content_type = content_types.get(ext, 'application/octet-stream')
            
            headers = {'Content-Type': content_type}
            # 设置缓存控制
            if file.endswith('.html'):
                headers['Cache-Control'] = 'no-cache'
            else:
                headers['Cache-Control'] = 'max-age=2592000'

            try:
                print(f"正在上传: {oss_path} ({content_type})...")
                with open(file_path, 'rb') as fileobj:
                    bucket.put_object(oss_path, fileobj, headers=headers)
                success_count += 1
            except Exception as e:
                print(f"上传失败 {oss_path}: {e}")
                fail_count += 1

    print("\n" + "="*30)
    print(f"部署完成!")
    print(f"成功: {success_count}")
    print(f"失败: {fail_count}")
    endpoint_host = endpoint.replace('https://', '').replace('http://', '')
    print(f"访问地址: https://{bucket_name}.{endpoint_host}/index.html")
    print("="*30)
    if fail_count > 0:
        sys.exit(1)

if __name__ == '__main__':
    deploy_to_oss()
