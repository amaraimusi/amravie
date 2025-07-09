#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import sys
import os

def show_file_content(file_path, output_lines):
    output_lines.append(f'■ {file_path}')
    output_lines.append('------------------------------')
    
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            output_lines.extend(f.readlines())
    except Exception as e:
        output_lines.append(f'【エラー】{file_path} を開けませんでした: {e}')
    
    output_lines.append('\n' + '=' * 80 + '\n')


def main():
    if len(sys.argv) < 2:
        print('使用方法: python one_text.py "出力ファイルパス"')
        return
    
    output_file_path = sys.argv[1]
    input_file_path = os.path.join(os.path.dirname(__file__), 'input.txt')

    if not os.path.isfile(input_file_path):
        print(f'【エラー】input.txt が見つかりません: {input_file_path}')
        return

    output_lines = []

    with open(input_file_path, 'r', encoding='utf-8') as input_file:
        for line in input_file:
            file_path = line.strip()
            if not file_path:
                continue
            if os.path.isfile(file_path):
                show_file_content(file_path, output_lines)
            else:
                output_lines.append(f'【スキップ】ファイルが見つかりません: {file_path}')
                output_lines.append('\n' + '=' * 80 + '\n')

    try:
        with open(output_file_path, 'w', encoding='utf-8') as output_file:
            output_file.writelines(output_lines)
        print(f'✅ 出力完了: {output_file_path}')
    except Exception as e:
        print(f'【エラー】出力ファイルに書き込めませんでした: {e}')


if __name__ == '__main__':
    main()
