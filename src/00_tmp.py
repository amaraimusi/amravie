import sys

def main():
    if len(sys.argv) < 2:
        print("引数が不足しています。")
        return

    file_arg = sys.argv[1]
    file_paths = [s.strip() for s in file_arg.split('|') if s.strip()]

    print("指定されたファイル:")
    for path in file_paths:
        print(f"- {path}")

if __name__ == "__main__":
    main()