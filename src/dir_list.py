import os
import sys

def list_directory_structure(root_dir, max_depth=2, current_depth=1, prefix=""):
    if current_depth > max_depth:
        return
    
    try:
        entries = [e for e in os.listdir(root_dir) if e not in ('./', '../')]
        entries.sort()
        
        for i, entry in enumerate(entries):
            path = os.path.join(root_dir, entry)
            is_last = (i == len(entries) - 1)
            connector = "└── " if is_last else "├── "
            
            print(prefix + connector + entry)
            
            if os.path.isdir(path):
                new_prefix = prefix + ("    " if is_last else "│   ")
                list_directory_structure(path, max_depth, current_depth + 1, new_prefix)
    except PermissionError:
        print(prefix + "[アクセス拒否]")

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("使用方法: python dir_list.py <ディレクトリパス> [階層数]")
        sys.exit(1)
    
    target_dir = sys.argv[1].strip()
    max_depth = int(sys.argv[2]) if len(sys.argv) > 2 else 2  # デフォルトの階層数は2
    
    if os.path.isdir(target_dir):
        print(target_dir)
        list_directory_structure(target_dir, max_depth)
    else:
        print("指定されたディレクトリが存在しません。")
